import uuid
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from weather_oms.storage.models import PaperPosition
from weather_oms.storage.paper_position_repository import (
    NewPaperPosition,
    PaperSide,
    StoredPaperPosition,
    load_open_paper_positions_for_event,
    load_paper_positions_for_date,
    save_open_paper_position,
    settle_paper_position,
)


def make_new_position() -> NewPaperPosition:
    return NewPaperPosition(
        paper_order_id="paper-order-1",
        event_ticker="KXHIGHNY-26SEP10",
        market_ticker="KXHIGHNY-26SEP10-T85",
        target_date=date(2026, 9, 10),
        side="yes",
        contracts=1,
        entry_price_cents=27,
        fee_dollars=Decimal("0.0138"),
        opened_at=datetime(2026, 9, 9, 15, 50, tzinfo=UTC),
    )


def make_database_position() -> PaperPosition:
    return PaperPosition(
        paper_order_id="paper-order-1",
        event_ticker="KXHIGHNY-26SEP10",
        market_ticker="KXHIGHNY-26SEP10-T85",
        target_date=date(2026, 9, 10),
        side="yes",
        contracts=1,
        entry_price_cents=27,
        fee_dollars=Decimal("0.0138"),
        status="open",
        opened_at=datetime(2026, 9, 9, 15, 50, tzinfo=UTC),
        settlement_result=None,
        payout_dollars=None,
        realized_pnl_dollars=None,
        settled_at=None,
    )


def make_stored_position() -> StoredPaperPosition:
    return StoredPaperPosition(
        paper_order_id="paper-order-1",
        event_ticker="KXHIGHNY-26SEP10",
        market_ticker="KXHIGHNY-26SEP10-T85",
        target_date=date(2026, 9, 10),
        side="yes",
        contracts=1,
        entry_price_cents=27,
        fee_dollars=Decimal("0.0138"),
        status="open",
        opened_at=datetime(2026, 9, 9, 15, 50, tzinfo=UTC),
        settlement_result=None,
        payout_dollars=None,
        realized_pnl_dollars=None,
        settled_at=None,
    )


def make_session_with_rows(
    rows: list[PaperPosition],
) -> AsyncMock:
    session = AsyncMock(spec=AsyncSession)
    result = Mock()
    result.scalars.return_value.all.return_value = rows
    session.execute.return_value = result
    return session


def test_stored_position_calculates_total_cost() -> None:
    position = make_stored_position()

    assert position.total_cost_dollars == Decimal("0.2838")


def test_stored_position_calculates_risk_per_contract() -> None:
    position = replace(
        make_stored_position(),
        contracts=2,
        entry_price_cents=40,
        fee_dollars=Decimal("0.02"),
    )

    assert position.total_cost_dollars == Decimal("0.82")
    assert position.risk_per_contract_dollars == Decimal("0.41")


@pytest.mark.asyncio
async def test_saving_new_position_returns_true() -> None:
    session = AsyncMock(spec=AsyncSession)
    result = Mock()
    result.scalar_one_or_none.return_value = uuid.uuid4()
    session.execute.return_value = result

    saved = await save_open_paper_position(
        session,
        make_new_position(),
    )

    assert saved is True
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_duplicate_position_returns_false() -> None:
    session = AsyncMock(spec=AsyncSession)
    result = Mock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result

    saved = await save_open_paper_position(
        session,
        make_new_position(),
    )

    assert saved is False


@pytest.mark.asyncio
async def test_loads_open_positions_for_event() -> None:
    session = make_session_with_rows(
        [make_database_position()]
    )

    positions = await load_open_paper_positions_for_event(
        session,
        "KXHIGHNY-26SEP10",
    )

    assert len(positions) == 1
    assert positions[0].paper_order_id == "paper-order-1"
    assert positions[0].side == "yes"
    assert positions[0].status == "open"
    assert positions[0].total_cost_dollars == Decimal("0.2838")


@pytest.mark.asyncio
async def test_loads_positions_for_date() -> None:
    session = make_session_with_rows(
        [make_database_position()]
    )

    positions = await load_paper_positions_for_date(
        session,
        date(2026, 9, 10),
    )

    assert len(positions) == 1
    assert positions[0].target_date == date(2026, 9, 10)


@pytest.mark.asyncio
async def test_rejects_empty_event_ticker() -> None:
    session = AsyncMock(spec=AsyncSession)

    with pytest.raises(
        ValueError,
        match="event_ticker cannot be empty",
    ):
        await load_open_paper_positions_for_event(
            session,
            "",
        )


@pytest.mark.asyncio
async def test_rejects_empty_identifiers() -> None:
    session = AsyncMock(spec=AsyncSession)
    position = replace(
        make_new_position(),
        paper_order_id="",
    )

    with pytest.raises(
        ValueError,
        match="identifiers cannot be empty",
    ):
        await save_open_paper_position(session, position)

    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_rejects_invalid_side() -> None:
    session = AsyncMock(spec=AsyncSession)
    position = replace(
        make_new_position(),
        side=cast(PaperSide, "maybe"),
    )

    with pytest.raises(
        ValueError,
        match="side must be yes or no",
    ):
        await save_open_paper_position(session, position)


@pytest.mark.asyncio
async def test_rejects_nonpositive_contracts() -> None:
    session = AsyncMock(spec=AsyncSession)
    position = replace(
        make_new_position(),
        contracts=0,
    )

    with pytest.raises(
        ValueError,
        match="contracts must be positive",
    ):
        await save_open_paper_position(session, position)


