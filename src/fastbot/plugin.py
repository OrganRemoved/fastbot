import asyncio
import logging
import os
import sys
from contextlib import (
    AbstractAsyncContextManager,
    AbstractContextManager,
    AsyncExitStack,
    asynccontextmanager,
    contextmanager,
)
from functools import wraps
from importlib import import_module, reload
from inspect import (
    Parameter,
    isasyncgenfunction,
    isclass,
    iscoroutinefunction,
    isgeneratorfunction,
    signature,
)
from textwrap import dedent
from types import ModuleType, UnionType
from typing import (
    Annotated,
    Any,
    Awaitable,
    Callable,
    NamedTuple,
    Union,
    get_args,
    get_origin,
)

from fastbot.bot import FastBot
from fastbot.event import Context, Event
from fastbot.matcher import Matcher, ensure_async


class Plugin:
    class Background(NamedTuple):
        func: Callable[..., Any]

    class Executor(NamedTuple):
        func: Callable[..., Any]

        async def __call__(self, event: Event) -> Any:
            try:
                return await self.func(event)

            except RuntimeWarning as e:
                if send := getattr(event, "send", None):
                    if len(args := e.args) > 1:
                        for arg in args:
                            await send(arg)

                    elif msg := str(e):
                        await send(msg)

                    elif doc := self.func.__doc__ or self.func.__module__.__doc__:
                        await send(dedent(doc))

            except RuntimeError as e:
                logging.exception(e)

    __slots__ = ("module", "init", "backgrounds", "commanders")

    def __init__(self, module: ModuleType) -> None:
        self.module = module

        self.init = getattr(module, "init", None)

        self.backgrounds: list[Plugin.Background] = []
        self.commanders: list[Plugin.Executor] = []

        for handler in vars(module).values():
            if (
                isinstance(handler, self.Executor)
                and handler.func.__module__ == module.__name__
            ):
                self.commanders.append(handler)

            elif (
                isinstance(handler, self.Background)
                and handler.func.__module__ == module.__name__
            ):
                self.backgrounds.append(handler)

    async def __call__(self, event: Event) -> None:
        async with asyncio.TaskGroup() as tg:
            for executor in self.commanders:
                tg.create_task(executor(event))


class Dependency:
    __slots__ = ("dependency", "signature", "use_cache")

    def __init__(
        self, dependency: Callable[..., Any], *, use_cache: bool = True
    ) -> None:
        self.dependency = dependency
        self.signature = signature(dependency)

        self.use_cache = use_cache

    @classmethod
    def provide(cls, dependency: Callable[..., Any], *, use_cache: bool = True) -> Any:
        return cls(dependency, use_cache=use_cache)


class PluginManager:
    __slots__ = ("bot", "plugins", "sessions")

    def __init__(self, bot: FastBot) -> None:
        self.bot = bot

        self.plugins: dict[str, Plugin] = {}
        self.sessions: dict[tuple[int, int, int], asyncio.Future] = {}

    async def __call__(self, ctx: Context) -> Any:
        event = Event(self.bot, ctx)

        try:
            if future := self.sessions.get(
                (
                    self.bot.bot_id.get(),
                    getattr(event, "group_id", 0),
                    getattr(event, "user_id", 0),
                )
            ):
                future.set_result(event)

            async with asyncio.TaskGroup() as tg:
                for plugin in self.plugins.values():
                    tg.create_task(plugin(event))

        except* Exception as eg:
            logging.exception(eg)

    def import_from(self, plugins: str) -> None:
        def load_module(module_path: str) -> None:
            module_name = (
                os.path.relpath(module_path, os.path.dirname(plugins))
                .removesuffix(".py")
                .replace(os.sep, ".")
            )

            try:
                if module_name in sys.modules:
                    logging.info(f"reloading plugin [{module_name}]")

                    module = reload(sys.modules[module_name])

                else:
                    module = import_module(module_name)

                self.plugins[module_name] = plugin = Plugin(module)

                logging.info(f"loaded plugin [{module_name}]")

                if not (plugin.init or plugin.backgrounds or plugin.commanders):
                    logging.warning(
                        f"unloaded plugin [{module_name}] due to missing handlers"
                    )

                    self.plugins.pop(module_name, None)

            except Exception as e:
                logging.exception(f"failed to load plugin [{module_name}]: {e}")

                self.plugins.pop(module_name, None)

        if os.path.isdir(plugins):
            for root, _, files in os.walk(plugins):
                for file in files:
                    if file.endswith(".py") and not file.startswith("_"):
                        load_module(os.path.join(root, file))

        elif (
            os.path.isfile(plugins)
            and plugins.endswith(".py")
            and not os.path.basename(plugins).startswith("_")
        ):
            load_module(plugins)


def background(func: Callable[..., Any]) -> Plugin.Background:
    return Plugin.Background(ensure_async(func, to_thread=True))


