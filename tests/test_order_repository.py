import uuid
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from weather_oms.events import OrderIntent
from weather_oms.oms.idempotency import key_for
from weather_oms.oms.order_state import (
    InvalidOrderTransition,
    OrderState,
)
from weather_oms.storage.models import Order
from weather_oms.storage.order_repository import (
    load_order_by_client_id,
    load_orders_for_event,
    record_exchange_acknowledgement,
    save_decided_order,
    transition_stored_order,
)


def make_intent() -> OrderIntent:
    return OrderIntent(
        market_ticker="KXHIGHNY-26SEP15-T85",
        side="yes",
        price_cents=27,
        count=1,
        model_probability=Decimal("0.47"),
        event_received_time=datetime(
            2026,
            9,
            14,
            15,
            50,
            tzinfo=UTC,
        ),
    )


def make_order(
    state: OrderState = OrderState.DECIDED,
) -> Order:
    intent = make_intent()

    return Order(
        id=uuid.uuid4(),
        client_order_id=key_for(
            intent,
            "decision-1",
        ).value,
        exchange_order_id=None,
        market_ticker=intent.market_ticker,
        side=intent.side,
        price_cents=intent.price_cents,
        count=intent.count,
        filled_count=0,
        state=state.value,
        created_at=datetime(
            2026,
            9,
            14,
            15,
            50,
            tzinfo=UTC,
        ),
        updated_at=datetime(
            2026,
            9,
            14,
            15,
            50,
            tzinfo=UTC,
        ),
    )


def make_result(value: Order | None) -> Mock:
    result = Mock()
    result.scalar_one_or_none.return_value = value
    return result


@pytest.mark.asyncio
async def test_saves_new_decided_order() -> None:
    session = AsyncMock(spec=AsyncSession)
    order = make_order()
    session.execute.return_value = make_result(order)

    result = await save_decided_order(
        session=session,
        intent=make_intent(),
        decision_id="decision-1",
    )

    assert result.created is True
    assert result.order.state == OrderState.DECIDED
    assert result.order.filled_count == 0
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_exact_retry_returns_existing_order() -> None:
    session = AsyncMock(spec=AsyncSession)
    order = make_order()

    session.execute.side_effect = [
        make_result(None),
        make_result(order),
    ]

    result = await save_decided_order(
        session=session,
        intent=make_intent(),
        decision_id="decision-1",
    )

    assert result.created is False
    assert result.order.client_order_id == order.client_order_id
    assert session.execute.await_count == 2


@pytest.mark.asyncio
async def test_idempotency_collision_is_rejected() -> None:
    session = AsyncMock(spec=AsyncSession)
    conflicting_order = make_order()
    conflicting_order.price_cents = 99

    session.execute.side_effect = [
        make_result(None),
        make_result(conflicting_order),
    ]

    with pytest.raises(
        RuntimeError,
        match="Idempotency-key collision",
    ):
        await save_decided_order(
            session=session,
            intent=make_intent(),
            decision_id="decision-1",
        )


@pytest.mark.asyncio
async def test_duplicate_that_cannot_be_loaded_is_error() -> None:
    session = AsyncMock(spec=AsyncSession)
    session.execute.side_effect = [
        make_result(None),
        make_result(None),
    ]

    with pytest.raises(
        RuntimeError,
        match="could not be loaded",
    ):
        await save_decided_order(
            session=session,
            intent=make_intent(),
            decision_id="decision-1",
        )


@pytest.mark.asyncio
async def test_loads_order_by_client_id() -> None:
    session = AsyncMock(spec=AsyncSession)
    order = make_order()
    session.execute.return_value = make_result(order)

    stored = await load_order_by_client_id(
        session=session,
        client_order_id=order.client_order_id,
    )

    assert stored is not None
    assert stored.client_order_id == order.client_order_id
    assert stored.state == OrderState.DECIDED


@pytest.mark.asyncio
async def test_missing_order_returns_none() -> None:
    session = AsyncMock(spec=AsyncSession)
    session.execute.return_value = make_result(None)

    stored = await load_order_by_client_id(
        session=session,
        client_order_id="missing-order",
    )

    assert stored is None


