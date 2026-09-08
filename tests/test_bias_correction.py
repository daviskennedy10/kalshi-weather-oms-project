from datetime import UTC, date, datetime

import pytest

from weather_oms.signal.bias_correction import apply_bias_correction
from weather_oms.signal.bias_model import ForecastFeatures
from weather_oms.signal.forecast_dataset import ForecastOutcome


def features(raw_high_f: float = 75.0) -> ForecastFeatures:
    return ForecastFeatures(
        raw_high_f=raw_high_f,
        lead_hours=20.0,
        ensemble_stddev_f=2.0,
        station="KNYC",
        day_of_year=250,
    )


def outcome(
    observation_date: date,
    error_f: float,
) -> ForecastOutcome:
    raw_high_f = 75.0

    return ForecastOutcome(
        station_code="KNYC",
        observation_date=observation_date,
        cutoff_at=datetime(
            2026,
            9,
            1,
            16,
            tzinfo=UTC,
        ),
        forecast_retrieved_at=datetime(
            2026,
            9,
            1,
            14,
            tzinfo=UTC,
        ),
        lead_hours=20.0,
        raw_high_f=raw_high_f,
        ensemble_stddev_f=2.0,
        actual_high_f=raw_high_f + error_f,
        error_f=error_f,
    )


def test_does_not_correct_with_insufficient_history() -> None:
    training_outcomes = [
        outcome(date(2026, 9, 1), 1.0),
        outcome(date(2026, 9, 2), 2.0),
    ]

    result = apply_bias_correction(
        features(),
        target_date=date(2026, 9, 10),
        available_outcomes=training_outcomes,
        minimum_training_size=3,
    )

    assert result.correction_applied is False
    assert result.raw_high_f == pytest.approx(75.0)
    assert result.corrected_high_f == pytest.approx(75.0)
    assert result.learned_bias_f == pytest.approx(0.0)
    assert result.training_count == 2
    assert "2 available, 3 required" in result.reason


def test_corrects_when_enough_history_exists() -> None:
    training_outcomes = [
        outcome(date(2026, 9, 1), 1.0),
        outcome(date(2026, 9, 2), 2.0),
        outcome(date(2026, 9, 3), 3.0),
    ]

    result = apply_bias_correction(
        features(raw_high_f=75.0),
        target_date=date(2026, 9, 10),
        available_outcomes=training_outcomes,
        minimum_training_size=3,
    )

    assert result.correction_applied is True
    assert result.training_count == 3
    assert result.learned_bias_f == pytest.approx(2.0)
    assert result.corrected_high_f == pytest.approx(77.0)
    assert result.reason == "Bias correction applied."


def test_exact_minimum_is_enough() -> None:
    training_outcomes = [
        outcome(date(2026, 9, 1), 1.0),
        outcome(date(2026, 9, 2), 1.0),
    ]

    result = apply_bias_correction(
        features(),
        target_date=date(2026, 9, 10),
        available_outcomes=training_outcomes,
        minimum_training_size=2,
    )

    assert result.correction_applied is True


def test_rejects_invalid_minimum_training_size() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        apply_bias_correction(
            features(),
            target_date=date(2026, 9, 10),
            available_outcomes=[],
            minimum_training_size=0,
        )

def test_excludes_same_day_and_future_outcomes() -> None:
    available_outcomes = [
        outcome(date(2026, 9, 8), 1.0),
        outcome(date(2026, 9, 9), 3.0),
        outcome(date(2026, 9, 10), 100.0),
        outcome(date(2026, 9, 11), 100.0),
    ]

    result = apply_bias_correction(
        features(raw_high_f=75.0),
        target_date=date(2026, 9, 10),
        available_outcomes=available_outcomes,
        minimum_training_size=2,
    )

    assert result.correction_applied is True
    assert result.training_count == 2
    assert result.learned_bias_f == pytest.approx(2.0)
    assert result.corrected_high_f == pytest.approx(77.0)


def test_excludes_outcomes_from_other_stations() -> None:
    knyc_outcome = outcome(
        date(2026, 9, 8),
        2.0,
    )

    klax_outcome = ForecastOutcome(
        station_code="KLAX",
        observation_date=date(2026, 9, 9),
        cutoff_at=datetime(
            2026,
            9,
            8,
            16,
            tzinfo=UTC,
        ),
        forecast_retrieved_at=datetime(
            2026,
            9,
            8,
            14,
            tzinfo=UTC,
        ),
        lead_hours=20.0,
        raw_high_f=75.0,
        ensemble_stddev_f=2.0,
        actual_high_f=175.0,
        error_f=100.0,
    )

    result = apply_bias_correction(
        features(raw_high_f=75.0),
        target_date=date(2026, 9, 10),
        available_outcomes=[
            knyc_outcome,
            klax_outcome,
        ],
        minimum_training_size=1,
    )

    assert result.correction_applied is True
    assert result.training_count == 1
    assert result.learned_bias_f == pytest.approx(2.0)
    assert result.corrected_high_f == pytest.approx(77.0)