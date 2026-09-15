from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from weather_oms.analysis.paper_performance import (
    calculate_paper_performance,
)
from weather_oms.storage.paper_position_repository import (
    StoredPaperPosition,
)


def make_settled_position(
    *,
    paper_order_id: str,
    side: str,
    settlement_result: str,
    cost: Decimal,
    payout: Decimal,
    pnl: Decimal,
    settled_hour: int,
) -> StoredPaperPosition:
    contracts = 1
    entry_price_cents = int(cost * 100)

    return StoredPaperPosition(
        paper_order_id=paper_order_id,
        event_ticker="KXHIGHNY-26SEP15",
        market_ticker="KXHIGHNY-26SEP15-T85",
        target_date=date(2026, 9, 15),
        side=side,  # type: ignore[arg-type]
        contracts=contracts,
        entry_price_cents=entry_price_cents,
        fee_dollars=Decimal(0),
        status="settled",
        opened_at=datetime(
            2026,
            9,
            14,
            15,
            50,
            tzinfo=UTC,
        ),
        settlement_result=settlement_result,  # type: ignore[arg-type]
        payout_dollars=payout,
        realized_pnl_dollars=pnl,
        settled_at=datetime(
            2026,
            9,
            15,
            settled_hour,
            0,
            tzinfo=UTC,
        ),
    )


def make_open_position() -> StoredPaperPosition:
    return StoredPaperPosition(
        paper_order_id="paper-open",
        event_ticker="KXHIGHNY-26SEP16",
        market_ticker="KXHIGHNY-26SEP16-T85",
        target_date=date(2026, 9, 16),
        side="yes",
        contracts=1,
        entry_price_cents=40,
        fee_dollars=Decimal("0.01"),
        status="open",
        opened_at=datetime(
            2026,
            9,
            15,
            15,
            50,
            tzinfo=UTC,
        ),
        settlement_result=None,
        payout_dollars=None,
        realized_pnl_dollars=None,
        settled_at=None,
    )


def test_empty_performance_is_zero() -> None:
    performance = calculate_paper_performance(())

    assert performance.total_positions == 0
    assert performance.settled_positions == 0
    assert performance.total_pnl_dollars == Decimal(0)
    assert performance.win_rate is None
    assert performance.return_on_cost is None


def test_summarizes_open_and_settled_positions() -> None:
    winner = make_settled_position(
        paper_order_id="paper-win",
        side="yes",
        settlement_result="yes",
        cost=Decimal("0.40"),
        payout=Decimal("1.00"),
        pnl=Decimal("0.60"),
        settled_hour=12,
    )
    loser = make_settled_position(
        paper_order_id="paper-loss",
        side="no",
        settlement_result="yes",
        cost=Decimal("0.30"),
        payout=Decimal("0.00"),
        pnl=Decimal("-0.30"),
        settled_hour=13,
    )

    performance = calculate_paper_performance(
        (winner, loser, make_open_position())
    )

    assert performance.total_positions == 3
    assert performance.open_positions == 1
    assert performance.settled_positions == 2
    assert performance.settled_contracts == 2
    assert performance.winning_positions == 1
    assert performance.losing_positions == 1
    assert performance.win_rate == Decimal("0.5")
    assert (
        performance.total_cost_dollars
        == Decimal("0.70")
    )
    assert (
        performance.total_payout_dollars
        == Decimal("1.00")
    )
    assert (
        performance.total_pnl_dollars
        == Decimal("0.30")
    )
    assert (
        performance.average_pnl_dollars
        == Decimal("0.15")
    )
    assert (
        performance.return_on_cost
        == Decimal("0.30") / Decimal("0.70")
    )
    assert (
        performance.maximum_drawdown_dollars
        == Decimal("0.30")
    )


def test_detects_pnl_inconsistency() -> None:
    position = make_settled_position(
        paper_order_id="paper-bad",
        side="yes",
        settlement_result="yes",
        cost=Decimal("0.40"),
        payout=Decimal("1.00"),
        pnl=Decimal("0.50"),
        settled_hour=12,
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        calculate_paper_performance((position,))


def test_rejects_settled_position_with_missing_data() -> None:
    position = make_settled_position(
        paper_order_id="paper-missing",
        side="yes",
        settlement_result="yes",
        cost=Decimal("0.40"),
        payout=Decimal("1.00"),
        pnl=Decimal("0.60"),
        settled_hour=12,
    )
    incomplete = replace(
        position,
        settled_at=None,
    )

    with pytest.raises(
        ValueError,
        match="complete settlement data",
    ):
        calculate_paper_performance((incomplete,))


def test_rejects_open_position_with_settlement_data() -> None:
    position = replace(
        make_open_position(),
        payout_dollars=Decimal("1.00"),
    )

    with pytest.raises(
        ValueError,
        match="cannot contain settlement data",
    ):
        calculate_paper_performance((position,))