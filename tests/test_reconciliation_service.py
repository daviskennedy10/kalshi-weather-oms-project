import uuid
from datetime import UTC, datetime

import pytest

from weather_oms.oms.order_state import OrderState
from weather_oms.oms.reconciliation import OrderSnapshot
from weather_oms.oms.reconciliation_service import (
    reconcile_event_orders,
)
from weather_oms.storage.order_repository import StoredOrder


class FakeOrderReader:
    def __init__(
        self,
        orders: tuple[OrderSnapshot, ...],
    ) -> None:
        self.orders = orders
        self.received_event_ticker: str | None = None

    async def get_orders(
        self,
        *,
        event_ticker: str | None = None,
    ) -> tuple[OrderSnapshot, ...]:
        self.received_event_ticker = event_ticker
        return self.orders


def make_local_order() -> StoredOrder:
    timestamp = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)

    return StoredOrder(
        id=uuid.uuid4(),
        client_order_id="oms-client-1",
        exchange_order_id="exchange-1",
        market_ticker="KXHIGHNY-26SEP15-T85",
        side="yes",
        price_cents=27,
        count=10,
        filled_count=3,
        state=OrderState.PARTIALLY_FILLED,
        created_at=timestamp,
        updated_at=timestamp,
    )


def make_exchange_order() -> OrderSnapshot:
    return OrderSnapshot(
        client_order_id="oms-client-1",
        exchange_order_id="exchange-1",
        state=OrderState.PARTIALLY_FILLED,
        count=10,
        filled_count=3,
    )


@pytest.mark.asyncio
async def test_matching_orders_are_in_sync() -> None:
    reader = FakeOrderReader(
        (make_exchange_order(),)
    )

    report = await reconcile_event_orders(
        local_orders=(make_local_order(),),
        exchange_reader=reader,
        event_ticker="kxhighny-26sep15",
    )

    assert report.in_sync is True
    assert report.differences == ()
    assert (
        reader.received_event_ticker
        == "KXHIGHNY-26SEP15"
    )


@pytest.mark.asyncio
async def test_reports_order_difference() -> None:
    reader = FakeOrderReader(
        (
            OrderSnapshot(
                client_order_id="oms-client-1",
                exchange_order_id="exchange-1",
                state=OrderState.FILLED,
                count=10,
                filled_count=10,
            ),
        )
    )

    report = await reconcile_event_orders(
        local_orders=(make_local_order(),),
        exchange_reader=reader,
        event_ticker="KXHIGHNY-26SEP15",
    )

    assert report.in_sync is False
    assert {
        difference.field
        for difference in report.differences
    } == {
        "state",
        "filled_count",
        "remaining_count",
    }


@pytest.mark.asyncio
async def test_rejects_empty_event_ticker() -> None:
    reader = FakeOrderReader(())

    with pytest.raises(
        ValueError,
        match="event_ticker cannot be empty",
    ):
        await reconcile_event_orders(
            local_orders=(),
            exchange_reader=reader,
            event_ticker=" ",
        )