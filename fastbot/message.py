from base64 import b64encode
from dataclasses import KW_ONLY, asdict, dataclass
from itertools import chain, groupby
from operator import attrgetter
from typing import Any, Iterable, Iterator, Literal, Self, TypedDict, Union

PREV, NEXT, DATA = 0, 1, 2


class MessageSegmentData(TypedDict):
    type: str
    data: dict[str, Any]


class Link(list):
    __slots__ = ("length", "maxlen")

    def __init__(
        self, iterable: Iterable[Any] | None = None, maxlen: int | None = None
    ) -> None:
        self[:] = [self, self, None]

        self.length = 0
        self.maxlen = maxlen

        if iterable:
            self.extend(iterable)

    def __iter__(self) -> Iterator[Any]:
        next_node = self[NEXT]

        while next_node is not self:
            yield next_node[DATA]
            next_node = next_node[NEXT]

    def __len__(self) -> int:
        return self.length

    def __delitem__(self, idx: int) -> None:
        if not (-self.length <= idx < self.length):
            raise IndexError("index out of range")

        if idx < 0:
            idx += self.length

        if idx <= self.length // 2:
            current_node = self[NEXT]
            for _ in range(idx):
                current_node = current_node[NEXT]
        else:
            current_node = self[PREV]
            for _ in range(self.length - idx - 1):
                current_node = current_node[PREV]

        prev_node = current_node[PREV]
        next_node = current_node[NEXT]
        prev_node[NEXT] = next_node
        next_node[PREV] = prev_node

        self.length -= 1

    def append(self, value: Any) -> None:
        if self.maxlen is not None and self.length == self.maxlen:
            self.popleft()

        prev_node = self[PREV]
        prev_node[NEXT] = self[PREV] = [prev_node, self, value]

        self.length += 1

    def appendleft(self, value: Any) -> None:
        if self.maxlen is not None and self.length == self.maxlen:
            self.pop()

        next_node = self[NEXT]
        next_node[PREV] = self[NEXT] = [self, next_node, value]

        self.length += 1

    def clear(self) -> None:
        self[:] = [self, self, None]
        self.length = 0

    def extend(self, values: Any) -> None:
        for value in values:
            self.append(value)

    def extendleft(self, values: Any) -> None:
        for value in values:
            self.appendleft(value)

    def insert(self, idx: int, value: Any) -> None:
        if not (-self.length <= idx < self.length):
            raise IndexError("index out of range")

        if self.maxlen is not None and self.length == self.maxlen:
            raise IndexError("list has reached its maximum length")

        if idx == 0:
            self.appendleft(value)

        elif idx < 0:
            idx += self.length

        if idx <= self.length // 2:
            current_node = self[NEXT]
            for _ in range(idx):
                current_node = current_node[NEXT]

        else:
            current_node = self
            for _ in range(self.length - idx):
                current_node = current_node[PREV]

        prev_node = current_node
        next_node = current_node[NEXT]
        link = [prev_node, next_node, value]
        next_node[PREV] = link
        prev_node[NEXT] = link

        self.length += 1

    def pop(self) -> Any:
        if self.length == 0:
            raise IndexError("pop from empty list")

        prev_node = self[PREV]
        prev_node[PREV][NEXT] = self
        self[PREV] = prev_node[PREV]

        self.length -= 1
        return prev_node[DATA]

    def popleft(self) -> Any:
        if self.length == 0:
            raise IndexError("pop from empty list")

        next_node = self[NEXT]
        next_node[NEXT][PREV] = self
        self[NEXT] = next_node[NEXT]

        self.length -= 1
        return next_node[DATA]

    def reverse(self) -> None:
        prev_node = self
        current_node = self[NEXT]
        self[NEXT] = self[PREV] = self

        while current_node is not self:
            next_node = current_node[NEXT]
            current_node[NEXT] = prev_node
            current_node[PREV] = prev_node
            prev_node = current_node
            current_node = next_node

        self[NEXT] = prev_node
        self[PREV] = prev_node[PREV]

    def remove(self, value: Any) -> None:
        current_node = self[NEXT]
        while current_node is not self:
            if current_node[DATA] == value:
                prev_node = current_node[PREV]
                next_node = current_node[NEXT]
                prev_node[NEXT] = next_node
                next_node[PREV] = prev_node

                self.length -= 1
                return

            current_node = current_node[NEXT]

        raise ValueError(f"{value} is not in list")

    def rotate(self, n: int) -> None:
        if (length := self.length) == 0:
            return

        n %= length
        if n == 0:
            return

        if n < 0:
            n += length

        if n <= length // 2:
            for _ in range(n):
                prev_node = self[PREV]
                self[PREV] = prev_node[PREV]
                prev_node[PREV][NEXT] = self
                self[NEXT][PREV] = prev_node
                prev_node[NEXT] = self[NEXT]
                self[NEXT] = prev_node
                prev_node[PREV] = self

        else:
            for _ in range(length - n):
                next_node = self[NEXT]
                self[NEXT] = next_node[NEXT]
                next_node[NEXT][PREV] = self
                self[PREV][NEXT] = next_node
                next_node[PREV] = self[PREV]
                self[PREV] = next_node
                next_node[NEXT] = self


@dataclass
class MessageSegment:
    __slots__ = ("type", "data")

    _: KW_ONLY

    type: str
    data: dict[str, Any]

    def __add__(self, other: Union[str, Iterable[Any], "MessageSegment"]) -> "Message":
        return Message(content=self) + other

    def __radd__(self, other: Union[str, Iterable[Any], "MessageSegment"]) -> "Message":
        return Message(content=other) + self

    @classmethod
    def text(cls, text: str) -> Self:
        return cls(type="text", data={"text": text})

    @classmethod
    def face(cls, id: int) -> Self:
        return cls(type="face", data={"id": str(id)})

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
    def at(cls, qq: int | Literal["all"]) -> Self:
        return cls(type="at", data={"qq": str(qq)})

    @classmethod
    def reply(cls, id: int) -> Self:
        return cls(type="reply", data={"id": str(id)})

    @classmethod
    def forward(cls, id: int) -> Self:
        return cls(type="forward", data={"id": str(id)})

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
                            asdict(segment)
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


class Message(list):
    __slots__ = ()

    def __init__(
        self, content: str | Iterable[Any] | MessageSegment | None = None
    ) -> None:
        super().__init__()

        if content:
            if isinstance(content, MessageSegment):
                self.append(content)
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

    def compact(self, *, concat: str = "") -> "Message":
        return Message(
            MessageSegment.text(
                text=concat.join(segment.data["text"] for segment in segments)
            )
            if key == "text"
            else segments
            for key, segments in groupby(self, key=attrgetter("type"))
        )
