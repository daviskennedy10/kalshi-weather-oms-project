from dataclasses import dataclass

from weather_oms.events import OrderIntent


@dataclass(frozen=True, slots=True)
class IdempotencyKey:
    value: str


def key_for(intent: OrderIntent, decision_id: str) -> IdempotencyKey:
    """YOUR CORE LOGIC: produce a stable key for retries of one economic decision."""
    # TODO(you): Decide which fields identify the decision, canonicalize them, then hash.
    # Explain why a random key generated per HTTP attempt would fail to prevent duplicates.
    raise NotImplementedError("Design and implement idempotency key generation")

