"""Pure risk decisions. This module never places orders."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

TradeMode = Literal["research", "paper", "live"]
TradeSide = Literal["yes", "no"]


@dataclass(frozen=True, slots=True)
class RiskPolicy:
    minimum_net_edge: Decimal = Decimal("0.05")
    maximum_contracts_per_order: int = 1
    maximum_contracts_per_market: int = 1
    maximum_order_risk_dollars: Decimal = Decimal("1.00")
    maximum_event_risk_dollars: Decimal = Decimal("3.00")
    maximum_daily_exposure_dollars: Decimal = Decimal("10.00")
    maximum_daily_loss_dollars: Decimal = Decimal("5.00")


DEFAULT_RISK_POLICY = RiskPolicy()

@dataclass(frozen=True, slots=True)
class PositionRisk:
    market_ticker: str
    bracket_id: str
    side: TradeSide
    contracts: int
    risk_per_contract_dollars: Decimal

    @property
    def total_risk_dollars(self) -> Decimal:
        return self.risk_per_contract_dollars * self.contracts


@dataclass(frozen=True, slots=True)
class RiskRequest:
    mode: TradeMode
    kill_switch_active: bool

    inputs_complete: bool
    inputs_aligned: bool
    forecast_eligible: bool
    quote_eligible: bool
    quote_fresh: bool
    model_ready: bool

    net_edge: Decimal
    proposed_position: PositionRisk

    existing_event_positions: tuple[PositionRisk, ...] = ()
    other_daily_exposure_dollars: Decimal = Decimal(0)
    daily_realized_loss_dollars: Decimal = Decimal(0)


@dataclass(frozen=True, slots=True)
class RiskDecision:
    allowed: bool
    reasons: tuple[str, ...]
    event_worst_case_risk_dollars: Decimal
    daily_exposure_dollars: Decimal


def calculate_event_worst_case_risk(
    positions: tuple[PositionRisk, ...],
) -> Decimal:
    """Find the largest possible loss across all temperature outcomes."""

    if not positions:
        return Decimal(0)

    brackets = {position.bracket_id for position in positions}

    # None represents an unowned bracket winning.
    possible_winners: tuple[str | None, ...] = (*sorted(brackets), None)

    scenario_losses: list[Decimal] = []

    for winning_bracket in possible_winners:
        loss = Decimal(0)

        for position in positions:
            yes_loses = (
                position.side == "yes"
                and position.bracket_id != winning_bracket
            )
            no_loses = (
                position.side == "no"
                and position.bracket_id == winning_bracket
            )

            if yes_loses or no_loses:
                loss += position.total_risk_dollars

        scenario_losses.append(loss)

    return max(scenario_losses)


def assess_risk(
    request: RiskRequest,
    policy: RiskPolicy = DEFAULT_RISK_POLICY,
) -> RiskDecision:
    """Return ALLOW or BLOCK without performing any external action."""

    _validate_inputs(request, policy)

    reasons: list[str] = []
    proposed = request.proposed_position

    if request.mode != "paper":
        reasons.append("Only paper trading is allowed.")

    if request.kill_switch_active:
        reasons.append("The kill switch is active.")

    if not request.inputs_complete:
        reasons.append("Decision inputs are incomplete.")

    if not request.inputs_aligned:
        reasons.append("Forecast and quote data are not time-aligned.")

    if not request.forecast_eligible:
        reasons.append("The forecast is not eligible.")

    if not request.quote_eligible:
        reasons.append("The quote is later than the cutoff.")

    if not request.quote_fresh:
        reasons.append("The quote is stale.")

    if not request.model_ready:
        reasons.append("The model probability is not ready.")

    if request.net_edge < policy.minimum_net_edge:
        reasons.append("Net edge is below the minimum.")

    if proposed.contracts > policy.maximum_contracts_per_order:
        reasons.append("The order exceeds the contract limit.")

    if proposed.total_risk_dollars > policy.maximum_order_risk_dollars:
        reasons.append("The order exceeds the dollar-risk limit.")

    positions = (*request.existing_event_positions, proposed)

    market_contracts = sum(
        position.contracts
        for position in positions
        if position.market_ticker == proposed.market_ticker
    )

    if market_contracts > policy.maximum_contracts_per_market:
        reasons.append("The position exceeds the per-market limit.")

    event_risk = calculate_event_worst_case_risk(positions)

    if event_risk > policy.maximum_event_risk_dollars:
        reasons.append("Worst-case event risk exceeds the event limit.")

    daily_exposure = (
        request.other_daily_exposure_dollars + event_risk
    )

    if daily_exposure > policy.maximum_daily_exposure_dollars:
        reasons.append("Total daily exposure exceeds the daily limit.")

    if (
        request.daily_realized_loss_dollars
        >= policy.maximum_daily_loss_dollars
    ):
        reasons.append("The daily loss limit has been reached.")

    return RiskDecision(
        allowed=not reasons,
        reasons=tuple(reasons),
        event_worst_case_risk_dollars=event_risk,
        daily_exposure_dollars=daily_exposure,
    )


def _validate_inputs(
    request: RiskRequest,
    policy: RiskPolicy,
) -> None:
    if policy.minimum_net_edge < 0:
        raise ValueError("minimum_net_edge cannot be negative")

    if policy.maximum_contracts_per_order <= 0:
        raise ValueError("maximum_contracts_per_order must be positive")

    if policy.maximum_contracts_per_market <= 0:
        raise ValueError("maximum_contracts_per_market must be positive")

    money_limits = (
        policy.maximum_order_risk_dollars,
        policy.maximum_event_risk_dollars,
        policy.maximum_daily_exposure_dollars,
        policy.maximum_daily_loss_dollars,
    )

    if any(limit <= 0 for limit in money_limits):
        raise ValueError("Dollar limits must be positive")

    all_positions = (
        *request.existing_event_positions,
        request.proposed_position,
    )

    for position in all_positions:
        if not position.market_ticker or not position.bracket_id:
            raise ValueError("Positions must have market and bracket IDs")

        if position.contracts <= 0:
            raise ValueError("Position contracts must be positive")

        if position.risk_per_contract_dollars < 0:
            raise ValueError("Position risk cannot be negative")

    if request.other_daily_exposure_dollars < 0:
        raise ValueError("Daily exposure cannot be negative")

    if request.daily_realized_loss_dollars < 0:
        raise ValueError("Daily realized loss cannot be negative")