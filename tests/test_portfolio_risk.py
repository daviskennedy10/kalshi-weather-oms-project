from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from weather_oms.execution.portfolio_risk import (
    summarize_portfolio_risk,
)
from weather_oms.storage.paper_position_repository import (
    PaperPositionStatus,
    PaperSide,
    StoredPaperPosition,
)


def make_position(
    order_id: str = "paper-order-1",
    event_ticker: str = "EVENT-A",
    market_ticker: str = "MARKET-A",
    side: PaperSide = "yes",
    price_cents: int = 40,
    fee_dollars: str = "0.00",
    status: PaperPositionStatus = "open",
    realized_pnl_dollars: Decimal | None = None,
) -> StoredPaperPosition:
    is_settled = status == "settled"

    return StoredPaperPosition(
        paper_order_id=order_id,
        event_ticker=event_ticker,
        market_ticker=market_ticker,
        target_date=date(2026, 9, 10),
        side=side,
        contracts=1,
        entry_price_cents=price_cents,
        fee_dollars=Decimal(fee_dollars),
        status=status,
        opened_at=datetime(2026, 9, 9, 15, 50, tzinfo=UTC),
        settlement_result="yes" if is_settled else None,
        payout_dollars=(
            Decimal("1.00")
            if is_settled
            else None
        ),
        realized_pnl_dollars=realized_pnl_dollars,
        settled_at=(
            datetime(2026, 9, 10, 23, 0, tzinfo=UTC)
            if is_settled
            else None
        ),
    )


def test_empty_portfolio_returns_zero_risk() -> None:
    summary = summarize_portfolio_risk(
        positions=(),
        current_event_ticker="EVENT-A",
    )

    assert summary.current_event_positions == ()
    assert summary.current_event_risk_dollars == Decimal(0)
    assert summary.other_event_risk_dollars == Decimal(0)
    assert summary.total_daily_exposure_dollars == Decimal(0)
    assert summary.daily_realized_loss_dollars == Decimal(0)


def test_current_event_positions_are_converted() -> None:
    positions = (
        make_position(
            order_id="order-1",
            market_ticker="MARKET-A",
            price_cents=40,
            fee_dollars="0.01",
        ),
    )

    summary = summarize_portfolio_risk(
        positions,
        current_event_ticker="EVENT-A",
    )

    assert len(summary.current_event_positions) == 1

    risk_position = summary.current_event_positions[0]

    assert risk_position.market_ticker == "MARKET-A"
    assert risk_position.bracket_id == "MARKET-A"
    assert risk_position.side == "yes"
    assert risk_position.risk_per_contract_dollars == Decimal("0.41")


def test_correlated_yes_positions_are_combined() -> None:
    positions = (
        make_position(
            order_id="order-1",
            market_ticker="MARKET-A",
            price_cents=40,
        ),
        make_position(
            order_id="order-2",
            market_ticker="MARKET-B",
            price_cents=30,
        ),
    )

    summary = summarize_portfolio_risk(
        positions,
        current_event_ticker="EVENT-A",
    )

    assert summary.current_event_risk_dollars == Decimal("0.70")
    assert summary.total_daily_exposure_dollars == Decimal("0.70")


def test_other_events_are_calculated_separately() -> None:
    positions = (
        make_position(
            order_id="order-1",
            event_ticker="EVENT-B",
            market_ticker="MARKET-B1",
            side="no",
            price_cents=80,
        ),
        make_position(
            order_id="order-2",
            event_ticker="EVENT-B",
            market_ticker="MARKET-B2",
            side="no",
            price_cents=70,
        ),
        make_position(
            order_id="order-3",
            event_ticker="EVENT-C",
            market_ticker="MARKET-C1",
            side="yes",
            price_cents=50,
        ),
    )

    summary = summarize_portfolio_risk(
        positions,
        current_event_ticker="EVENT-A",
    )

    # Only one NO position in EVENT-B can lose because
    # only one temperature bracket can win.
    assert summary.other_event_risk_dollars == Decimal("1.30")
    assert summary.total_daily_exposure_dollars == Decimal("1.30")


def test_settled_positions_do_not_count_as_open_exposure() -> None:
    settled = make_position(
        status="settled",
        realized_pnl_dollars=Decimal("-0.40"),
    )

    summary = summarize_portfolio_risk(
        (settled,),
        current_event_ticker="EVENT-A",
    )

    assert summary.current_event_positions == ()
    assert summary.total_daily_exposure_dollars == Decimal(0)


def test_losses_are_added_together() -> None:
    positions = (
        make_position(
            order_id="loss-1",
            status="settled",
            realized_pnl_dollars=Decimal("-0.40"),
        ),
        make_position(
            order_id="loss-2",
            market_ticker="MARKET-B",
            status="settled",
            realized_pnl_dollars=Decimal("-0.25"),
        ),
    )

    summary = summarize_portfolio_risk(
        positions,
        current_event_ticker="EVENT-A",
    )

    assert summary.daily_realized_loss_dollars == Decimal("0.65")


def test_profits_do_not_erase_daily_losses() -> None:
    positions = (
        make_position(
            order_id="loss",
            status="settled",
            realized_pnl_dollars=Decimal("-0.40"),
        ),
        make_position(
            order_id="profit",
            market_ticker="MARKET-B",
            status="settled",
            realized_pnl_dollars=Decimal("0.80"),
        ),
    )

    summary = summarize_portfolio_risk(
        positions,
        current_event_ticker="EVENT-A",
    )

    assert summary.daily_realized_loss_dollars == Decimal("0.40")


def test_rejects_empty_current_event_ticker() -> None:
    with pytest.raises(
        ValueError,
        match="current_event_ticker cannot be empty",
    ):
        summarize_portfolio_risk(
            positions=(),
            current_event_ticker="",
        )


def test_rejects_positions_from_multiple_dates() -> None:
    first = make_position(order_id="order-1")
    second = replace(
        make_position(order_id="order-2"),
        target_date=date(2026, 9, 11),
    )

    with pytest.raises(
        ValueError,
        match="same target date",
    ):
        summarize_portfolio_risk(
            positions=(first, second),
            current_event_ticker="EVENT-A",
        )