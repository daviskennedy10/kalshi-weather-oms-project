from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from weather_oms.signal.market_probability import (
    TemperatureBracket,
)


class KalshiMarketParseError(ValueError):
    """Raised when a Kalshi temperature market is malformed."""


@dataclass(frozen=True, slots=True)
class KalshiTemperatureMarket:
    ticker: str
    title: str
    yes_sub_title: str
    bracket: TemperatureBracket
    yes_bid_cents: int
    yes_ask_cents: int
    no_bid_cents: int
    no_ask_cents: int


def parse_integer_strike(
    value: object,
    field_name: str,
) -> int:
    if isinstance(value, bool) or not isinstance(
        value,
        (int, float),
    ):
        raise KalshiMarketParseError(
            f"{field_name} must be numeric."
        )

    integer_value = int(value)

    if float(value) != integer_value:
        raise KalshiMarketParseError(
            f"{field_name} must be a whole number."
        )

    return integer_value


def parse_price_cents(
    value: object,
    field_name: str,
) -> int:
    if not isinstance(value, str):
        raise KalshiMarketParseError(
            f"{field_name} must be a decimal string."
        )

    try:
        dollars = Decimal(value)
    except InvalidOperation as error:
        raise KalshiMarketParseError(
            f"{field_name} is not a valid price."
        ) from error

    cents = dollars * 100

    if cents != cents.to_integral_value():
        raise KalshiMarketParseError(
            f"{field_name} must use whole cents."
        )

    cents_integer = int(cents)

    if not 0 <= cents_integer <= 100:
        raise KalshiMarketParseError(
            f"{field_name} must be between 0 and 100 cents."
        )

    return cents_integer


def parse_temperature_bracket(
    market: dict[str, Any],
) -> TemperatureBracket:
    strike_type = market.get("strike_type")

    if strike_type == "less":
        cap_strike = parse_integer_strike(
            market.get("cap_strike"),
            "cap_strike",
        )

        return TemperatureBracket(
            lower_f=None,
            upper_f=cap_strike - 1,
        )

    if strike_type == "greater":
        floor_strike = parse_integer_strike(
            market.get("floor_strike"),
            "floor_strike",
        )

        return TemperatureBracket(
            lower_f=floor_strike + 1,
            upper_f=None,
        )

    if strike_type == "between":
        floor_strike = parse_integer_strike(
            market.get("floor_strike"),
            "floor_strike",
        )
        cap_strike = parse_integer_strike(
            market.get("cap_strike"),
            "cap_strike",
        )

        return TemperatureBracket(
            lower_f=floor_strike,
            upper_f=cap_strike,
        )

    raise KalshiMarketParseError(
        f"Unsupported strike type: {strike_type!r}."
    )


def parse_temperature_markets(
    response: dict[str, Any],
) -> list[KalshiTemperatureMarket]:
    event = response.get("event")

    if not isinstance(event, dict):
        raise KalshiMarketParseError(
            "Kalshi response does not contain an event object."
        )

    markets = event.get("markets")

    if not isinstance(markets, list) or not markets:
        raise KalshiMarketParseError(
            "Kalshi event does not contain any markets."
        )

    parsed_markets: list[KalshiTemperatureMarket] = []

    for market in markets:
        if not isinstance(market, dict):
            raise KalshiMarketParseError(
                "Kalshi market must be an object."
            )

        ticker = market.get("ticker")
        title = market.get("title")
        yes_sub_title = market.get("yes_sub_title")

        if not isinstance(ticker, str) or not ticker:
            raise KalshiMarketParseError(
                "Market ticker must be a non-empty string."
            )

        if not isinstance(title, str) or not title:
            raise KalshiMarketParseError(
                "Market title must be a non-empty string."
            )

        if (
            not isinstance(yes_sub_title, str)
            or not yes_sub_title
        ):
            raise KalshiMarketParseError(
                "YES subtitle must be a non-empty string."
            )

        parsed_markets.append(
            KalshiTemperatureMarket(
                ticker=ticker,
                title=title,
                yes_sub_title=yes_sub_title,
                bracket=parse_temperature_bracket(market),
                yes_bid_cents=parse_price_cents(
                    market.get("yes_bid_dollars"),
                    "yes_bid_dollars",
                ),
                yes_ask_cents=parse_price_cents(
                    market.get("yes_ask_dollars"),
                    "yes_ask_dollars",
                ),
                no_bid_cents=parse_price_cents(
                    market.get("no_bid_dollars"),
                    "no_bid_dollars",
                ),
                no_ask_cents=parse_price_cents(
                    market.get("no_ask_dollars"),
                    "no_ask_dollars",
                ),
            )
        )

    return parsed_markets
