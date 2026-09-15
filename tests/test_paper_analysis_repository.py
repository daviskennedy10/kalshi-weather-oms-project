import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from weather_oms.storage.models import PaperRiskDecision
from weather_oms.storage.paper_analysis_repository import (
    load_paper_probability_observations,
)


def make_decision(
    *,
    decision_id: str,
    market_ticker: str,
    side: str,
    probability: Decimal,
) -> PaperRiskDecision:
    timestamp = datetime(
        2026,
        9,
        15,
        15,
        50,
        tzinfo=UTC,
    )

    return PaperRiskDecision(
        id=uuid.uuid4(),
        decision_id=decision_id,
        event_ticker="KXHIGHNY-26SEP16",
        market_ticker=market_ticker,
        target_date=date(2026, 9, 16),
        quote_retrieved_at=timestamp,
        side=side,
        net_edge=Decimal("0.10"),
        model_probability=probability,
        contracts=1,
        allowed=True,
        reasons=[],
        proposed_risk_dollars=Decimal("0.40"),
        event_risk_after_dollars=Decimal("0.40"),
        daily_exposure_after_dollars=Decimal("0.40"),
        kill_switch_active=False,
        stored_at=timestamp,
    )


def make_result(
    rows: list[tuple[PaperRiskDecision, str | None]],
) -> Mock:
    result = Mock()
    result.all.return_value = rows
    return result


@pytest.mark.asyncio
async def test_yes_observation_wins_when_market_wins() -> None:
    session = AsyncMock(spec=AsyncSession)
    decision = make_decision(
        decision_id="decision-yes",
        market_ticker="MARKET-A",
        side="yes",
        probability=Decimal("0.70"),
    )
    session.execute.return_value = make_result(
        [(decision, "MARKET-A")]
    )

    observations = (
        await load_paper_probability_observations(
            session=session,
            target_date=date(2026, 9, 16),
        )
    )

    assert len(observations) == 1
    assert observations[0].model_probability == Decimal(
        "0.70"
    )
    assert observations[0].outcome == 1


@pytest.mark.asyncio
async def test_no_observation_wins_when_other_market_wins() -> None:
    session = AsyncMock(spec=AsyncSession)
    decision = make_decision(
        decision_id="decision-no",
        market_ticker="MARKET-A",
        side="no",
        probability=Decimal("0.80"),
    )
    session.execute.return_value = make_result(
        [(decision, "MARKET-B")]
    )

    observations = (
        await load_paper_probability_observations(
            session=session,
        )
    )

    assert observations[0].outcome == 1


@pytest.mark.asyncio
async def test_no_observation_loses_when_market_wins() -> None:
    session = AsyncMock(spec=AsyncSession)
    decision = make_decision(
        decision_id="decision-no",
        market_ticker="MARKET-A",
        side="no",
        probability=Decimal("0.80"),
    )
    session.execute.return_value = make_result(
        [(decision, "MARKET-A")]
    )

    observations = (
        await load_paper_probability_observations(
            session=session,
        )
    )

    assert observations[0].outcome == 0


@pytest.mark.asyncio
async def test_loader_can_return_empty() -> None:
    session = AsyncMock(spec=AsyncSession)
    session.execute.return_value = make_result([])

    observations = (
        await load_paper_probability_observations(
            session=session,
        )
    )

    assert observations == ()


@pytest.mark.asyncio
async def test_rejects_non_string_winning_ticker() -> None:
    session = AsyncMock(spec=AsyncSession)
    decision = make_decision(
        decision_id="decision-yes",
        market_ticker="MARKET-A",
        side="yes",
        probability=Decimal("0.70"),
    )
    session.execute.return_value = make_result(
        [(decision, None)]
    )

    with pytest.raises(
        TypeError,
        match="must be a string",
    ):
        await load_paper_probability_observations(
            session=session,
        )