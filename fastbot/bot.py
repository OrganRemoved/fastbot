import asyncio
from contextlib import AsyncExitStack, asynccontextmanager
from inspect import isasyncgenfunction
import logging
import os
from contextvars import ContextVar
from functools import partial
from typing import Any, AsyncGenerator, ClassVar, Iterable, Self
from weakref import WeakValueDictionary

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketException, status

from fastbot.plugin import PluginManager

try:
    import ujson as json

    json.dumps = partial(json.dumps, ensure_ascii=False, sort_keys=False)

except ImportError:
    import json

    json.dumps = partial(
        json.dumps, ensure_ascii=False, separators=(",", ":"), sort_keys=False
    )


class FastBot:
    __slots__ = ()

    app: ClassVar[FastAPI]

    connectors: ClassVar[WeakValueDictionary[int, WebSocket]] = WeakValueDictionary()
    futures: ClassVar[dict[int, asyncio.Future]] = {}

    self_id: ClassVar[ContextVar[int | None]] = ContextVar("self_id", default=None)

    @classmethod
    async def ws_adapter(cls, websocket: WebSocket) -> None:
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

        if not (self_id := websocket.headers.get("x-self-id")):
            raise WebSocketException(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="missing `x-self-id` header",
            )

        if not (self_id.isdigit() and (self_id := int(self_id))):
            raise WebSocketException(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="invalid `x-self-id` header",
            )

        if self_id in cls.connectors:
            raise WebSocketException(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="duplicate `x-self-id` header",
            )

        await websocket.accept()

        logging.info(f"websocket connected {self_id=}")

        cls.connectors[self_id] = websocket

        await cls.event_handler(websocket=websocket)

    @classmethod
    async def event_handler(cls, websocket: WebSocket) -> None:
        async with asyncio.TaskGroup() as tg:
            while True:
                match message := await websocket.receive():
                    case {"bytes": data} | {"text": data}:
                        if "post_type" in (ctx := json.loads(data)):
                            cls.self_id.set(ctx.get("self_id"))

                            tg.create_task(PluginManager.run(ctx=ctx))

                        elif ctx["status"] == "ok":
                            cls.futures[ctx["echo"]].set_result(ctx.get("data"))

                        else:
                            cls.futures[ctx["echo"]].set_exception(RuntimeError(ctx))

                    case _:
                        logging.warning(f"unknow websocket message received {message=}")

    @classmethod
    async def do(cls, *, endpoint: str, self_id: int | None = None, **kwargs) -> Any:
        if not (
            self_id := (
                self_id
                or cls.self_id.get()
                or (next(iter(cls.connectors)) if len(cls.connectors) == 1 else None)
            )
        ):
            raise RuntimeError("parameter `self_id` must be specified")

        logging.debug(f"{endpoint=} {self_id=} {kwargs=}")

        future = asyncio.Future()
        future_id = id(future)

        cls.futures[future_id] = future

        try:
            await cls.connectors[self_id].send_bytes(
                json.dumps(
                    {"action": endpoint, "params": kwargs, "echo": future_id}
                ).encode(encoding="utf-8")
            )

            return await future

        finally:
            del cls.futures[future_id]

    @classmethod
    def build(cls, plugins: str | Iterable[str] | None = None, **kwargs) -> Self:
        if isinstance(plugins, str):
            PluginManager.import_from(plugins)

        elif isinstance(plugins, Iterable):
            for plugin in plugins:
                PluginManager.import_from(plugin)

        @asynccontextmanager
        async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
            app.add_api_websocket_route("/onebot/v11/ws", cls.ws_adapter)

            async with AsyncExitStack() as stack, asyncio.TaskGroup() as tg:
                if lifespan := kwargs.pop("lifespan", None):
                    await stack.enter_async_context(lifespan(app))

                await asyncio.gather(
                    *(
                        (
                            stack.enter_async_context(asynccontextmanager(init)())
                            if isasyncgenfunction(init)
                            else init()
                        )
                        for plugin in PluginManager.plugins.values()
                        if (init := plugin.init)
                    )
                )

                for plugin in PluginManager.plugins.values():
                    if background := plugin.backgrounds:
                        for task in background:
                            tg.create_task(task())

                yield

        app = FastAPI(lifespan=lifespan, **kwargs)

        cls.app = app

        return cls()

    @classmethod
    def run(cls, **kwargs) -> None:
        uvicorn.run(app=cls.app, **kwargs)
