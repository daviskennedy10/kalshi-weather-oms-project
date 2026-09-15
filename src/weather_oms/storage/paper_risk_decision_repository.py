import hashlib
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from weather_oms.storage.models import PaperRiskDecision

DecisionSide = Literal["yes", "no"]


@dataclass(frozen=True, slots=True)
class NewPaperRiskDecision:
    decision_id: str
    event_ticker: str
    market_ticker: str
    target_date: date
    quote_retrieved_at: datetime
    side: DecisionSide
    net_edge: Decimal
    allowed: bool
    reasons: tuple[str, ...]
    proposed_risk_dollars: Decimal
    event_risk_after_dollars: Decimal
    daily_exposure_after_dollars: Decimal
    kill_switch_active: bool


def create_paper_decision_id(
    event_ticker: str,
    market_ticker: str,
    side: DecisionSide,
    target_date: date,
    kill_switch_active: bool,
    quote_retrieved_at: datetime,
) -> str:
    """Create a repeatable ID for one candidate decision."""

    if not event_ticker or not market_ticker:
        raise ValueError("Decision identifiers cannot be empty.")

    if quote_retrieved_at.tzinfo is None:
        raise ValueError(
            "quote_retrieved_at must include a timezone."
        )

    normalized_time = quote_retrieved_at.astimezone(UTC)

    identity = (
        f"{event_ticker}|{market_ticker}|{side}|"
        f"{target_date.isoformat()}|"
        f"{normalized_time.isoformat()}"
        f"kill_switch={kill_switch_active}"
    )

    fingerprint = hashlib.sha256(
        identity.encode("utf-8")
    ).hexdigest()

    return f"decision-{fingerprint}"


async def save_paper_risk_decision(
    session: AsyncSession,
    decision: NewPaperRiskDecision,
) -> bool:
    """Save one paper risk decision without creating duplicates."""

    _validate_decision(decision)

    statement = (
        insert(PaperRiskDecision)
        .values(
            decision_id=decision.decision_id,
            event_ticker=decision.event_ticker,
            market_ticker=decision.market_ticker,
            target_date=decision.target_date,
            quote_retrieved_at=(
                decision.quote_retrieved_at.astimezone(UTC)
            ),
            side=decision.side,
            net_edge=decision.net_edge,
            allowed=decision.allowed,
            reasons=list(decision.reasons),
            proposed_risk_dollars=(
                decision.proposed_risk_dollars
            ),
            event_risk_after_dollars=(
                decision.event_risk_after_dollars
            ),
            daily_exposure_after_dollars=(
                decision.daily_exposure_after_dollars
            ),
            kill_switch_active=(
                decision.kill_switch_active
            ),
        )
        .on_conflict_do_nothing(
            index_elements=[
                PaperRiskDecision.decision_id
            ]
        )
        .returning(PaperRiskDecision.id)
    )

    result = await session.execute(statement)
    inserted_id = result.scalar_one_or_none()

    return inserted_id is not None


def _validate_decision(
    decision: NewPaperRiskDecision,
) -> None:
    identifiers = (
        decision.decision_id,
        decision.event_ticker,
        decision.market_ticker,
    )

    if any(not identifier for identifier in identifiers):
        raise ValueError(
            "Risk-decision identifiers cannot be empty."
        )

    if decision.quote_retrieved_at.tzinfo is None:
        raise ValueError(
            "quote_retrieved_at must include a timezone."
        )

    if (
        not decision.net_edge.is_finite()
        or not Decimal(-1)
        <= decision.net_edge
        <= Decimal(1)
    ):
        raise ValueError(
            "net_edge must be finite and between -1 and 1."
        )

    risk_amounts = (
        decision.proposed_risk_dollars,
        decision.event_risk_after_dollars,
        decision.daily_exposure_after_dollars,
    )

    if any(
        not amount.is_finite() or amount < 0
        for amount in risk_amounts
    ):
        raise ValueError(
            "Risk amounts must be finite and nonnegative."
        )

    if (
        decision.daily_exposure_after_dollars
        < decision.event_risk_after_dollars
    ):
        raise ValueError(
            "Daily exposure cannot be below event risk."
        )

    if decision.allowed and decision.reasons:
        raise ValueError(
            "An allowed decision cannot have blocking reasons."
        )

    if not decision.allowed and not decision.reasons:
        raise ValueError(
            "A blocked decision must have a reason."
        )