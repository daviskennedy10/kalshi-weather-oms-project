from decimal import Decimal

import pytest

from weather_oms.execution.fees import (
    calculate_taker_fee,
)


@pytest.mark.parametrize(
    ("price", "expected_fee"),
    [
        (Decimal("0.01"), Decimal("0.0007")),
        (Decimal("0.10"), Decimal("0.0063")),
        (Decimal("0.50"), Decimal("0.0175")),
        (Decimal("0.90"), Decimal("0.0063")),
        (Decimal("0.99"), Decimal("0.0007")),
    ],
)
def test_calculates_one_contract_taker_fee(
    price: Decimal,
    expected_fee: Decimal,
) -> None:
    assert calculate_taker_fee(price) == expected_fee


def test_rounds_fee_up_to_centicent() -> None:
    fee = calculate_taker_fee(
        Decimal("0.55"),
    )

    assert fee == Decimal("0.0174")


def test_calculates_fee_for_multiple_contracts() -> None:
    fee = calculate_taker_fee(
        price=Decimal("0.50"),
        contract_count=10,
    )

    assert fee == Decimal("0.1750")


@pytest.mark.parametrize(
    "invalid_price",
    [
        Decimal("-0.01"),
        Decimal("1.01"),
    ],
)
def test_rejects_invalid_price(
    invalid_price: Decimal,
) -> None:
    with pytest.raises(ValueError, match="between 0 and 1"):
        calculate_taker_fee(invalid_price)


def test_rejects_invalid_contract_count() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        calculate_taker_fee(
            Decimal("0.50"),
            contract_count=0,
        )