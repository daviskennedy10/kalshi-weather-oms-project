from datetime import UTC, date, datetime, timedelta

import pytest

from weather_oms.analysis.walk_forward import (
    walk_forward_predictions,
)
from weather_oms.signal.forecast_dataset import ForecastOutcome


def outcome(
    observation_date: date,
    raw_high_f: float,
    actual_high_f: float,
    station_code: str = "KNYC",
) -> ForecastOutcome:
    cutoff_at = datetime.combine(
        observation_date - timedelta(days=1),
        datetime.min.time(),
        tzinfo=UTC,
    )

    return ForecastOutcome(
        station_code=station_code,
        observation_date=observation_date,
        cutoff_at=cutoff_at,
        forecast_retrieved_at=cutoff_at,
        lead_hours=24.0,
        raw_high_f=raw_high_f,
        ensemble_stddev_f=2.0,
        actual_high_f=actual_high_f,
        error_f=actual_high_f - raw_high_f,
    )


def test_predicts_each_date_using_only_earlier_dates() -> None:
    outcomes = [
        outcome(date(2026, 9, 3), 70.0, 74.0),
        outcome(date(2026, 9, 1), 70.0, 72.0),
        outcome(date(2026, 9, 2), 70.0, 71.0),
    ]

    predictions = walk_forward_predictions(outcomes)

    assert len(predictions) == 2

    second_day = predictions[0]
    assert second_day.observation_date == date(2026, 9, 2)
    assert second_day.training_count == 1
    assert second_day.learned_bias_f == pytest.approx(2.0)
    assert second_day.corrected_high_f == pytest.approx(72.0)
    assert second_day.corrected_error_f == pytest.approx(-1.0)

    third_day = predictions[1]
    assert third_day.training_count == 2
    assert third_day.learned_bias_f == pytest.approx(1.5)
    assert third_day.corrected_high_f == pytest.approx(71.5)
    assert third_day.corrected_error_f == pytest.approx(2.5)


def test_respects_minimum_training_size() -> None:
    outcomes = [
        outcome(date(2026, 9, 1), 70.0, 72.0),
        outcome(date(2026, 9, 2), 70.0, 71.0),
        outcome(date(2026, 9, 3), 70.0, 74.0),
    ]

    predictions = walk_forward_predictions(
        outcomes,
        minimum_training_size=2,
    )

    assert len(predictions) == 1
    assert predictions[0].observation_date == date(2026, 9, 3)
    assert predictions[0].training_count == 2


def test_same_date_outcomes_do_not_leak_into_each_other() -> None:
    outcomes = [
        outcome(date(2026, 9, 1), 70.0, 72.0),
        outcome(
            date(2026, 9, 2),
            70.0,
            80.0,
            station_code="KNYC",
        ),
        outcome(
            date(2026, 9, 2),
            60.0,
            50.0,
            station_code="KLAX",
        ),
    ]

    predictions = walk_forward_predictions(outcomes)

    assert len(predictions) == 2
    assert all(
        prediction.training_count == 1
        for prediction in predictions
    )
    assert all(
        prediction.learned_bias_f == pytest.approx(2.0)
        for prediction in predictions
    )


def test_rejects_invalid_minimum_training_size() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        walk_forward_predictions(
            [],
            minimum_training_size=0,
        )