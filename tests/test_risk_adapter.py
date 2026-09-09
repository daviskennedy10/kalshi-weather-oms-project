from decimal import Decimal

import pytest

from weather_oms.execution.risk import PositionRisk, TradeSide, assess_risk
from weather_oms.execution.risk_adapter import build_risk_request
from weather_oms.signal.market_comparison import MarketComparison


def make_comparison(
    candidate_side: TradeSide | None = "yes",
) -> MarketComparison:
    return MarketComparison(
        market_ticker="KXHIGHNY-26SEP10-T79",
        our_yes_probability=0.70,
        our_no_probability=0.30,
        yes_ask_cents=40,
        no_ask_cents=62,
        yes_fee_dollars=0.01,
        no_fee_dollars=0.02,
        yes_pre_fee_edge=0.30,
        no_pre_fee_edge=-0.32,
        yes_net_edge=0.29,
        no_net_edge=-0.34,
        minimum_net_edge=0.05,
        candidate_side=candidate_side,
        candidate_edge=0.29,
    )



def test_yes_candidate_uses_yes_price_and_fee() -> None:
    request = build_risk_request(
        comparison=make_comparison("yes"),
        bracket_id="79_or_below",
        mode="paper",
        kill_switch_active=False,
        inputs_complete=True,
        inputs_aligned=True,
        forecast_eligible=True,
        quote_eligible=True,
        quote_fresh=True,
        model_ready=True,
    )

    position = request.proposed_position

    assert position.side == "yes"
    assert position.contracts == 1
    assert position.risk_per_contract_dollars == Decimal("0.41")
    assert request.net_edge == Decimal("0.29")


def test_no_candidate_uses_no_price_and_fee() -> None:
    comparison = make_comparison("no")

    request = build_risk_request(
        comparison=comparison,
        bracket_id="79_or_below",
        mode="paper",
        kill_switch_active=False,
        inputs_complete=True,
        inputs_aligned=True,
        forecast_eligible=True,
        quote_eligible=True,
        quote_fresh=True,
        model_ready=True,
    )

    position = request.proposed_position

    assert position.side == "no"
    assert position.risk_per_contract_dollars == Decimal("0.64")


def test_missing_candidate_side_is_rejected() -> None:
    comparison = make_comparison(None)

    with pytest.raises(
        ValueError,
        match="without a candidate side",
    ):
        build_risk_request(
            comparison=comparison,
            bracket_id="79_or_below",
            mode="paper",
            kill_switch_active=False,
            inputs_complete=True,
            inputs_aligned=True,
            forecast_eligible=True,
            quote_eligible=True,
            quote_fresh=True,
            model_ready=True,
        )


def test_existing_risk_information_is_preserved() -> None:
    existing = PositionRisk(
        market_ticker="MARKET-B",
        bracket_id="80_to_81",
        side="no",
        contracts=1,
        risk_per_contract_dollars=Decimal("0.30"),
    )

    request = build_risk_request(
        comparison=make_comparison(),
        bracket_id="79_or_below",
        mode="paper",
        kill_switch_active=False,
        inputs_complete=True,
        inputs_aligned=True,
        forecast_eligible=True,
        quote_eligible=True,
        quote_fresh=True,
        model_ready=True,
        existing_event_positions=(existing,),
        other_daily_exposure_dollars=Decimal("2.00"),
        daily_realized_loss_dollars=Decimal("1.00"),
    )

    assert request.existing_event_positions == (existing,)
    assert request.other_daily_exposure_dollars == Decimal("2.00")
    assert request.daily_realized_loss_dollars == Decimal("1.00")


def test_adapter_output_can_be_checked_by_risk_engine() -> None:
    request = build_risk_request(
        comparison=make_comparison(),
        bracket_id="79_or_below",
        mode="paper",
        kill_switch_active=False,
        inputs_complete=True,
        inputs_aligned=True,
        forecast_eligible=True,
        quote_eligible=True,
        quote_fresh=True,
        model_ready=True,
    )

    decision = assess_risk(request)

    assert decision.allowed is True
    assert decision.reasons == ()