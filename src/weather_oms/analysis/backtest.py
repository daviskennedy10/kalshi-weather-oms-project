from math import sqrt


def brier_score(probabilities: list[float], outcomes: list[int]) -> float:
    if not probabilities or len(probabilities) != len(outcomes):
        raise ValueError("non-empty inputs must have equal length")
    return sum((p - y) ** 2 for p, y in zip(probabilities, outcomes, strict=True)) / len(outcomes)


def sharpe_ratio(returns: list[float], periods_per_year: int = 365) -> float:
    if len(returns) < 2:
        raise ValueError("at least two returns are required")
    mean = sum(returns) / len(returns)
    variance = sum((value - mean) ** 2 for value in returns) / (len(returns) - 1)
    return 0.0 if variance == 0 else mean / sqrt(variance) * sqrt(periods_per_year)

