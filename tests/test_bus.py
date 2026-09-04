import asyncio
from datetime import UTC, datetime

from weather_oms.bus import EventBus
from weather_oms.events import Event, EventKind


async def test_bus_preserves_event() -> None:
    bus = EventBus(maxsize=1)
    event = Event(EventKind.FORECAST_UPDATED, datetime.now(UTC))
    await bus.publish(event)
    assert await bus.next() == event


async def test_bus_applies_backpressure() -> None:
    bus = EventBus(maxsize=1)
    event = Event(EventKind.FORECAST_UPDATED, datetime.now(UTC))
    await bus.publish(event)
    blocked = asyncio.create_task(bus.publish(event))
    await asyncio.sleep(0)
    assert not blocked.done()
    await bus.next()
    await blocked

