from datetime import date, datetime

from weather_oms.ingest.forecast_parser import DailyForecast


def select_target_forecast(
    forecasts: list[DailyForecast],
    target_date: date,
) -> DailyForecast:
    matches = [
        forecast
        for forecast in forecasts
        if forecast.forecast_date == target_date
    ]

    if len(matches) != 1:
        raise ValueError(
            "Expected exactly one WeatherNext forecast for "
            f"{target_date}, received {len(matches)}."
        )

    return matches[0]


def eligibility_label(
    retrieved_at: datetime,
    cutoff_at: datetime,
) -> str:
    if retrieved_at.tzinfo is None:
        raise ValueError(
            "retrieved_at must include a timezone."
        )

    if cutoff_at.tzinfo is None:
        raise ValueError(
            "cutoff_at must include a timezone."
        )

    if retrieved_at <= cutoff_at:
        return "ELIGIBLE"

    return "LATE"