@pytest.mark.asyncio
async def test_legal_transition_updates_stored_order() -> None:
    session = AsyncMock(spec=AsyncSession)
    order = make_order(OrderState.DECIDED)
    session.execute.return_value = make_result(order)

    stored = await transition_stored_order(
        session=session,
        client_order_id=order.client_order_id,
        target=OrderState.SUBMITTING,
    )

    assert stored.state == OrderState.SUBMITTING
    assert order.state == OrderState.SUBMITTING.value
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_illegal_transition_does_not_update_order() -> None:
    session = AsyncMock(spec=AsyncSession)
    order = make_order(OrderState.DECIDED)
    session.execute.return_value = make_result(order)

    with pytest.raises(InvalidOrderTransition):
        await transition_stored_order(
            session=session,
            client_order_id=order.client_order_id,
            target=OrderState.FILLED,
        )

    assert order.state == OrderState.DECIDED.value
    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_repeated_state_does_not_write_again() -> None:
    session = AsyncMock(spec=AsyncSession)
    order = make_order(OrderState.OPEN)
    session.execute.return_value = make_result(order)

    stored = await transition_stored_order(
        session=session,
        client_order_id=order.client_order_id,
        target=OrderState.OPEN,
    )

    assert stored.state == OrderState.OPEN
    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_transition_rejects_missing_order() -> None:
    session = AsyncMock(spec=AsyncSession)
    session.execute.return_value = make_result(None)

    with pytest.raises(KeyError, match="was not found"):
        await transition_stored_order(
            session=session,
            client_order_id="missing-order",
            target=OrderState.SUBMITTING,
        )


@pytest.mark.asyncio
async def test_rejects_empty_client_order_id() -> None:
    session = AsyncMock(spec=AsyncSession)

    with pytest.raises(
        ValueError,
        match="client_order_id cannot be empty",
    ):
        await load_order_by_client_id(
            session=session,
            client_order_id="",
        )

    session.execute.assert_not_awaited()


def test_changed_order_has_different_client_id() -> None:
    original = make_intent()
    changed = replace(
        original,
        price_cents=28,
    )

    assert (
        key_for(original, "decision-1")
        != key_for(changed, "decision-1")
    )

@pytest.mark.asyncio
async def test_acknowledgement_opens_submitting_order() -> None:
    session = AsyncMock(spec=AsyncSession)
    order = make_order(OrderState.SUBMITTING)
    session.execute.return_value = make_result(order)

    stored = await record_exchange_acknowledgement(
        session=session,
        client_order_id=order.client_order_id,
        exchange_order_id="exchange-1",
        filled_count=0,
    )

    assert stored.exchange_order_id == "exchange-1"
    assert stored.state == OrderState.OPEN
    assert stored.filled_count == 0
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_acknowledgement_records_partial_fill() -> None:
    session = AsyncMock(spec=AsyncSession)
    order = make_order(OrderState.SUBMITTING)
    order.count = 2
    session.execute.return_value = make_result(order)

    stored = await record_exchange_acknowledgement(
        session=session,
        client_order_id=order.client_order_id,
        exchange_order_id="exchange-1",
        filled_count=1,
    )

    assert stored.state == OrderState.PARTIALLY_FILLED
    assert stored.filled_count == 1


@pytest.mark.asyncio
async def test_acknowledgement_records_full_fill() -> None:
    session = AsyncMock(spec=AsyncSession)
    order = make_order(OrderState.SUBMITTING)
    session.execute.return_value = make_result(order)

    stored = await record_exchange_acknowledgement(
        session=session,
        client_order_id=order.client_order_id,
        exchange_order_id="exchange-1",
        filled_count=1,
    )

    assert stored.state == OrderState.FILLED
    assert stored.filled_count == 1


