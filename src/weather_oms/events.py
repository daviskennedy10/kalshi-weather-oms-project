from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any


class EventKind(StrEnum):
    FORECAST_UPDATED = "forecast.updated"
    TEMPERATURE_SETTLED = "temperature.settled"
    ORDERBOOK_UPDATED = "orderbook.updated"
    FILL_RECEIVED = "fill.received"
    


@dataclass(frozen=True, slots=True)
class Event:
    kind: EventKind
    source_time: datetime
    received_time: datetime = field(default_factory=lambda: datetime.now(UTC))
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class OrderIntent:
    market_ticker: str
    side: str
    price_cents: int
    count: int
    model_probability: Decimal
    event_received_time: datetime

