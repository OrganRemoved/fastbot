from typing import ClassVar, Literal, override

from fastbot.event import Context, Event


class MetaEvent(Event):
    __slots__ = ("meta_event_type",)

    post_type: ClassVar[Literal["meta_event"]] = "meta_event"

    meta_event_type: Literal["heartbeat", "lifecycle"]

    event: ClassVar[dict[str, type["MetaEvent"]]] = {}

    def __init__(self, ctx: Context) -> None:
        super().__init__(ctx=ctx)

    def __init_subclass__(cls, *args, **kwargs) -> None:
        MetaEvent.event[cls.meta_event_type] = cls

    @classmethod
    @override
    def dispatch(cls, *, ctx: Context) -> "MetaEvent":
        return (
            event(ctx=ctx)
            if (event := cls.event.get(ctx["meta_event_type"]))
            else cls(ctx=ctx)
        )


class LifecycleMetaEvent(MetaEvent):
    __slots__ = ("sub_type",)

    meta_event_type: ClassVar[Literal["lifecycle"]] = "lifecycle"

    sub_type: Literal["enable", "disable", "connect"]

    def __init__(self, *, ctx: Context) -> None:
        self.sub_type = ctx["sub_type"]

        super().__init__(ctx=ctx)


class HeartbeatMetaEvent(MetaEvent):
    __slots__ = ("status", "interval")

    meta_event_type: ClassVar[Literal["heartbeat"]] = "heartbeat"

    status: dict
    interval: int

    def __init__(self, *, ctx: Context) -> None:
        self.status = ctx["status"]
        self.interval = ctx["interval"]

        super().__init__(ctx=ctx)
