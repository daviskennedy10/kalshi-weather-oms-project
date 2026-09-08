import pytest

from weather_oms.signal.bias_model import (
    BiasModel,
    ForecastFeatures,
)


def features(raw_high_f: float = 75.0) -> ForecastFeatures:
    return ForecastFeatures(
        raw_high_f=raw_high_f,
        lead_hours=20.0,
        ensemble_stddev_f=2.0,
        station="KNYC",
        day_of_year=249,
    )


def test_learns_mean_historical_error() -> None:
    model = BiasModel()

    model.fit(
        [
            (features(), -1.0),
            (features(), 2.0),
            (features(), 3.0),
        ]
    )

    assert model.bias_f == pytest.approx(4 / 3)


def test_adds_learned_bias_to_raw_forecast() -> None:
    model = BiasModel()
    model.fit(
        [
            (features(), 1.0),
            (features(), 2.0),
        ]
    )

    corrected = model.corrected_high(
        features(raw_high_f=75.0)
    )

    assert corrected == pytest.approx(76.5)


def test_rejects_prediction_before_fitting() -> None:
    model = BiasModel()

    with pytest.raises(RuntimeError, match="not been fitted"):
        model.corrected_high(features())


def test_rejects_empty_training_data() -> None:
    model = BiasModel()

    with pytest.raises(
        ValueError,
        match="At least one training row",
    ):
        model.fit([])


@pytest.mark.parametrize("invalid_error", [float("nan"), float("inf")])
def test_rejects_non_finite_training_error(
    invalid_error: float,
) -> None:
    model = BiasModel()

    with pytest.raises(ValueError, match="finite"):
        model.fit([(features(), invalid_error)])


def test_refitting_replaces_previous_bias() -> None:
    model = BiasModel()
    model.fit([(features(), 1.0)])
    model.fit([(features(), -2.0)])

    assert model.bias_f == pytest.approx(-2.0)