from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from weather_oms.dashboard.summary import (
    build_dashboard_summary,
)
from weather_oms.storage.paper_analysis_repository import (
    PaperProbabilityObservation,
)
from weather_oms.storage.paper_position_repository import (
    StoredPaperPosition,
)
from weather_oms.storage.paper_risk_decision_repository import (
    StoredPaperDecisionMetric,
    StoredPaperDecisionTiming,
)


def make_position() -> StoredPaperPosition:
    opened_at = datetime(
        2026,
        9,
        14,
        15,
        50,
        tzinfo=UTC,
    )

    return StoredPaperPosition(
        paper_order_id="paper-1",
        event_ticker="KXHIGHNY-26SEP15",
        market_ticker="KXHIGHNY-26SEP15-T85",
        target_date=date(2026, 9, 15),
        side="yes",
        contracts=1,
        entry_price_cents=40,
        fee_dollars=Decimal(0),
        status="settled",
        opened_at=opened_at,
        settlement_result="yes",
        payout_dollars=Decimal("1.00"),
        realized_pnl_dollars=Decimal("0.60"),
        settled_at=opened_at + timedelta(days=1),
    )


def make_timing() -> StoredPaperDecisionTiming:
    quote_time = datetime(
        2026,
        9,
        14,
        15,
        49,
        tzinfo=UTC,
    )

    return StoredPaperDecisionTiming(
        decision_id="decision-1",
        quote_retrieved_at=quote_time,
        stored_at=quote_time + timedelta(seconds=2),
    )

def make_decision_metric() -> StoredPaperDecisionMetric:
    return StoredPaperDecisionMetric(
        market_ticker="KXHIGHNY-26SEP15-T85",
        side="yes",
        contracts=1,
        model_probability=Decimal("0.70"),
        net_edge=Decimal("0.15"),
        quote_retrieved_at=datetime(
            2026,
            9,
            14,
            15,
            50,
            tzinfo=UTC,
        ),
    )


def make_observation() -> PaperProbabilityObservation:
    return PaperProbabilityObservation(
        decision_id="decision-1",
        target_date=date(2026, 9, 15),
        market_ticker="KXHIGHNY-26SEP15-T85",
        side="yes",
        model_probability=Decimal("0.70"),
        outcome=1,
    )


def test_builds_complete_dashboard_summary() -> None:
    summary = build_dashboard_summary(
        positions=(make_position(),),
        stored_timings=(make_timing(),),
        observations=(make_observation(),),
        decision_metrics=(make_decision_metric(),),
    )

    assert summary.performance.total_positions == 1
    assert (
        summary.performance.total_pnl_dollars
        == Decimal("0.60")
    )
    assert summary.latency.sample_count == 1
    assert summary.latency.mean == timedelta(seconds=2)
    assert summary.probability is not None
    assert summary.probability.sample_count == 1
    assert summary.probability.brier_score == pytest.approx(
        0.09
    )
    assert len(summary.positions) == 1
    assert (
        summary.positions[0].model_probability
        == Decimal("0.70")
    )
    assert (
        summary.positions[0].net_edge
        == Decimal("0.15")
    )


def test_builds_empty_dashboard_summary() -> None:
    summary = build_dashboard_summary(
        positions=(),
        stored_timings=(),
        observations=(),
        decision_metrics=(),
    )

    assert summary.performance.total_positions == 0
    assert summary.latency.sample_count == 0
    assert summary.probability is None