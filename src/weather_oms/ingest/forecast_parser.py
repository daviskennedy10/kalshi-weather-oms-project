from dataclasses import dataclass
from datetime import date
from statistics import fmean, pstdev
from typing import Any

from weather_oms.stations import Station

MEMBER_KEYS = (
    "temperature_2m_max",
    *(
        f"temperature_2m_max_member{number:02d}"
        for number in range(1, 64)
    ),
)


class ForecastParseError(ValueError):
    """Raised when Open-Meteo returns missing or invalid forecast data."""


@dataclass(frozen=True, slots=True)
class DailyForecast:
    station_code: str
    forecast_date: date
    member_highs_f: tuple[float, ...]
    source_latitude: float
    source_longitude: float

    @property
    def mean_high_f(self) -> float:
        return fmean(self.member_highs_f)

    @property
    def minimum_high_f(self) -> float:
        return min(self.member_highs_f)

    @property
    def maximum_high_f(self) -> float:
        return max(self.member_highs_f)

    @property
    def spread_f(self) -> float:
        return self.maximum_high_f - self.minimum_high_f

    @property
    def standard_deviation_f(self) -> float:
        return pstdev(self.member_highs_f)


def parse_daily_forecasts(
    response: dict[str, Any],
    station: Station,
) -> list[DailyForecast]:
    daily = response.get("daily")

    if not isinstance(daily, dict):
        raise ForecastParseError(
            "Open-Meteo response does not contain a valid 'daily' section."
        )

    dates = daily.get("time")

    if not isinstance(dates, list) or not dates:
        raise ForecastParseError(
            "Open-Meteo response does not contain any forecast dates."
        )

    units = response.get("daily_units", {})
    temperature_unit = units.get("temperature_2m_max")

    if temperature_unit != "°F":
        raise ForecastParseError(
            f"Expected Fahrenheit temperatures, received {temperature_unit!r}."
        )

    for key in MEMBER_KEYS:
        values = daily.get(key)

        if not isinstance(values, list):
            raise ForecastParseError(
                f"Open-Meteo response is missing temperature series {key!r}."
            )

        if len(values) != len(dates):
            raise ForecastParseError(
                f"Temperature series {key!r} does not match the number of dates."
            )

    forecasts: list[DailyForecast] = []

    for date_index, date_text in enumerate(dates):
        try:
            forecast_date = date.fromisoformat(date_text)
        except (TypeError, ValueError) as error:
            raise ForecastParseError(
                f"Invalid forecast date: {date_text!r}."
            ) from error

        raw_temperatures = [
            daily[key][date_index]
            for key in MEMBER_KEYS
        ]

        if any(value is None for value in raw_temperatures):
            continue

        temperatures: list[float] = []

        for key, value in zip(
            MEMBER_KEYS,
            raw_temperatures,
            strict=True,
        ):
            if isinstance(value, bool) or not isinstance(
                value,
                (int, float),
            ):
                raise ForecastParseError(
                    f"Invalid temperature for {key!r} on {date_text!r}: {value!r}."
                )

            temperatures.append(float(value))

        forecasts.append(
            DailyForecast(
                station_code=station.code,
                forecast_date=forecast_date,
                member_highs_f=tuple(temperatures),
                source_latitude=float(response["latitude"]),
                source_longitude=float(response["longitude"]),
            )
        )
    if not forecasts:
        raise ForecastParseError(
            "Open-Meteo response contains no complete daily forecasts."
        )
    return forecasts