from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from weather_oms.storage.models import (
    PaperRiskDecision,
    TemperatureSettlement,
)
from weather_oms.storage.paper_risk_decision_repository import (
    DecisionSide,
)


@dataclass(frozen=True, slots=True)
class PaperProbabilityObservation:
    decision_id: str
    target_date: date
    market_ticker: str
    side: DecisionSide
    model_probability: Decimal
    outcome: int


async def load_paper_probability_observations(
    session: AsyncSession,
    target_date: date | None = None,
) -> tuple[PaperProbabilityObservation, ...]:
    """Load allowed decisions that now have settlements."""

    statement = (
        select(
            PaperRiskDecision,
            TemperatureSettlement.winning_market_ticker,
        )
        .join(
            TemperatureSettlement,
            (
                TemperatureSettlement.event_ticker
                == PaperRiskDecision.event_ticker
            ),
        )
        .where(
            PaperRiskDecision.allowed.is_(True),
            (
                TemperatureSettlement.winning_market_ticker
                .is_not(None)
            ),
        )
    )

    if target_date is not None:
        statement = statement.where(
            PaperRiskDecision.target_date == target_date
        )

    statement = statement.order_by(
        PaperRiskDecision.target_date,
        PaperRiskDecision.decision_id,
    )

    result = await session.execute(statement)
    rows = result.all()

    observations: list[
        PaperProbabilityObservation
    ] = []

    for decision, winning_market_ticker in rows:
        if not isinstance(winning_market_ticker, str):
            raise TypeError(
                "Winning market ticker must be a string."
            )

        side = cast(DecisionSide, decision.side)
        market_won = (
            decision.market_ticker
            == winning_market_ticker
        )

        side_won = (
            market_won
            if side == "yes"
            else not market_won
        )

        observations.append(
            PaperProbabilityObservation(
                decision_id=decision.decision_id,
                target_date=decision.target_date,
                market_ticker=decision.market_ticker,
                side=side,
                model_probability=(
                    decision.model_probability
                ),
                outcome=int(side_won),
            )
        )

    return tuple(observations)