import asyncio

import httpx

from weather_oms.bus import EventBus
from weather_oms.config import Settings
from weather_oms.ingest.forecast_parser import DailyForecast
from weather_oms.ingest.forecast_poller import (
    ForecastPoller,
    WeatherNextClient,
)
from weather_oms.ingest.kalshi_public_client import (
    KalshiPublicClient,
)
from weather_oms.ingest.kalshi_settlement_parser import (
    ParsedTemperatureSettlement,
)
from weather_oms.ingest.kalshi_stream import KalshiStream
from weather_oms.ingest.settlement_poller import (
    SettlementPoller,
)
from weather_oms.stations import STATIONS
from weather_oms.storage.db import Database
from weather_oms.storage.forecast_repository import save_forecast
from weather_oms.storage.temperature_settlement_repository import (
    save_temperature_settlement,
)


async def serve() -> None:
    settings = Settings()
    bus = EventBus()
    database = Database(settings.database_url)

    async with httpx.AsyncClient(timeout=20) as http:
        forecast_poller = ForecastPoller(
            WeatherNextClient(http),
            bus,
            [STATIONS["KNYC"]],
        )

        settlement_poller = SettlementPoller(
            client=KalshiPublicClient(http),
            bus=bus,
            series_ticker="KXHIGHNY",
            station_code="KNYC",
        )

        tasks = [
            asyncio.create_task(
                forecast_poller.run(
                    settings.forecast_refresh_seconds
                )
            ),
            asyncio.create_task(
                settlement_poller.run(
                    settings.settlement_refresh_seconds
                )
            ),
        ]

        if (
            settings.tickers
            and settings.kalshi_key_id
            and settings.kalshi_private_key_path
        ):
            stream = KalshiStream(
                settings.kalshi_ws_url,
                settings.kalshi_key_id,
                settings.kalshi_private_key_path,
                settings.tickers,
                bus,
            )

            tasks.append(
                asyncio.create_task(stream.run())
            )

        try:
            while True:
                event = await bus.next()

                try:
                    forecast = event.payload.get("forecast")

                    if isinstance(forecast, DailyForecast):
                        async with database.session() as session:
                            inserted = await save_forecast(
                                session=session,
                                forecast=forecast,
                                retrieved_at=event.received_time,
                            )

                        result = (
                            "saved"
                            if inserted
                            else "already existed"
                        )

                        print(
                            f"{event.kind} "
                            f"station={forecast.station_code} "
                            f"date={forecast.forecast_date} "
                            f"mean={forecast.mean_high_f:.2f}°F "
                            f"result={result}"
                        )
                    settlement = event.payload.get(
                        "settlement"
                    )

                    if isinstance(
                        settlement,
                        ParsedTemperatureSettlement,
                    ):
                        async with database.session() as session:
                            inserted = (
                                await save_temperature_settlement(
                                    session=session,
                                    settlement=settlement,
                                )
                            )

                        result = (
                            "saved"
                            if inserted
                            else "already existed"
                        )

                        print(
                            f"{event.kind} "
                            f"station={settlement.station_code} "
                            f"date={settlement.observation_date} "
                            f"temperature="
                            f"{settlement.temperature_f}°F "
                            f"result={result}"
                        )
                finally:
                    bus.task_done()
        finally:
            for task in tasks:
                task.cancel()

            await asyncio.gather(
                *tasks,
                return_exceptions=True,
            )

            await database.close()


def run() -> None:
    asyncio.run(serve())


if __name__ == "__main__":
    run()