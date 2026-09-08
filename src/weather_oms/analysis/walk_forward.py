from dataclasses import dataclass
from datetime import date
from itertools import groupby

from weather_oms.signal.bias_model import (
    BiasModel,
    ForecastFeatures,
)
from weather_oms.signal.forecast_dataset import ForecastOutcome


@dataclass(frozen=True, slots=True)
class WalkForwardPrediction:
    station_code: str
    observation_date: date
    training_count: int
    learned_bias_f: float
    raw_high_f: float
    corrected_high_f: float
    actual_high_f: float
    raw_error_f: float
    corrected_error_f: float


def outcome_features(
    outcome: ForecastOutcome,
) -> ForecastFeatures:
    return ForecastFeatures(
        raw_high_f=outcome.raw_high_f,
        lead_hours=outcome.lead_hours,
        ensemble_stddev_f=outcome.ensemble_stddev_f,
        station=outcome.station_code,
        day_of_year=outcome.observation_date.timetuple().tm_yday,
    )


def walk_forward_predictions(
    outcomes: list[ForecastOutcome],
    minimum_training_size: int = 1,
) -> list[WalkForwardPrediction]:
    if minimum_training_size < 1:
        raise ValueError(
            "minimum_training_size must be at least 1."
        )

    ordered_outcomes = sorted(
        outcomes,
        key=lambda outcome: (
            outcome.observation_date,
            outcome.station_code,
        ),
    )

    training_outcomes: list[ForecastOutcome] = []
    predictions: list[WalkForwardPrediction] = []

    grouped_outcomes = groupby(
        ordered_outcomes,
        key=lambda outcome: outcome.observation_date,
    )

    for _, date_group in grouped_outcomes:
        current_outcomes = list(date_group)

        if len(training_outcomes) >= minimum_training_size:
            model = BiasModel()
            model.fit(
                [
                    (
                        outcome_features(training_outcome),
                        training_outcome.error_f,
                    )
                    for training_outcome in training_outcomes
                ]
            )

            for outcome in current_outcomes:
                corrected_high_f = model.corrected_high(
                    outcome_features(outcome)
                )

                predictions.append(
                    WalkForwardPrediction(
                        station_code=outcome.station_code,
                        observation_date=outcome.observation_date,
                        training_count=len(training_outcomes),
                        learned_bias_f=model.bias_f,
                        raw_high_f=outcome.raw_high_f,
                        corrected_high_f=corrected_high_f,
                        actual_high_f=outcome.actual_high_f,
                        raw_error_f=outcome.error_f,
                        corrected_error_f=(
                            outcome.actual_high_f
                            - corrected_high_f
                        ),
                    )
                )

        training_outcomes.extend(current_outcomes)

    return predictions