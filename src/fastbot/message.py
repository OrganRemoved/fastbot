from base64 import b64encode
from itertools import chain, groupby
from operator import itemgetter
from typing import Any, Iterable, Literal, Self, TypedDict, Union

PREV, NEXT, DATA = 0, 1, 2


class MessageSegmentData(TypedDict):
    type: str
    data: dict[str, Any]


class MessageSegment(dict):
    __slots__ = ()

    def __init__(self, type: str, data: dict[str, Any]) -> None:
        super().__init__(type=type, data=data)

    def __add__(self, other: Union[str, Iterable[Any], "MessageSegment"]) -> "Message":
        return Message(content=self) + other

    def __radd__(self, other: Union[str, Iterable[Any], "MessageSegment"]) -> "Message":
        return Message(content=other) + self

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(type={self['type']}, data={self['data']})"

    @classmethod
    def text(cls, text: str) -> Self:
        return cls(type="text", data={"text": text})

    @classmethod
    def face(cls, id: str) -> Self:
        return cls(type="face", data={"id": id})

    @classmethod
    def image(
        cls,
        file: bytes | str,
        type: Literal["flash"] | None = None,
        url: str | None = None,
        cache: bool | None = None,
        proxy: bool | None = None,
        timeout: int | None = None,
    ) -> Self:
        return cls(
            type="image",
            data={
                "file": (
                    file
                    if isinstance(file, str)
                    else f"base64://{b64encode(file).decode(encoding='utf-8')}"
                ),
                "type": type,
                "url": url,
                "cache": cache,
                "proxy": proxy,
                "timeout": timeout,
            },
        )

    @classmethod
    def record(
        cls,
        file: str,
        magic: bool | None = None,
        url: str | None = None,
        cache: bool | None = None,
        proxy: bool | None = None,
        timeout: int | None = None,
    ) -> Self:
        return cls(
            type="record",
            data={
                "file": file,
                "magic": magic,
                "url": url,
                "cache": cache,
                "proxy": proxy,
                "timeout": timeout,
            },
        )

    @classmethod
    def video(
        cls,
        file: str,
        url: str | None = None,
        cache: bool | None = None,
        proxy: bool | None = None,
        timeout: int | None = None,
    ) -> Self:
        return cls(
            type="video",
            data={
                "file": file,
                "url": url,
                "cache": cache,
                "proxy": proxy,
                "timeout": timeout,
            },
        )

    @classmethod
    def at(cls, qq: str | Literal["all"]) -> Self:
        return cls(type="at", data={"qq": qq})

    @classmethod
    def reply(cls, id: str) -> Self:
        return cls(type="reply", data={"id": id})

    @classmethod
    def forward(cls, id: str) -> Self:
        return cls(type="forward", data={"id": id})

    @classmethod
    def node(
        cls,
        id: int | None = None,
        content: Union["Message", list[Union["MessageSegment", MessageSegmentData]]]
        | None = None,
        **kwargs,
    ) -> Self:
        if id:
            return cls(type="node", data={"id": str(id)})
        elif content:
            return cls(
                type="node",
                data={
                    "content": [
                        (
                            dict(segment)
                            if isinstance(segment, MessageSegment)
                            else segment
                        )
                        for segment in content
                    ],
                    **kwargs,
                },
            )
        else:
            raise ValueError("parameter `id` or `content` must be specified")


class Message(list[MessageSegment]):
    __slots__ = ()

    def __init__(
        self, content: dict | str | Iterable[Any] | MessageSegment | None = None
    ) -> None:
        super().__init__()

        if content:
            if isinstance(content, MessageSegment):
                self.append(content)

            elif isinstance(content, dict):
                self.append(MessageSegment(type=content["type"], data=content["data"]))

            elif isinstance(content, str):
                self.append(MessageSegment.text(text=content))

            elif isinstance(content, Iterable):
                self.extend(
                    chain.from_iterable(Message(content=item) for item in content)
                )

            else:
                raise ValueError("unsupported message type")

    def __add__(self, other: str | Iterable[Any] | MessageSegment) -> "Message":
        message = Message(content=self)
        message += other

        return message

    def __radd__(self, other: str | Iterable[Any] | MessageSegment) -> "Message":
        message = Message(content=other)
        message += self

        return message

    def __iadd__(self, other: str | Iterable[Any] | MessageSegment) -> "Message":
        if isinstance(other, Message):
            self.extend(other)

        elif isinstance(other, MessageSegment):
            self.append(other)

        elif isinstance(other, str):
            self.append(MessageSegment.text(text=other))

        elif isinstance(other, Iterable):
            self.extend(chain.from_iterable(Message(content=item) for item in other))

        else:
            raise ValueError("unsupported message type")

        return self

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}([{', '.join(repr(segment) for segment in self)}])"

    def compact(self, *, concat: str = "") -> "Message":
        return Message(
            MessageSegment.text(
                text=concat.join(segment["data"]["text"] for segment in segments)
            )
            if key == "text"
            else segments
            for key, segments in groupby(self, key=itemgetter("type"))
        )
