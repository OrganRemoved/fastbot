import asyncio
from functools import partial, reduce, wraps
from operator import and_, or_
from typing import Any, Awaitable, Callable, Coroutine, Literal


def ensure_async(
    func: Callable[..., Any] | None = None, *, to_thread: bool = False
) -> Callable[..., Awaitable[Any]]:
    if func is None:
        return partial(ensure_async, to_thread=to_thread)

    if asyncio.iscoroutinefunction(func):
        return func

    if to_thread:

        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            return await asyncio.to_thread(func, *args, **kwargs)
    else:

        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            return func(*args, **kwargs)

    return wrapper


class Matcher:
    __slots__ = ("rule", "awaitable", "matchers", "operator")

    def __init__(
        self,
        rule: Callable[..., Any] = lambda *args, **kwargs: True,
        *,
        awaitable: bool = False,
        matchers: list["Matcher"] | None = None,
        operator: Literal["AND", "OR"] | None = None,
    ) -> None:
        self.rule = rule

        self.awaitable = (
            awaitable
            or asyncio.iscoroutinefunction(rule)
            or asyncio.iscoroutinefunction(self.__call__)
        )

        self.matchers = matchers or []
        self.operator = operator

    def __call__(
        self, *args, **kwargs
    ) -> dict[str, Any] | Coroutine[Any, Any, dict[str, Any]]:
        return self.rule(*args, **kwargs)

    def __and__(self, other: "Matcher") -> "Matcher":
        matchers = [
            *(self.matchers if self.operator == "AND" else [self]),
            *(other.matchers if other.operator == "AND" else [other]),
        ]

        async_matchers = [matcher for matcher in matchers if matcher.awaitable]
        sync_matchers = [matcher for matcher in matchers if not matcher.awaitable]

        if awaitable := async_matchers:

            async def wrapper(*args, **kwargs) -> dict[str, Any]:
                ctx = {}

                for matcher in sync_matchers:
                    if not (matched := matcher(*args, **kwargs)):
                        return {}

                    ctx |= matched if isinstance(matched, dict) else {"_": matched}

                try:
                    async for completed_task in asyncio.as_completed(
                        tasks := [
                            asyncio.create_task(
                                matcher(*args, **kwargs), eager_start=True
                            )
                            for matcher in async_matchers
                        ]
                    ):
                        if not (matched := await completed_task):
                            return {}

                        ctx |= matched if isinstance(matched, dict) else {"_": matched}

                finally:
                    for task in tasks:
                        if not task.done():
                            task.cancel()

                return ctx

        else:

            def wrapper(*args, **kwargs) -> dict[str, Any]:
                ctx = {}

                for matcher in sync_matchers:
                    if not (matched := matcher(*args, **kwargs)):
                        return {}

                    ctx |= matched if isinstance(matched, dict) else {"_": matched}

                return ctx

        return Matcher(
            rule=wrapper, awaitable=awaitable, matchers=matchers, operator="AND"
        )

    def __or__(self, other: "Matcher") -> "Matcher":
        matchers = [
            *(self.matchers if self.operator == "OR" else [self]),
            *(other.matchers if other.operator == "OR" else [other]),
        ]

        async_matchers = [matcher for matcher in matchers if matcher.awaitable]
        sync_matchers = [matcher for matcher in matchers if not matcher.awaitable]

        if awaitable := async_matchers:

            async def wrapper(*args, **kwargs) -> dict[str, Any]:
                for matcher in sync_matchers:
                    if matched := matcher(*args, **kwargs):
                        return matched if isinstance(matched, dict) else {"_": matched}

                try:
                    async for completed_task in asyncio.as_completed(
                        tasks := [
                            asyncio.create_task(
                                matcher(*args, **kwargs), eager_start=True
                            )
                            for matcher in async_matchers
                        ]
                    ):
                        if matched := await completed_task:
                            return (
                                matched if isinstance(matched, dict) else {"_": matched}
                            )

                finally:
                    for task in tasks:
                        if not task.done():
                            task.cancel()

                return {}
        else:

            def wrapper(*args, **kwargs) -> dict[str, Any]:
                for matcher in sync_matchers:
                    if matched := matcher(*args, **kwargs):
                        return matched if isinstance(matched, dict) else {"_": matched}

                return {}

        return Matcher(
            rule=wrapper, awaitable=awaitable, matchers=matchers, operator="OR"
        )

    def __invert__(self) -> "Matcher":
        if not self.awaitable:

            def wrapper(*args, **kwargs) -> bool:
                return not self(*args, **kwargs)

        else:

            async def wrapper(*args, **kwargs) -> bool:
                return not await self(*args, **kwargs)

        return Matcher(rule=wrapper, awaitable=self.awaitable)

    async def match(self, *args, **kwargs) -> dict[str, Any]:
        if matched := (
            await self(*args, **kwargs) if self.awaitable else self(*args, **kwargs)
        ):
            return matched if isinstance(matched, dict) else {"_": matched}

        return {}

    @classmethod
    def all(cls, *matchers: "Matcher") -> "Matcher":
        return reduce(and_, matchers)

    @classmethod
    def any(cls, *matchers: "Matcher") -> "Matcher":
        return reduce(or_, matchers)
