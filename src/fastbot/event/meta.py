from typing import ClassVar, Literal, override

from fastbot.bot import FastBot
from fastbot.event import Context, Event


class MetaEvent(Event):
    post_type: ClassVar[Literal["meta_event"]] = "meta_event"

    meta_event_type: Literal["heartbeat", "lifecycle"]

    event: ClassVar[dict[str, type["MetaEvent"]]] = {}

    def __init__(self, bot: FastBot, ctx: Context) -> None:
        super().__init__(bot, ctx)

    def __init_subclass__(cls, *args, **kwargs) -> None:
        MetaEvent.event[cls.meta_event_type] = cls

    @classmethod
    @override
    def dispatch(cls, ctx: Context) -> type["MetaEvent"]:
        return cls.event.get(ctx["meta_event_type"], cls)


class LifecycleMetaEvent(MetaEvent):
    meta_event_type: ClassVar[Literal["lifecycle"]] = "lifecycle"

    sub_type: Literal["enable", "disable", "connect"]


class HeartbeatMetaEvent(MetaEvent):
    meta_event_type: ClassVar[Literal["heartbeat"]] = "heartbeat"

    status: dict
    interval: int
