import asyncio
import logging
from dataclasses import asdict
from typing import Any, ClassVar, Iterable, Literal, Self, override

from fastbot.bot import FastBot
from fastbot.event import Context, Event
from fastbot.message import Message, MessageSegment


class MessageEvent(Event):
    __slots__ = ("message_type",)

    post_type: ClassVar[Literal["message"]] = "message"

    message_type: Literal["group", "private"]

    event: ClassVar[dict[str, type["MessageEvent"]]] = {}

    def __init__(self, *, ctx: Context) -> None:
        super().__init__(ctx=ctx)

        logging.info(self.__repr__())

    def __init_subclass__(cls, *args, **kwargs) -> None:
        MessageEvent.event[cls.message_type] = cls

    @classmethod
    @override
    def dispatch(cls, *, ctx: Context) -> "MessageEvent":
        return (
            event(ctx=ctx)
            if (event := cls.event.get(ctx["message_type"]))
            else cls(ctx=ctx)
        )


class PrivateMessageEvent(MessageEvent):
    __slots__ = (
        "__weakref__",
        "sub_type",
        "message_id",
        "user_id",
        "message",
        "raw_message",
        "font",
        "sender",
        "plaintext",
    )

    class Sender:
        __slots__ = ("user_id", "nickname", "sex", "age")

        def __init__(
            self,
            user_id: int | None = None,
            nickname: str | None = None,
            sex: str | None = None,
            age: int | None = None,
        ) -> None:
            self.user_id = user_id
            self.nickname = nickname
            self.sex = sex
            self.age = age

        def __repr__(self) -> str:
            return f"""{self.__class__.__name__}({
                ", ".join(
                    f"{item}={value}"
                    for item in self.__slots__
                    if (not item.startswith("__"))
                    and (value := getattr(self, item, None))
                )
            })"""

    message_type: ClassVar[Literal["private"]] = "private"

    sub_type: Literal["friend", "group", "other"]

    message_id: int
    user_id: int
    message: Message
    raw_message: str
    font: int
    sender: Sender

    plaintext: str

    futures: ClassVar[dict[int, asyncio.Future]] = {}

    def __init__(self, *, ctx: Context) -> None:
        self.sub_type = ctx["sub_type"]

        self.message_id = ctx["message_id"]
        self.user_id = ctx["user_id"]
        self.message = Message(
            MessageSegment(type=msg["type"], data=msg["data"]) for msg in ctx["message"]
        )
        self.raw_message = ctx["raw_message"]
        self.font = ctx["font"]
        self.sender = ctx["sender"]

        self.sender = self.Sender(
            user_id=ctx["user_id"],
            nickname=ctx["nickname"],
            sex=ctx["sex"],
            age=ctx["age"],
        )

        self.plaintext = "".join(
            segment.data["text"] for segment in self.message if segment.type == "text"
        )

        super().__init__(ctx=ctx)

        if future := self.__class__.futures.get(self.user_id):
            future.set_result(self)

    def __hash__(self) -> int:
        return hash((self.user_id, self.time, self.self_id, self.raw_message))

    async def send(
        self,
        message: str
        | Message
        | MessageSegment
        | Iterable[str | Message | MessageSegment],
    ) -> Any:
        return await FastBot.invoke(
            endpoint="send_private_msg",
            message=[asdict(msg) for msg in Message(message)],
            self_id=self.self_id,
            user_id=self.user_id,
        )

    async def defer(
        self,
        message: str
        | Message
        | MessageSegment
        | Iterable[str | Message | MessageSegment],
    ) -> Self:
        self.__class__.futures[self.user_id] = future = asyncio.Future()

        await self.send(message=message)

        try:
            return await future
        finally:
            del self.__class__.futures[self.user_id]


class GroupMessageEvent(MessageEvent):
    __slots__ = (
        "__weakref__",
        "sub_type",
        "message_id",
        "group_id",
        "user_id",
        "message",
        "raw_message",
        "font",
        "sender",
        "plaintext",
    )

    class Sender:
        __slots__ = (
            "user_id",
            "nickname",
            "card",
            "role",
            "sex",
            "age",
            "area",
            "level",
            "title",
        )

        def __init__(
            self,
            user_id: int | None = None,
            nickname: str | None = None,
            card: str | None = None,
            role: str | None = None,
            sex: str | None = None,
            age: int | None = None,
            area: str | None = None,
            level: str | None = None,
            title: str | None = None,
        ) -> None:
            self.user_id = user_id
            self.nickname = nickname
            self.card = card
            self.role = role
            self.sex = sex
            self.age = age
            self.area = area
            self.level = level
            self.title = title

        def __repr__(self) -> str:
            return f"""{self.__class__.__name__}({
                ", ".join(
                    f"{item}={value}"
                    for item in self.__slots__
                    if (not item.startswith("__"))
                    and (value := getattr(self, item, None))
                )
            })"""

    message_type: ClassVar[Literal["group"]] = "group"

    sub_type: Literal["normal", "anonymous", "notice"]

    message_id: int
    group_id: int
    user_id: int
    message: Message
    raw_message: str
    font: int
    sender: Sender

    futures: ClassVar[dict[tuple[int, int], asyncio.Future]] = {}

    def __init__(self, *, ctx: Context) -> None:
        self.sub_type = ctx["sub_type"]

        self.message_id = ctx["message_id"]
        self.group_id = ctx["group_id"]
        self.user_id = ctx["user_id"]
        self.message = Message(
            MessageSegment(type=msg["type"], data=msg["data"]) for msg in ctx["message"]
        )
        self.raw_message = ctx["raw_message"]
        self.font = ctx["font"]
        self.sender = self.Sender(
            user_id=ctx["sender"]["user_id"],
            nickname=ctx["sender"]["nickname"],
            card=ctx["sender"]["card"],
            role=ctx["sender"]["role"],
            sex=ctx["sender"]["sex"],
            age=ctx["sender"]["age"],
            area=ctx["sender"]["area"],
            level=ctx["sender"]["level"],
            title=ctx["sender"]["title"],
        )

        self.plaintext = "".join(
            segment.data["text"] for segment in self.message if segment.type == "text"
        )

        super().__init__(ctx=ctx)

        if future := self.__class__.futures.get((self.group_id, self.user_id)):
            future.set_result(self)

    def __hash__(self) -> int:
        return hash((self.user_id, self.time, self.self_id, self.raw_message))

    async def send(
        self,
        message: str
        | Message
        | MessageSegment
        | Iterable[str | Message | MessageSegment],
    ) -> Any:
        return await FastBot.invoke(
            endpoint="send_group_msg",
            message=[asdict(msg) for msg in Message(message)],
            self_id=self.self_id,
            group_id=self.group_id,
        )

    async def defer(
        self,
        message: str
        | Message
        | MessageSegment
        | Iterable[str | Message | MessageSegment],
    ) -> Self:
        self.__class__.futures[(self.group_id, self.user_id)] = future = (
            asyncio.Future()
        )

        await self.send(message=message)

        try:
            return await future
        finally:
            del self.__class__.futures[(self.group_id, self.user_id)]
