import asyncio
import logging
from datetime import UTC, datetime
from typing import Any, Protocol, cast

import httpx

from weather_oms.bus import EventBus
from weather_oms.events import Event, EventKind
from weather_oms.ingest.forecast_parser import (
    ForecastParseError,
    parse_daily_forecasts,
)
from weather_oms.stations import Station

LOGGER = logging.getLogger(__name__)

class ForecastClient(Protocol):
    async def forecast(
        self,
        station: Station,
        days: int = 15,
    ) -> dict[str, Any]:
        ...


class WeatherNextClient:
    BASE_URL = "https://ensemble-api.open-meteo.com/v1/ensemble"

    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def forecast(
        self,
        station: Station,
        days: int = 15,
    ) -> dict[str, Any]:
        response = await self.client.get(
            self.BASE_URL,
            params={
                "latitude": station.latitude,
                "longitude": station.longitude,
                "daily": "temperature_2m_max",
                "models": "google_weathernext2_ensemble",
                "temperature_unit": "fahrenheit",
                "timezone": station.timezone,
                "forecast_days": days,
            },
        )

        response.raise_for_status()

        data: object = response.json()

        if not isinstance(data, dict):
            raise TypeError(
                "Expected Open-Meteo to return a JSON object."
            )

        return cast(dict[str, Any], data)


class ForecastPoller:
    """Publishes an event when a station's daily forecast changes."""

    def __init__(
        self,
        client: ForecastClient,
        bus: EventBus,
        stations: list[Station],
    ) -> None:
        self.client = client
        self.bus = bus
        self.stations = stations

        self._fingerprints: dict[
            tuple[str, str],
            tuple[float, ...],
        ] = {}

    async def poll_once(self) -> None:
        results = await asyncio.gather(
            *(
                self.client.forecast(station)
                for station in self.stations
            ),
            return_exceptions=True,
        )

        for station, result in zip(
            self.stations,
            results,
            strict=True,
        ):
            if isinstance(result, BaseException):
                LOGGER.error(
                    "Forecast request failed for station %s: %s",
                    station.code,
                    result,
                )
                continue

            try:
                daily_forecasts = parse_daily_forecasts(
                    result,
                    station,
                )
            except ForecastParseError as error:
                LOGGER.error(
                    "Invalid forecast response for station %s: %s",
                    station.code,
                    error,
                )
                continue

            for forecast in daily_forecasts:
                fingerprint_key = (
                    station.code,
                    forecast.forecast_date.isoformat(),
                )
                fingerprint = forecast.member_highs_f

                if (
                    self._fingerprints.get(fingerprint_key)
                    == fingerprint
                ):
                    continue

                self._fingerprints[fingerprint_key] = fingerprint

                await self.bus.publish(
                    Event(
                        kind=EventKind.FORECAST_UPDATED,
                        source_time=datetime.now(UTC),
                        payload={
                            "forecast": forecast,
                        },
                    )
                )

    async def run(self, interval_seconds: int) -> None:
        while True:
            await self.poll_once()
            await asyncio.sleep(interval_seconds)