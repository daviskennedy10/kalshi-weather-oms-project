from decimal import Decimal

import pytest

from weather_oms.execution.paper_planner import (
    PaperCandidate,
    plan_paper_positions,
)
from weather_oms.execution.portfolio_risk import (
    PortfolioRiskSummary,
)
from weather_oms.execution.risk import (
    PositionRisk,
    RiskPolicy,
    TradeSide,
)
from weather_oms.signal.market_comparison import MarketComparison


def make_comparison(
    ticker: str,
    side: TradeSide | None,
    candidate_edge: float,
    yes_ask_cents: int = 40,
    no_ask_cents: int = 60,
    yes_fee_dollars: float = 0.0,
    no_fee_dollars: float = 0.0,
) -> MarketComparison:
    return MarketComparison(
        market_ticker=ticker,
        our_yes_probability=0.70,
        our_no_probability=0.30,
        yes_ask_cents=yes_ask_cents,
        no_ask_cents=no_ask_cents,
        yes_fee_dollars=yes_fee_dollars,
        no_fee_dollars=no_fee_dollars,
        yes_pre_fee_edge=candidate_edge,
        no_pre_fee_edge=candidate_edge,
        yes_net_edge=candidate_edge,
        no_net_edge=candidate_edge,
        minimum_net_edge=0.05,
        candidate_side=side,
        candidate_edge=candidate_edge,
    )


def empty_portfolio() -> PortfolioRiskSummary:
    return PortfolioRiskSummary(
        current_event_positions=(),
        current_event_risk_dollars=Decimal(0),
        other_event_risk_dollars=Decimal(0),
        total_daily_exposure_dollars=Decimal(0),
        daily_realized_loss_dollars=Decimal(0),
    )


def test_empty_candidates_return_empty_plan() -> None:
    plan = plan_paper_positions(
        candidates=(),
        portfolio=empty_portfolio(),
    )

    assert plan == ()


def test_candidates_are_processed_highest_edge_first() -> None:
    lower_edge = PaperCandidate(
        bracket_id="MARKET-LOW",
        comparison=make_comparison(
            ticker="MARKET-LOW",
            side="yes",
            candidate_edge=0.08,
        ),
    )
    higher_edge = PaperCandidate(
        bracket_id="MARKET-HIGH",
        comparison=make_comparison(
            ticker="MARKET-HIGH",
            side="yes",
            candidate_edge=0.18,
        ),
    )

    plan = plan_paper_positions(
        candidates=(lower_edge, higher_edge),
        portfolio=empty_portfolio(),
    )

    assert plan[0].candidate == higher_edge
    assert plan[1].candidate == lower_edge


def test_allowed_position_affects_next_candidate() -> None:
    first = PaperCandidate(
        bracket_id="BRACKET-A",
        comparison=make_comparison(
            ticker="MARKET-A",
            side="yes",
            candidate_edge=0.20,
            yes_ask_cents=40,
        ),
    )
    second = PaperCandidate(
        bracket_id="BRACKET-B",
        comparison=make_comparison(
            ticker="MARKET-B",
            side="yes",
            candidate_edge=0.10,
            yes_ask_cents=30,
        ),
    )
    policy = RiskPolicy(
        maximum_event_risk_dollars=Decimal("0.50"),
    )

    plan = plan_paper_positions(
        candidates=(second, first),
        portfolio=empty_portfolio(),
        policy=policy,
    )

    assert plan[0].risk_decision.allowed is True
    assert (
        plan[0].risk_decision.event_worst_case_risk_dollars
        == Decimal("0.40")
    )

    assert plan[1].risk_decision.allowed is False
    assert (
        plan[1].risk_decision.event_worst_case_risk_dollars
        == Decimal("0.70")
    )
    assert (
        "Worst-case event risk exceeds the event limit."
        in plan[1].risk_decision.reasons
    )


def test_real_aligned_candidates_can_be_evaluated_together() -> None:
    lower_temperature_yes = PaperCandidate(
        bracket_id="KXHIGHNY-26SEP10-T85",
        comparison=make_comparison(
            ticker="KXHIGHNY-26SEP10-T85",
            side="yes",
            candidate_edge=0.186,
            yes_ask_cents=27,
            yes_fee_dollars=0.0138,
        ),
    )
    middle_temperature_no = PaperCandidate(
        bracket_id="KXHIGHNY-26SEP10-B87.5",
        comparison=make_comparison(
            ticker="KXHIGHNY-26SEP10-B87.5",
            side="no",
            candidate_edge=0.081,
            no_ask_cents=78,
            no_fee_dollars=0.0121,
        ),
    )

    plan = plan_paper_positions(
        candidates=(
            middle_temperature_no,
            lower_temperature_yes,
        ),
        portfolio=empty_portfolio(),
    )

    assert len(plan) == 2
    assert plan[0].risk_decision.allowed is True
    assert plan[1].risk_decision.allowed is True
    assert (
        plan[1].risk_decision.event_worst_case_risk_dollars
        == Decimal("1.0759")
    )


