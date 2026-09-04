from math import erf, sqrt


def normal_cdf(value: float, mean: float, stddev: float) -> float:
    if stddev <= 0:
        raise ValueError("stddev must be positive")
    return 0.5 * (1 + erf((value - mean) / (stddev * sqrt(2))))


def interval_probability(low_f: float, high_f: float, mean_f: float, stddev_f: float) -> float:
    """Baseline only; later replace with empirically calibrated ensemble probabilities."""
    if low_f >= high_f:
        raise ValueError("low_f must be below high_f")
    return normal_cdf(high_f, mean_f, stddev_f) - normal_cdf(low_f, mean_f, stddev_f)

