import logging
from typing import ClassVar, Literal, override

from fastbot.event import Context, Event


class NoticeEvent(Event):
    __slots__ = ("notice_type",)

    post_type: ClassVar[Literal["notice"]] = "notice"

    notice_type: str

    event: ClassVar[dict[str, type["NoticeEvent"]]] = {}

    def __init__(self, *, ctx: Context) -> None:
        super().__init__(ctx=ctx)

        logging.info(self.__repr__())

    def __init_subclass__(cls, *args, **kwargs) -> None:
        NoticeEvent.event[cls.notice_type] = cls

    @classmethod
    @override
    def dispatch(cls, *, ctx: Context) -> "NoticeEvent":
        return (
            event(ctx=ctx)
            if (event := cls.event.get(ctx["notice_type"]))
            else cls(ctx=ctx)
        )


class GroupFileUploadNoticeEvent(NoticeEvent):
    __slots__ = ("group_id", "user_id", "file")

    class File:
        __slots__ = ("id", "name", "size", "busid")

        def __init__(self, id: str, name: str, size: int, busid: int) -> None:
            self.id = id
            self.name = name
            self.size = size
            self.busid = busid

        def __repr__(self) -> str:
            return f"""{self.__class__.__name__}({
                ", ".join(
                    f"{item}={value}"
                    for item in self.__slots__
                    if (not item.startswith("__"))
                    and (value := getattr(self, item, None))
                )
            })"""

    notice_type: ClassVar[Literal["group_upload"]] = "group_upload"

    group_id: int
    user_id: int
    file: File

    def __init__(self, *, ctx: Context) -> None:
        self.group_id = ctx["group_id"]
        self.user_id = ctx["user_id"]

        self.file = self.File(
            id=ctx["id"], name=ctx["name"], size=ctx["size"], busid=ctx["busid"]
        )

        super().__init__(ctx=ctx)


class GroupAdminChangeNoticeEvent(NoticeEvent):
    __slots__ = ("sub_type", "group_id", "user_id")

    notice_type: ClassVar[Literal["group_admin"]] = "group_admin"

    sub_type: Literal["set", "unset"]

    group_id: int
    user_id: int

    def __init__(self, *, ctx: Context) -> None:
        self.sub_type = ctx["sub_type"]

        self.group_id = ctx["group_id"]
        self.user_id = ctx["user_id"]

        super().__init__(ctx=ctx)


class GroupMemberDecreaseNoticeEvent(NoticeEvent):
    __slots__ = ("sub_type", "group_id", "user_id", "operator_id")

    notice_type: ClassVar[Literal["group_decrease"]] = "group_decrease"

    sub_type: Literal["leave", "kick", "kick_me"]

    group_id: int
    user_id: int
    operator_id: int

    def __init__(self, *, ctx: Context) -> None:
        self.sub_type = ctx["sub_type"]

        self.group_id = ctx["group_id"]
        self.user_id = ctx["user_id"]
        self.operator_id = ctx["operator_id"]

        super().__init__(ctx=ctx)


class GroupMemberIncreaseNoticeEvent(NoticeEvent):
    __slots__ = ("sub_type", "group_id", "user_id", "operator_id")

    notice_type: ClassVar[Literal["group_increase"]] = "group_increase"

    sub_type: Literal["approve", "invite"]

    group_id: int
    user_id: int
    operator_id: int

    def __init__(self, *, ctx: Context) -> None:
        self.sub_type = ctx["sub_type"]

        self.group_id = ctx["group_id"]
        self.user_id = ctx["user_id"]
        self.operator_id = ctx["operator_id"]

        super().__init__(ctx=ctx)


class GroupBanNoticeEvent(NoticeEvent):
    __slots__ = ("sub_type", "group_id", "user_id", "operator_id", "duration")

    notice_type: ClassVar[Literal["group_ban"]] = "group_ban"

    sub_type: Literal["ban", "lift_ban"]

    group_id: int
    user_id: int
    operator_id: int
    duration: int

    def __init__(self, *, ctx: Context) -> None:
        self.sub_type = ctx["sub_type"]

        self.group_id = ctx["group_id"]
        self.user_id = ctx["user_id"]
        self.operator_id = ctx["operator_id"]
        self.duration = ctx["duration"]

        super().__init__(ctx=ctx)


class FriendAddNoticeEvent(NoticeEvent):
    __slots__ = ("user_id",)

    notice_type: ClassVar[Literal["friend_add"]] = "friend_add"

    user_id: int

    def __init__(self, *, ctx: Context) -> None:
        self.user_id = ctx["user_id"]

        super().__init__(ctx=ctx)


class GroupMessageRecallNoticeEvent(NoticeEvent):
    __slots__ = ("group_id", "user_id", "operator_id", "message_id")

    notice_type: Literal["group_recall"] = "group_recall"

    group_id: int
    user_id: int
    operator_id: int
    message_id: int

    def __init__(self, *, ctx: Context) -> None:
        self.group_id = ctx["group_id"]
        self.user_id = ctx["user_id"]
        self.operator_id = ctx["operator_id"]
        self.message_id = ctx["message_id"]

        super().__init__(ctx=ctx)


class FriendMessageRecallNoticeEvent(NoticeEvent):
    __slots__ = ("user_id", "message_id")

    notice_type: Literal["friend_recall"] = "friend_recall"

    user_id: int
    message_id: int

    def __init__(self, *, ctx: Context) -> None:
        self.user_id = ctx["user_id"]
        self.message_id = ctx["message_id"]

        super().__init__(ctx=ctx)
