import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from weather_oms.oms.order_state import OrderState
from weather_oms.storage.fill_repository import record_fill
from weather_oms.storage.models import Fill, Order

FILL_TIME = datetime(
    2026,
    9,
    14,
    16,
    0,
    tzinfo=UTC,
)


def make_order(
    state: OrderState = OrderState.OPEN,
    count: int = 1,
    filled_count: int = 0,
) -> Order:
    return Order(
        id=uuid.uuid4(),
        client_order_id="client-order-1",
        exchange_order_id="exchange-order-1",
        market_ticker="KXHIGHNY-26SEP15-T85",
        side="yes",
        price_cents=27,
        count=count,
        filled_count=filled_count,
        state=state.value,
        created_at=FILL_TIME,
        updated_at=FILL_TIME,
    )


def make_fill(
    order: Order,
    count: int = 1,
    price_cents: int = 27,
) -> Fill:
    return Fill(
        id=uuid.uuid4(),
        exchange_fill_id="exchange-fill-1",
        order_id=order.id,
        count=count,
        price_cents=price_cents,
        filled_at=FILL_TIME,
    )


def optional_result(value: object) -> Mock:
    result = Mock()
    result.scalar_one_or_none.return_value = value
    return result


def scalar_result(value: object) -> Mock:
    result = Mock()
    result.scalar_one.return_value = value
    return result


@pytest.mark.asyncio
async def test_new_fill_completes_one_contract_order() -> None:
    order = make_order()
    fill = make_fill(order)
    session = AsyncMock(spec=AsyncSession)
    session.execute.side_effect = [
        optional_result(order),
        optional_result(None),
        scalar_result(0),
        optional_result(fill),
    ]

    result = await record_fill(
        session=session,
        client_order_id=order.client_order_id,
        exchange_order_id="exchange-order-1",
        exchange_fill_id="exchange-fill-1",
        count=1,
        price_cents=27,
        filled_at=FILL_TIME,
    )

    assert result.created is True
    assert result.total_filled_count == 1
    assert result.order_state == OrderState.FILLED
    assert order.filled_count == 1
    assert order.state == OrderState.FILLED.value
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_new_fill_partially_fills_order() -> None:
    order = make_order(count=2)
    fill = make_fill(order)
    session = AsyncMock(spec=AsyncSession)
    session.execute.side_effect = [
        optional_result(order),
        optional_result(None),
        scalar_result(0),
        optional_result(fill),
    ]

    result = await record_fill(
        session=session,
        client_order_id=order.client_order_id,
        exchange_order_id="exchange-order-1",
        exchange_fill_id="exchange-fill-1",
        count=1,
        price_cents=27,
        filled_at=FILL_TIME,
    )

    assert result.total_filled_count == 1
    assert result.order_state == OrderState.PARTIALLY_FILLED


@pytest.mark.asyncio
async def test_fill_can_arrive_before_acknowledgement() -> None:
    order = make_order(OrderState.SUBMITTING)
    order.exchange_order_id = None
    fill = make_fill(order)
    session = AsyncMock(spec=AsyncSession)
    session.execute.side_effect = [
        optional_result(order),
        optional_result(None),
        scalar_result(0),
        optional_result(fill),
    ]

    result = await record_fill(
        session=session,
        client_order_id=order.client_order_id,
        exchange_order_id="exchange-order-1",
        exchange_fill_id="exchange-fill-1",
        count=1,
        price_cents=27,
        filled_at=FILL_TIME,
    )

    assert result.order_state == OrderState.FILLED
    assert order.exchange_order_id == "exchange-order-1"


@pytest.mark.asyncio
async def test_duplicate_fill_is_not_counted_twice() -> None:
    order = make_order(
        state=OrderState.FILLED,
        filled_count=1,
    )
    existing_fill = make_fill(order)
    session = AsyncMock(spec=AsyncSession)
    session.execute.side_effect = [
        optional_result(order),
        optional_result(existing_fill),
    ]

    result = await record_fill(
        session=session,
        client_order_id=order.client_order_id,
        exchange_order_id="exchange-order-1",
        exchange_fill_id="exchange-fill-1",
        count=1,
        price_cents=27,
        filled_at=FILL_TIME,
    )

    assert result.created is False
    assert result.total_filled_count == 1
    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_acknowledgement_count_is_not_added_twice() -> None:
    order = make_order(
        state=OrderState.PARTIALLY_FILLED,
        count=2,
        filled_count=1,
    )
    fill = make_fill(order)
    session = AsyncMock(spec=AsyncSession)
    session.execute.side_effect = [
        optional_result(order),
        optional_result(None),
        scalar_result(0),
        optional_result(fill),
    ]

    result = await record_fill(
        session=session,
        client_order_id=order.client_order_id,
        exchange_order_id="exchange-order-1",
        exchange_fill_id="exchange-fill-1",
        count=1,
        price_cents=27,
        filled_at=FILL_TIME,
    )

    assert result.total_filled_count == 1
    assert result.order_state == OrderState.PARTIALLY_FILLED


