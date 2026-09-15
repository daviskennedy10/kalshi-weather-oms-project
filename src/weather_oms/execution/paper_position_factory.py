import hashlib
from datetime import UTC, date, datetime
from decimal import Decimal

from weather_oms.execution.paper_planner import PaperPlanItem
from weather_oms.execution.risk import TradeSide
from weather_oms.storage.paper_position_repository import (
    NewPaperPosition,
)


def create_paper_order_id(
    event_ticker: str,
    market_ticker: str,
    side: TradeSide,
    target_date: date,
    quote_retrieved_at: datetime,
) -> str:
    """Create the same ID whenever the same decision is repeated."""

    if not event_ticker or not market_ticker:
        raise ValueError("Paper-order identifiers cannot be empty.")

    if quote_retrieved_at.tzinfo is None:
        raise ValueError(
            "quote_retrieved_at must include a timezone."
        )

    normalized_time = quote_retrieved_at.astimezone(UTC)

    identity = (
        f"{event_ticker}|{market_ticker}|{side}|"
        f"{target_date.isoformat()}|"
        f"{normalized_time.isoformat()}"
    )

    fingerprint = hashlib.sha256(
        identity.encode("utf-8")
    ).hexdigest()

    return f"paper-{fingerprint}"


def create_new_paper_position(
    plan_item: PaperPlanItem,
    event_ticker: str,
    target_date: date,
    quote_retrieved_at: datetime,
) -> NewPaperPosition:
    """Convert an allowed plan item into a database-ready position."""

    if not plan_item.risk_decision.allowed:
        raise ValueError(
            "Cannot create a paper position from a blocked plan item."
        )

    comparison = plan_item.candidate.comparison
    proposed = plan_item.risk_request.proposed_position
    side = comparison.candidate_side

    if side is None:
        raise ValueError(
            "Cannot create a paper position without a side."
        )

    if comparison.market_ticker != proposed.market_ticker:
        raise ValueError(
            "Comparison and proposed position markets do not match."
        )

    if side != proposed.side:
        raise ValueError(
            "Comparison and proposed position sides do not match."
        )

    if side == "yes":
        entry_price_cents = comparison.yes_ask_cents
        fee_dollars = Decimal(
            str(comparison.yes_fee_dollars)
        )
    else:
        entry_price_cents = comparison.no_ask_cents
        fee_dollars = Decimal(
            str(comparison.no_fee_dollars)
        )

    paper_order_id = create_paper_order_id(
        event_ticker=event_ticker,
        market_ticker=comparison.market_ticker,
        side=side,
        target_date=target_date,
        quote_retrieved_at=quote_retrieved_at,
    )

    return NewPaperPosition(
        paper_order_id=paper_order_id,
        event_ticker=event_ticker,
        market_ticker=comparison.market_ticker,
        target_date=target_date,
        side=side,
        contracts=proposed.contracts,
        entry_price_cents=entry_price_cents,
        fee_dollars=fee_dollars,
        opened_at=quote_retrieved_at.astimezone(UTC),
    )