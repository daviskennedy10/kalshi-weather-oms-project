import pytest

from weather_oms.ingest.kalshi_market_parser import (
    KalshiTemperatureMarket,
)
from weather_oms.signal.market_comparison import (
    compare_market_probability,
)
from weather_oms.signal.market_probability import (
    TemperatureBracket,
)


def market(
    yes_ask_cents: int,
    no_ask_cents: int,
) -> KalshiTemperatureMarket:
    return KalshiTemperatureMarket(
        ticker="KXHIGHNY-TEST-B80.5",
        title="Will the maximum temperature be 80-81°?",
        yes_sub_title="80° to 81°",
        bracket=TemperatureBracket(
            lower_f=80,
            upper_f=81,
        ),
        yes_bid_cents=52,
        yes_ask_cents=yes_ask_cents,
        no_bid_cents=46,
        no_ask_cents=no_ask_cents,
    )


def test_identifies_yes_candidate_after_fees() -> None:
    comparison = compare_market_probability(
        market(
            yes_ask_cents=55,
            no_ask_cents=40,
        ),
        our_yes_probability=0.625,
    )

    assert comparison.our_yes_probability == pytest.approx(
        0.625
    )
    assert comparison.our_no_probability == pytest.approx(
        0.375
    )

    assert comparison.yes_pre_fee_edge == pytest.approx(
        0.075
    )
    assert comparison.no_pre_fee_edge == pytest.approx(
        -0.025
    )

    assert comparison.yes_fee_dollars == pytest.approx(
        0.0174
    )
    assert comparison.no_fee_dollars == pytest.approx(
        0.0168
    )

    assert comparison.yes_net_edge == pytest.approx(
        0.0576
    )
    assert comparison.no_net_edge == pytest.approx(
        -0.0418
    )

    assert comparison.candidate_side == "yes"
    assert comparison.candidate_edge == pytest.approx(
        0.0576
    )


def test_identifies_no_candidate_after_fees() -> None:
    comparison = compare_market_probability(
        market(
            yes_ask_cents=40,
            no_ask_cents=60,
        ),
        our_yes_probability=0.30,
    )

    assert comparison.our_yes_probability == pytest.approx(
        0.30
    )
    assert comparison.our_no_probability == pytest.approx(
        0.70
    )

    assert comparison.yes_pre_fee_edge == pytest.approx(
        -0.10
    )
    assert comparison.no_pre_fee_edge == pytest.approx(
        0.10
    )

    assert comparison.yes_fee_dollars == pytest.approx(
        0.0168
    )
    assert comparison.no_fee_dollars == pytest.approx(
        0.0168
    )

    assert comparison.yes_net_edge == pytest.approx(
        -0.1168
    )
    assert comparison.no_net_edge == pytest.approx(
        0.0832
    )

    assert comparison.candidate_side == "no"
    assert comparison.candidate_edge == pytest.approx(
        0.0832
    )


def test_returns_no_candidate_when_both_sides_are_overpriced() -> None:
    comparison = compare_market_probability(
        market(
            yes_ask_cents=55,
            no_ask_cents=50,
        ),
        our_yes_probability=0.52,
    )

    assert comparison.yes_pre_fee_edge == pytest.approx(
        -0.03
    )
    assert comparison.no_pre_fee_edge == pytest.approx(
        -0.02
    )

    assert comparison.yes_fee_dollars == pytest.approx(
        0.0174
    )
    assert comparison.no_fee_dollars == pytest.approx(
        0.0175
    )

    assert comparison.yes_net_edge == pytest.approx(
        -0.0474
    )
    assert comparison.no_net_edge == pytest.approx(
        -0.0375
    )

    assert comparison.candidate_side is None
    assert comparison.candidate_edge == pytest.approx(
        0.0
    )


@pytest.mark.parametrize(
    "invalid_probability",
    [
        -0.01,
        1.01,
        float("nan"),
        float("inf"),
    ],
)
def test_rejects_invalid_probability(
    invalid_probability: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="between 0 and 1",
    ):
        compare_market_probability(
            market(
                yes_ask_cents=50,
                no_ask_cents=51,
            ),
            our_yes_probability=invalid_probability,
        )

def test_ignores_positive_edge_below_minimum() -> None:
    comparison = compare_market_probability(
        market(
            yes_ask_cents=50,
            no_ask_cents=51,
        ),
        our_yes_probability=0.55,
    )

    assert comparison.yes_pre_fee_edge == pytest.approx(
        0.05
    )
    assert comparison.yes_net_edge == pytest.approx(
        0.0325
    )
    assert comparison.candidate_side is None
    assert comparison.candidate_edge == pytest.approx(
        0.0
    )


@pytest.mark.parametrize(
    "invalid_minimum",
    [
        -0.01,
        1.01,
        float("nan"),
        float("inf"),
    ],
)
def test_rejects_invalid_minimum_edge(
    invalid_minimum: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="minimum_net_edge",
    ):
        compare_market_probability(
            market(
                yes_ask_cents=50,
                no_ask_cents=51,
            ),
            our_yes_probability=0.60,
            minimum_net_edge=invalid_minimum,
        )