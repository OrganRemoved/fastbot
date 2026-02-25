import logging
from typing import Any, ClassVar, Literal, override

from fastbot.bot import FastBot
from fastbot.event import Context, Event


class RequestEvent(Event):
    post_type: ClassVar[Literal["request"]] = "request"

    request_type: Literal["friend", "group"]

    event: ClassVar[dict[str, type["RequestEvent"]]] = {}

    def __init__(self, bot: FastBot, ctx: Context) -> None:
        super().__init__(bot, ctx)

        logging.info(self.__repr__())

    def __init_subclass__(cls, *args, **kwargs) -> None:
        RequestEvent.event[cls.request_type] = cls

    @classmethod
    @override
    def dispatch(cls, ctx: Context) -> type["RequestEvent"]:
        return cls.event.get(ctx["request_type"], cls)


class FriendRequestEvent(RequestEvent):
    request_type: ClassVar[Literal["friend"]] = "friend"

    user_id: int
    comment: str
    flag: str

    async def approve(self, *, remark: str | None = None) -> Any:
        return await self.bot(
            "set_friend_add_request",
            self_id=self.self_id,
            approve=True,
            flag=self.flag,
            remark=remark,
        )

    async def reject(self) -> Any:
        return await self.bot(
            "set_friend_add_request",
            self_id=self.self_id,
            approve=False,
            flag=self.flag,
        )


class GroupRequestEvent(RequestEvent):
    request_type: ClassVar[Literal["group"]] = "group"

    sub_type: Literal["add", "invite"]

    group_id: int
    user_id: int
    comment: str
    flag: str

    async def approve(self) -> Any:
        return await self.bot(
            "set_group_add_request",
            self_id=self.self_id,
            approve=True,
            flag=self.flag,
            sub_type=self.sub_type,
        )

    async def reject(self, *, reason: str | None = None) -> Any:
        return await self.bot(
            "set_group_add_request",
            self_id=self.self_id,
            approve=False,
            flag=self.flag,
            reason=reason,
        )
