from collections.abc import Iterable
from dataclasses import dataclass
from math import isfinite, sqrt
from statistics import fmean

from weather_oms.signal.forecast_dataset import ForecastOutcome


@dataclass(frozen=True, slots=True)
class ForecastMetrics:
    sample_count: int
    mean_error_f: float
    mean_absolute_error_f: float
    root_mean_squared_error_f: float


def calculate_error_metrics(
    errors: Iterable[float],
) -> ForecastMetrics:
    error_values = list(errors)

    if not error_values:
        raise ValueError(
            "At least one forecast error is required."
        )

    if not all(isfinite(error) for error in error_values):
        raise ValueError(
            "Forecast errors must all be finite."
        )

    return ForecastMetrics(
        sample_count=len(error_values),
        mean_error_f=fmean(error_values),
        mean_absolute_error_f=fmean(
            abs(error) for error in error_values
        ),
        root_mean_squared_error_f=sqrt(
            fmean(error**2 for error in error_values)
        ),
    )


def calculate_forecast_metrics(
    outcomes: list[ForecastOutcome],
) -> ForecastMetrics:
    if not outcomes:
        raise ValueError(
            "At least one forecast outcome is required."
        )

    return calculate_error_metrics(
        outcome.error_f for outcome in outcomes
    )