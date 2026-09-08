from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from weather_oms.signal.forecast_dataset import (
    ForecastOutcome,
    MatchedForecastSnapshot,
    select_forecast_outcomes,
)
from weather_oms.storage.models import Forecast, TemperatureSettlement


async def load_forecast_outcomes(
    session: AsyncSession,
    station_code: str,
    timezone: str,
) -> list[ForecastOutcome]:
    """Load matched snapshots and apply the leakage-safe cutoff policy."""
    statement = (
        select(Forecast, TemperatureSettlement)
        .join(
            TemperatureSettlement,
            (
                TemperatureSettlement.station_code
                == Forecast.station_code
            )
            & (
                TemperatureSettlement.observation_date
                == Forecast.forecast_date
            ),
        )
        .where(Forecast.station_code == station_code)
        .order_by(Forecast.forecast_date, Forecast.retrieved_at)
    )
    result = await session.execute(statement)

    snapshots = [
        MatchedForecastSnapshot(
            station_code=forecast.station_code,
            observation_date=forecast.forecast_date,
            retrieved_at=forecast.retrieved_at,
            mean_high_f=forecast.mean_high_f,
            ensemble_stddev_f=forecast.standard_deviation_f,
            actual_high_f=float(settlement.temperature_f),
        )
        for forecast, settlement in result.all()
    ]

    return select_forecast_outcomes(
        snapshots,
        timezone=timezone,
    )