@pytest.mark.asyncio
async def test_repeated_acknowledgement_is_idempotent() -> None:
    session = AsyncMock(spec=AsyncSession)
    order = make_order(OrderState.OPEN)
    order.exchange_order_id = "exchange-1"
    session.execute.return_value = make_result(order)

    stored = await record_exchange_acknowledgement(
        session=session,
        client_order_id=order.client_order_id,
        exchange_order_id="exchange-1",
        filled_count=0,
    )

    assert stored.state == OrderState.OPEN
    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_conflicting_exchange_id_is_rejected() -> None:
    session = AsyncMock(spec=AsyncSession)
    order = make_order(OrderState.OPEN)
    order.exchange_order_id = "exchange-1"
    session.execute.return_value = make_result(order)

    with pytest.raises(
        ValueError,
        match="different exchange_order_id",
    ):
        await record_exchange_acknowledgement(
            session=session,
            client_order_id=order.client_order_id,
            exchange_order_id="exchange-2",
            filled_count=0,
        )

    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_filled_count_cannot_move_backward() -> None:
    session = AsyncMock(spec=AsyncSession)
    order = make_order(OrderState.PARTIALLY_FILLED)
    order.count = 3
    order.filled_count = 2
    order.exchange_order_id = "exchange-1"
    session.execute.return_value = make_result(order)

    with pytest.raises(
        ValueError,
        match="cannot move backward",
    ):
        await record_exchange_acknowledgement(
            session=session,
            client_order_id=order.client_order_id,
            exchange_order_id="exchange-1",
            filled_count=1,
        )


@pytest.mark.asyncio
async def test_filled_count_cannot_exceed_order_count() -> None:
    session = AsyncMock(spec=AsyncSession)
    order = make_order(OrderState.SUBMITTING)
    session.execute.return_value = make_result(order)

    with pytest.raises(
        ValueError,
        match="between zero and the order count",
    ):
        await record_exchange_acknowledgement(
            session=session,
            client_order_id=order.client_order_id,
            exchange_order_id="exchange-1",
            filled_count=2,
        )


@pytest.mark.asyncio
async def test_unknown_order_must_reconcile_first() -> None:
    session = AsyncMock(spec=AsyncSession)
    order = make_order(OrderState.UNKNOWN)
    session.execute.return_value = make_result(order)

    with pytest.raises(InvalidOrderTransition):
        await record_exchange_acknowledgement(
            session=session,
            client_order_id=order.client_order_id,
            exchange_order_id="exchange-1",
            filled_count=0,
        )


@pytest.mark.asyncio
async def test_reconciling_order_accepts_exchange_record() -> None:
    session = AsyncMock(spec=AsyncSession)
    order = make_order(OrderState.RECONCILING)
    session.execute.return_value = make_result(order)

    stored = await record_exchange_acknowledgement(
        session=session,
        client_order_id=order.client_order_id,
        exchange_order_id="exchange-1",
        filled_count=0,
    )

    assert stored.state == OrderState.OPEN
    assert stored.exchange_order_id == "exchange-1"


@pytest.mark.asyncio
async def test_acknowledgement_rejects_missing_order() -> None:
    session = AsyncMock(spec=AsyncSession)
    session.execute.return_value = make_result(None)

    with pytest.raises(KeyError, match="was not found"):
        await record_exchange_acknowledgement(
            session=session,
            client_order_id="missing-order",
            exchange_order_id="exchange-1",
            filled_count=0,
        )

def make_multiple_result(
    orders: list[Order],
) -> Mock:
    scalar_result = Mock()
    scalar_result.all.return_value = orders

    result = Mock()
    result.scalars.return_value = scalar_result
    return result


@pytest.mark.asyncio
async def test_loads_orders_for_event() -> None:
    session = AsyncMock(spec=AsyncSession)
    first = make_order()
    second = make_order(OrderState.OPEN)
    second.id = uuid.uuid4()
    second.client_order_id = "oms-second"

    session.execute.return_value = make_multiple_result(
        [first, second]
    )

    orders = await load_orders_for_event(
        session=session,
        event_ticker="kxhighny-26sep15",
    )

    assert len(orders) == 2
    assert orders[0].client_order_id == first.client_order_id
    assert orders[1].client_order_id == "oms-second"


@pytest.mark.asyncio
async def test_load_orders_for_event_can_be_empty() -> None:
    session = AsyncMock(spec=AsyncSession)
    session.execute.return_value = make_multiple_result([])

    orders = await load_orders_for_event(
        session=session,
        event_ticker="KXHIGHNY-26SEP15",
    )

    assert orders == ()


@pytest.mark.asyncio
async def test_rejects_empty_event_ticker() -> None:
    session = AsyncMock(spec=AsyncSession)

    with pytest.raises(
        ValueError,
        match="event_ticker cannot be empty",
    ):
        await load_orders_for_event(
            session=session,
            event_ticker=" ",
        )

    session.execute.assert_not_awaited()