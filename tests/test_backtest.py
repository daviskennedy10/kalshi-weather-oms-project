from math import sqrt

import pytest

from weather_oms.analysis.backtest import (
    brier_score,
    calculate_log_loss,
    calculate_probability_metrics,
    sharpe_ratio,
)


def test_calculates_brier_score() -> None:
    score = brier_score(
        probabilities=[0.8, 0.3],
        outcomes=[1, 0],
    )

    assert score == pytest.approx(0.065)


def test_calculates_log_loss() -> None:
    score = calculate_log_loss(
        probabilities=[0.8, 0.3],
        outcomes=[1, 0],
    )

    assert score > 0
    assert score < 1


def test_calculates_probability_metrics() -> None:
    metrics = calculate_probability_metrics(
        probabilities=[0.8, 0.3],
        outcomes=[1, 0],
        bin_count=10,
    )

    assert metrics.sample_count == 2
    assert metrics.brier_score == pytest.approx(0.065)
    assert (
        metrics.expected_calibration_error
        == pytest.approx(0.25)
    )
    assert len(metrics.calibration_bins) == 2


def test_probability_of_one_uses_final_bin() -> None:
    metrics = calculate_probability_metrics(
        probabilities=[1.0],
        outcomes=[1],
    )

    final_bin = metrics.calibration_bins[0]

    assert final_bin.lower_probability == 0.9
    assert final_bin.upper_probability == 1.0
    assert final_bin.observed_frequency == 1.0


def test_rejects_empty_probabilities() -> None:
    with pytest.raises(
        ValueError,
        match="At least one probability",
    ):
        brier_score([], [])


def test_rejects_unequal_lengths() -> None:
    with pytest.raises(
        ValueError,
        match="equal length",
    ):
        brier_score([0.5], [0, 1])


def test_rejects_invalid_probability() -> None:
    with pytest.raises(
        ValueError,
        match="between zero and one",
    ):
        brier_score([1.1], [1])


def test_rejects_invalid_outcome() -> None:
    with pytest.raises(
        ValueError,
        match="zero or one",
    ):
        brier_score([0.5], [2])


def test_rejects_boolean_outcome() -> None:
    with pytest.raises(
        ValueError,
        match="zero or one",
    ):
        brier_score([0.5], [True])


def test_rejects_invalid_bin_count() -> None:
    with pytest.raises(
        ValueError,
        match="bin_count must be positive",
    ):
        calculate_probability_metrics(
            probabilities=[0.5],
            outcomes=[1],
            bin_count=0,
        )


def test_calculates_sharpe_ratio() -> None:
    ratio = sharpe_ratio(
        returns=[0.10, 0.20, 0.30],
        periods_per_year=1,
    )

    assert ratio == pytest.approx(2.0)


def test_constant_returns_have_zero_sharpe() -> None:
    assert sharpe_ratio(
        [0.10, 0.10],
    ) == 0.0


def test_rejects_too_few_returns() -> None:
    with pytest.raises(
        ValueError,
        match="At least two returns",
    ):
        sharpe_ratio([0.10])


def test_rejects_nonpositive_periods() -> None:
    with pytest.raises(
        ValueError,
        match="periods_per_year must be positive",
    ):
        sharpe_ratio(
            [0.10, 0.20],
            periods_per_year=0,
        )


def test_sharpe_matches_manual_formula() -> None:
    ratio = sharpe_ratio(
        returns=[-1.0, 1.0],
        periods_per_year=2,
    )

    assert ratio == pytest.approx(0.0 / sqrt(2.0))