@pytest.mark.asyncio
async def test_second_distinct_fill_completes_order() -> None:
    order = make_order(
        state=OrderState.PARTIALLY_FILLED,
        count=2,
        filled_count=1,
    )
    second_fill = make_fill(order)
    second_fill.exchange_fill_id = "exchange-fill-2"
    session = AsyncMock(spec=AsyncSession)
    session.execute.side_effect = [
        optional_result(order),
        optional_result(None),
        scalar_result(1),
        optional_result(second_fill),
    ]

    result = await record_fill(
        session=session,
        client_order_id=order.client_order_id,
        exchange_order_id="exchange-order-1",
        exchange_fill_id="exchange-fill-2",
        count=1,
        price_cents=27,
        filled_at=FILL_TIME,
    )

    assert result.total_filled_count == 2
    assert result.order_state == OrderState.FILLED


@pytest.mark.asyncio
async def test_overfill_is_rejected() -> None:
    order = make_order(count=1)
    session = AsyncMock(spec=AsyncSession)
    session.execute.side_effect = [
        optional_result(order),
        optional_result(None),
        scalar_result(0),
    ]

    with pytest.raises(
        ValueError,
        match="exceed the order count",
    ):
        await record_fill(
            session=session,
            client_order_id=order.client_order_id,
            exchange_order_id="exchange-order-1",
            exchange_fill_id="exchange-fill-1",
            count=2,
            price_cents=27,
            filled_at=FILL_TIME,
        )

    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_fill_id_collision_is_rejected() -> None:
    order = make_order()
    conflicting_fill = make_fill(
        order,
        price_cents=99,
    )
    session = AsyncMock(spec=AsyncSession)
    session.execute.side_effect = [
        optional_result(order),
        optional_result(conflicting_fill),
    ]

    with pytest.raises(
        RuntimeError,
        match="exchange_fill_id collision",
    ):
        await record_fill(
            session=session,
            client_order_id=order.client_order_id,
            exchange_order_id="exchange-order-1",
            exchange_fill_id="exchange-fill-1",
            count=1,
            price_cents=27,
            filled_at=FILL_TIME,
        )


@pytest.mark.asyncio
async def test_conflicting_exchange_order_id_is_rejected() -> None:
    order = make_order()
    session = AsyncMock(spec=AsyncSession)
    session.execute.return_value = optional_result(order)

    with pytest.raises(
        ValueError,
        match="different exchange_order_id",
    ):
        await record_fill(
            session=session,
            client_order_id=order.client_order_id,
            exchange_order_id="different-exchange-order",
            exchange_fill_id="exchange-fill-1",
            count=1,
            price_cents=27,
            filled_at=FILL_TIME,
        )


@pytest.mark.asyncio
async def test_missing_order_is_rejected() -> None:
    session = AsyncMock(spec=AsyncSession)
    session.execute.return_value = optional_result(None)

    with pytest.raises(KeyError, match="was not found"):
        await record_fill(
            session=session,
            client_order_id="missing-order",
            exchange_order_id="exchange-order-1",
            exchange_fill_id="exchange-fill-1",
            count=1,
            price_cents=27,
            filled_at=FILL_TIME,
        )


@pytest.mark.asyncio
async def test_invalid_fill_is_rejected_before_database_use() -> None:
    session = AsyncMock(spec=AsyncSession)

    with pytest.raises(
        ValueError,
        match="Fill count must be positive",
    ):
        await record_fill(
            session=session,
            client_order_id="client-order-1",
            exchange_order_id="exchange-order-1",
            exchange_fill_id="exchange-fill-1",
            count=0,
            price_cents=27,
            filled_at=FILL_TIME,
        )

    session.execute.assert_not_awaited()