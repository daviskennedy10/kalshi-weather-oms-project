from dataclasses import replace
from decimal import Decimal

import pytest

from weather_oms.execution.risk import (
    PositionRisk,
    RiskPolicy,
    RiskRequest,
    TradeSide,
    assess_risk,
    calculate_event_worst_case_risk,
)


def make_position(
    ticker: str = "KXHIGHNY-26SEP10-T79",
    bracket: str = "79_or_below",
    side: TradeSide = "yes",
    contracts: int = 1,
    risk: str = "0.40",
) -> PositionRisk:
    return PositionRisk(
        market_ticker=ticker,
        bracket_id=bracket,
        side=side,
        contracts=contracts,
        risk_per_contract_dollars=Decimal(risk),
    )


def make_safe_request() -> RiskRequest:
    return RiskRequest(
        mode="paper",
        kill_switch_active=False,
        inputs_complete=True,
        inputs_aligned=True,
        forecast_eligible=True,
        quote_eligible=True,
        quote_fresh=True,
        model_ready=True,
        net_edge=Decimal("0.06"),
        proposed_position=make_position(),
    )


def test_safe_paper_trade_is_allowed() -> None:
    decision = assess_risk(make_safe_request())

    assert decision.allowed is True
    assert decision.reasons == ()
    assert decision.event_worst_case_risk_dollars == Decimal("0.40")
    assert decision.daily_exposure_dollars == Decimal("0.40")


def test_live_trade_is_blocked() -> None:
    request = replace(make_safe_request(), mode="live")

    decision = assess_risk(request)

    assert decision.allowed is False
    assert "Only paper trading is allowed." in decision.reasons


def test_kill_switch_blocks_trade() -> None:
    request = replace(
        make_safe_request(),
        kill_switch_active=True,
    )

    decision = assess_risk(request)

    assert decision.allowed is False
    assert "The kill switch is active." in decision.reasons



@pytest.mark.parametrize(
    ("risk_request", "expected_reason"),
    [
        (
            replace(make_safe_request(), inputs_complete=False),
            "Decision inputs are incomplete.",
        ),
        (
            replace(make_safe_request(), inputs_aligned=False),
            "Forecast and quote data are not time-aligned.",
        ),
        (
            replace(make_safe_request(), forecast_eligible=False),
            "The forecast is not eligible.",
        ),
        (
            replace(make_safe_request(), quote_eligible=False),
            "The quote is later than the cutoff.",
        ),
        (
            replace(make_safe_request(), quote_fresh=False),
            "The quote is stale.",
        ),
        (
            replace(make_safe_request(), model_ready=False),
            "The model probability is not ready.",
        ),
    ],
)
def test_invalid_data_blocks_trade(
    risk_request: RiskRequest,
    expected_reason: str,
) -> None:
    decision = assess_risk(risk_request)

    assert decision.allowed is False
    assert expected_reason in decision.reasons

def test_edge_below_five_percent_is_blocked() -> None:
    request = replace(
        make_safe_request(),
        net_edge=Decimal("0.0499"),
    )

    decision = assess_risk(request)

    assert decision.allowed is False
    assert "Net edge is below the minimum." in decision.reasons


def test_exactly_five_percent_edge_is_allowed() -> None:
    request = replace(
        make_safe_request(),
        net_edge=Decimal("0.05"),
    )

    assert assess_risk(request).allowed is True


def test_more_than_one_contract_per_order_is_blocked() -> None:
    proposed = make_position(
        contracts=2,
        risk="0.20",
    )
    request = replace(
        make_safe_request(),
        proposed_position=proposed,
    )

    decision = assess_risk(request)

    assert "The order exceeds the contract limit." in decision.reasons


def test_order_risk_above_one_dollar_is_blocked() -> None:
    proposed = make_position(risk="1.01")
    request = replace(
        make_safe_request(),
        proposed_position=proposed,
    )

    decision = assess_risk(request)

    assert "The order exceeds the dollar-risk limit." in decision.reasons


def test_existing_contract_in_same_market_blocks_another() -> None:
    existing = make_position(risk="0.20")
    request = replace(
        make_safe_request(),
        existing_event_positions=(existing,),
    )

    decision = assess_risk(request)

    assert "The position exceeds the per-market limit." in decision.reasons


def test_correlated_yes_positions_can_lose_together() -> None:
    positions = (
        make_position(
            ticker="MARKET-A",
            bracket="79_or_below",
            side="yes",
            risk="0.80",
        ),
        make_position(
            ticker="MARKET-B",
            bracket="80_to_81",
            side="yes",
            risk="0.70",
        ),
    )

    risk = calculate_event_worst_case_risk(positions)

    assert risk == Decimal("1.50")


def test_no_positions_cannot_all_lose_in_one_outcome() -> None:
    positions = (
        make_position(
            ticker="MARKET-A",
            bracket="79_or_below",
            side="no",
            risk="0.80",
        ),
        make_position(
            ticker="MARKET-B",
            bracket="80_to_81",
            side="no",
            risk="0.70",
        ),
    )

    risk = calculate_event_worst_case_risk(positions)

    assert risk == Decimal("0.80")


def test_event_risk_above_three_dollars_is_blocked() -> None:
    existing = (
        make_position("MARKET-A", "bracket_a", risk="1.00"),
        make_position("MARKET-B", "bracket_b", risk="1.00"),
        make_position("MARKET-C", "bracket_c", risk="1.00"),
    )
    proposed = make_position(
        ticker="MARKET-D",
        bracket="bracket_d",
        risk="0.50",
    )
    request = replace(
        make_safe_request(),
        proposed_position=proposed,
        existing_event_positions=existing,
    )

    decision = assess_risk(request)

    assert decision.event_worst_case_risk_dollars == Decimal("3.50")
    assert (
        "Worst-case event risk exceeds the event limit."
        in decision.reasons
    )


def test_daily_exposure_above_ten_dollars_is_blocked() -> None:
    request = replace(
        make_safe_request(),
        other_daily_exposure_dollars=Decimal("9.70"),
    )

    decision = assess_risk(request)

    assert decision.daily_exposure_dollars == Decimal("10.10")
    assert (
        "Total daily exposure exceeds the daily limit."
        in decision.reasons
    )


def test_daily_loss_limit_blocks_new_trade() -> None:
    request = replace(
        make_safe_request(),
        daily_realized_loss_dollars=Decimal("5.00"),
    )

    decision = assess_risk(request)

    assert decision.allowed is False
    assert "The daily loss limit has been reached." in decision.reasons


def test_all_blocking_reasons_are_returned() -> None:
    request = replace(
        make_safe_request(),
        mode="live",
        kill_switch_active=True,
        quote_fresh=False,
        net_edge=Decimal("0.01"),
    )

    decision = assess_risk(request)

    assert decision.allowed is False
    assert len(decision.reasons) == 4


def test_invalid_position_is_rejected() -> None:
    proposed = make_position(contracts=0)
    request = replace(
        make_safe_request(),
        proposed_position=proposed,
    )

    with pytest.raises(
        ValueError,
        match="Position contracts must be positive",
    ):
        assess_risk(request)


def test_invalid_policy_is_rejected() -> None:
    policy = RiskPolicy(
        maximum_event_risk_dollars=Decimal(-1),
    )

    with pytest.raises(ValueError, match="Dollar limits must be positive"):
        assess_risk(make_safe_request(), policy)