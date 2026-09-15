from typing import Protocol

from weather_oms.oms.reconciliation import (
    OrderSnapshot,
    ReconciliationReport,
    compare_orders,
)
from weather_oms.oms.reconciliation_adapter import (
    stored_order_to_snapshot,
)
from weather_oms.storage.order_repository import StoredOrder


class ExchangeOrderReader(Protocol):
    async def get_orders(
        self,
        *,
        event_ticker: str | None = None,
    ) -> tuple[OrderSnapshot, ...]: ...


async def reconcile_event_orders(
    local_orders: tuple[StoredOrder, ...],
    exchange_reader: ExchangeOrderReader,
    event_ticker: str,
) -> ReconciliationReport:
    """Compare local orders with Kalshi without changing either."""

    normalized_event = event_ticker.strip().upper()

    if not normalized_event:
        raise ValueError("event_ticker cannot be empty.")

    internal_snapshots = tuple(
        stored_order_to_snapshot(order)
        for order in local_orders
    )

    exchange_snapshots = await exchange_reader.get_orders(
        event_ticker=normalized_event,
    )

    return compare_orders(
        internal=internal_snapshots,
        exchange=exchange_snapshots,
    )