from dataclasses import replace
from decimal import Decimal

import pytest

from weather_oms.execution.position_sizing import (
    SizingPolicy,
    SizingRequest,
    size_position,
)


def make_request() -> SizingRequest:
    return SizingRequest(
        bankroll_dollars=Decimal("100.00"),
        side_probability=Decimal("0.70"),
        entry_price_dollars=Decimal("0.50"),
        fee_per_contract_dollars=Decimal("0.01"),
        available_risk_dollars=Decimal("3.00"),
        maximum_contracts=10,
    )


def test_sizes_with_quarter_kelly_and_risk_cap() -> None:
    decision = size_position(make_request())

    assert decision.should_trade is True
    assert decision.contracts == 5
    assert decision.total_risk_dollars == Decimal("2.55")
    assert decision.net_edge == Decimal("0.19")
    assert decision.full_kelly_fraction > Decimal(0)
    assert decision.applied_kelly_fraction > Decimal(0)


def test_contract_limit_can_reduce_size() -> None:
    request = replace(
        make_request(),
        maximum_contracts=2,
    )

    decision = size_position(request)

    assert decision.contracts == 2
    assert decision.total_risk_dollars == Decimal("1.02")


def test_available_risk_can_block_trade() -> None:
    request = replace(
        make_request(),
        available_risk_dollars=Decimal("0.40"),
    )

    decision = size_position(request)

    assert decision.should_trade is False
    assert decision.contracts == 0
    assert decision.total_risk_dollars == Decimal(0)
    assert decision.reason == (
        "Available risk cannot fund one contract."
    )


def test_low_edge_blocks_trade() -> None:
    request = replace(
        make_request(),
        side_probability=Decimal("0.54"),
    )

    decision = size_position(request)

    assert decision.should_trade is False
    assert decision.contracts == 0
    assert decision.net_edge == Decimal("0.03")
    assert decision.reason == (
        "Net edge is below the minimum."
    )


def test_custom_kelly_multiplier_changes_size() -> None:
    policy = SizingPolicy(
        minimum_net_edge=Decimal("0.05"),
        kelly_multiplier=Decimal("0.05"),
    )

    decision = size_position(
        make_request(),
        policy,
    )

    assert decision.contracts == 3
    assert decision.total_risk_dollars == Decimal("1.53")


def test_rejects_nonpositive_bankroll() -> None:
    request = replace(
        make_request(),
        bankroll_dollars=Decimal(0),
    )

    with pytest.raises(ValueError):
        size_position(request)


def test_rejects_invalid_probability() -> None:
    request = replace(
        make_request(),
        side_probability=Decimal("1.01"),
    )

    with pytest.raises(ValueError):
        size_position(request)


def test_rejects_invalid_entry_price() -> None:
    request = replace(
        make_request(),
        entry_price_dollars=Decimal(0),
    )

    with pytest.raises(ValueError):
        size_position(request)


def test_rejects_negative_fee() -> None:
    request = replace(
        make_request(),
        fee_per_contract_dollars=Decimal("-0.01"),
    )

    with pytest.raises(ValueError):
        size_position(request)


def test_rejects_negative_available_risk() -> None:
    request = replace(
        make_request(),
        available_risk_dollars=Decimal(-1),
    )

    with pytest.raises(ValueError):
        size_position(request)


def test_rejects_negative_contract_limit() -> None:
    request = replace(
        make_request(),
        maximum_contracts=-1,
    )

    with pytest.raises(ValueError):
        size_position(request)


def test_rejects_price_and_fee_of_one_dollar() -> None:
    request = replace(
        make_request(),
        entry_price_dollars=Decimal("0.99"),
        fee_per_contract_dollars=Decimal("0.01"),
    )

    with pytest.raises(
        ValueError,
        match="Price plus fee",
    ):
        size_position(request)


def test_rejects_invalid_policy() -> None:
    policy = SizingPolicy(
        kelly_multiplier=Decimal("1.01"),
    )

    with pytest.raises(
        ValueError,
        match="kelly_multiplier",
    ):
        size_position(
            make_request(),
            policy,
        )

def test_full_contract_limit_blocks_trade() -> None:
    request = replace(
        make_request(),
        maximum_contracts=0,
    )

    decision = size_position(request)

    assert decision.should_trade is False
    assert decision.contracts == 0
    assert decision.reason == (
        "The market contract limit is already full."
    )