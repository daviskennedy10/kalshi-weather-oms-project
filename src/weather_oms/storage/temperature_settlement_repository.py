from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from weather_oms.ingest.kalshi_settlement_parser import (
    ParsedTemperatureSettlement,
)
from weather_oms.storage.models import TemperatureSettlement


async def save_temperature_settlement(
    session: AsyncSession,
    settlement: ParsedTemperatureSettlement,
) -> bool:
    statement = (
        insert(TemperatureSettlement)
        .values(
            series_ticker=settlement.series_ticker,
            event_ticker=settlement.event_ticker,
            station_code=settlement.station_code,
            observation_date=settlement.observation_date,
            temperature_f=settlement.temperature_f,
            source_name=settlement.source_name,
            source_url=settlement.source_url,
            settled_at=settlement.settled_at,
            retrieved_at=settlement.retrieved_at,
        )
        .on_conflict_do_nothing(
            index_elements=[
                TemperatureSettlement.event_ticker
            ]
        )
        .returning(TemperatureSettlement.id)
    )

    result = await session.execute(statement)
    inserted_id = result.scalar_one_or_none()

    return inserted_id is not None