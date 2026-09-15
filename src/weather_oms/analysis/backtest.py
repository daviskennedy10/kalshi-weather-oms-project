from dataclasses import dataclass
from math import isfinite, log, sqrt

_LOG_EPSILON = 1e-15


@dataclass(frozen=True, slots=True)
class CalibrationBin:
    lower_probability: float
    upper_probability: float
    sample_count: int
    mean_probability: float
    observed_frequency: float


@dataclass(frozen=True, slots=True)
class ProbabilityMetrics:
    sample_count: int
    brier_score: float
    log_loss: float
    expected_calibration_error: float
    calibration_bins: tuple[CalibrationBin, ...]


def calculate_probability_metrics(
    probabilities: list[float],
    outcomes: list[int],
    bin_count: int = 10,
) -> ProbabilityMetrics:
    """Measure probability accuracy and calibration."""

    _validate_probability_inputs(
        probabilities,
        outcomes,
    )

    if bin_count <= 0:
        raise ValueError("bin_count must be positive.")

    bins: list[list[tuple[float, int]]] = [
        [] for _ in range(bin_count)
    ]

    for probability, outcome in zip(
        probabilities,
        outcomes,
        strict=True,
    ):
        bin_index = min(
            int(probability * bin_count),
            bin_count - 1,
        )
        bins[bin_index].append(
            (probability, outcome)
        )

    calibration_bins: list[CalibrationBin] = []
    calibration_error = 0.0
    sample_count = len(probabilities)

    for bin_index, observations in enumerate(bins):
        if not observations:
            continue

        mean_probability = sum(
            probability
            for probability, _ in observations
        ) / len(observations)
        observed_frequency = sum(
            outcome
            for _, outcome in observations
        ) / len(observations)

        calibration_error += (
            len(observations)
            / sample_count
            * abs(
                mean_probability
                - observed_frequency
            )
        )

        calibration_bins.append(
            CalibrationBin(
                lower_probability=(
                    bin_index / bin_count
                ),
                upper_probability=(
                    (bin_index + 1) / bin_count
                ),
                sample_count=len(observations),
                mean_probability=mean_probability,
                observed_frequency=observed_frequency,
            )
        )

    return ProbabilityMetrics(
        sample_count=sample_count,
        brier_score=brier_score(
            probabilities,
            outcomes,
        ),
        log_loss=calculate_log_loss(
            probabilities,
            outcomes,
        ),
        expected_calibration_error=calibration_error,
        calibration_bins=tuple(calibration_bins),
    )


def brier_score(
    probabilities: list[float],
    outcomes: list[int],
) -> float:
    """Average squared probability error. Lower is better."""

    _validate_probability_inputs(
        probabilities,
        outcomes,
    )

    return sum(
        (probability - outcome) ** 2
        for probability, outcome in zip(
            probabilities,
            outcomes,
            strict=True,
        )
    ) / len(probabilities)


def calculate_log_loss(
    probabilities: list[float],
    outcomes: list[int],
) -> float:
    """Penalize confident incorrect probabilities."""

    _validate_probability_inputs(
        probabilities,
        outcomes,
    )

    total_loss = 0.0

    for probability, outcome in zip(
        probabilities,
        outcomes,
        strict=True,
    ):
        safe_probability = min(
            max(probability, _LOG_EPSILON),
            1.0 - _LOG_EPSILON,
        )

        total_loss -= (
            outcome * log(safe_probability)
            + (1 - outcome)
            * log(1.0 - safe_probability)
        )

    return total_loss / len(probabilities)


def sharpe_ratio(
    returns: list[float],
    periods_per_year: int = 365,
) -> float:
    """Measure average return relative to its variability."""

    if len(returns) < 2:
        raise ValueError(
            "At least two returns are required."
        )

    if not all(isfinite(value) for value in returns):
        raise ValueError("Returns must all be finite.")

    if periods_per_year <= 0:
        raise ValueError(
            "periods_per_year must be positive."
        )

    mean = sum(returns) / len(returns)
    variance = sum(
        (value - mean) ** 2
        for value in returns
    ) / (len(returns) - 1)

    if variance == 0:
        return 0.0

    return (
        mean
        / sqrt(variance)
        * sqrt(periods_per_year)
    )


def _validate_probability_inputs(
    probabilities: list[float],
    outcomes: list[int],
) -> None:
    if not probabilities:
        raise ValueError(
            "At least one probability is required."
        )

    if len(probabilities) != len(outcomes):
        raise ValueError(
            "Probabilities and outcomes must have "
            "equal length."
        )

    if not all(
        isfinite(probability)
        and 0.0 <= probability <= 1.0
        for probability in probabilities
    ):
        raise ValueError(
            "Probabilities must be finite values "
            "between zero and one."
        )

    if not all(
        isinstance(outcome, int)
        and not isinstance(outcome, bool)
        and outcome in (0, 1)
        for outcome in outcomes
    ):
        raise ValueError(
            "Outcomes must be integers containing "
            "only zero or one."
        )