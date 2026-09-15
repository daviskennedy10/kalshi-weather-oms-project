from decimal import Decimal

import pytest

from weather_oms.execution.paper_sizing import (
    size_paper_candidate,
)
from weather_oms.execution.portfolio_risk import (
    PortfolioRiskSummary,
)
from weather_oms.execution.risk import (
    PositionRisk,
    RiskPolicy,
)
from weather_oms.signal.market_comparison import MarketComparison


def make_comparison() -> MarketComparison:
    return MarketComparison(
        market_ticker="KXHIGHNY-26SEP15-T85",
        our_yes_probability=0.70,
        our_no_probability=0.30,
        yes_ask_cents=50,
        no_ask_cents=50,
        yes_fee_dollars=0.01,
        no_fee_dollars=0.01,
        yes_pre_fee_edge=0.20,
        no_pre_fee_edge=-0.20,
        yes_net_edge=0.19,
        no_net_edge=-0.21,
        minimum_net_edge=0.05,
        candidate_side="yes",
        candidate_edge=0.19,
    )


def empty_portfolio() -> PortfolioRiskSummary:
    return PortfolioRiskSummary(
        current_event_positions=(),
        current_event_risk_dollars=Decimal(0),
        other_event_risk_dollars=Decimal(0),
        total_daily_exposure_dollars=Decimal(0),
        daily_realized_loss_dollars=Decimal(0),
    )


def test_default_policy_sizes_one_contract() -> None:
    decision = size_paper_candidate(
        comparison=make_comparison(),
        portfolio=empty_portfolio(),
        bankroll_dollars=Decimal("100.00"),
    )

    assert decision.should_trade is True
    assert decision.contracts == 1
    assert decision.total_risk_dollars == Decimal("0.51")


def test_custom_limits_allow_multiple_contracts() -> None:
    policy = RiskPolicy(
        maximum_contracts_per_order=10,
        maximum_contracts_per_market=10,
        maximum_order_risk_dollars=Decimal("3.00"),
    )

    decision = size_paper_candidate(
        comparison=make_comparison(),
        portfolio=empty_portfolio(),
        bankroll_dollars=Decimal("100.00"),
        risk_policy=policy,
    )

    assert decision.contracts == 5
    assert decision.total_risk_dollars == Decimal("2.55")


def test_existing_market_limit_blocks_size() -> None:
    existing = PositionRisk(
        market_ticker="KXHIGHNY-26SEP15-T85",
        bracket_id="KXHIGHNY-26SEP15-T85",
        side="yes",
        contracts=1,
        risk_per_contract_dollars=Decimal("0.51"),
    )
    portfolio = PortfolioRiskSummary(
        current_event_positions=(existing,),
        current_event_risk_dollars=Decimal("0.51"),
        other_event_risk_dollars=Decimal(0),
        total_daily_exposure_dollars=Decimal("0.51"),
        daily_realized_loss_dollars=Decimal(0),
    )

    decision = size_paper_candidate(
        comparison=make_comparison(),
        portfolio=portfolio,
        bankroll_dollars=Decimal("100.00"),
    )

    assert decision.should_trade is False
    assert decision.reason == (
        "The market contract limit is already full."
    )


def test_daily_headroom_can_block_size() -> None:
    portfolio = PortfolioRiskSummary(
        current_event_positions=(),
        current_event_risk_dollars=Decimal(0),
        other_event_risk_dollars=Decimal("9.80"),
        total_daily_exposure_dollars=Decimal("9.80"),
        daily_realized_loss_dollars=Decimal(0),
    )

    decision = size_paper_candidate(
        comparison=make_comparison(),
        portfolio=portfolio,
        bankroll_dollars=Decimal("100.00"),
    )

    assert decision.should_trade is False
    assert decision.reason == (
        "Available risk cannot fund one contract."
    )


def test_comparison_without_side_is_rejected() -> None:
    comparison = make_comparison()
    comparison_without_side = MarketComparison(
        market_ticker=comparison.market_ticker,
        our_yes_probability=comparison.our_yes_probability,
        our_no_probability=comparison.our_no_probability,
        yes_ask_cents=comparison.yes_ask_cents,
        no_ask_cents=comparison.no_ask_cents,
        yes_fee_dollars=comparison.yes_fee_dollars,
        no_fee_dollars=comparison.no_fee_dollars,
        yes_pre_fee_edge=comparison.yes_pre_fee_edge,
        no_pre_fee_edge=comparison.no_pre_fee_edge,
        yes_net_edge=comparison.yes_net_edge,
        no_net_edge=comparison.no_net_edge,
        minimum_net_edge=comparison.minimum_net_edge,
        candidate_side=None,
        candidate_edge=0.0,
    )

    with pytest.raises(
        ValueError,
        match="without a candidate side",
    ):
        size_paper_candidate(
            comparison=comparison_without_side,
            portfolio=empty_portfolio(),
            bankroll_dollars=Decimal("100.00"),
        )