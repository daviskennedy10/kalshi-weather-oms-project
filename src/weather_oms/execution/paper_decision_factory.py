from datetime import date, datetime
from decimal import Decimal

from weather_oms.execution.paper_planner import PaperPlanItem
from weather_oms.storage.paper_risk_decision_repository import (
    NewPaperRiskDecision,
    create_paper_decision_id,
)


def create_new_paper_risk_decision(
    plan_item: PaperPlanItem,
    event_ticker: str,
    target_date: date,
    quote_retrieved_at: datetime,
    kill_switch_active: bool,
) -> NewPaperRiskDecision:
    """Convert one plan result into an audit record."""

    comparison = plan_item.candidate.comparison
    risk_request = plan_item.risk_request
    risk_decision = plan_item.risk_decision
    proposed = risk_request.proposed_position
    side = comparison.candidate_side

    if side is None:
        raise ValueError(
            "Cannot audit a candidate without a side."
        )

    if comparison.market_ticker != proposed.market_ticker:
        raise ValueError(
            "Comparison and proposed position markets do not match."
        )

    decision_id = create_paper_decision_id(
        event_ticker=event_ticker,
        market_ticker=comparison.market_ticker,
        side=side,
        target_date=target_date,
        quote_retrieved_at=quote_retrieved_at,
        kill_switch_active=kill_switch_active,
    )

    return NewPaperRiskDecision(
        decision_id=decision_id,
        event_ticker=event_ticker,
        market_ticker=comparison.market_ticker,
        target_date=target_date,
        quote_retrieved_at=quote_retrieved_at,
        side=side,
        net_edge=Decimal(
            str(comparison.candidate_edge)
        ),
        allowed=risk_decision.allowed,
        reasons=risk_decision.reasons,
        proposed_risk_dollars=(
            proposed.total_risk_dollars
        ),
        event_risk_after_dollars=(
            risk_decision.event_worst_case_risk_dollars
        ),
        daily_exposure_after_dollars=(
            risk_decision.daily_exposure_dollars
        ),
        kill_switch_active=kill_switch_active,
    )