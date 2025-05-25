# FastBot

A lightweight bot framework built on `FastAPI` and the `OneBot v11` protocol.

## Quick Start

### Installation

#### Install from GitHub (for development or bleeding-edge features):

```sh
pip install --no-cache --upgrade git+https://github.com/OrganRemoved/fastbot.git
```

or

```sh
pip install --no-cache --upgrade https://github.com/OrganRemoved/fastbot/archive/refs/heads/main.zip
```

#### Install from PyPI (recommended for stable versions):

```sh
pip install --no-cache --upgrade fastbot-onebot
```

### Example

The recommended project structure is as follows:

```sh
bot_example
|   __init__.py
|   bot.py
|
\---plugins
        __init__.py
        plugin_example.py
```

#### bot.py

```python
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastbot.bot import FastBot
from fastbot.plugin import PluginManager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Perform application startup and shutdown tasks here.
    yield


if __name__ == "__main__":
    (
        FastBot
        # `plugins`: Path(s) to plugin directories, passed to `fastbot.plugin.PluginManager.import_from(...)`.
        # Remaining arguments: Passed directly to `FastAPI(...)`.
        .build(plugins=["plugins"], lifespan=lifespan)
        # Arguments: Passed directly to `uvicorn.run(...)`.
        .run(host="0.0.0.0", port=80)
    )
```

#### plugin_example.py

```python
from typing import AsyncGenerator
from os import environ

from fastbot.event import Context
from fastbot.event.message import GroupMessageEvent, PrivateMessageEvent
from fastbot.matcher import Matcher
from fastbot.plugin import Dependency, PluginManager, background, middleware, on
from redis.asyncio.client import Redis, Pipeline


# Defining custom Matchers for complex rule evaluation.
IsNotGroupAdmin = Matcher(rule=lambda event: event.sender.role != "admin")


# Example: Reusable Matcher for checking against a group blacklist.  Demonstrates Matcher subclassing.
class IsInGroupBlacklist(Matcher):
    def __init__(self, *blacklist):
        self.blacklist = blacklist

    async def __call__(self, event: GroupMessageEvent) -> bool:
        return event.group_id in self.blacklist


async def init() -> None:
    # Perform asynchronous initialization tasks when the plugin loads.
    # Asynchronous generators can be used to implement `lifespan`-like functionality for plugin setup/teardown.
    ...

    # yield  (Optional: include if you will need a teardown)

@background
async def blocking_backgroud_task() -> None:
    # The `@background` decorator enables fire-and-forget execution of blocking tasks, ensuring non-blocking operation of the main bot loop.
    while True:
        ...


# Dependency Injection examples:

# Define an async generator for Redis, handling connection creation and cleanup.
async def get_redis(*args, **kwargs) -> AsyncGenerator[Redis, None]:
    if "url" in kwargs:
        redis = Redis.from_url(decode_responses=True, *args, **kwargs)

    elif "connection_pool" in kwargs:
        redis = Redis.from_pool(*args, **kwargs)

    else:
        redis = Redis(
            host=kwargs.pop("host", environ.get("REDIS_HOST", "localhost")), # Provide a default value!!!
            port=kwargs.pop("port", int(environ.get("REDIS_PORT", 6379))), # Provide a default value!!!
            db=kwargs.pop("db", environ.get("REDIS_DB", 0)), # Provide a default value!!!
            password=kwargs.pop("password", environ.get("REDIS_PASSWORD", None)), # Provide a default value!!!
            decode_responses=kwargs.pop("decode_responses", True),
            **kwargs,
        )

    async with redis as r:
        yield r


# Chaining Dependency Injection: Define an async generator that depends on another (Redis connection).
async def get_pipeline(
    redis: Redis = Dependency.provide(dependency=get_redis), *args, **kwargs
) -> AsyncGenerator[Pipeline, None]:
    async with redis.pipeline(*args, **kwargs) as pipeline:
        yield pipeline

        await pipeline.execute()


# Middleware examples:

# Middleware functions are executed in sequence before event handlers.
@middleware(priority=0)
async def preprocessing(ctx: Context):
    if (group_id := ctx.get("group_id")) == ...:  # Replace elipsis with actual condition
        # Temporarily disable the plugin for specific groups.
        PluginManager.plugins["plugins.plugin_example"].state.set(False)
    elif group_id is None:
        # When the `Context` is cleared, the middleware will discard
        # the event and terminate processing, preventing further handlers from being executed.
        ctx.clear()


# Event Handler example:

# Combining multiple rules using `&(and)`, `|(or)`, and `~(not)`.
@on(matcher=IsNotGroupAdmin & ~IsInGroupBlacklist(...))
# For maximum performance, consider using a callable (e.g., a lambda function) directly in the `matcher`.
# Example: `lambda event: event.get("group_id") in (...)`
async def func(
    # Specify the event type(s) this handler should process using type hints.  Use `|` or `typing.Union` for multiple types.
    event: GroupMessageEvent | PrivateMessageEvent,
    *,
    redis: Redis = Dependency.provide(dependency=get_redis),
    pipeline: Pipeline = Dependency.provide(dependency=get_pipeline),
) -> None:
    if event.text == "guess":
        await event.send("Start guessing the number game now: [0-10]!")

        while new_event := await event.defer("Enter a number: "):
            if new_event.text != "10":
                await new_event.send("Guess wrong!")
                continue

            await new_event.send("Guess right!")
            return
```
