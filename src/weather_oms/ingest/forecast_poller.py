import asyncio
from datetime import UTC, datetime
from typing import Any, cast

import httpx

from weather_oms.bus import EventBus
from weather_oms.events import Event, EventKind
from weather_oms.stations import Station


class WeatherNextClient:
    BASE_URL = "https://ensemble-api.open-meteo.com/v1/ensemble"

    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def forecast(self, station: Station, days: int = 15) -> dict[str, Any]:
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
    """Polls cheaply, but emits only when Open-Meteo's generation time changes."""

    def __init__(self, client: WeatherNextClient, bus: EventBus, stations: list[Station]) -> None:
        self.client, self.bus, self.stations = client, bus, stations
        self._fingerprints: dict[str, str] = {}

    async def poll_once(self) -> None:
        results = await asyncio.gather(
            *(self.client.forecast(station) for station in self.stations),
            return_exceptions=True,
        )
        for station, result in zip(self.stations, results, strict=True):
            if isinstance(result, BaseException):
                continue  # caller's logger/metrics layer will make failures observable
            fingerprint = repr(result.get("daily"))
            if self._fingerprints.get(station.code) == fingerprint:
                continue
            self._fingerprints[station.code] = fingerprint
            await self.bus.publish(Event(
                kind=EventKind.FORECAST_UPDATED,
                source_time=datetime.now(UTC),
                payload={"station": station.code, "forecast": result},
            ))

    async def run(self, interval_seconds: int) -> None:
        while True:
            await self.poll_once()
            await asyncio.sleep(interval_seconds)

