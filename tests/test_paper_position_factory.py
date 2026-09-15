from dataclasses import replace
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from weather_oms.execution.paper_planner import (
    PaperCandidate,
    PaperPlanItem,
    plan_paper_positions,
)
from weather_oms.execution.paper_position_factory import (
    create_new_paper_position,
    create_paper_order_id,
)
from weather_oms.execution.portfolio_risk import (
    PortfolioRiskSummary,
)
from weather_oms.execution.risk import TradeSide
from weather_oms.signal.market_comparison import MarketComparison

TARGET_DATE = date(2026, 9, 10)
QUOTE_TIME = datetime(2026, 9, 9, 15, 49, tzinfo=UTC)


def make_comparison(
    side: TradeSide = "yes",
) -> MarketComparison:
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
        candidate_side=side,
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
    side: TradeSide = "yes",
    kill_switch_active: bool = False,
) -> PaperPlanItem:
    candidate = PaperCandidate(
        bracket_id="KXHIGHNY-26SEP10-T85",
        comparison=make_comparison(side),
    )

    plan = plan_paper_positions(
        candidates=(candidate,),
        portfolio=empty_portfolio(),
        kill_switch_active=kill_switch_active,
    )

    return plan[0]


def test_same_decision_creates_same_order_id() -> None:
    first = create_paper_order_id(
        event_ticker="KXHIGHNY-26SEP10",
        market_ticker="KXHIGHNY-26SEP10-T85",
        side="yes",
        target_date=TARGET_DATE,
        quote_retrieved_at=QUOTE_TIME,
    )
    second = create_paper_order_id(
        event_ticker="KXHIGHNY-26SEP10",
        market_ticker="KXHIGHNY-26SEP10-T85",
        side="yes",
        target_date=TARGET_DATE,
        quote_retrieved_at=QUOTE_TIME,
    )

    assert first == second
    assert first.startswith("paper-")


def test_equivalent_timezones_create_same_order_id() -> None:
    new_york_offset = timezone(
        timedelta(hours=-4)
    )
    local_time = QUOTE_TIME.astimezone(
        new_york_offset
    )

    utc_id = create_paper_order_id(
        event_ticker="KXHIGHNY-26SEP10",
        market_ticker="KXHIGHNY-26SEP10-T85",
        side="yes",
        target_date=TARGET_DATE,
        quote_retrieved_at=QUOTE_TIME,
    )
    local_id = create_paper_order_id(
        event_ticker="KXHIGHNY-26SEP10",
        market_ticker="KXHIGHNY-26SEP10-T85",
        side="yes",
        target_date=TARGET_DATE,
        quote_retrieved_at=local_time,
    )

    assert utc_id == local_id


def test_different_market_creates_different_order_id() -> None:
    first = create_paper_order_id(
        event_ticker="KXHIGHNY-26SEP10",
        market_ticker="MARKET-A",
        side="yes",
        target_date=TARGET_DATE,
        quote_retrieved_at=QUOTE_TIME,
    )
    second = create_paper_order_id(
        event_ticker="KXHIGHNY-26SEP10",
        market_ticker="MARKET-B",
        side="yes",
        target_date=TARGET_DATE,
        quote_retrieved_at=QUOTE_TIME,
    )

    assert first != second


def test_yes_plan_creates_open_position_data() -> None:
    position = create_new_paper_position(
        plan_item=make_plan_item("yes"),
        event_ticker="KXHIGHNY-26SEP10",
        target_date=TARGET_DATE,
        quote_retrieved_at=QUOTE_TIME,
    )

    assert position.side == "yes"
    assert position.contracts == 1
    assert position.entry_price_cents == 27
    assert position.fee_dollars == Decimal("0.0138")
    assert position.opened_at == QUOTE_TIME


def test_no_plan_uses_no_price_and_fee() -> None:
    position = create_new_paper_position(
        plan_item=make_plan_item("no"),
        event_ticker="KXHIGHNY-26SEP10",
        target_date=TARGET_DATE,
        quote_retrieved_at=QUOTE_TIME,
    )

    assert position.side == "no"
    assert position.entry_price_cents == 76
    assert position.fee_dollars == Decimal("0.0128")


def test_blocked_plan_cannot_create_position() -> None:
    blocked_item = make_plan_item(
        kill_switch_active=True
    )

    with pytest.raises(
        ValueError,
        match="blocked plan item",
    ):
        create_new_paper_position(
            plan_item=blocked_item,
            event_ticker="KXHIGHNY-26SEP10",
            target_date=TARGET_DATE,
            quote_retrieved_at=QUOTE_TIME,
        )


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
        create_new_paper_position(
            plan_item=changed_item,
            event_ticker="KXHIGHNY-26SEP10",
            target_date=TARGET_DATE,
            quote_retrieved_at=QUOTE_TIME,
        )


def test_naive_quote_time_is_rejected() -> None:
    naive_time = QUOTE_TIME.replace(tzinfo=None)

    with pytest.raises(
        ValueError,
        match="must include a timezone",
    ):
        create_paper_order_id(
            event_ticker="KXHIGHNY-26SEP10",
            market_ticker="KXHIGHNY-26SEP10-T85",
            side="yes",
            target_date=TARGET_DATE,
            quote_retrieved_at=naive_time,
        )