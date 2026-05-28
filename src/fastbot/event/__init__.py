import asyncio
import logging
from contextlib import AsyncExitStack
from typing import Any, Callable, ClassVar, Literal, Self

from fastbot.bot import FastBot


class Context(dict):
    post_type: Literal["message", "notice", "request", "meta_event"]
    time: int
    self_id: int


class Event:
    post_type: Literal["message", "notice", "request", "meta_event"]
    time: int
    self_id: int

    dependency_cache: dict[Callable[..., Any], Any]
    stack: AsyncExitStack

    event: ClassVar[dict[str, type["Event"]]] = {}

    def __new__(cls, bot: FastBot, ctx: Context) -> "Event":
        return (
            event.__new__(event, bot, ctx)
            if (event := cls.dispatch(ctx)) is not cls
            else super().__new__(cls)
        )

    def __init__(self, bot: FastBot, ctx: Context) -> None:
        self.bot = bot
        self.ctx = ctx

        logging.debug(self)

    def __init_subclass__(cls, *args, **kwargs) -> None:
        Event.event[cls.post_type] = cls

    def __getattr__(self, name: str) -> Any:
        try:
            return self.ctx[name]

        except KeyError:
            raise AttributeError(
                f"{type(self).__name__!r} object has no attribute {name!r}"
            ) from None

    def __getitem__(self, name: str) -> Any:
        return self.ctx[name]

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({', '.join(f'{k}={v}' for k, v in self.ctx.items())})"

    async def __aenter__(self) -> Self:
        self.dependency_cache: dict[Callable[..., Any], asyncio.Future] = {}
        self.stack: AsyncExitStack = AsyncExitStack()

        await self.stack.__aenter__()

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.stack.__aexit__(exc_type, exc_val, exc_tb)

    @classmethod
    def dispatch(cls, ctx: Context) -> type["Event"]:
        return cls.event.get(ctx["post_type"], cls)
