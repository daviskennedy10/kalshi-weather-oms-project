from dataclasses import replace

import pytest

from weather_oms.oms.order_state import OrderState
from weather_oms.oms.reconciliation import (
    OrderSnapshot,
    compare_orders,
)


def make_order(
    client_order_id: str = "order-a",
) -> OrderSnapshot:
    return OrderSnapshot(
        client_order_id=client_order_id,
        exchange_order_id="exchange-a",
        state=OrderState.OPEN,
        count=2,
        filled_count=0,
    )


def test_matching_orders_are_in_sync() -> None:
    order = make_order()

    report = compare_orders(
        internal=(order,),
        exchange=(order,),
    )

    assert report.in_sync is True
    assert report.differences == ()


def test_detects_order_missing_from_exchange() -> None:
    report = compare_orders(
        internal=(make_order(),),
        exchange=(),
    )

    assert report.in_sync is False
    assert len(report.differences) == 1

    difference = report.differences[0]

    assert difference.client_order_id == "order-a"
    assert difference.field == "presence"
    assert difference.internal is True
    assert difference.exchange is False


def test_detects_order_missing_internally() -> None:
    report = compare_orders(
        internal=(),
        exchange=(make_order(),),
    )

    difference = report.differences[0]

    assert difference.field == "presence"
    assert difference.internal is False
    assert difference.exchange is True


def test_detects_exchange_order_id_mismatch() -> None:
    internal = make_order()
    exchange = replace(
        internal,
        exchange_order_id="different-exchange-id",
    )

    report = compare_orders(
        internal=(internal,),
        exchange=(exchange,),
    )

    assert {
        difference.field
        for difference in report.differences
    } == {"exchange_order_id"}


def test_detects_state_mismatch() -> None:
    internal = make_order()
    exchange = replace(
        internal,
        state=OrderState.FILLED,
        filled_count=2,
    )

    report = compare_orders(
        internal=(internal,),
        exchange=(exchange,),
    )

    assert {
        difference.field
        for difference in report.differences
    } == {
        "state",
        "filled_count",
        "remaining_count",
    }


def test_detects_order_count_mismatch() -> None:
    internal = make_order()
    exchange = replace(
        internal,
        count=3,
    )

    report = compare_orders(
        internal=(internal,),
        exchange=(exchange,),
    )

    assert {
        difference.field
        for difference in report.differences
    } == {
        "count",
        "remaining_count",
    }


def test_detects_partial_fill_mismatch() -> None:
    internal = replace(
        make_order(),
        state=OrderState.PARTIALLY_FILLED,
        filled_count=1,
    )
    exchange = replace(
        internal,
        filled_count=0,
    )

    report = compare_orders(
        internal=(internal,),
        exchange=(exchange,),
    )

    assert {
        difference.field
        for difference in report.differences
    } == {
        "filled_count",
        "remaining_count",
    }


def test_reports_multiple_orders_in_stable_order() -> None:
    internal = (
        make_order("order-b"),
        make_order("order-a"),
    )

    report = compare_orders(
        internal=internal,
        exchange=(),
    )

    assert [
        difference.client_order_id
        for difference in report.differences
    ] == [
        "order-a",
        "order-b",
    ]


def test_rejects_duplicate_internal_order_ids() -> None:
    order = make_order()

    with pytest.raises(
        ValueError,
        match="Duplicate internal client_order_id",
    ):
        compare_orders(
            internal=(order, order),
            exchange=(),
        )


def test_rejects_duplicate_exchange_order_ids() -> None:
    order = make_order()

    with pytest.raises(
        ValueError,
        match="Duplicate exchange client_order_id",
    ):
        compare_orders(
            internal=(),
            exchange=(order, order),
        )


def test_snapshot_calculates_remaining_count() -> None:
    order = OrderSnapshot(
        client_order_id="order-a",
        exchange_order_id="exchange-a",
        state=OrderState.PARTIALLY_FILLED,
        count=5,
        filled_count=2,
    )

    assert order.remaining_count == 3


def test_snapshot_rejects_invalid_filled_count() -> None:
    with pytest.raises(
        ValueError,
        match="filled_count must be between",
    ):
        OrderSnapshot(
            client_order_id="order-a",
            exchange_order_id="exchange-a",
            state=OrderState.OPEN,
            count=2,
            filled_count=3,
        )


def test_empty_inputs_are_in_sync() -> None:
    report = compare_orders(
        internal=(),
        exchange=(),
    )

    assert report.in_sync is True
