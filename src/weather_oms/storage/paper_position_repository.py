from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal, cast

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from weather_oms.execution.paper_settlement import (
    calculate_paper_settlement,
)
from weather_oms.storage.models import PaperPosition

PaperSide = Literal["yes", "no"]
PaperPositionStatus = Literal["open", "settled"]
SettlementWriteResult = Literal[
    "settled",
    "already_settled",
    "not_found",
]


@dataclass(frozen=True, slots=True)
class NewPaperPosition:
    paper_order_id: str
    event_ticker: str
    market_ticker: str
    target_date: date
    side: PaperSide
    contracts: int
    entry_price_cents: int
    fee_dollars: Decimal
    opened_at: datetime


@dataclass(frozen=True, slots=True)
class StoredPaperPosition:
    paper_order_id: str
    event_ticker: str
    market_ticker: str
    target_date: date
    side: PaperSide
    contracts: int
    entry_price_cents: int
    fee_dollars: Decimal
    status: PaperPositionStatus
    opened_at: datetime
    settlement_result: PaperSide | None
    payout_dollars: Decimal | None
    realized_pnl_dollars: Decimal | None
    settled_at: datetime | None

    @property
    def total_cost_dollars(self) -> Decimal:
        contract_cost = (
            Decimal(self.entry_price_cents)
            / Decimal(100)
            * self.contracts
        )
        return contract_cost + self.fee_dollars

    @property
    def risk_per_contract_dollars(self) -> Decimal:
        return self.total_cost_dollars / self.contracts


async def save_open_paper_position(
    session: AsyncSession,
    position: NewPaperPosition,
) -> bool:
    """Save a pretend position once."""

    _validate_new_position(position)

    statement = (
        insert(PaperPosition)
        .values(
            paper_order_id=position.paper_order_id,
            event_ticker=position.event_ticker,
            market_ticker=position.market_ticker,
            target_date=position.target_date,
            side=position.side,
            contracts=position.contracts,
            entry_price_cents=position.entry_price_cents,
            fee_dollars=position.fee_dollars,
            status="open",
            opened_at=position.opened_at.astimezone(UTC),
        )
        .on_conflict_do_nothing(
            index_elements=[PaperPosition.paper_order_id],
        )
        .returning(PaperPosition.id)
    )

    result = await session.execute(statement)
    inserted_id = result.scalar_one_or_none()

    return inserted_id is not None


async def load_open_paper_positions_for_event(
    session: AsyncSession,
    event_ticker: str,
) -> tuple[StoredPaperPosition, ...]:
    if not event_ticker:
        raise ValueError("event_ticker cannot be empty.")

    statement = (
        select(PaperPosition)
        .where(
            PaperPosition.event_ticker == event_ticker,
            PaperPosition.status == "open",
        )
        .order_by(
            PaperPosition.opened_at,
            PaperPosition.paper_order_id,
        )
    )

    result = await session.execute(statement)
    rows = result.scalars().all()

    return tuple(_to_stored_position(row) for row in rows)


async def load_paper_positions_for_date(
    session: AsyncSession,
    target_date: date,
) -> tuple[StoredPaperPosition, ...]:
    statement = (
        select(PaperPosition)
        .where(PaperPosition.target_date == target_date)
        .order_by(
            PaperPosition.opened_at,
            PaperPosition.paper_order_id,
        )
    )

    result = await session.execute(statement)
    rows = result.scalars().all()

    return tuple(_to_stored_position(row) for row in rows)


def _validate_new_position(position: NewPaperPosition) -> None:
    identifiers = (
        position.paper_order_id,
        position.event_ticker,
        position.market_ticker,
    )

    if any(not identifier for identifier in identifiers):
        raise ValueError("Paper-position identifiers cannot be empty.")

    if position.side not in ("yes", "no"):
        raise ValueError("Paper-position side must be yes or no.")

    if position.contracts <= 0:
        raise ValueError("Paper-position contracts must be positive.")

    if not 0 <= position.entry_price_cents <= 100:
        raise ValueError(
            "Paper-position price must be between 0 and 100 cents."
        )

    if position.fee_dollars < 0:
        raise ValueError("Paper-position fee cannot be negative.")

    if position.opened_at.tzinfo is None:
        raise ValueError("opened_at must include a timezone.")


def _to_stored_position(
    row: PaperPosition,
) -> StoredPaperPosition:
    settlement_result = (
        None
        if row.settlement_result is None
        else cast(PaperSide, row.settlement_result)
    )

    return StoredPaperPosition(
        paper_order_id=row.paper_order_id,
        event_ticker=row.event_ticker,
        market_ticker=row.market_ticker,
        target_date=row.target_date,
        side=cast(PaperSide, row.side),
        contracts=row.contracts,
        entry_price_cents=row.entry_price_cents,
        fee_dollars=row.fee_dollars,
        status=cast(PaperPositionStatus, row.status),
        opened_at=row.opened_at,
        settlement_result=settlement_result,
        payout_dollars=row.payout_dollars,
        realized_pnl_dollars=row.realized_pnl_dollars,
        settled_at=row.settled_at,
    )

async def settle_paper_position(
    session: AsyncSession,
    paper_order_id: str,
    settlement_result: PaperSide,
    settled_at: datetime,
) -> SettlementWriteResult:
    """Settle one paper position safely and idempotently."""

    if not paper_order_id:
        raise ValueError("paper_order_id cannot be empty.")

    if settlement_result not in ("yes", "no"):
        raise ValueError(
            "settlement_result must be yes or no."
        )

    if settled_at.tzinfo is None:
        raise ValueError(
            "settled_at must include a timezone."
        )

    statement = (
        select(PaperPosition)
        .where(
            PaperPosition.paper_order_id
            == paper_order_id
        )
        .with_for_update()
    )

    result = await session.execute(statement)
    position = result.scalar_one_or_none()

    if position is None:
        return "not_found"

    if position.status == "settled":
        if position.settlement_result != settlement_result:
            raise ValueError(
                "Paper position already has a different "
                "settlement result."
            )

        return "already_settled"

    if position.status != "open":
        raise ValueError(
            f"Unsupported paper-position status: "
            f"{position.status}."
        )

    calculation = calculate_paper_settlement(
        position_side=cast(PaperSide, position.side),
        settlement_result=settlement_result,
        contracts=position.contracts,
        entry_price_cents=position.entry_price_cents,
        fee_dollars=position.fee_dollars,
    )

    position.status = "settled"
    position.settlement_result = settlement_result
    position.payout_dollars = calculation.payout_dollars
    position.realized_pnl_dollars = (
        calculation.realized_pnl_dollars
    )
    position.settled_at = settled_at.astimezone(UTC)

    await session.flush()

    return "settled"