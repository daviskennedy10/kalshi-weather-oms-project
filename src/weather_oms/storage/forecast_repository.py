import hashlib
import json
from datetime import datetime

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from weather_oms.ingest.forecast_parser import DailyForecast
from weather_oms.storage.models import Forecast


def create_forecast_fingerprint(
    forecast: DailyForecast,
) -> str:
    member_json = json.dumps(
        forecast.member_highs_f,
        separators=(",", ":"),
        allow_nan=False,
    )

    return hashlib.sha256(
        member_json.encode("utf-8")
    ).hexdigest()


async def save_forecast(
    session: AsyncSession,
    forecast: DailyForecast,
    retrieved_at: datetime,
    model_run_at: datetime | None = None,
) -> bool:
    if retrieved_at.tzinfo is None:
        raise ValueError(
            "retrieved_at must include a timezone."
        )

    if (
        model_run_at is not None
        and model_run_at.tzinfo is None
    ):
        raise ValueError(
            "model_run_at must include a timezone."
        )

    fingerprint = create_forecast_fingerprint(forecast)

    statement = (
        insert(Forecast)
        .values(
            station_code=forecast.station_code,
            forecast_date=forecast.forecast_date,
            model_run_at=model_run_at,
            retrieved_at=retrieved_at,
            source_latitude=forecast.source_latitude,
            source_longitude=forecast.source_longitude,
            member_highs_f=list(forecast.member_highs_f),
            mean_high_f=forecast.mean_high_f,
            minimum_high_f=forecast.minimum_high_f,
            maximum_high_f=forecast.maximum_high_f,
            standard_deviation_f=(
                forecast.standard_deviation_f
            ),
            fingerprint=fingerprint,
        )
        .on_conflict_do_nothing(
            constraint=(
                "uq_forecast_station_date_fingerprint"
            )
        )
        .returning(Forecast.id)
    )

    result = await session.execute(statement)
    inserted_id = result.scalar_one_or_none()

    return inserted_id is not None