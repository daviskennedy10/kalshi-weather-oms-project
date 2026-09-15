import hashlib
import json
from dataclasses import dataclass
from datetime import UTC

from weather_oms.events import OrderIntent


@dataclass(frozen=True, slots=True)
class IdempotencyKey:
    value: str


def key_for(
    intent: OrderIntent,
    decision_id: str,
) -> IdempotencyKey:
    """Create one stable key for every retry of the same order."""

    if not decision_id:
        raise ValueError("decision_id cannot be empty.")

    market_ticker = intent.market_ticker.strip().upper()

    if not market_ticker:
        raise ValueError("market_ticker cannot be empty.")

    side = intent.side.strip().lower()

    if side not in ("yes", "no"):
        raise ValueError("side must be yes or no.")

    if not 0 <= intent.price_cents <= 100:
        raise ValueError(
            "price_cents must be between 0 and 100."
        )

    if intent.count <= 0:
        raise ValueError("count must be positive.")

    if (
        not intent.model_probability.is_finite()
        or not 0
        <= intent.model_probability
        <= 1
    ):
        raise ValueError(
            "model_probability must be between 0 and 1."
        )

    if intent.event_received_time.tzinfo is None:
        raise ValueError(
            "event_received_time must include a timezone."
        )

    identity = {
        "decision_id": decision_id,
        "market_ticker": (
            intent.market_ticker.strip().upper()
        ),
        "side": side,
        "price_cents": intent.price_cents,
        "count": intent.count,
        "model_probability": format(
            intent.model_probability.normalize(),
            "f",
        ),
        "event_received_time": (
            intent.event_received_time
            .astimezone(UTC)
            .isoformat()
        ),
    }

    canonical_json = json.dumps(
        identity,
        sort_keys=True,
        separators=(",", ":"),
    )

    fingerprint = hashlib.sha256(
        canonical_json.encode("utf-8")
    ).hexdigest()

    return IdempotencyKey(
        value=f"oms-{fingerprint}"
    )