"""Convert a market comparison into a risk-engine request."""

from decimal import Decimal

from weather_oms.execution.risk import (
    PositionRisk,
    RiskRequest,
    TradeMode,
)
from weather_oms.signal.market_comparison import MarketComparison


def build_risk_request(
    comparison: MarketComparison,
    bracket_id: str,
    mode: TradeMode,
    kill_switch_active: bool,
    inputs_complete: bool,
    inputs_aligned: bool,
    forecast_eligible: bool,
    quote_eligible: bool,
    quote_fresh: bool,
    model_ready: bool,
    contracts: int = 1,
    existing_event_positions: tuple[PositionRisk, ...] = (),
    other_daily_exposure_dollars: Decimal = Decimal(0),
    daily_realized_loss_dollars: Decimal = Decimal(0),
) -> RiskRequest:
    """Build a risk request for one research candidate."""

    side = comparison.candidate_side

    if side is None:
        raise ValueError(
            "Cannot build a risk request without a candidate side."
        )

    if side == "yes":
        ask_cents = comparison.yes_ask_cents
        fee_dollars = comparison.yes_fee_dollars
    else:
        ask_cents = comparison.no_ask_cents
        fee_dollars = comparison.no_fee_dollars
    
    if contracts <= 0:
        raise ValueError("contracts must be positive")

    price_dollars = Decimal(ask_cents) / Decimal(100)
    fee = Decimal(str(fee_dollars))

    position = PositionRisk(
        market_ticker=comparison.market_ticker,
        bracket_id=bracket_id,
        side=side,
        contracts=contracts,
        risk_per_contract_dollars=price_dollars + fee,
    )

    return RiskRequest(
        mode=mode,
        kill_switch_active=kill_switch_active,
        inputs_complete=inputs_complete,
        inputs_aligned=inputs_aligned,
        forecast_eligible=forecast_eligible,
        quote_eligible=quote_eligible,
        quote_fresh=quote_fresh,
        model_ready=model_ready,
        net_edge=Decimal(str(comparison.candidate_edge)),
        proposed_position=position,
        existing_event_positions=existing_event_positions,
        other_daily_exposure_dollars=other_daily_exposure_dollars,
        daily_realized_loss_dollars=daily_realized_loss_dollars,
    )