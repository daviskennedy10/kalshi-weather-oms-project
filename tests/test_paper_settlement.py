from decimal import Decimal

import pytest

from weather_oms.execution.paper_settlement import (
    calculate_paper_settlement,
)


def test_yes_position_wins_when_market_settles_yes() -> None:
    result = calculate_paper_settlement(
        position_side="yes",
        settlement_result="yes",
        contracts=1,
        entry_price_cents=27,
        fee_dollars=Decimal("0.0138"),
    )

    assert result.position_won is True
    assert result.contract_cost_dollars == Decimal("0.27")
    assert result.total_cost_dollars == Decimal("0.2838")
    assert result.payout_dollars == Decimal(1)
    assert result.realized_pnl_dollars == Decimal("0.7162")


def test_yes_position_loses_when_market_settles_no() -> None:
    result = calculate_paper_settlement(
        position_side="yes",
        settlement_result="no",
        contracts=1,
        entry_price_cents=27,
        fee_dollars=Decimal("0.0138"),
    )

    assert result.position_won is False
    assert result.payout_dollars == Decimal(0)
    assert result.realized_pnl_dollars == Decimal("-0.2838")


def test_no_position_wins_when_market_settles_no() -> None:
    result = calculate_paper_settlement(
        position_side="no",
        settlement_result="no",
        contracts=1,
        entry_price_cents=78,
        fee_dollars=Decimal("0.0121"),
    )

    assert result.position_won is True
    assert result.total_cost_dollars == Decimal("0.7921")
    assert result.payout_dollars == Decimal(1)
    assert result.realized_pnl_dollars == Decimal("0.2079")


def test_no_position_loses_when_market_settles_yes() -> None:
    result = calculate_paper_settlement(
        position_side="no",
        settlement_result="yes",
        contracts=1,
        entry_price_cents=78,
        fee_dollars=Decimal("0.0121"),
    )

    assert result.position_won is False
    assert result.payout_dollars == Decimal(0)
    assert result.realized_pnl_dollars == Decimal("-0.7921")


def test_multiple_contracts_receive_multiple_payouts() -> None:
    result = calculate_paper_settlement(
        position_side="yes",
        settlement_result="yes",
        contracts=2,
        entry_price_cents=40,
        fee_dollars=Decimal("0.02"),
    )

    assert result.contract_cost_dollars == Decimal("0.80")
    assert result.total_cost_dollars == Decimal("0.82")
    assert result.payout_dollars == Decimal(2)
    assert result.realized_pnl_dollars == Decimal("1.18")


def test_rejects_nonpositive_contract_count() -> None:
    with pytest.raises(
        ValueError,
        match="contracts must be positive",
    ):
        calculate_paper_settlement(
            position_side="yes",
            settlement_result="yes",
            contracts=0,
            entry_price_cents=40,
            fee_dollars=Decimal("0.01"),
        )


@pytest.mark.parametrize("price_cents", [-1, 101])
def test_rejects_invalid_entry_price(
    price_cents: int,
) -> None:
    with pytest.raises(
        ValueError,
        match="between 0 and 100",
    ):
        calculate_paper_settlement(
            position_side="yes",
            settlement_result="yes",
            contracts=1,
            entry_price_cents=price_cents,
            fee_dollars=Decimal("0.01"),
        )


def test_rejects_negative_fee() -> None:
    with pytest.raises(
        ValueError,
        match="fee_dollars cannot be negative",
    ):
        calculate_paper_settlement(
            position_side="yes",
            settlement_result="yes",
            contracts=1,
            entry_price_cents=40,
            fee_dollars=Decimal("-0.01"),
        )