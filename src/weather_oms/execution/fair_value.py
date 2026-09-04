from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class Quote:
    yes_bid: Decimal
    yes_ask: Decimal


def buy_yes_edge(model_probability: Decimal, quote: Quote) -> Decimal:
    return model_probability - quote.yes_ask


def buy_no_edge(model_probability: Decimal, quote: Quote) -> Decimal:
    return (Decimal(1) - model_probability) - (Decimal(1) - quote.yes_bid)

