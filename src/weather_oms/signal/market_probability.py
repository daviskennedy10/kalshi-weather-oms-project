from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from itertools import pairwise
from math import isfinite


@dataclass(frozen=True, slots=True)
class TemperatureBracket:
    lower_f: int | None
    upper_f: int | None

    def __post_init__(self) -> None:
        if self.lower_f is None and self.upper_f is None:
            raise ValueError(
                "A temperature bracket must have at least one bound."
            )

        if (
            self.lower_f is not None
            and self.upper_f is not None
            and self.lower_f > self.upper_f
        ):
            raise ValueError(
                "Bracket lower bound cannot exceed upper bound."
            )

    def contains(self, temperature_f: int) -> bool:
        if (
            self.lower_f is not None
            and temperature_f < self.lower_f
        ):
            return False

        return not (
            self.upper_f is not None
            and temperature_f > self.upper_f
        )


@dataclass(frozen=True, slots=True)
class BracketProbability:
    matching_members: int
    total_members: int
    probability: float


def round_reported_temperature(
    temperature_f: float,
) -> int:
    if not isfinite(temperature_f):
        raise ValueError(
            "Temperature must be finite."
        )

    rounded = Decimal(str(temperature_f)).quantize(
        Decimal(1),
        rounding=ROUND_HALF_UP,
    )

    return int(rounded)


def calculate_bracket_probability(
    member_highs_f: tuple[float, ...],
    bracket: TemperatureBracket,
    bias_adjustment_f: float = 0.0,
) -> BracketProbability:
    if not member_highs_f:
        raise ValueError(
            "At least one ensemble member is required."
        )

    if not isfinite(bias_adjustment_f):
        raise ValueError(
            "bias_adjustment_f must be finite."
        )

    reported_temperatures = [
        round_reported_temperature(
            member_high_f + bias_adjustment_f
        )
        for member_high_f in member_highs_f
    ]

    matching_members = sum(
        bracket.contains(temperature_f)
        for temperature_f in reported_temperatures
    )
    total_members = len(reported_temperatures)

    return BracketProbability(
        matching_members=matching_members,
        total_members=total_members,
        probability=matching_members / total_members,
    )

@dataclass(frozen=True, slots=True)
class EventBracketProbability:
    bracket: TemperatureBracket
    matching_members: int
    total_members: int
    raw_probability: float
    smoothed_probability: float


def validate_complete_brackets(
    brackets: tuple[TemperatureBracket, ...],
) -> None:
    if len(brackets) < 2:
        raise ValueError(
            "At least two temperature brackets are required."
        )

    ordered = sorted(
        brackets,
        key=lambda bracket: (
            float("-inf")
            if bracket.lower_f is None
            else bracket.lower_f
        ),
    )

    if ordered[0].lower_f is not None:
        raise ValueError(
            "Brackets must begin with a lower-tail market."
        )

    if ordered[-1].upper_f is not None:
        raise ValueError(
            "Brackets must end with an upper-tail market."
        )

    for current, following in pairwise(ordered):
        if (
            current.upper_f is None
            or following.lower_f is None
            or following.lower_f != current.upper_f + 1
        ):
            raise ValueError(
                "Temperature brackets contain a gap or overlap."
            )


def calculate_event_probabilities(
    member_highs_f: tuple[float, ...],
    brackets: tuple[TemperatureBracket, ...],
    bias_adjustment_f: float = 0.0,
    prior_weight: float = 0.5,
) -> tuple[EventBracketProbability, ...]:
    if not member_highs_f:
        raise ValueError(
            "At least one ensemble member is required."
        )

    if not isfinite(bias_adjustment_f):
        raise ValueError(
            "bias_adjustment_f must be finite."
        )

    if not isfinite(prior_weight) or prior_weight <= 0:
        raise ValueError(
            "prior_weight must be finite and positive."
        )

    validate_complete_brackets(brackets)

    counts = [0] * len(brackets)

    for member_high_f in member_highs_f:
        reported_temperature = round_reported_temperature(
            member_high_f + bias_adjustment_f
        )

        matching_indexes = [
            index
            for index, bracket in enumerate(brackets)
            if bracket.contains(reported_temperature)
        ]

        if len(matching_indexes) != 1:
            raise ValueError(
                "Each ensemble member must match exactly "
                "one temperature bracket."
            )

        counts[matching_indexes[0]] += 1

    total_members = len(member_highs_f)
    smoothed_total = (
        total_members + prior_weight * len(brackets)
    )

    return tuple(
        EventBracketProbability(
            bracket=bracket,
            matching_members=count,
            total_members=total_members,
            raw_probability=count / total_members,
            smoothed_probability=(
                (count + prior_weight) / smoothed_total
            ),
        )
        for bracket, count in zip(
            brackets,
            counts,
            strict=True,
        )
    )