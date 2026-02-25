import logging
from typing import ClassVar, Literal

from fastbot.bot import FastBot


class Context(dict):
    post_type: Literal["message", "notice", "request", "meta_event"]
    time: int
    self_id: int


class Event:
    post_type: Literal["message", "notice", "request", "meta_event"]
    time: int
    self_id: int

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

        self.__dict__.update(ctx)

        logging.debug(self.__repr__())

    def __init_subclass__(cls, *args, **kwargs) -> None:
        Event.event[cls.post_type] = cls

    def __repr__(self) -> str:
        return f"""{self.__class__.__name__}({
            ", ".join(
                f"{k}={v}"
                for k, v in self.__dict__.items()
                if not (k.startswith("__") or k == "bot") and v
            )
        })"""

    @classmethod
    def dispatch(cls, ctx: Context) -> type["Event"]:
        return cls.event.get(ctx["post_type"], cls)
