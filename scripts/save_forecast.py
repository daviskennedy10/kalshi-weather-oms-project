import asyncio
from datetime import UTC, datetime

import httpx

from weather_oms.config import Settings
from weather_oms.ingest.forecast_parser import (
    parse_daily_forecasts,
)
from weather_oms.ingest.forecast_poller import WeatherNextClient
from weather_oms.stations import STATIONS
from weather_oms.storage.db import Database
from weather_oms.storage.forecast_repository import save_forecast


async def save_current_forecasts() -> None:
    settings = Settings()
    station = STATIONS["KNYC"]

    async with httpx.AsyncClient(timeout=20) as http:
        client = WeatherNextClient(http)
        response = await client.forecast(
            station,
            days=2,
        )
        retrieved_at = datetime.now(UTC)

    forecasts = parse_daily_forecasts(
        response,
        station,
    )

    database = Database(settings.database_url)

    try:
        async with database.session() as session:
            for forecast in forecasts:
                inserted = await save_forecast(
                    session=session,
                    forecast=forecast,
                    retrieved_at=retrieved_at,
                )

                if inserted:
                    print(
                        f"Saved new forecast: "
                        f"{forecast.station_code} "
                        f"{forecast.forecast_date}"
                    )
                else:
                    print(
                        f"Forecast already exists: "
                        f"{forecast.station_code} "
                        f"{forecast.forecast_date}"
                    )
    finally:
        await database.close()


if __name__ == "__main__":
    asyncio.run(save_current_forecasts())