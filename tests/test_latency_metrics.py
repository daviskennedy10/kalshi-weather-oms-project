from datetime import UTC, datetime, timedelta

import pytest

from weather_oms.analysis.latency_metrics import (
    DecisionTiming,
    calculate_latency_metrics,
)


def make_timing(
    decision_id: str,
    latency_seconds: int,
) -> DecisionTiming:
    retrieved_at = datetime(
        2026,
        9,
        15,
        15,
        50,
        tzinfo=UTC,
    )

    return DecisionTiming(
        decision_id=decision_id,
        quote_retrieved_at=retrieved_at,
        decision_stored_at=(
            retrieved_at
            + timedelta(seconds=latency_seconds)
        ),
    )


def test_empty_timings_return_empty_metrics() -> None:
    metrics = calculate_latency_metrics(())

    assert metrics.sample_count == 0
    assert metrics.minimum is None
    assert metrics.mean is None
    assert metrics.percentile_95 is None
    assert metrics.maximum is None


def test_calculates_latency_summary() -> None:
    timings = tuple(
        make_timing(
            decision_id=f"decision-{seconds}",
            latency_seconds=seconds,
        )
        for seconds in (1, 2, 3, 4, 10)
    )

    metrics = calculate_latency_metrics(timings)

    assert metrics.sample_count == 5
    assert metrics.minimum == timedelta(seconds=1)
    assert metrics.mean == timedelta(seconds=4)
    assert metrics.percentile_95 == timedelta(seconds=10)
    assert metrics.maximum == timedelta(seconds=10)


def test_single_timing_uses_same_value() -> None:
    metrics = calculate_latency_metrics(
        (make_timing("decision-1", 2),)
    )

    expected = timedelta(seconds=2)

    assert metrics.minimum == expected
    assert metrics.mean == expected
    assert metrics.percentile_95 == expected
    assert metrics.maximum == expected


def test_rejects_empty_decision_id() -> None:
    with pytest.raises(
        ValueError,
        match="decision_id cannot be empty",
    ):
        make_timing("", 1)


def test_rejects_naive_retrieval_time() -> None:
    with pytest.raises(
        ValueError,
        match="quote_retrieved_at",
    ):
        DecisionTiming(
            decision_id="decision-1",
            quote_retrieved_at=datetime(
                2026,
                9,
                15,
                15,
                50,
                tzinfo=UTC,
            ).replace(tzinfo=None),
            decision_stored_at=datetime(
                2026,
                9,
                15,
                15,
                51,
                tzinfo=UTC,
            ).replace(tzinfo=None),
        )


def test_rejects_naive_storage_time() -> None:
    with pytest.raises(
        ValueError,
        match="decision_stored_at",
    ):
        DecisionTiming(
            decision_id="decision-1",
            quote_retrieved_at=datetime(
                2026,
                9,
                15,
                15,
                50,
                tzinfo=UTC,
            ),
            decision_stored_at=datetime(
                2026,
                9,
                15,
                15,
                51,
                tzinfo=UTC,
            ).replace(tzinfo=None),
        )


def test_rejects_negative_latency() -> None:
    with pytest.raises(
        ValueError,
        match="cannot happen before",
    ):
        make_timing("decision-1", -1)