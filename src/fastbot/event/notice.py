import logging
from typing import ClassVar, Literal, override

from fastbot.bot import FastBot
from fastbot.event import Context, Event


class NoticeEvent(Event):
    post_type: ClassVar[Literal["notice"]] = "notice"

    notice_type: str

    event: ClassVar[dict[str, type["NoticeEvent"]]] = {}

    def __init__(self, bot: FastBot, ctx: Context) -> None:
        super().__init__(bot, ctx)

        logging.info(self.__repr__())

    def __init_subclass__(cls, *args, **kwargs) -> None:
        NoticeEvent.event[cls.notice_type] = cls

    @classmethod
    @override
    def dispatch(cls, ctx: Context) -> type["NoticeEvent"]:
        return cls.event.get(ctx["notice_type"], cls)


class GroupFileUploadNoticeEvent(NoticeEvent):
    notice_type: ClassVar[Literal["group_upload"]] = "group_upload"

    group_id: int
    user_id: int
    file: dict


class GroupAdminChangeNoticeEvent(NoticeEvent):
    notice_type: ClassVar[Literal["group_admin"]] = "group_admin"

    sub_type: Literal["set", "unset"]

    group_id: int
    user_id: int


class GroupMemberDecreaseNoticeEvent(NoticeEvent):
    notice_type: ClassVar[Literal["group_decrease"]] = "group_decrease"

    sub_type: Literal["leave", "kick", "kick_me"]

    group_id: int
    user_id: int
    operator_id: int


class GroupMemberIncreaseNoticeEvent(NoticeEvent):
    notice_type: ClassVar[Literal["group_increase"]] = "group_increase"

    sub_type: Literal["approve", "invite"]

    group_id: int
    user_id: int
    operator_id: int


class GroupBanNoticeEvent(NoticeEvent):
    notice_type: ClassVar[Literal["group_ban"]] = "group_ban"

    sub_type: Literal["ban", "lift_ban"]

    group_id: int
    user_id: int
    operator_id: int
    duration: int


class FriendAddNoticeEvent(NoticeEvent):
    notice_type: ClassVar[Literal["friend_add"]] = "friend_add"

    user_id: int


class GroupMessageRecallNoticeEvent(NoticeEvent):
    notice_type: Literal["group_recall"] = "group_recall"

    group_id: int
    user_id: int
    operator_id: int
    message_id: int


class FriendMessageRecallNoticeEvent(NoticeEvent):
    notice_type: Literal["friend_recall"] = "friend_recall"

    user_id: int
    message_id: int
