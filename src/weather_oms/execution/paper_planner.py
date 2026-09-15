from dataclasses import dataclass

from weather_oms.execution.portfolio_risk import (
    PortfolioRiskSummary,
)
from weather_oms.execution.risk import (
    DEFAULT_RISK_POLICY,
    RiskDecision,
    RiskPolicy,
    RiskRequest,
)
from weather_oms.execution.risk_adapter import build_risk_request
from weather_oms.signal.market_comparison import MarketComparison


@dataclass(frozen=True, slots=True)
class PaperCandidate:
    bracket_id: str
    comparison: MarketComparison
    contracts: int = 1


@dataclass(frozen=True, slots=True)
class PaperPlanItem:
    candidate: PaperCandidate
    risk_request: RiskRequest
    risk_decision: RiskDecision


def plan_paper_positions(
    candidates: tuple[PaperCandidate, ...],
    portfolio: PortfolioRiskSummary,
    kill_switch_active: bool = False,
    policy: RiskPolicy = DEFAULT_RISK_POLICY,
) -> tuple[PaperPlanItem, ...]:
    """Evaluate candidates from highest edge to lowest edge."""

    for candidate in candidates:
        if candidate.contracts <= 0:
            raise ValueError(
                "Candidate contracts must be positive."
            )
        if candidate.comparison.candidate_side is None:
            raise ValueError(
                "Every paper candidate must have a candidate side."
            )

        if not candidate.bracket_id:
            raise ValueError("Candidate bracket_id cannot be empty.")

    ordered_candidates = sorted(
        candidates,
        key=lambda candidate: (
            candidate.comparison.candidate_edge
        ),
        reverse=True,
    )

    event_positions = list(
        portfolio.current_event_positions
    )
    plan: list[PaperPlanItem] = []

    for candidate in ordered_candidates:
        risk_request = build_risk_request(
            comparison=candidate.comparison,
            bracket_id=candidate.bracket_id,
            contracts=candidate.contracts,
            mode="paper",
            kill_switch_active=kill_switch_active,
            inputs_complete=True,
            inputs_aligned=True,
            forecast_eligible=True,
            quote_eligible=True,
            quote_fresh=True,
            model_ready=True,
            existing_event_positions=tuple(event_positions),
            other_daily_exposure_dollars=(
                portfolio.other_event_risk_dollars
            ),
            daily_realized_loss_dollars=(
                portfolio.daily_realized_loss_dollars
            ),
        )

        risk_decision = assess_candidate(
            risk_request,
            policy,
        )

        plan_item = PaperPlanItem(
            candidate=candidate,
            risk_request=risk_request,
            risk_decision=risk_decision,
        )
        plan.append(plan_item)

        if risk_decision.allowed:
            event_positions.append(
                risk_request.proposed_position
            )

    return tuple(plan)


def assess_candidate(
    request: RiskRequest,
    policy: RiskPolicy,
) -> RiskDecision:
    from weather_oms.execution.risk import assess_risk

    return assess_risk(request, policy)