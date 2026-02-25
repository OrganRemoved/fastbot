import asyncio
import logging
from functools import cached_property
from typing import Any, ClassVar, Iterable, Literal, Self, override

from fastbot.bot import FastBot
from fastbot.event import Event, Context
from fastbot.message import Message, MessageSegment


class MessageEvent(Event):
    post_type: ClassVar[Literal["message"]] = "message"

    message_type: Literal["group", "private"]

    event: ClassVar[dict[str, type["MessageEvent"]]] = {}

    def __init__(self, bot: FastBot, ctx: Context) -> None:
        super().__init__(bot, ctx)

        logging.info(self.__repr__())

    def __init_subclass__(cls, *args, **kwargs) -> None:
        MessageEvent.event[cls.message_type] = cls

    @classmethod
    @override
    def dispatch(cls, ctx: Context) -> type["MessageEvent"]:
        return cls.event.get(ctx["message_type"], cls)


class PrivateMessageEvent(MessageEvent):
    class Sender:
        def __init__(self, sender: dict[str, Any]) -> None:
            self.user_id: int
            self.nickname: str
            self.sex: str
            self.age: int

            self.__dict__.update(sender)

        def __repr__(self) -> str:
            return f"""{self.__class__.__name__}({
                ", ".join(
                    f"{k}={v}"
                    for k, v in self.__dict__.items()
                    if not k.startswith("__") and v
                )
            })"""

    message_type: ClassVar[Literal["private"]] = "private"

    sub_type: Literal["friend", "group", "other"]

    message_id: int
    user_id: int
    # message: Message
    raw_message: str
    font: int
    # sender: Sender

    async def send(
        self,
        message: str
        | Message
        | MessageSegment
        | Iterable[str | Message | MessageSegment],
    ) -> Any:
        return await self.bot(
            "send_private_msg",
            message=Message(message),
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
        key = (self.self_id, 0, self.user_id)

        self.bot.plugin_manager.sessions[key] = future = (
            asyncio.get_running_loop().create_future()
        )

        await self.send(message)

        try:
            return await future

        finally:
            self.bot.plugin_manager.sessions.pop(key, None)

    @cached_property
    def message(self) -> Message:
        return Message(
            MessageSegment(msg["type"], msg["data"]) for msg in self.ctx["message"]
        )

    @cached_property
    def plaintext(self) -> str:
        return "".join(
            segment["data"]["text"]
            for segment in self.message
            if segment["type"] == "text"
        )

    @cached_property
    def sender(self) -> Sender:
        return self.Sender(self.ctx["sender"])


class GroupMessageEvent(MessageEvent):
    class Sender:
        def __init__(self, sender: dict) -> None:
            self.user_id: int
            self.nickname: str
            self.card: str
            self.role: str
            self.sex: str
            self.age: int
            self.area: str
            self.level: str
            self.title: str

            self.__dict__.update(sender)

        def __repr__(self) -> str:
            return f"""{self.__class__.__name__}({
                ", ".join(
                    f"{k}={v}"
                    for k, v in self.__dict__.items()
                    if not k.startswith("__") and v
                )
            })"""

    message_type: ClassVar[Literal["group"]] = "group"

    sub_type: Literal["normal", "anonymous", "notice"]

    message_id: int
    group_id: int
    user_id: int
    # message: Message
    raw_message: str
    font: int
    # sender: Sender

    async def send(
        self,
        message: str
        | Message
        | MessageSegment
        | Iterable[str | Message | MessageSegment],
    ) -> Any:
        return await self.bot(
            "send_group_msg",
            message=Message(message),
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
        key = (self.self_id, self.group_id, self.user_id)

        self.bot.plugin_manager.sessions[key] = future = (
            asyncio.get_running_loop().create_future()
        )

        await self.send(message)

        try:
            return await future

        finally:
            self.bot.plugin_manager.sessions.pop(key, None)

    @cached_property
    def message(self) -> Message:
        return Message(
            MessageSegment(msg["type"], msg["data"]) for msg in self.ctx["message"]
        )

    @cached_property
    def plaintext(self) -> str:
        return "".join(
            segment["data"]["text"]
            for segment in self.message
            if segment["type"] == "text"
        )

    @cached_property
    def sender(self) -> Sender:
        return self.Sender(self.ctx["sender"])
