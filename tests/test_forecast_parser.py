from typing import Any

import pytest

from weather_oms.ingest.forecast_parser import (
    MEMBER_KEYS,
    ForecastParseError,
    parse_daily_forecasts,
)
from weather_oms.stations import STATIONS


def make_valid_response() -> dict[str, Any]:
    daily: dict[str, Any] = {
        "time": ["2026-09-03", "2026-09-04"],
    }

    for member_number, member_key in enumerate(MEMBER_KEYS):
        daily[member_key] = [
            70.0 + member_number,
            71.0 + member_number,
        ]

    return {
        "latitude": 40.75,
        "longitude": -74.0,
        "timezone": "America/New_York",
        "daily_units": {
            "temperature_2m_max": "°F",
        },
        "daily": daily,
    }


def test_parses_two_daily_forecasts() -> None:
    response = make_valid_response()
    station = STATIONS["KNYC"]

    forecasts = parse_daily_forecasts(response, station)

    assert len(forecasts) == 2

    first_forecast = forecasts[0]

    assert first_forecast.station_code == "KNYC"
    assert first_forecast.forecast_date.isoformat() == "2026-09-03"
    assert len(first_forecast.member_highs_f) == 64
    assert first_forecast.minimum_high_f == 70.0
    assert first_forecast.maximum_high_f == 133.0
    assert first_forecast.mean_high_f == 101.5
    assert first_forecast.spread_f == 63.0
    assert first_forecast.standard_deviation_f > 0
    assert first_forecast.source_latitude == 40.75
    assert first_forecast.source_longitude == -74.0


def test_rejects_response_with_missing_member() -> None:
    response = make_valid_response()
    del response["daily"]["temperature_2m_max_member63"]

    with pytest.raises(
        ForecastParseError,
        match="missing temperature series",
    ):
        parse_daily_forecasts(response, STATIONS["KNYC"])


def test_rejects_non_fahrenheit_temperatures() -> None:
    response = make_valid_response()
    response["daily_units"]["temperature_2m_max"] = "°C"

    with pytest.raises(
        ForecastParseError,
        match="Expected Fahrenheit",
    ):
        parse_daily_forecasts(response, STATIONS["KNYC"])

def test_skips_incomplete_forecast_date() -> None:
    response = make_valid_response()

    response["daily"]["temperature_2m_max_member63"][1] = None

    forecasts = parse_daily_forecasts(
        response,
        STATIONS["KNYC"],
    )

    assert len(forecasts) == 1
    assert forecasts[0].forecast_date.isoformat() == "2026-09-03"