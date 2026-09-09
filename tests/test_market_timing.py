from datetime import UTC, datetime, timedelta

import pytest

from weather_oms.signal.market_timing import (
    calculate_quote_age,
)


def test_accepts_fresh_quote() -> None:
    decision_at = datetime(
        2026,
        9,
        9,
        16,
        tzinfo=UTC,
    )
    retrieved_at = decision_at - timedelta(
        minutes=10
    )

    age = calculate_quote_age(
        retrieved_at,
        decision_at,
    )

    assert age == timedelta(minutes=10)


def test_accepts_quote_at_maximum_age() -> None:
    decision_at = datetime(
        2026,
        9,
        9,
        16,
        tzinfo=UTC,
    )
    retrieved_at = decision_at - timedelta(
        minutes=15
    )

    age = calculate_quote_age(
        retrieved_at,
        decision_at,
    )

    assert age == timedelta(minutes=15)


def test_rejects_stale_quote() -> None:
    decision_at = datetime(
        2026,
        9,
        9,
        16,
        tzinfo=UTC,
    )
    retrieved_at = decision_at - timedelta(
        minutes=16
    )

    with pytest.raises(ValueError, match="too old"):
        calculate_quote_age(
            retrieved_at,
            decision_at,
        )


def test_rejects_quote_after_decision() -> None:
    decision_at = datetime(
        2026,
        9,
        9,
        16,
        tzinfo=UTC,
    )
    retrieved_at = decision_at + timedelta(
        seconds=1
    )

    with pytest.raises(ValueError, match="after"):
        calculate_quote_age(
            retrieved_at,
            decision_at,
        )


def test_rejects_invalid_maximum_age() -> None:
    timestamp = datetime(
        2026,
        9,
        9,
        16,
        tzinfo=UTC,
    )

    with pytest.raises(ValueError, match="positive"):
        calculate_quote_age(
            timestamp,
            timestamp,
            maximum_age=timedelta(0),
        )