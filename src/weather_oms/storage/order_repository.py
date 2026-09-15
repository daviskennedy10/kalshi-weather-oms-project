import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from weather_oms.events import OrderIntent
from weather_oms.oms.idempotency import key_for
from weather_oms.oms.order_state import (
    OrderState,
    transition,
)
from weather_oms.storage.models import Order


@dataclass(frozen=True, slots=True)
class StoredOrder:
    id: uuid.UUID
    client_order_id: str
    exchange_order_id: str | None
    market_ticker: str
    side: str
    price_cents: int
    count: int
    filled_count: int
    state: OrderState
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class SaveOrderResult:
    order: StoredOrder
    created: bool


async def save_decided_order(
    session: AsyncSession,
    intent: OrderIntent,
    decision_id: str,
) -> SaveOrderResult:
    """Save an order before any submission attempt."""

    client_order_id = key_for(
        intent,
        decision_id,
    ).value

    market_ticker = intent.market_ticker.strip().upper()
    side = intent.side.strip().lower()

    statement = (
        insert(Order)
        .values(
            client_order_id=client_order_id,
            exchange_order_id=None,
            market_ticker=market_ticker,
            side=side,
            price_cents=intent.price_cents,
            count=intent.count,
            filled_count=0,
            state=OrderState.DECIDED.value,
        )
        .on_conflict_do_nothing(
            index_elements=[Order.client_order_id],
        )
        .returning(Order)
    )

    result = await session.execute(statement)
    inserted = result.scalar_one_or_none()

    if inserted is not None:
        return SaveOrderResult(
            order=_to_stored_order(inserted),
            created=True,
        )

    existing = await _load_order(
        session,
        client_order_id,
    )

    if existing is None:
        raise RuntimeError(
            "Duplicate order was detected but could not be loaded."
        )

    _verify_same_order(
        existing=existing,
        market_ticker=market_ticker,
        side=side,
        price_cents=intent.price_cents,
        count=intent.count,
    )

    return SaveOrderResult(
        order=_to_stored_order(existing),
        created=False,
    )


async def load_order_by_client_id(
    session: AsyncSession,
    client_order_id: str,
) -> StoredOrder | None:
    if not client_order_id:
        raise ValueError("client_order_id cannot be empty.")

    order = await _load_order(
        session,
        client_order_id,
    )

    if order is None:
        return None

    return _to_stored_order(order)


async def load_orders_for_event(
    session: AsyncSession,
    event_ticker: str,
) -> tuple[StoredOrder, ...]:
    """Load local orders belonging to one Kalshi event."""

    normalized_event = event_ticker.strip().upper()

    if not normalized_event:
        raise ValueError("event_ticker cannot be empty.")

    market_prefix = f"{normalized_event}-"

    statement = (
        select(Order)
        .where(
            Order.market_ticker.startswith(
                market_prefix,
                autoescape=True,
            )
        )
        .order_by(Order.client_order_id)
    )

    result = await session.execute(statement)
    orders = result.scalars().all()

    return tuple(
        _to_stored_order(order)
        for order in orders
    )
    
async def transition_stored_order(
    session: AsyncSession,
    client_order_id: str,
    target: OrderState,
) -> StoredOrder:
    """Lock an order and apply one legal state transition."""

    if not client_order_id:
        raise ValueError("client_order_id cannot be empty.")

    statement = (
        select(Order)
        .where(
            Order.client_order_id == client_order_id
        )
        .with_for_update()
    )

    result = await session.execute(statement)
    order = result.scalar_one_or_none()

    if order is None:
        raise KeyError(
            f"Order {client_order_id!r} was not found."
        )

    current = OrderState(order.state)
    new_state = transition(current, target)

    if new_state != current:
        order.state = new_state.value
        await session.flush()

    return _to_stored_order(order)

async def record_exchange_acknowledgement(
    session: AsyncSession,
    client_order_id: str,
    exchange_order_id: str,
    filled_count: int,
) -> StoredOrder:
    """Record an exchange response without submitting an order."""

    if not client_order_id:
        raise ValueError("client_order_id cannot be empty.")

    if not exchange_order_id:
        raise ValueError("exchange_order_id cannot be empty.")

    statement = (
        select(Order)
        .where(
            Order.client_order_id == client_order_id
        )
        .with_for_update()
    )

    result = await session.execute(statement)
    order = result.scalar_one_or_none()

    if order is None:
        raise KeyError(
            f"Order {client_order_id!r} was not found."
        )

    if not 0 <= filled_count <= order.count:
        raise ValueError(
            "filled_count must be between zero and "
            "the order count."
        )

    if filled_count < order.filled_count:
        raise ValueError(
            "filled_count cannot move backward."
        )

    if (
        order.exchange_order_id is not None
        and order.exchange_order_id != exchange_order_id
    ):
        raise ValueError(
            "Order already has a different exchange_order_id."
        )

    if filled_count == 0:
        target_state = OrderState.OPEN
    elif filled_count < order.count:
        target_state = OrderState.PARTIALLY_FILLED
    else:
        target_state = OrderState.FILLED

    current_state = OrderState(order.state)
    new_state = transition(
        current_state,
        target_state,
    )

    changed = (
        order.exchange_order_id != exchange_order_id
        or order.filled_count != filled_count
        or current_state != new_state
    )

    if changed:
        order.exchange_order_id = exchange_order_id
        order.filled_count = filled_count
        order.state = new_state.value
        await session.flush()

    return _to_stored_order(order)

async def _load_order(
    session: AsyncSession,
    client_order_id: str,
) -> Order | None:
    statement = select(Order).where(
        Order.client_order_id == client_order_id
    )

    result = await session.execute(statement)
    return result.scalar_one_or_none()


def _verify_same_order(
    existing: Order,
    market_ticker: str,
    side: str,
    price_cents: int,
    count: int,
) -> None:
    existing_fields = (
        existing.market_ticker,
        existing.side,
        existing.price_cents,
        existing.count,
    )
    requested_fields = (
        market_ticker,
        side,
        price_cents,
        count,
    )

    if existing_fields != requested_fields:
        raise RuntimeError(
            "Idempotency-key collision: stored order does not "
            "match the requested order."
        )


def _to_stored_order(order: Order) -> StoredOrder:
    return StoredOrder(
        id=order.id,
        client_order_id=order.client_order_id,
        exchange_order_id=order.exchange_order_id,
        market_ticker=order.market_ticker,
        side=order.side,
        price_cents=order.price_cents,
        count=order.count,
        filled_count=order.filled_count,
        state=OrderState(order.state),
        created_at=order.created_at,
        updated_at=order.updated_at,
    )