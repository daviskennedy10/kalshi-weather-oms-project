from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from weather_oms.events import OrderIntent
from weather_oms.oms.idempotency import key_for

EVENT_TIME = datetime(
    2026,
    9,
    14,
    15,
    50,
    tzinfo=UTC,
)


def make_intent() -> OrderIntent:
    return OrderIntent(
        market_ticker="KXHIGHNY-26SEP15-T85",
        side="yes",
        price_cents=27,
        count=1,
        model_probability=Decimal("0.47"),
        event_received_time=EVENT_TIME,
    )


def test_same_order_creates_same_key() -> None:
    first = key_for(make_intent(), "decision-1")
    second = key_for(make_intent(), "decision-1")

    assert first == second
    assert first.value.startswith("oms-")


def test_equivalent_timezones_create_same_key() -> None:
    local_zone = timezone(timedelta(hours=-4))
    local_intent = replace(
        make_intent(),
        event_received_time=EVENT_TIME.astimezone(
            local_zone
        ),
    )

    assert (
        key_for(make_intent(), "decision-1")
        == key_for(local_intent, "decision-1")
    )


def test_equivalent_probability_formats_create_same_key() -> None:
    first = make_intent()
    second = replace(
        first,
        model_probability=Decimal("0.4700"),
    )

    assert (
        key_for(first, "decision-1")
        == key_for(second, "decision-1")
    )


def test_market_case_and_whitespace_are_normalized() -> None:
    changed = replace(
        make_intent(),
        market_ticker="  kxhighny-26sep15-t85  ",
    )

    assert (
        key_for(make_intent(), "decision-1")
        == key_for(changed, "decision-1")
    )


def test_changed_price_creates_different_key() -> None:
    changed = replace(
        make_intent(),
        price_cents=28,
    )

    assert (
        key_for(make_intent(), "decision-1")
        != key_for(changed, "decision-1")
    )


def test_changed_quantity_creates_different_key() -> None:
    changed = replace(
        make_intent(),
        count=2,
    )

    assert (
        key_for(make_intent(), "decision-1")
        != key_for(changed, "decision-1")
    )


def test_changed_decision_creates_different_key() -> None:
    assert (
        key_for(make_intent(), "decision-1")
        != key_for(make_intent(), "decision-2")
    )


def test_rejects_empty_decision_id() -> None:
    with pytest.raises(
        ValueError,
        match="decision_id cannot be empty",
    ):
        key_for(make_intent(), "")


def test_rejects_blank_market() -> None:
    intent = replace(
        make_intent(),
        market_ticker="   ",
    )

    with pytest.raises(
        ValueError,
        match="market_ticker cannot be empty",
    ):
        key_for(intent, "decision-1")


def test_rejects_invalid_side() -> None:
    intent = replace(
        make_intent(),
        side="maybe",
    )

    with pytest.raises(
        ValueError,
        match="side must be yes or no",
    ):
        key_for(intent, "decision-1")


@pytest.mark.parametrize("price_cents", [-1, 101])
def test_rejects_invalid_price(
    price_cents: int,
) -> None:
    intent = replace(
        make_intent(),
        price_cents=price_cents,
    )

    with pytest.raises(
        ValueError,
        match="between 0 and 100",
    ):
        key_for(intent, "decision-1")


def test_rejects_nonpositive_count() -> None:
    intent = replace(
        make_intent(),
        count=0,
    )

    with pytest.raises(
        ValueError,
        match="count must be positive",
    ):
        key_for(intent, "decision-1")


@pytest.mark.parametrize(
    "probability",
    [
        Decimal("-0.01"),
        Decimal("1.01"),
        Decimal("NaN"),
    ],
)
def test_rejects_invalid_probability(
    probability: Decimal,
) -> None:
    intent = replace(
        make_intent(),
        model_probability=probability,
    )

    with pytest.raises(
        ValueError,
        match="between 0 and 1",
    ):
        key_for(intent, "decision-1")


def test_rejects_naive_event_time() -> None:
    intent = replace(
        make_intent(),
        event_received_time=(
            EVENT_TIME.replace(tzinfo=None)
        ),
    )

    with pytest.raises(
        ValueError,
        match="must include a timezone",
    ):
        key_for(intent, "decision-1")