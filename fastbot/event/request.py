import logging
from typing import Any, ClassVar, Literal, override

from fastbot.bot import FastBot
from fastbot.event import Context, Event


class RequestEvent(Event):
    __slots__ = ("request_type",)

    post_type: ClassVar[Literal["request"]] = "request"

    request_type: Literal["friend", "group"]

    event: ClassVar[dict[str, type["RequestEvent"]]] = {}

    def __init__(self, *, ctx: Context) -> None:
        super().__init__(ctx=ctx)

        logging.info(self.__repr__())

    def __init_subclass__(cls, *args, **kwargs) -> None:
        RequestEvent.event[cls.request_type] = cls

    @classmethod
    @override
    def dispatch(cls, *, ctx: Context) -> "RequestEvent":
        return (
            event(ctx=ctx)
            if (event := cls.event.get(ctx["request_type"]))
            else cls(ctx=ctx)
        )


class FriendRequestEvent(RequestEvent):
    __slots__ = ("user_id", "comment", "flag")

    request_type: ClassVar[Literal["friend"]] = "friend"

    user_id: int
    comment: str
    flag: str

    def __init__(self, *, ctx: Context) -> None:
        self.user_id = ctx["user_id"]
        self.comment = ctx["comment"]
        self.flag = ctx["flag"]

        super().__init__(ctx=ctx)

    async def approve(self, *, remark: str | None = None) -> Any:
        return await FastBot.invoke(
            endpoint="set_friend_add_request",
            self_id=self.self_id,
            approve=True,
            flag=self.flag,
            remark=remark,
        )

    async def reject(self) -> Any:
        return await FastBot.invoke(
            endpoint="set_friend_add_request",
            self_id=self.self_id,
            approve=False,
            flag=self.flag,
        )


class GroupRequestEvent(RequestEvent):
    __slots__ = ("sub_type", "group_id", "user_id", "comment", "flag")

    request_type: ClassVar[Literal["group"]] = "group"

    sub_type: Literal["add", "invite"]

    group_id: int
    user_id: int
    comment: str
    flag: str

    def __init__(self, *, ctx: Context) -> None:
        self.sub_type = ctx["sub_type"]

        self.group_id = ctx["group_id"]
        self.user_id = ctx["user_id"]
        self.comment = ctx["comment"]
        self.flag = ctx["flag"]

        super().__init__(ctx=ctx)

    async def approve(self) -> Any:
        return await FastBot.invoke(
            endpoint="set_group_add_request",
            self_id=self.self_id,
            approve=True,
            flag=self.flag,
            sub_type=self.sub_type,
        )

    async def reject(self, *, reason: str | None = None) -> Any:
        return await FastBot.invoke(
            endpoint="set_group_add_request",
            self_id=self.self_id,
            approve=False,
            flag=self.flag,
            reason=reason,
        )
