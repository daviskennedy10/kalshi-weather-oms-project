import pytest

from weather_oms.signal.calibrate import interval_probability, normal_cdf


def test_mean_has_half_cumulative_probability() -> None:
    assert normal_cdf(70, 70, 2) == pytest.approx(0.5)


def test_interval_probability_is_bounded() -> None:
    assert 0 < interval_probability(68, 72, 70, 2) < 1

