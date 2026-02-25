import asyncio
import logging
import os
from contextlib import AsyncExitStack, asynccontextmanager
from contextvars import ContextVar
from functools import partial
from inspect import isasyncgenfunction
from typing import Any, AsyncGenerator, Awaitable, Callable, Iterable, Optional

from fastapi import FastAPI, WebSocket, WebSocketException, status

from fastbot.matcher import ensure_async


class Singleton(type):
    instance: Optional["FastBot"] = None

    def __call__(cls, *args, **kwargs) -> "FastBot":
        if not (instance := cls.instance):
            cls.instance = instance = super().__call__(*args, **kwargs)

        return instance


class FastBot(metaclass=Singleton):
    __slots__ = ("app", "bot_id", "connectors", "futures", "plugin_manager")

    def __init__(self, plugins: str | Iterable[str] | None = None, **kwargs) -> None:
        from fastbot.plugin import PluginManager

        self.plugin_manager = plugin_manager = PluginManager(self)

        if isinstance(plugins, str):
            plugin_manager.import_from(plugins)

        elif isinstance(plugins, Iterable):
            for plugin in plugins:
                plugin_manager.import_from(plugin)

        @asynccontextmanager
        async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
            app.add_websocket_route("/onebot/v11/ws", self.websocket_adapter)

            async with AsyncExitStack() as stack, asyncio.TaskGroup() as tg:
                if lifespan := kwargs.pop("lifespan", None):
                    await stack.enter_async_context(lifespan(app))

                await asyncio.gather(
                    *(
                        (
                            stack.enter_async_context(asynccontextmanager(init)())
                            if isasyncgenfunction(init)
                            else ensure_async(init, to_thread=False)()
                        )
                        for plugin in plugin_manager.plugins.values()
                        if (init := plugin.init)
                    )
                )

                for plugin in plugin_manager.plugins.values():
                    for task in plugin.backgrounds:
                        tg.create_task(task.func())

                yield

        self.app: FastAPI = FastAPI(lifespan=lifespan, **kwargs)

        self.bot_id: ContextVar[int] = ContextVar("bot_id")

        self.connectors: dict[int, WebSocket] = {}
        self.futures: dict[str, asyncio.Future] = {}

    async def __call__(self, endpoint: str, **kwargs) -> Any:
        if not (
            bot := (
                kwargs.get("self_id")
                or self.bot_id.get()
                or (len(connectors := self.connectors) == 1 and next(iter(connectors)))
            )
        ):
            raise RuntimeError("parameter `self_id` must be specified")

        logging.debug(f"{endpoint=} {self.bot_id=} {kwargs=}")

        self.futures[future_id := hex(id(future))] = (
            future := asyncio.get_running_loop().create_future()
        )

        try:
            await self.connectors[bot].send_json(
                {"action": endpoint, "params": kwargs, "echo": future_id}
            )

            return await future

        finally:
            del self.futures[future_id]

    def __getattr__(self, item: str) -> Callable[..., Awaitable[Any]]:
        return partial(self, item)

    async def websocket_adapter(self, websocket: WebSocket) -> None:
        if authorization := os.getenv("FASTBOT_AUTHORIZATION"):
            if not (access_token := websocket.headers.get("authorization")):
                raise WebSocketException(
                    code=status.WS_1008_POLICY_VIOLATION,
                    reason="missing `authorization` header",
                )

            match access_token.split():
                case [header, token] if header.title() in ("Bearer", "Token"):
                    if token != authorization:
                        raise WebSocketException(
                            code=status.HTTP_403_FORBIDDEN,
                            reason="invalid `authorization` header",
                        )

                case [token]:
                    if token != authorization:
                        raise WebSocketException(
                            code=status.HTTP_403_FORBIDDEN,
                            reason="invalid `authorization` header",
                        )

                case _:
                    raise WebSocketException(
                        code=status.HTTP_403_FORBIDDEN,
                        reason="invalid `authorization` header",
                    )

        if not (bot_id := websocket.headers.get("x-self-id")):
            raise WebSocketException(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="missing `x-self-id` header",
            )

        if not (bot_id.isdigit() and (bot_id := int(bot_id))):
            raise WebSocketException(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="invalid `x-self-id` header",
            )

        if bot_id in self.connectors:
            raise WebSocketException(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="duplicate `x-self-id` header",
            )

        self.bot_id.set(bot_id)

        await websocket.accept()

        logging.info(f"websocket connected {bot_id=}")

        self.connectors[bot_id] = websocket

        try:
            await self.event_handler(websocket)

        finally:
            del self.connectors[bot_id]

    async def event_handler(
        self, websocket: WebSocket, *, background_tasks: set[asyncio.Task] = set()
    ) -> None:
        async for ctx in websocket.iter_json():
            if "post_type" in ctx:
                background_tasks.add(
                    task := asyncio.create_task(self.plugin_manager(ctx))
                )

                task.add_done_callback(background_tasks.discard)

            elif future := self.futures.get(ctx["echo"]):
                if ctx["status"] == "ok":
                    future.set_result(ctx.get("data"))

                else:
                    future.set_exception(RuntimeError(ctx))
