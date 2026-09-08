from datetime import UTC, date, datetime

import pytest

from weather_oms.analysis.forecast_metrics import (
    calculate_error_metrics,
    calculate_forecast_metrics,
)
from weather_oms.signal.forecast_dataset import ForecastOutcome


def outcome(error_f: float) -> ForecastOutcome:
    raw_high_f = 75.0

    return ForecastOutcome(
        station_code="KNYC",
        observation_date=date(2026, 9, 6),
        cutoff_at=datetime(
            2026,
            9,
            5,
            16,
            tzinfo=UTC,
        ),
        forecast_retrieved_at=datetime(
            2026,
            9,
            5,
            14,
            tzinfo=UTC,
        ),
        lead_hours=14.0,
        raw_high_f=raw_high_f,
        ensemble_stddev_f=2.0,
        actual_high_f=raw_high_f + error_f,
        error_f=error_f,
    )


def test_calculates_baseline_metrics() -> None:
    metrics = calculate_forecast_metrics(
        [
            outcome(-1.0),
            outcome(2.0),
            outcome(3.0),
        ]
    )

    assert metrics.sample_count == 3
    assert metrics.mean_error_f == pytest.approx(4 / 3)
    assert metrics.mean_absolute_error_f == pytest.approx(2.0)
    assert metrics.root_mean_squared_error_f == pytest.approx(
        (14 / 3) ** 0.5
    )


def test_calculates_metrics_directly_from_errors() -> None:
    metrics = calculate_error_metrics(
        error for error in [-1.0, 2.0, 3.0]
    )

    assert metrics.sample_count == 3
    assert metrics.mean_error_f == pytest.approx(4 / 3)
    assert metrics.mean_absolute_error_f == pytest.approx(2.0)


def test_rejects_empty_outcome_dataset() -> None:
    with pytest.raises(
        ValueError,
        match="At least one forecast outcome",
    ):
        calculate_forecast_metrics([])


def test_rejects_empty_error_dataset() -> None:
    with pytest.raises(
        ValueError,
        match="At least one forecast error",
    ):
        calculate_error_metrics([])


@pytest.mark.parametrize("invalid_error", [float("nan"), float("inf")])
def test_rejects_non_finite_errors(
    invalid_error: float,
) -> None:
    with pytest.raises(ValueError, match="finite"):
        calculate_error_metrics([invalid_error])