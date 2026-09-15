from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from weather_oms.execution.paper_decision_factory import (
    create_new_paper_risk_decision,
)
from weather_oms.execution.paper_planner import (
    PaperCandidate,
    PaperPlanItem,
    plan_paper_positions,
)
from weather_oms.execution.portfolio_risk import (
    PortfolioRiskSummary,
)
from weather_oms.signal.market_comparison import MarketComparison

TARGET_DATE = date(2026, 9, 10)
QUOTE_TIME = datetime(
    2026,
    9,
    9,
    15,
    49,
    tzinfo=UTC,
)


def make_comparison() -> MarketComparison:
    return MarketComparison(
        market_ticker="KXHIGHNY-26SEP10-T85",
        our_yes_probability=0.47,
        our_no_probability=0.53,
        yes_ask_cents=27,
        no_ask_cents=76,
        yes_fee_dollars=0.0138,
        no_fee_dollars=0.0128,
        yes_pre_fee_edge=0.20,
        no_pre_fee_edge=-0.23,
        yes_net_edge=0.186,
        no_net_edge=-0.243,
        minimum_net_edge=0.05,
        candidate_side="yes",
        candidate_edge=0.186,
    )


def empty_portfolio() -> PortfolioRiskSummary:
    return PortfolioRiskSummary(
        current_event_positions=(),
        current_event_risk_dollars=Decimal(0),
        other_event_risk_dollars=Decimal(0),
        total_daily_exposure_dollars=Decimal(0),
        daily_realized_loss_dollars=Decimal(0),
    )


def make_plan_item(
    kill_switch_active: bool = False,
) -> PaperPlanItem:
    candidate = PaperCandidate(
        bracket_id="KXHIGHNY-26SEP10-T85",
        comparison=make_comparison(),
    )

    plan = plan_paper_positions(
        candidates=(candidate,),
        portfolio=empty_portfolio(),
        kill_switch_active=kill_switch_active,
    )

    return plan[0]


def test_creates_allowed_audit_record() -> None:
    record = create_new_paper_risk_decision(
        plan_item=make_plan_item(),
        event_ticker="KXHIGHNY-26SEP10",
        target_date=TARGET_DATE,
        quote_retrieved_at=QUOTE_TIME,
        kill_switch_active=False,
    )

    assert record.market_ticker == "KXHIGHNY-26SEP10-T85"
    assert record.side == "yes"
    assert record.net_edge == Decimal("0.186")
    assert record.allowed is True
    assert record.reasons == ()
    assert record.proposed_risk_dollars == Decimal("0.2838")
    assert record.event_risk_after_dollars == Decimal("0.2838")
    assert record.daily_exposure_after_dollars == Decimal("0.2838")
    assert record.kill_switch_active is False
    assert record.model_probability == Decimal("0.47")
    assert record.contracts == 1



def test_creates_blocked_kill_switch_record() -> None:
    record = create_new_paper_risk_decision(
        plan_item=make_plan_item(
            kill_switch_active=True
        ),
        event_ticker="KXHIGHNY-26SEP10",
        target_date=TARGET_DATE,
        quote_retrieved_at=QUOTE_TIME,
        kill_switch_active=True,
    )

    assert record.allowed is False
    assert record.reasons == (
        "The kill switch is active.",
    )
    assert record.kill_switch_active is True


def test_same_decision_creates_same_id() -> None:
    first = create_new_paper_risk_decision(
        plan_item=make_plan_item(),
        event_ticker="KXHIGHNY-26SEP10",
        target_date=TARGET_DATE,
        quote_retrieved_at=QUOTE_TIME,
        kill_switch_active=False,
    )
    second = create_new_paper_risk_decision(
        plan_item=make_plan_item(),
        event_ticker="KXHIGHNY-26SEP10",
        target_date=TARGET_DATE,
        quote_retrieved_at=QUOTE_TIME,
        kill_switch_active=False,
    )

    assert first.decision_id == second.decision_id


def test_mismatched_market_is_rejected() -> None:
    plan_item = make_plan_item()

    changed_position = replace(
        plan_item.risk_request.proposed_position,
        market_ticker="DIFFERENT-MARKET",
    )
    changed_request = replace(
        plan_item.risk_request,
        proposed_position=changed_position,
    )
    changed_item = replace(
        plan_item,
        risk_request=changed_request,
    )

    with pytest.raises(
        ValueError,
        match="markets do not match",
    ):
        create_new_paper_risk_decision(
            plan_item=changed_item,
            event_ticker="KXHIGHNY-26SEP10",
            target_date=TARGET_DATE,
            quote_retrieved_at=QUOTE_TIME,
            kill_switch_active=False,
        )