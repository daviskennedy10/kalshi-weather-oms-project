from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from weather_oms.ingest.kalshi_market_parser import (
    KalshiTemperatureMarket,
)
from weather_oms.signal.market_probability import (
    TemperatureBracket,
)
from weather_oms.storage.models import MarketQuoteSnapshot


async def save_market_quote_snapshot(
    session: AsyncSession,
    event_ticker: str,
    target_date: date,
    markets: list[KalshiTemperatureMarket],
    retrieved_at: datetime,
) -> int:
    if retrieved_at.tzinfo is None:
        raise ValueError(
            "retrieved_at must include a timezone."
        )

    if not markets:
        raise ValueError(
            "At least one Kalshi market is required."
        )

    normalized_retrieved_at = retrieved_at.astimezone(UTC)

    rows = [
        {
            "event_ticker": event_ticker,
            "market_ticker": market.ticker,
            "target_date": target_date,
            "lower_f": market.bracket.lower_f,
            "upper_f": market.bracket.upper_f,
            "yes_bid_cents": market.yes_bid_cents,
            "yes_ask_cents": market.yes_ask_cents,
            "no_bid_cents": market.no_bid_cents,
            "no_ask_cents": market.no_ask_cents,
            "retrieved_at": normalized_retrieved_at,
        }
        for market in markets
    ]

    statement = (
        insert(MarketQuoteSnapshot)
        .values(rows)
        .on_conflict_do_nothing(
            constraint="uq_market_quote_ticker_retrieved"
        )
        .returning(MarketQuoteSnapshot.id)
    )

    result = await session.execute(statement)
    inserted_ids = result.scalars().all()

    return len(inserted_ids)

@dataclass(frozen=True, slots=True)
class StoredMarketQuote:
    ticker: str
    bracket: TemperatureBracket
    yes_bid_cents: int
    yes_ask_cents: int
    no_bid_cents: int
    no_ask_cents: int


@dataclass(frozen=True, slots=True)
class StoredMarketQuoteSet:
    event_ticker: str
    target_date: date
    retrieved_at: datetime
    markets: tuple[StoredMarketQuote, ...]


async def load_latest_market_quotes_by_cutoff(
    session: AsyncSession,
    event_ticker: str,
    target_date: date,
    cutoff_at: datetime,
) -> StoredMarketQuoteSet | None:
    if cutoff_at.tzinfo is None:
        raise ValueError(
            "cutoff_at must include a timezone."
        )

    latest_time_statement = select(
        func.max(MarketQuoteSnapshot.retrieved_at)
    ).where(
        MarketQuoteSnapshot.event_ticker == event_ticker,
        MarketQuoteSnapshot.target_date == target_date,
        MarketQuoteSnapshot.retrieved_at <= cutoff_at,
    )

    latest_time_result = await session.execute(
        latest_time_statement
    )
    latest_retrieved_at = (
        latest_time_result.scalar_one_or_none()
    )

    if latest_retrieved_at is None:
        return None

    quotes_statement = (
        select(MarketQuoteSnapshot)
        .where(
            MarketQuoteSnapshot.event_ticker
            == event_ticker,
            MarketQuoteSnapshot.target_date
            == target_date,
            MarketQuoteSnapshot.retrieved_at
            == latest_retrieved_at,
        )
        .order_by(MarketQuoteSnapshot.market_ticker)
    )

    quotes_result = await session.execute(
        quotes_statement
    )
    rows = quotes_result.scalars().all()

    if not rows:
        return None

    markets = tuple(
        StoredMarketQuote(
            ticker=row.market_ticker,
            bracket=TemperatureBracket(
                lower_f=row.lower_f,
                upper_f=row.upper_f,
            ),
            yes_bid_cents=row.yes_bid_cents,
            yes_ask_cents=row.yes_ask_cents,
            no_bid_cents=row.no_bid_cents,
            no_ask_cents=row.no_ask_cents,
        )
        for row in rows
    )

    return StoredMarketQuoteSet(
        event_ticker=event_ticker,
        target_date=target_date,
        retrieved_at=latest_retrieved_at,
        markets=markets,
    )