def test_existing_same_market_position_blocks_candidate() -> None:
    existing = PositionRisk(
        market_ticker="MARKET-A",
        bracket_id="BRACKET-A",
        side="yes",
        contracts=1,
        risk_per_contract_dollars=Decimal("0.30"),
    )
    portfolio = PortfolioRiskSummary(
        current_event_positions=(existing,),
        current_event_risk_dollars=Decimal("0.30"),
        other_event_risk_dollars=Decimal(0),
        total_daily_exposure_dollars=Decimal("0.30"),
        daily_realized_loss_dollars=Decimal(0),
    )
    candidate = PaperCandidate(
        bracket_id="BRACKET-A",
        comparison=make_comparison(
            ticker="MARKET-A",
            side="yes",
            candidate_edge=0.15,
        ),
    )

    plan = plan_paper_positions(
        candidates=(candidate,),
        portfolio=portfolio,
    )

    assert plan[0].risk_decision.allowed is False
    assert (
        "The position exceeds the per-market limit."
        in plan[0].risk_decision.reasons
    )


def test_kill_switch_blocks_every_candidate() -> None:
    candidates = (
        PaperCandidate(
            bracket_id="BRACKET-A",
            comparison=make_comparison(
                ticker="MARKET-A",
                side="yes",
                candidate_edge=0.20,
            ),
        ),
        PaperCandidate(
            bracket_id="BRACKET-B",
            comparison=make_comparison(
                ticker="MARKET-B",
                side="yes",
                candidate_edge=0.10,
            ),
        ),
    )

    plan = plan_paper_positions(
        candidates=candidates,
        portfolio=empty_portfolio(),
        kill_switch_active=True,
    )

    assert all(
        not item.risk_decision.allowed
        for item in plan
    )
    assert all(
        "The kill switch is active."
        in item.risk_decision.reasons
        for item in plan
    )


def test_candidate_without_side_is_rejected() -> None:
    candidate = PaperCandidate(
        bracket_id="BRACKET-A",
        comparison=make_comparison(
            ticker="MARKET-A",
            side=None,
            candidate_edge=0.0,
        ),
    )

    with pytest.raises(
        ValueError,
        match="must have a candidate side",
    ):
        plan_paper_positions(
            candidates=(candidate,),
            portfolio=empty_portfolio(),
        )


def test_candidate_without_bracket_is_rejected() -> None:
    candidate = PaperCandidate(
        bracket_id="",
        comparison=make_comparison(
            ticker="MARKET-A",
            side="yes",
            candidate_edge=0.10,
        ),
    )

    with pytest.raises(
        ValueError,
        match="bracket_id cannot be empty",
    ):
        plan_paper_positions(
            candidates=(candidate,),
            portfolio=empty_portfolio(),
        )

def test_candidate_contract_count_reaches_risk_engine() -> None:
    candidate = PaperCandidate(
        bracket_id="BRACKET-A",
        comparison=make_comparison(
            ticker="MARKET-A",
            side="yes",
            candidate_edge=0.20,
            yes_ask_cents=40,
        ),
        contracts=3,
    )
    policy = RiskPolicy(
        maximum_contracts_per_order=3,
        maximum_contracts_per_market=3,
        maximum_order_risk_dollars=Decimal("2.00"),
        maximum_event_risk_dollars=Decimal("3.00"),
    )

    plan = plan_paper_positions(
        candidates=(candidate,),
        portfolio=empty_portfolio(),
        policy=policy,
    )

    assert (
        plan[0].risk_request.proposed_position.contracts
        == 3
    )
    assert (
        plan[0].risk_request.proposed_position.total_risk_dollars
        == Decimal("1.20")
    )
    assert plan[0].risk_decision.allowed is True


def test_nonpositive_candidate_contracts_are_rejected() -> None:
    candidate = PaperCandidate(
        bracket_id="BRACKET-A",
        comparison=make_comparison(
            ticker="MARKET-A",
            side="yes",
            candidate_edge=0.20,
        ),
        contracts=0,
    )

    with pytest.raises(
        ValueError,
        match="contracts must be positive",
    ):
        plan_paper_positions(
            candidates=(candidate,),
            portfolio=empty_portfolio(),
        )