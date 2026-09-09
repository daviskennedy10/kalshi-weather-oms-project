from decimal import ROUND_CEILING, Decimal

GENERAL_TAKER_FEE_RATE = Decimal("0.07")
CENTICENT = Decimal("0.0001")


def calculate_taker_fee(
    price: Decimal,
    contract_count: int = 1,
    multiplier: Decimal = Decimal(1),
) -> Decimal:
    if not Decimal(0) <= price <= Decimal(1):
        raise ValueError(
            "price must be between 0 and 1."
        )

    if contract_count < 1:
        raise ValueError(
            "contract_count must be at least 1."
        )

    if multiplier <= 0:
        raise ValueError(
            "multiplier must be positive."
        )

    unrounded_fee = (
        multiplier
        * GENERAL_TAKER_FEE_RATE
        * contract_count
        * price
        * (Decimal(1) - price)
    )

    return unrounded_fee.quantize(
        CENTICENT,
        rounding=ROUND_CEILING,
    )