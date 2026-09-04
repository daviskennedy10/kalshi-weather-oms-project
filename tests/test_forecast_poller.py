import asyncio
import logging
from typing import Any

import pytest

from weather_oms.bus import EventBus
from weather_oms.events import EventKind
from weather_oms.ingest.forecast_parser import (
    MEMBER_KEYS,
    DailyForecast,
)
from weather_oms.ingest.forecast_poller import ForecastPoller
from weather_oms.stations import STATIONS, Station


def make_response(base_temperature: float) -> dict[str, Any]:
    daily: dict[str, Any] = {
        "time": ["2026-09-04"],
    }

    for member_number, member_key in enumerate(MEMBER_KEYS):
        daily[member_key] = [
            base_temperature + member_number / 10
        ]

    return {
        "latitude": 40.75,
        "longitude": -74.0,
        "daily_units": {
            "temperature_2m_max": "°F",
        },
        "daily": daily,
    }


class FakeWeatherClient:
    def __init__(
        self,
        responses: list[dict[str, Any] | Exception],
    ) -> None:
        self.responses = responses

    async def forecast(
        self,
        station: Station,
        days: int = 15,
    ) -> dict[str, Any]:
        result = self.responses.pop(0)

        if isinstance(result, Exception):
            raise result

        return result


async def test_publishes_only_new_or_changed_forecasts() -> None:
    unchanged_response = make_response(70.0)
    changed_response = make_response(71.0)

    client = FakeWeatherClient(
        [
            unchanged_response,
            unchanged_response,
            changed_response,
        ]
    )
    bus = EventBus()
    poller = ForecastPoller(
        client=client,
        bus=bus,
        stations=[STATIONS["KNYC"]],
    )

    await poller.poll_once()

    first_event = await bus.next()
    first_forecast = first_event.payload["forecast"]

    assert first_event.kind == EventKind.FORECAST_UPDATED
    assert isinstance(first_forecast, DailyForecast)
    assert first_forecast.station_code == "KNYC"
    assert first_forecast.member_highs_f[0] == 70.0

    bus.task_done()

    await poller.poll_once()

    with pytest.raises(TimeoutError):
        await asyncio.wait_for(
            bus.next(),
            timeout=0.01,
        )

    await poller.poll_once()

    changed_event = await bus.next()
    changed_forecast = changed_event.payload["forecast"]

    assert isinstance(changed_forecast, DailyForecast)
    assert changed_forecast.member_highs_f[0] == 71.0

    bus.task_done()


async def test_reports_failed_forecast_request(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = FakeWeatherClient(
        [
            OSError("Open-Meteo could not be reached"),
        ]
    )
    bus = EventBus()
    poller = ForecastPoller(
        client=client,
        bus=bus,
        stations=[STATIONS["KNYC"]],
    )

    with caplog.at_level(logging.ERROR):
        await poller.poll_once()

    assert "Forecast request failed for station KNYC" in caplog.text
    assert "Open-Meteo could not be reached" in caplog.text