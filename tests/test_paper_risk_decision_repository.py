import uuid
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from weather_oms.storage.models import PaperRiskDecision
from weather_oms.storage.paper_risk_decision_repository import (
    NewPaperRiskDecision,
    create_paper_decision_id,
    load_paper_decision_timings,
    save_paper_risk_decision,
)

QUOTE_TIME = datetime(
    2026,
    9,
    9,
    15,
    49,
    tzinfo=UTC,
)


def make_decision() -> NewPaperRiskDecision:
    return NewPaperRiskDecision(
        decision_id="decision-1",
        event_ticker="KXHIGHNY-26SEP10",
        market_ticker="KXHIGHNY-26SEP10-T85",
        target_date=date(2026, 9, 10),
        quote_retrieved_at=QUOTE_TIME,
        side="yes",
        net_edge=Decimal("0.186"),
        model_probability=Decimal("0.47"),
        contracts=1,
        allowed=True,
        reasons=(),
        proposed_risk_dollars=Decimal("0.2838"),
        event_risk_after_dollars=Decimal("0.2838"),
        daily_exposure_after_dollars=Decimal("0.2838"),
        kill_switch_active=False,
    )


def test_same_candidate_creates_same_decision_id() -> None:
    first = create_paper_decision_id(
        event_ticker="KXHIGHNY-26SEP10",
        market_ticker="KXHIGHNY-26SEP10-T85",
        side="yes",
        target_date=date(2026, 9, 10),
        quote_retrieved_at=QUOTE_TIME,
        kill_switch_active=False,
    )
    second = create_paper_decision_id(
        event_ticker="KXHIGHNY-26SEP10",
        market_ticker="KXHIGHNY-26SEP10-T85",
        side="yes",
        target_date=date(2026, 9, 10),
        quote_retrieved_at=QUOTE_TIME,
        kill_switch_active=False,
    )

    assert first == second
    assert first.startswith("decision-")


def test_different_market_creates_different_decision_id() -> None:
    first = create_paper_decision_id(
        event_ticker="KXHIGHNY-26SEP10",
        market_ticker="MARKET-A",
        side="yes",
        target_date=date(2026, 9, 10),
        quote_retrieved_at=QUOTE_TIME,
        kill_switch_active=False,

    )
    second = create_paper_decision_id(
        event_ticker="KXHIGHNY-26SEP10",
        market_ticker="MARKET-B",
        side="yes",
        target_date=date(2026, 9, 10),
        quote_retrieved_at=QUOTE_TIME,
        kill_switch_active=False,
    )

    assert first != second


@pytest.mark.asyncio
async def test_saves_new_decision() -> None:
    session = AsyncMock(spec=AsyncSession)
    result = Mock()
    result.scalar_one_or_none.return_value = uuid.uuid4()
    session.execute.return_value = result

    inserted = await save_paper_risk_decision(
        session=session,
        decision=make_decision(),
    )

    assert inserted is True
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_duplicate_decision_returns_false() -> None:
    session = AsyncMock(spec=AsyncSession)
    result = Mock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result

    inserted = await save_paper_risk_decision(
        session=session,
        decision=make_decision(),
    )

    assert inserted is False


@pytest.mark.asyncio
async def test_saves_blocked_decision_with_reason() -> None:
    session = AsyncMock(spec=AsyncSession)
    result = Mock()
    result.scalar_one_or_none.return_value = uuid.uuid4()
    session.execute.return_value = result

    decision = replace(
        make_decision(),
        allowed=False,
        reasons=("The kill switch is active.",),
        kill_switch_active=True,
    )

    inserted = await save_paper_risk_decision(
        session=session,
        decision=decision,
    )

    assert inserted is True


@pytest.mark.asyncio
async def test_allowed_decision_cannot_have_reasons() -> None:
    session = AsyncMock(spec=AsyncSession)
    decision = replace(
        make_decision(),
        reasons=("Unexpected reason.",),
    )

    with pytest.raises(
        ValueError,
        match="allowed decision cannot have",
    ):
        await save_paper_risk_decision(
            session=session,
            decision=decision,
        )


@pytest.mark.asyncio
async def test_blocked_decision_requires_reason() -> None:
    session = AsyncMock(spec=AsyncSession)
    decision = replace(
        make_decision(),
        allowed=False,
        reasons=(),
    )

    with pytest.raises(
        ValueError,
        match="blocked decision must have a reason",
    ):
        await save_paper_risk_decision(
            session=session,
            decision=decision,
        )


@pytest.mark.asyncio
async def test_rejects_invalid_net_edge() -> None:
    session = AsyncMock(spec=AsyncSession)
    decision = replace(
        make_decision(),
        net_edge=Decimal("1.01"),
    )

    with pytest.raises(
        ValueError,
        match="between -1 and 1",
    ):
        await save_paper_risk_decision(
            session=session,
            decision=decision,
        )


