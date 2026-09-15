import uuid
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from weather_oms.oms.order_state import OrderState
from weather_oms.oms.reconciliation_adapter import (
    kalshi_order_to_snapshot,
    stored_order_to_snapshot,
)
from weather_oms.storage.order_repository import StoredOrder


def make_stored_order() -> StoredOrder:
    timestamp = datetime(2026, 9, 14, 12, 0, tzinfo=UTC)

    return StoredOrder(
        id=uuid.uuid4(),
        client_order_id="oms-client-123",
        exchange_order_id="exchange-456",
        market_ticker="KXHIGHNY-26SEP10-T85",
        side="yes",
        price_cents=27,
        count=10,
        filled_count=3,
        state=OrderState.PARTIALLY_FILLED,
        created_at=timestamp,
        updated_at=timestamp,
    )


def make_kalshi_order() -> dict[str, object]:
    return {
        "client_order_id": "oms-client-123",
        "order_id": "exchange-456",
        "status": "resting",
        "initial_count_fp": "10.00",
        "fill_count_fp": "3.00",
        "remaining_count_fp": "7.00",
    }


def test_converts_stored_order() -> None:
    snapshot = stored_order_to_snapshot(
        make_stored_order()
    )

    assert snapshot.client_order_id == "oms-client-123"
    assert snapshot.exchange_order_id == "exchange-456"
    assert snapshot.state is OrderState.PARTIALLY_FILLED
    assert snapshot.count == 10
    assert snapshot.filled_count == 3
    assert snapshot.remaining_count == 7


def test_converts_resting_unfilled_kalshi_order() -> None:
    payload = make_kalshi_order()
    payload["fill_count_fp"] = "0.00"
    payload["remaining_count_fp"] = "10.00"

    snapshot = kalshi_order_to_snapshot(payload)

    assert snapshot.state is OrderState.OPEN
    assert snapshot.filled_count == 0


def test_converts_resting_partially_filled_order() -> None:
    snapshot = kalshi_order_to_snapshot(
        make_kalshi_order()
    )

    assert snapshot.state is OrderState.PARTIALLY_FILLED
    assert snapshot.count == 10
    assert snapshot.filled_count == 3


def test_converts_executed_order() -> None:
    payload = make_kalshi_order()
    payload["status"] = "executed"
    payload["fill_count_fp"] = "10.00"
    payload["remaining_count_fp"] = "0.00"

    snapshot = kalshi_order_to_snapshot(payload)

    assert snapshot.state is OrderState.FILLED


def test_converts_canceled_order() -> None:
    payload = make_kalshi_order()
    payload["status"] = "canceled"

    snapshot = kalshi_order_to_snapshot(payload)

    assert snapshot.state is OrderState.CANCELLED
    assert snapshot.filled_count == 3


@pytest.mark.parametrize(
    "field_name",
    (
        "client_order_id",
        "order_id",
        "status",
    ),
)
def test_rejects_missing_text_field(
    field_name: str,
) -> None:
    payload = make_kalshi_order()
    del payload[field_name]

    with pytest.raises(
        ValueError,
        match=field_name,
    ):
        kalshi_order_to_snapshot(payload)


def test_rejects_unknown_status() -> None:
    payload = make_kalshi_order()
    payload["status"] = "mystery"

    with pytest.raises(
        ValueError,
        match="Unsupported Kalshi order status",
    ):
        kalshi_order_to_snapshot(payload)


def test_rejects_fractional_contract_count() -> None:
    payload = make_kalshi_order()
    payload["fill_count_fp"] = "3.50"

    with pytest.raises(
        ValueError,
        match="nonnegative whole number",
    ):
        kalshi_order_to_snapshot(payload)


def test_rejects_inconsistent_counts() -> None:
    payload = make_kalshi_order()
    payload["remaining_count_fp"] = "8.00"

    with pytest.raises(
        ValueError,
        match="do not equal",
    ):
        kalshi_order_to_snapshot(payload)


def test_rejects_incomplete_executed_order() -> None:
    payload = make_kalshi_order()
    payload["status"] = "executed"

    with pytest.raises(
        ValueError,
        match="fully filled",
    ):
        kalshi_order_to_snapshot(payload)


def test_rejects_resting_order_without_remaining_count() -> None:
    payload = make_kalshi_order()
    payload["fill_count_fp"] = "10.00"
    payload["remaining_count_fp"] = "0.00"

    with pytest.raises(
        ValueError,
        match="remaining contracts",
    ):
        kalshi_order_to_snapshot(payload)


def test_conversion_preserves_terminal_local_state() -> None:
    order = replace(
        make_stored_order(),
        state=OrderState.FILLED,
        filled_count=10,
    )

    snapshot = stored_order_to_snapshot(order)

    assert snapshot.state is OrderState.FILLED
    assert snapshot.remaining_count == 0