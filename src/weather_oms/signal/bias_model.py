from dataclasses import dataclass
from math import isfinite
from statistics import fmean


@dataclass(frozen=True, slots=True)
class ForecastFeatures:
    raw_high_f: float
    lead_hours: float
    ensemble_stddev_f: float
    station: str
    day_of_year: int


class BiasModel:
    """Estimate forecast bias using the mean historical residual."""

    def __init__(self) -> None:
        self._bias_f: float | None = None

    @property
    def bias_f(self) -> float:
        if self._bias_f is None:
            raise RuntimeError("Bias model has not been fitted.")

        return self._bias_f

    def fit(
        self,
        rows: list[tuple[ForecastFeatures, float]],
    ) -> None:
        if not rows:
            raise ValueError(
                "At least one training row is required."
            )

        errors = [error_f for _, error_f in rows]

        if not all(isfinite(error_f) for error_f in errors):
            raise ValueError(
                "Training errors must all be finite."
            )

        self._bias_f = fmean(errors)

    def corrected_high(
        self,
        features: ForecastFeatures,
    ) -> float:
        if not isfinite(features.raw_high_f):
            raise ValueError("raw_high_f must be finite.")

        return features.raw_high_f + self.bias_f