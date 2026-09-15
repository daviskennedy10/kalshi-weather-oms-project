from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class SizingPolicy:
    minimum_net_edge: Decimal = Decimal("0.05")
    kelly_multiplier: Decimal = Decimal("0.25")


DEFAULT_SIZING_POLICY = SizingPolicy()


@dataclass(frozen=True, slots=True)
class SizingRequest:
    bankroll_dollars: Decimal
    side_probability: Decimal
    entry_price_dollars: Decimal
    fee_per_contract_dollars: Decimal
    available_risk_dollars: Decimal
    maximum_contracts: int


@dataclass(frozen=True, slots=True)
class SizingDecision:
    contracts: int
    total_risk_dollars: Decimal
    net_edge: Decimal
    full_kelly_fraction: Decimal
    applied_kelly_fraction: Decimal
    reason: str

    @property
    def should_trade(self) -> bool:
        return self.contracts > 0


def size_position(
    request: SizingRequest,
    policy: SizingPolicy = DEFAULT_SIZING_POLICY,
) -> SizingDecision:
    """Choose a contract count without performing any action."""

    _validate(request, policy)

    risk_per_contract = (
        request.entry_price_dollars
        + request.fee_per_contract_dollars
    )
    net_edge = (
        request.side_probability
        - risk_per_contract
    )

    if request.maximum_contracts == 0:
        return _no_trade(
            net_edge=net_edge,
            reason="The market contract limit is already full.",
        )

    profit_per_winning_contract = (
        Decimal(1)
        - request.entry_price_dollars
        - request.fee_per_contract_dollars
    )

    if net_edge < policy.minimum_net_edge:
        return _no_trade(
            net_edge=net_edge,
            reason="Net edge is below the minimum.",
        )

    win_odds = (
        profit_per_winning_contract
        / risk_per_contract
    )
    loss_probability = (
        Decimal(1) - request.side_probability
    )

    full_kelly_fraction = (
        (
            win_odds * request.side_probability
            - loss_probability
        )
        / win_odds
    )

    if full_kelly_fraction <= 0:
        return _no_trade(
            net_edge=net_edge,
            reason="The Kelly size is not positive.",
        )

    applied_kelly_fraction = (
        full_kelly_fraction
        * policy.kelly_multiplier
    )
    kelly_risk_budget = (
        request.bankroll_dollars
        * applied_kelly_fraction
    )
    final_risk_budget = min(
        kelly_risk_budget,
        request.available_risk_dollars,
    )

    affordable_contracts = int(
        final_risk_budget // risk_per_contract
    )
    contracts = min(
        affordable_contracts,
        request.maximum_contracts,
    )

    if contracts == 0:
        return SizingDecision(
            contracts=0,
            total_risk_dollars=Decimal(0),
            net_edge=net_edge,
            full_kelly_fraction=full_kelly_fraction,
            applied_kelly_fraction=(
                applied_kelly_fraction
            ),
            reason=(
                "Available risk cannot fund one contract."
            ),
        )

    return SizingDecision(
        contracts=contracts,
        total_risk_dollars=(
            risk_per_contract * contracts
        ),
        net_edge=net_edge,
        full_kelly_fraction=full_kelly_fraction,
        applied_kelly_fraction=applied_kelly_fraction,
        reason="Position sized within every limit.",
    )


def _no_trade(
    net_edge: Decimal,
    reason: str,
) -> SizingDecision:
    return SizingDecision(
        contracts=0,
        total_risk_dollars=Decimal(0),
        net_edge=net_edge,
        full_kelly_fraction=Decimal(0),
        applied_kelly_fraction=Decimal(0),
        reason=reason,
    )


def _validate(
    request: SizingRequest,
    policy: SizingPolicy,
) -> None:
    if request.bankroll_dollars <= 0:
        raise ValueError("bankroll_dollars must be positive.")

    if not Decimal(0) <= request.side_probability <= Decimal(1):
        raise ValueError(
            "side_probability must be between zero and one."
        )

    if not Decimal(0) < request.entry_price_dollars < Decimal(1):
        raise ValueError(
            "entry_price_dollars must be between zero and one."
        )

    if request.fee_per_contract_dollars < 0:
        raise ValueError(
            "fee_per_contract_dollars cannot be negative."
        )

    total_contract_risk = (
        request.entry_price_dollars
        + request.fee_per_contract_dollars
    )

    if total_contract_risk >= 1:
        raise ValueError(
            "Price plus fee must be less than one dollar."
        )

    if request.available_risk_dollars < 0:
        raise ValueError(
            "available_risk_dollars cannot be negative."
        )

    if request.maximum_contracts < 0:
        raise ValueError(
            "maximum_contracts cannot be negative."
        )

    if policy.minimum_net_edge < 0:
        raise ValueError(
            "minimum_net_edge cannot be negative."
        )

    if not Decimal(0) < policy.kelly_multiplier <= Decimal(1):
        raise ValueError(
            "kelly_multiplier must be between zero and one."
        )