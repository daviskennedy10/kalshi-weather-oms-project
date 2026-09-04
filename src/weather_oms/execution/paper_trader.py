import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from weather_oms.events import OrderIntent


@dataclass(frozen=True, slots=True)
class PaperFill:
    fill_id: str
    client_order_id: str
    price_cents: int
    count: int
    filled_at: datetime


class PaperTrader:
    """Deterministic MVP fill model: marketable limit orders fill at their limit."""

    async def submit(self, intent: OrderIntent, client_order_id: str) -> PaperFill:
        return PaperFill(
            fill_id=str(uuid.uuid4()),
            client_order_id=client_order_id,
            price_cents=intent.price_cents,
            count=intent.count,
            filled_at=datetime.now(UTC),
        )

