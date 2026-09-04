from decimal import Decimal


def fractional_kelly(
    probability: Decimal,
    price: Decimal,
    bankroll: Decimal,
    fraction: Decimal,
    max_risk: Decimal,
) -> Decimal:
    """YOUR CORE LOGIC: size a binary contract with a capped fractional Kelly rule."""
    # TODO(you): Derive binary Kelly from payoff/price, validate inputs, apply the fraction,
    # clamp negative edge to zero, cap risk, and choose a rounding policy for contracts.
    raise NotImplementedError("Derive and implement fractional Kelly sizing")