@pytest.mark.asyncio
async def test_rejects_invalid_price() -> None:
    session = AsyncMock(spec=AsyncSession)
    position = replace(
        make_new_position(),
        entry_price_cents=101,
    )

    with pytest.raises(
        ValueError,
        match="between 0 and 100 cents",
    ):
        await save_open_paper_position(session, position)


@pytest.mark.asyncio
async def test_rejects_negative_fee() -> None:
    session = AsyncMock(spec=AsyncSession)
    position = replace(
        make_new_position(),
        fee_dollars=Decimal("-0.01"),
    )

    with pytest.raises(
        ValueError,
        match="fee cannot be negative",
    ):
        await save_open_paper_position(session, position)


@pytest.mark.asyncio
async def test_rejects_timezone_naive_opened_at() -> None:
    session = AsyncMock(spec=AsyncSession)
    position = replace(
        make_new_position(),
        opened_at=datetime(
            2026,
            9,
            9,
            15,
            50,
            tzinfo=UTC,
        ).replace(tzinfo=None),
    )

    with pytest.raises(
        ValueError,
        match="opened_at must include a timezone",
    ):
        await save_open_paper_position(session, position)


def make_settlement_session(
    position: PaperPosition | None,
) -> AsyncMock:
    session = AsyncMock(spec=AsyncSession)
    result = Mock()
    result.scalar_one_or_none.return_value = position
    session.execute.return_value = result
    return session


@pytest.mark.asyncio
async def test_settles_winning_paper_position() -> None:
    position = make_database_position()
    session = make_settlement_session(position)
    settled_at = datetime(
        2026,
        9,
        10,
        23,
        0,
        tzinfo=UTC,
    )

    result = await settle_paper_position(
        session=session,
        paper_order_id=position.paper_order_id,
        settlement_result="yes",
        settled_at=settled_at,
    )

    assert result == "settled"
    assert position.status == "settled"
    assert position.settlement_result == "yes"
    assert position.payout_dollars == Decimal(1)
    assert position.realized_pnl_dollars == Decimal("0.7162")
    assert position.settled_at == settled_at
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_settles_losing_paper_position() -> None:
    position = make_database_position()
    session = make_settlement_session(position)

    result = await settle_paper_position(
        session=session,
        paper_order_id=position.paper_order_id,
        settlement_result="no",
        settled_at=datetime(
            2026,
            9,
            10,
            23,
            0,
            tzinfo=UTC,
        ),
    )

    assert result == "settled"
    assert position.payout_dollars == Decimal(0)
    assert position.realized_pnl_dollars == Decimal("-0.2838")


@pytest.mark.asyncio
async def test_missing_position_returns_not_found() -> None:
    session = make_settlement_session(None)

    result = await settle_paper_position(
        session=session,
        paper_order_id="missing-order",
        settlement_result="yes",
        settled_at=datetime.now(UTC),
    )

    assert result == "not_found"
    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_repeated_same_settlement_is_idempotent() -> None:
    position = make_database_position()
    position.status = "settled"
    position.settlement_result = "yes"
    position.payout_dollars = Decimal(1)
    position.realized_pnl_dollars = Decimal("0.7162")
    position.settled_at = datetime(
        2026,
        9,
        10,
        23,
        0,
        tzinfo=UTC,
    )
    session = make_settlement_session(position)

    result = await settle_paper_position(
        session=session,
        paper_order_id=position.paper_order_id,
        settlement_result="yes",
        settled_at=datetime.now(UTC),
    )

    assert result == "already_settled"
    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_conflicting_settlement_is_rejected() -> None:
    position = make_database_position()
    position.status = "settled"
    position.settlement_result = "yes"
    position.payout_dollars = Decimal(1)
    position.realized_pnl_dollars = Decimal("0.7162")
    position.settled_at = datetime.now(UTC)
    session = make_settlement_session(position)

    with pytest.raises(
        ValueError,
        match="different settlement result",
    ):
        await settle_paper_position(
            session=session,
            paper_order_id=position.paper_order_id,
            settlement_result="no",
            settled_at=datetime.now(UTC),
        )


@pytest.mark.asyncio
async def test_settlement_rejects_empty_order_id() -> None:
    session = AsyncMock(spec=AsyncSession)

    with pytest.raises(
        ValueError,
        match="paper_order_id cannot be empty",
    ):
        await settle_paper_position(
            session=session,
            paper_order_id="",
            settlement_result="yes",
            settled_at=datetime.now(UTC),
        )


@pytest.mark.asyncio
async def test_settlement_rejects_invalid_result() -> None:
    session = AsyncMock(spec=AsyncSession)

    with pytest.raises(
        ValueError,
        match="settlement_result must be yes or no",
    ):
        await settle_paper_position(
            session=session,
            paper_order_id="paper-order-1",
            settlement_result=cast(PaperSide, "maybe"),
            settled_at=datetime.now(UTC),
        )


@pytest.mark.asyncio
async def test_settlement_rejects_naive_timestamp() -> None:
    session = AsyncMock(spec=AsyncSession)
    naive_time = datetime.now(UTC).replace(tzinfo=None)

    with pytest.raises(
        ValueError,
        match="settled_at must include a timezone",
    ):
        await settle_paper_position(
            session=session,
            paper_order_id="paper-order-1",
            settlement_result="yes",
            settled_at=naive_time,
        )