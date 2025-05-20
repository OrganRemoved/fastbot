import logging
from typing import Any, ClassVar, Literal, TypeAlias

Context: TypeAlias = dict[str, Any]


class Event:
    __slots__ = ("ctx", "post_type", "time", "self_id")

    post_type: Literal["message", "notice", "request", "meta_event"]
    time: int
    self_id: int

    event: ClassVar[dict[str, type["Event"]]] = {}

    def __init__(self, *, ctx: Context) -> None:
        self.ctx = ctx

        self.time = ctx["time"]
        self.self_id = ctx["self_id"]

        logging.debug(self.__repr__())

    def __init_subclass__(cls, *args, **kwargs) -> None:
        Event.event[cls.post_type] = cls

    def __repr__(self) -> str:
        return f"""{self.__class__.__name__}({
            ", ".join(
                f"{item}={value}"
                for item in self.__slots__
                if (not item.startswith("__")) and (value := getattr(self, item, None))
            )
        })"""

    @classmethod
    def dispatch(cls, *, ctx: Context) -> "Event":
        return (
            event.dispatch(ctx=ctx)
            if (event := cls.event.get(ctx["post_type"]))
            else cls(ctx=ctx)
        )
