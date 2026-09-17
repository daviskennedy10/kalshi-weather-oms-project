from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from weather_oms.ingest.kalshi_settlement_parser import (
    ParsedTemperatureSettlement,
)
from weather_oms.storage.models import TemperatureSettlement


@dataclass(frozen=True, slots=True)
class StoredTemperatureSettlement:
    event_ticker: str
    winning_market_ticker: str | None
    observation_date: date
    temperature_f: Decimal
    settled_at: datetime

async def save_temperature_settlement(
    session: AsyncSession,
    settlement: ParsedTemperatureSettlement,
) -> bool:
    """Insert a settlement or complete its missing winner."""

    insert_statement = insert(
        TemperatureSettlement
    ).values(
        series_ticker=settlement.series_ticker,
        event_ticker=settlement.event_ticker,
        winning_market_ticker=(
            settlement.winning_market_ticker
        ),
        station_code=settlement.station_code,
        observation_date=settlement.observation_date,
        temperature_f=settlement.temperature_f,
        source_name=settlement.source_name,
        source_url=settlement.source_url,
        settled_at=settlement.settled_at,
        retrieved_at=settlement.retrieved_at,
    )

    statement = (
        insert_statement
        .on_conflict_do_update(
            index_elements=[
                TemperatureSettlement.event_ticker
            ],
            set_={
                "winning_market_ticker": (
                    insert_statement.excluded
                    .winning_market_ticker
                )
            },
            where=(
                TemperatureSettlement
                .winning_market_ticker
                .is_(None)
            ),
        )
        .returning(TemperatureSettlement.id)
    )

    result = await session.execute(statement)
    changed_id = result.scalar_one_or_none()

    return changed_id is not None

async def load_temperature_settlement(
    session: AsyncSession,
    event_ticker: str,
) -> StoredTemperatureSettlement | None:
    if not event_ticker:
        raise ValueError("event_ticker cannot be empty.")

    statement = select(
        TemperatureSettlement
    ).where(
        TemperatureSettlement.event_ticker
        == event_ticker
    )

    result = await session.execute(statement)
    row = result.scalar_one_or_none()

    if row is None:
        return None

    return StoredTemperatureSettlement(
        event_ticker=row.event_ticker,
        winning_market_ticker=(
            row.winning_market_ticker
        ),
        observation_date=row.observation_date,
        temperature_f=row.temperature_f,
        settled_at=row.settled_at,
    )