from decimal import Decimal

from weather_oms.execution.portfolio_risk import (
    PortfolioRiskSummary,
)
from weather_oms.execution.position_sizing import (
    DEFAULT_SIZING_POLICY,
    SizingDecision,
    SizingPolicy,
    SizingRequest,
    size_position,
)
from weather_oms.execution.risk import (
    DEFAULT_RISK_POLICY,
    RiskPolicy,
)
from weather_oms.signal.market_comparison import MarketComparison


def size_paper_candidate(
    comparison: MarketComparison,
    portfolio: PortfolioRiskSummary,
    bankroll_dollars: Decimal,
    risk_policy: RiskPolicy = DEFAULT_RISK_POLICY,
    sizing_policy: SizingPolicy = DEFAULT_SIZING_POLICY,
) -> SizingDecision:
    """Size one paper candidate using current risk headroom."""

    side = comparison.candidate_side

    if side is None:
        raise ValueError(
            "Cannot size a comparison without a candidate side."
        )

    if side == "yes":
        side_probability = Decimal(
            str(comparison.our_yes_probability)
        )
        ask_cents = comparison.yes_ask_cents
        fee_dollars = Decimal(
            str(comparison.yes_fee_dollars)
        )
    else:
        side_probability = Decimal(
            str(comparison.our_no_probability)
        )
        ask_cents = comparison.no_ask_cents
        fee_dollars = Decimal(
            str(comparison.no_fee_dollars)
        )

    existing_market_contracts = sum(
        position.contracts
        for position in portfolio.current_event_positions
        if (
            position.market_ticker
            == comparison.market_ticker
        )
    )

    remaining_market_contracts = max(
        0,
        (
            risk_policy.maximum_contracts_per_market
            - existing_market_contracts
        ),
    )
    maximum_contracts = min(
        risk_policy.maximum_contracts_per_order,
        remaining_market_contracts,
    )

    remaining_event_risk = max(
        Decimal(0),
        (
            risk_policy.maximum_event_risk_dollars
            - portfolio.current_event_risk_dollars
        ),
    )
    remaining_daily_risk = max(
        Decimal(0),
        (
            risk_policy.maximum_daily_exposure_dollars
            - portfolio.total_daily_exposure_dollars
        ),
    )
    available_risk = min(
        risk_policy.maximum_order_risk_dollars,
        remaining_event_risk,
        remaining_daily_risk,
    )

    return size_position(
        request=SizingRequest(
            bankroll_dollars=bankroll_dollars,
            side_probability=side_probability,
            entry_price_dollars=(
                Decimal(ask_cents) / Decimal(100)
            ),
            fee_per_contract_dollars=fee_dollars,
            available_risk_dollars=available_risk,
            maximum_contracts=maximum_contracts,
        ),
        policy=sizing_policy,
    )