from dataclasses import dataclass
from datetime import date

from weather_oms.signal.bias_model import (
    BiasModel,
    ForecastFeatures,
)
from weather_oms.signal.forecast_dataset import ForecastOutcome

DEFAULT_MINIMUM_TRAINING_SIZE = 30


@dataclass(frozen=True, slots=True)
class BiasCorrectionResult:
    raw_high_f: float
    corrected_high_f: float
    learned_bias_f: float
    training_count: int
    correction_applied: bool
    reason: str


def apply_bias_correction(
    features: ForecastFeatures,
    target_date: date,
    available_outcomes: list[ForecastOutcome],
    minimum_training_size: int = DEFAULT_MINIMUM_TRAINING_SIZE,
) -> BiasCorrectionResult:
    if minimum_training_size < 1:
        raise ValueError(
            "minimum_training_size must be at least 1."
        )

    training_outcomes = [
        outcome
        for outcome in available_outcomes
        if outcome.station_code == features.station
        and outcome.observation_date < target_date
    ]

    training_count = len(training_outcomes)

    if training_count < minimum_training_size:
        return BiasCorrectionResult(
            raw_high_f=features.raw_high_f,
            corrected_high_f=features.raw_high_f,
            learned_bias_f=0.0,
            training_count=training_count,
            correction_applied=False,
            reason=(
                "Insufficient eligible training history: "
                f"{training_count} available, "
                f"{minimum_training_size} required."
            ),
        )

    model = BiasModel()
    model.fit(
        [
            (
                ForecastFeatures(
                    raw_high_f=outcome.raw_high_f,
                    lead_hours=outcome.lead_hours,
                    ensemble_stddev_f=outcome.ensemble_stddev_f,
                    station=outcome.station_code,
                    day_of_year=(
                        outcome.observation_date.timetuple().tm_yday
                    ),
                ),
                outcome.error_f,
            )
            for outcome in training_outcomes
        ]
    )

    corrected_high_f = model.corrected_high(features)

    return BiasCorrectionResult(
        raw_high_f=features.raw_high_f,
        corrected_high_f=corrected_high_f,
        learned_bias_f=model.bias_f,
        training_count=training_count,
        correction_applied=True,
        reason="Bias correction applied.",
    )