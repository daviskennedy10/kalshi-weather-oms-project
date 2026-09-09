import pytest

from weather_oms.signal.market_probability import (
    TemperatureBracket,
    calculate_bracket_probability,
    calculate_event_probabilities,
    round_reported_temperature,
    validate_complete_brackets,
)


def test_rounds_temperature_half_up() -> None:
    assert round_reported_temperature(80.49) == 80
    assert round_reported_temperature(80.50) == 81
    assert round_reported_temperature(81.50) == 82


def test_calculates_bounded_bracket_probability() -> None:
    members = (
        79.2,
        79.6,
        80.4,
        81.2,
        81.6,
        83.0,
    )

    result = calculate_bracket_probability(
        members,
        TemperatureBracket(
            lower_f=80,
            upper_f=81,
        ),
    )

    assert result.matching_members == 3
    assert result.total_members == 6
    assert result.probability == pytest.approx(0.5)


def test_calculates_lower_tail_probability() -> None:
    members = (
        78.2,
        79.2,
        79.6,
        80.4,
    )

    result = calculate_bracket_probability(
        members,
        TemperatureBracket(
            lower_f=None,
            upper_f=79,
        ),
    )

    assert result.matching_members == 2
    assert result.probability == pytest.approx(0.5)


def test_calculates_upper_tail_probability() -> None:
    members = (
        86.4,
        87.4,
        87.6,
        88.4,
    )

    result = calculate_bracket_probability(
        members,
        TemperatureBracket(
            lower_f=88,
            upper_f=None,
        ),
    )

    assert result.matching_members == 2
    assert result.probability == pytest.approx(0.5)


def test_applies_bias_before_assigning_brackets() -> None:
    members = (
        78.6,
        79.2,
        80.2,
        81.2,
    )

    result = calculate_bracket_probability(
        members,
        TemperatureBracket(
            lower_f=80,
            upper_f=81,
        ),
        bias_adjustment_f=1.0,
    )

    assert result.matching_members == 3
    assert result.probability == pytest.approx(0.75)


def test_rejects_empty_ensemble() -> None:
    with pytest.raises(ValueError, match="At least one"):
        calculate_bracket_probability(
            (),
            TemperatureBracket(
                lower_f=80,
                upper_f=81,
            ),
        )


def test_rejects_bracket_without_bounds() -> None:
    with pytest.raises(ValueError, match="at least one bound"):
        TemperatureBracket(
            lower_f=None,
            upper_f=None,
        )


def test_rejects_reversed_bracket() -> None:
    with pytest.raises(ValueError, match="cannot exceed"):
        TemperatureBracket(
            lower_f=82,
            upper_f=81,
        )


@pytest.mark.parametrize(
    "invalid_temperature",
    [float("nan"), float("inf")],
)
def test_rejects_non_finite_member(
    invalid_temperature: float,
) -> None:
    with pytest.raises(ValueError, match="finite"):
        calculate_bracket_probability(
            (80.0, invalid_temperature),
            TemperatureBracket(
                lower_f=80,
                upper_f=81,
            ),
        )

def event_brackets() -> tuple[TemperatureBracket, ...]:
    return (
        TemperatureBracket(None, 79),
        TemperatureBracket(80, 81),
        TemperatureBracket(82, 83),
        TemperatureBracket(84, 85),
        TemperatureBracket(86, 87),
        TemperatureBracket(88, None),
    )


def test_calculates_smoothed_event_probabilities() -> None:
    members = tuple(
        [79.0] * 40
        + [80.0] * 20
        + [82.0] * 4
    )

    probabilities = calculate_event_probabilities(
        members,
        event_brackets(),
    )

    assert probabilities[0].matching_members == 40
    assert probabilities[0].raw_probability == pytest.approx(
        40 / 64
    )
    assert probabilities[0].smoothed_probability == (
        pytest.approx(40.5 / 67)
    )

    assert probabilities[3].matching_members == 0
    assert probabilities[3].smoothed_probability == (
        pytest.approx(0.5 / 67)
    )

    assert sum(
        result.smoothed_probability
        for result in probabilities
    ) == pytest.approx(1.0)


def test_rejects_gap_between_brackets() -> None:
    brackets = (
        TemperatureBracket(None, 79),
        TemperatureBracket(81, None),
    )

    with pytest.raises(ValueError, match="gap or overlap"):
        validate_complete_brackets(brackets)


def test_rejects_overlap_between_brackets() -> None:
    brackets = (
        TemperatureBracket(None, 80),
        TemperatureBracket(80, None),
    )

    with pytest.raises(ValueError, match="gap or overlap"):
        validate_complete_brackets(brackets)


def test_rejects_missing_lower_tail() -> None:
    brackets = (
        TemperatureBracket(78, 79),
        TemperatureBracket(80, None),
    )

    with pytest.raises(ValueError, match="lower-tail"):
        validate_complete_brackets(brackets)


def test_rejects_missing_upper_tail() -> None:
    brackets = (
        TemperatureBracket(None, 79),
        TemperatureBracket(80, 81),
    )

    with pytest.raises(ValueError, match="upper-tail"):
        validate_complete_brackets(brackets)