def on(
    matcher: Matcher | Callable[..., bool | Awaitable[bool]] | None = None,
) -> Callable[..., Any]:
    def annotation_event_type(annotation: Any) -> tuple[type[Event], ...]:
        if get_origin(annotation) in (Annotated, Union, UnionType):
            return tuple(
                arg
                for arg in get_args(annotation)
                if isclass(arg) and issubclass(arg, Event)
            )

        elif isclass(annotation) and issubclass(annotation, Event):
            return (annotation,)

        else:
            return ()

    async def resolve_dependency(
        event: Event,
        dependency: Dependency,
        dependency_cache: dict[Callable[..., Any], asyncio.Future],
        stack: AsyncExitStack,
    ) -> Any:
        if dependency.use_cache:
            if future := dependency_cache.get(dependency.dependency):
                return await future

            dependency_cache[dependency.dependency] = future = (
                asyncio.get_running_loop().create_future()
            )

        try:
            func = dependency.dependency
            sign = dependency.signature

            kwargs: dict[str, Any] = {}
            tasks: dict[str, asyncio.Task] = {}

            async with asyncio.TaskGroup() as tg:
                for param_name, param in sign.parameters.items():
                    if isinstance(param.default, Dependency):
                        tasks[param_name] = tg.create_task(
                            resolve_dependency(
                                event, param.default, dependency_cache, stack
                            )
                        )

                    elif param.annotation is FastBot:
                        kwargs[param_name] = event.bot

                    elif isinstance(event, annotation_event_type(param.annotation)):
                        kwargs[param_name] = event

                    elif param.default is not Parameter.empty:
                        kwargs[param_name] = param.default

                    elif param.kind in (
                        Parameter.VAR_POSITIONAL,
                        Parameter.VAR_KEYWORD,
                    ):
                        pass

                    else:
                        raise ValueError(
                            f"cannot resolve dependency for parameter '{param_name}' "
                            f"in function '{func.__name__}'. "
                            f"parameter must have either a default value, be an Event, or be a Dependency"
                        )

            kwargs.update({k: v.result() for k, v in tasks.items()})

            if isclass(func) and issubclass(func, AbstractAsyncContextManager):
                result = await stack.enter_async_context(func(**kwargs))

            elif isclass(func) and issubclass(func, AbstractContextManager):
                result = stack.enter_context(func(**kwargs))

            elif isasyncgenfunction(func):
                result = await stack.enter_async_context(
                    asynccontextmanager(func)(**kwargs)
                )

            elif isgeneratorfunction(func):
                result = stack.enter_context(contextmanager(func)(**kwargs))

            elif iscoroutinefunction(func):
                result = await func(**kwargs)

            else:
                result = func(**kwargs)

            if dependency.use_cache:
                future.set_result(result)

            return result

        except BaseException as e:
            future.set_exception(e)

            raise e

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        sign = signature(func)

        event_type = tuple(
            event
            for param in sign.parameters.values()
            for event in annotation_event_type(param.annotation)
        )

        async_matcher = (
            matcher
            if isinstance(matcher, Matcher)
            else Matcher(matcher or (lambda _: True))
        )

        if any(
            param
            for param in sign.parameters.values()
            if isinstance(param.default, Dependency) or param.annotation is FastBot
        ):

            @wraps(func)
            async def wrapper(event: Event, **kwargs) -> Any:
                if isinstance(event, event_type) and (
                    matched := await async_matcher.match(event)
                ):
                    func_kwargs: dict[str, Any] = {}
                    tasks: dict[str, asyncio.Task] = {}
                    dependency_cache: dict[Callable[..., Any], asyncio.Future] = {}

                    async with AsyncExitStack() as stack:
                        async with asyncio.TaskGroup() as tg:
                            for param_name, param in sign.parameters.items():
                                if isinstance(param.default, Dependency):
                                    tasks[param_name] = tg.create_task(
                                        resolve_dependency(
                                            event,
                                            param.default,
                                            dependency_cache,
                                            stack,
                                        )
                                    )

                                elif param.annotation is FastBot:
                                    func_kwargs[param_name] = event.bot

                                elif isinstance(
                                    event, annotation_event_type(param.annotation)
                                ):
                                    func_kwargs[param_name] = event

                                elif param.default is not Parameter.empty:
                                    func_kwargs[param_name] = param.default

                                elif param_name in matched:
                                    func_kwargs[param_name] = matched.pop(param_name)

                                elif param.kind is Parameter.VAR_POSITIONAL:
                                    pass

                                elif param.kind is Parameter.VAR_KEYWORD:
                                    func_kwargs.update(matched)

                                else:
                                    raise ValueError(
                                        f"cannot resolve dependency for parameter '{param_name}' "
                                        f"in function '{func.__name__}'. "
                                        f"parameter must have either a default value, be an Event, or be a Dependency."
                                    )

                        return await func(
                            **{
                                **kwargs,
                                **func_kwargs,
                                **{k: v.result() for k, v in tasks.items()},
                            }
                        )

        else:
            if not (
                (param := next(iter(sign.parameters.values()), None))
                and annotation_event_type(param.annotation)
            ):
                raise TypeError(
                    f"function '{func.__name__}' must accept an Event object as its first parameter."
                )

            if any(p.kind == Parameter.VAR_KEYWORD for p in sign.parameters.values()):

                @wraps(func)
                async def wrapper(event: Event, **kwargs) -> Any:
                    if isinstance(event, event_type) and (
                        matched := await async_matcher.match(event)
                    ):
                        return await func(event, **{**kwargs, **matched})

            else:

                @wraps(func)
                async def wrapper(event: Event, **kwargs) -> Any:
                    if isinstance(event, event_type) and (
                        matched := await async_matcher.match(event)
                    ):
                        return await func(
                            event,
                            **{
                                **kwargs,
                                **{
                                    k: v
                                    for k, v in matched.items()
                                    if k in sign.parameters
                                },
                            },
                        )

        return Plugin.Executor(wrapper)

    return decorator
