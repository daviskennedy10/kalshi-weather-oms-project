from decimal import Decimal

from weather_oms.execution.fair_value import Quote
from weather_oms.execution.router import Candidate, best_route


def test_router_chooses_largest_edge() -> None:
    route = best_route([
        Candidate("LOW", Decimal("0.55"), Quote(Decimal("0.40"), Decimal("0.45"))),
        Candidate("HIGH", Decimal("0.75"), Quote(Decimal("0.55"), Decimal("0.60"))),
    ], Decimal("0.05"))
    assert route is not None
    assert route.ticker == "HIGH"
    assert route.side == "yes"
    assert route.edge == Decimal("0.15")

