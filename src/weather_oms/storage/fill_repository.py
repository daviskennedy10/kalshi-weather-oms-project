import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from weather_oms.oms.order_state import (
    OrderState,
    transition,
)
from weather_oms.storage.models import Fill, Order


@dataclass(frozen=True, slots=True)
class StoredFill:
    id: uuid.UUID
    exchange_fill_id: str
    order_id: uuid.UUID
    count: int
    price_cents: int
    filled_at: datetime


@dataclass(frozen=True, slots=True)
class RecordFillResult:
    fill: StoredFill
    created: bool
    total_filled_count: int
    order_state: OrderState


async def record_fill(
    session: AsyncSession,
    client_order_id: str,
    exchange_order_id: str,
    exchange_fill_id: str,
    count: int,
    price_cents: int,
    filled_at: datetime,
) -> RecordFillResult:
    """Save one fill exactly once and update its order."""

    _validate_fill(
        client_order_id=client_order_id,
        exchange_order_id=exchange_order_id,
        exchange_fill_id=exchange_fill_id,
        count=count,
        price_cents=price_cents,
        filled_at=filled_at,
    )

    order_statement = (
        select(Order)
        .where(
            Order.client_order_id == client_order_id
        )
        .with_for_update()
    )

    order_result = await session.execute(
        order_statement
    )
    order = order_result.scalar_one_or_none()

    if order is None:
        raise KeyError(
            f"Order {client_order_id!r} was not found."
        )

    if (
        order.exchange_order_id is not None
        and order.exchange_order_id != exchange_order_id
    ):
        raise ValueError(
            "Order already has a different exchange_order_id."
        )

    existing = await _load_fill(
        session,
        exchange_fill_id,
    )

    if existing is not None:
        _verify_same_fill(
            existing=existing,
            order_id=order.id,
            count=count,
            price_cents=price_cents,
            filled_at=filled_at,
        )

        return RecordFillResult(
            fill=_to_stored_fill(existing),
            created=False,
            total_filled_count=order.filled_count,
            order_state=OrderState(order.state),
        )

    total_statement = select(
        func.coalesce(func.sum(Fill.count), 0)
    ).where(
        Fill.order_id == order.id
    )

    total_result = await session.execute(
        total_statement
    )
    recorded_fill_count = int(
        total_result.scalar_one()
    )

    projected_fill_count = max(
        order.filled_count,
        recorded_fill_count + count,
    )

    if projected_fill_count > order.count:
        raise ValueError(
            "Fill would exceed the order count."
        )

    target_state = (
        OrderState.FILLED
        if projected_fill_count == order.count
        else OrderState.PARTIALLY_FILLED
    )

    new_state = transition(
        OrderState(order.state),
        target_state,
    )

    normalized_filled_at = filled_at.astimezone(UTC)

    fill_statement = (
        insert(Fill)
        .values(
            exchange_fill_id=exchange_fill_id,
            order_id=order.id,
            count=count,
            price_cents=price_cents,
            filled_at=normalized_filled_at,
        )
        .on_conflict_do_nothing(
            index_elements=[Fill.exchange_fill_id],
        )
        .returning(Fill)
    )

    fill_result = await session.execute(
        fill_statement
    )
    inserted_fill = (
        fill_result.scalar_one_or_none()
    )

    if inserted_fill is None:
        conflicting_fill = await _load_fill(
            session,
            exchange_fill_id,
        )

        if conflicting_fill is None:
            raise RuntimeError(
                "Duplicate fill was detected but could not "
                "be loaded."
            )

        _verify_same_fill(
            existing=conflicting_fill,
            order_id=order.id,
            count=count,
            price_cents=price_cents,
            filled_at=filled_at,
        )

        return RecordFillResult(
            fill=_to_stored_fill(conflicting_fill),
            created=False,
            total_filled_count=order.filled_count,
            order_state=OrderState(order.state),
        )

    order.exchange_order_id = exchange_order_id
    order.filled_count = projected_fill_count
    order.state = new_state.value

    await session.flush()

    return RecordFillResult(
        fill=_to_stored_fill(inserted_fill),
        created=True,
        total_filled_count=projected_fill_count,
        order_state=new_state,
    )


async def _load_fill(
    session: AsyncSession,
    exchange_fill_id: str,
) -> Fill | None:
    statement = select(Fill).where(
        Fill.exchange_fill_id == exchange_fill_id
    )

    result = await session.execute(statement)
    return result.scalar_one_or_none()


def _validate_fill(
    client_order_id: str,
    exchange_order_id: str,
    exchange_fill_id: str,
    count: int,
    price_cents: int,
    filled_at: datetime,
) -> None:
    identifiers = (
        client_order_id,
        exchange_order_id,
        exchange_fill_id,
    )

    if any(not identifier for identifier in identifiers):
        raise ValueError("Fill identifiers cannot be empty.")

    if count <= 0:
        raise ValueError("Fill count must be positive.")

    if not 0 <= price_cents <= 100:
        raise ValueError(
            "Fill price must be between 0 and 100 cents."
        )

    if filled_at.tzinfo is None:
        raise ValueError(
            "filled_at must include a timezone."
        )


def _verify_same_fill(
    existing: Fill,
    order_id: uuid.UUID,
    count: int,
    price_cents: int,
    filled_at: datetime,
) -> None:
    normalized_filled_at = filled_at.astimezone(UTC)

    existing_fields = (
        existing.order_id,
        existing.count,
        existing.price_cents,
        existing.filled_at,
    )
    received_fields = (
        order_id,
        count,
        price_cents,
        normalized_filled_at,
    )

    if existing_fields != received_fields:
        raise RuntimeError(
            "exchange_fill_id collision: stored fill does "
            "not match the received fill."
        )


def _to_stored_fill(fill: Fill) -> StoredFill:
    return StoredFill(
        id=fill.id,
        exchange_fill_id=fill.exchange_fill_id,
        order_id=fill.order_id,
        count=fill.count,
        price_cents=fill.price_cents,
        filled_at=fill.filled_at,
    )