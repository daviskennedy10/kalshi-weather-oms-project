from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ForecastFeatures:
    raw_high_f: float
    lead_hours: int
    ensemble_spread_f: float
    station: str
    day_of_year: int


class BiasModel:
    """YOUR CORE LOGIC: learn E[actual - forecast | features]."""

    def fit(self, rows: list[tuple[ForecastFeatures, float]]) -> None:
        # TODO(you): Choose the first defensible baseline (e.g. regularized linear model).
        # Decide how to time-split data without future leakage and how to encode season/station.
        raise NotImplementedError("Design and implement the bias model")

    def corrected_high(self, features: ForecastFeatures) -> float:
        # TODO(you): Return raw_high_f + predicted residual. Define pre-fit behavior explicitly.
        raise NotImplementedError("Design and implement inference")

