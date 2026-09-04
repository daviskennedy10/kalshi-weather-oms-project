import asyncio

from weather_oms.events import Event


class EventBus:
    """Bounded in-process bus; backpressure is explicit instead of silently dropping data."""

    def __init__(self, maxsize: int = 10_000) -> None:
        self._queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=maxsize)

    async def publish(self, event: Event) -> None:
        await self._queue.put(event)

    async def next(self) -> Event:
        return await self._queue.get()

    def task_done(self) -> None:
        self._queue.task_done()

