from dataclasses import dataclass
from decimal import Decimal
from math import isfinite
from typing import Literal, Protocol

from weather_oms.execution.fees import calculate_taker_fee

DEFAULT_MINIMUM_NET_EDGE = 0.05


class MarketPrices(Protocol):
    @property
    def ticker(self) -> str:
        ...

    @property
    def yes_ask_cents(self) -> int:
        ...

    @property
    def no_ask_cents(self) -> int:
        ...


TradeSide = Literal["yes", "no"]


@dataclass(frozen=True, slots=True)
class MarketComparison:
    market_ticker: str
    our_yes_probability: float
    our_no_probability: float
    yes_ask_cents: int
    no_ask_cents: int
    yes_fee_dollars: float
    no_fee_dollars: float
    yes_pre_fee_edge: float
    no_pre_fee_edge: float
    yes_net_edge: float
    no_net_edge: float
    minimum_net_edge: float
    candidate_side: TradeSide | None
    candidate_edge: float


def compare_market_probability(
    market: MarketPrices,
    our_yes_probability: float,
    minimum_net_edge: float = DEFAULT_MINIMUM_NET_EDGE,
) -> MarketComparison:
    if (
        not isfinite(our_yes_probability)
        or not 0.0 <= our_yes_probability <= 1.0
    ):
        raise ValueError(
            "our_yes_probability must be between 0 and 1."
        )

    if (
        not isfinite(minimum_net_edge)
        or not 0.0 <= minimum_net_edge <= 1.0
    ):
        raise ValueError(
            "minimum_net_edge must be between 0 and 1."
        )

    our_no_probability = 1.0 - our_yes_probability

    yes_ask_price = (
        Decimal(market.yes_ask_cents) / Decimal(100)
    )
    no_ask_price = (
        Decimal(market.no_ask_cents) / Decimal(100)
    )

    yes_fee = calculate_taker_fee(yes_ask_price)
    no_fee = calculate_taker_fee(no_ask_price)

    yes_ask_probability = float(yes_ask_price)
    no_ask_probability = float(no_ask_price)

    yes_pre_fee_edge = (
        our_yes_probability - yes_ask_probability
    )
    no_pre_fee_edge = (
        our_no_probability - no_ask_probability
    )

    yes_net_edge = yes_pre_fee_edge - float(yes_fee)
    no_net_edge = no_pre_fee_edge - float(no_fee)

    candidate_side: TradeSide | None = None
    candidate_edge = 0.0

    if (
        yes_net_edge >= minimum_net_edge
        and yes_net_edge >= no_net_edge
    ):
        candidate_side = "yes"
        candidate_edge = yes_net_edge
    elif no_net_edge >= minimum_net_edge:
        candidate_side = "no"
        candidate_edge = no_net_edge

    return MarketComparison(
        market_ticker=market.ticker,
        our_yes_probability=our_yes_probability,
        our_no_probability=our_no_probability,
        yes_ask_cents=market.yes_ask_cents,
        no_ask_cents=market.no_ask_cents,
        yes_fee_dollars=float(yes_fee),
        no_fee_dollars=float(no_fee),
        yes_pre_fee_edge=yes_pre_fee_edge,
        no_pre_fee_edge=no_pre_fee_edge,
        yes_net_edge=yes_net_edge,
        no_net_edge=no_net_edge,
        minimum_net_edge=minimum_net_edge,
        candidate_side=candidate_side,
        candidate_edge=candidate_edge,
    )