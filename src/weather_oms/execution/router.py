from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from weather_oms.execution.fair_value import Quote, buy_no_edge, buy_yes_edge


@dataclass(frozen=True, slots=True)
class Candidate:
    ticker: str
    probability: Decimal
    quote: Quote


@dataclass(frozen=True, slots=True)
class Route:
    ticker: str
    side: str
    edge: Decimal


def best_route(candidates: Iterable[Candidate], minimum_edge: Decimal) -> Route | None:
    routes = [
        route
        for item in candidates
        for route in (
            Route(item.ticker, "yes", buy_yes_edge(item.probability, item.quote)),
            Route(item.ticker, "no", buy_no_edge(item.probability, item.quote)),
        )
        if route.edge >= minimum_edge
    ]
    return max(routes, key=lambda route: route.edge, default=None)