@pytest.mark.asyncio
async def test_rejects_negative_risk() -> None:
    session = AsyncMock(spec=AsyncSession)
    decision = replace(
        make_decision(),
        proposed_risk_dollars=Decimal("-0.01"),
    )

    with pytest.raises(
        ValueError,
        match="finite and nonnegative",
    ):
        await save_paper_risk_decision(
            session=session,
            decision=decision,
        )


@pytest.mark.asyncio
async def test_daily_exposure_cannot_be_below_event_risk() -> None:
    session = AsyncMock(spec=AsyncSession)
    decision = replace(
        make_decision(),
        event_risk_after_dollars=Decimal("1.00"),
        daily_exposure_after_dollars=Decimal("0.50"),
    )

    with pytest.raises(
        ValueError,
        match="cannot be below event risk",
    ):
        await save_paper_risk_decision(
            session=session,
            decision=decision,
        )


def test_decision_id_rejects_naive_timestamp() -> None:
    naive_time = QUOTE_TIME.replace(tzinfo=None)

    with pytest.raises(
        ValueError,
        match="must include a timezone",
    ):
        create_paper_decision_id(
            event_ticker="KXHIGHNY-26SEP10",
            market_ticker="KXHIGHNY-26SEP10-T85",
            side="yes",
            target_date=date(2026, 9, 10),
            quote_retrieved_at=naive_time,
            kill_switch_active=False,
        )

def test_kill_switch_changes_decision_id() -> None:
    switch_off = create_paper_decision_id(
        event_ticker="KXHIGHNY-26SEP10",
        market_ticker="KXHIGHNY-26SEP10-T85",
        side="yes",
        target_date=date(2026, 9, 10),
        quote_retrieved_at=QUOTE_TIME,
        kill_switch_active=False,
    )
    switch_on = create_paper_decision_id(
        event_ticker="KXHIGHNY-26SEP10",
        market_ticker="KXHIGHNY-26SEP10-T85",
        side="yes",
        target_date=date(2026, 9, 10),
        quote_retrieved_at=QUOTE_TIME,
        kill_switch_active=True,
    )

    assert switch_off != switch_on


def make_stored_decision() -> PaperRiskDecision:
    return PaperRiskDecision(
        id=uuid.uuid4(),
        decision_id="decision-stored",
        event_ticker="KXHIGHNY-26SEP10",
        market_ticker="KXHIGHNY-26SEP10-T85",
        target_date=date(2026, 9, 10),
        quote_retrieved_at=QUOTE_TIME,
        side="yes",
        net_edge=Decimal("0.186"),
        model_probability=Decimal("0.47"),
        contracts=1,
        allowed=True,
        reasons=[],
        proposed_risk_dollars=Decimal("0.2838"),
        event_risk_after_dollars=Decimal("0.2838"),
        daily_exposure_after_dollars=Decimal("0.2838"),
        kill_switch_active=False,
        stored_at=QUOTE_TIME.replace(
            minute=50,
        ),
    )


def make_timing_result(
    rows: list[PaperRiskDecision],
) -> Mock:
    scalars = Mock()
    scalars.all.return_value = rows

    result = Mock()
    result.scalars.return_value = scalars
    return result


@pytest.mark.asyncio
async def test_loads_paper_decision_timings() -> None:
    session = AsyncMock(spec=AsyncSession)
    session.execute.return_value = make_timing_result(
        [make_stored_decision()]
    )

    timings = await load_paper_decision_timings(
        session=session,
        target_date=date(2026, 9, 10),
    )

    assert len(timings) == 1
    assert timings[0].decision_id == "decision-stored"
    assert timings[0].quote_retrieved_at == QUOTE_TIME
    assert timings[0].stored_at == QUOTE_TIME.replace(
        minute=50,
    )
    assert timings[0].latency.total_seconds() == 60


@pytest.mark.asyncio
async def test_load_timings_can_return_empty() -> None:
    session = AsyncMock(spec=AsyncSession)
    session.execute.return_value = make_timing_result([])

    timings = await load_paper_decision_timings(
        session=session,
    )

    assert timings == ()

@pytest.mark.asyncio
async def test_rejects_invalid_model_probability() -> None:
    session = AsyncMock(spec=AsyncSession)
    decision = replace(
        make_decision(),
        model_probability=Decimal("1.01"),
    )

    with pytest.raises(
        ValueError,
        match="model_probability",
    ):
        await save_paper_risk_decision(
            session=session,
            decision=decision,
        )


@pytest.mark.asyncio
async def test_rejects_nonpositive_contracts() -> None:
    session = AsyncMock(spec=AsyncSession)
    decision = replace(
        make_decision(),
        contracts=0,
    )

    with pytest.raises(
        ValueError,
        match="contracts must be positive",
    ):
        await save_paper_risk_decision(
            session=session,
            decision=decision,
        )