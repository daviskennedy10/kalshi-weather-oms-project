import pytest

from weather_oms.ingest.kalshi_market_parser import (
    KalshiMarketParseError,
    parse_price_cents,
    parse_temperature_markets,
)


def market(
    ticker: str,
    strike_type: str,
    floor_strike: float | None,
    cap_strike: float | None,
    yes_bid: str,
    yes_ask: str,
) -> dict[str, object]:
    return {
        "ticker": ticker,
        "title": f"Market {ticker}",
        "yes_sub_title": f"Outcome for {ticker}",
        "strike_type": strike_type,
        "floor_strike": floor_strike,
        "cap_strike": cap_strike,
        "yes_bid_dollars": yes_bid,
        "yes_ask_dollars": yes_ask,
        "no_bid_dollars": "0.4600",
        "no_ask_dollars": "0.4800",

    }


def test_parses_all_temperature_bracket_shapes() -> None:
    response = {
        "event": {
            "markets": [
                market(
                    "LOW",
                    "less",
                    None,
                    80,
                    "0.0600",
                    "0.0800",
                ),
                market(
                    "MIDDLE",
                    "between",
                    80,
                    81,
                    "0.5200",
                    "0.5300",
                ),
                market(
                    "HIGH",
                    "greater",
                    87,
                    None,
                    "0.0000",
                    "0.0100",
                ),
            ]
        }
    }

    markets = parse_temperature_markets(response)

    assert len(markets) == 3

    assert markets[0].bracket.lower_f is None
    assert markets[0].bracket.upper_f == 79
    assert markets[0].yes_bid_cents == 6
    assert markets[0].yes_ask_cents == 8

    assert markets[1].bracket.lower_f == 80
    assert markets[1].bracket.upper_f == 81
    assert markets[1].yes_bid_cents == 52
    assert markets[1].yes_ask_cents == 53

    assert markets[2].bracket.lower_f == 88
    assert markets[2].bracket.upper_f is None

    assert markets[0].no_bid_cents == 46
    assert markets[0].no_ask_cents == 48


def test_rejects_unknown_strike_type() -> None:
    response = {
        "event": {
            "markets": [
                market(
                    "UNKNOWN",
                    "approximately",
                    80,
                    81,
                    "0.5000",
                    "0.5100",
                )
            ]
        }
    }

    with pytest.raises(
        KalshiMarketParseError,
        match="Unsupported strike type",
    ):
        parse_temperature_markets(response)


def test_rejects_fractional_strike() -> None:
    response = {
        "event": {
            "markets": [
                market(
                    "FRACTIONAL",
                    "between",
                    80.5,
                    81,
                    "0.5000",
                    "0.5100",
                )
            ]
        }
    }

    with pytest.raises(
        KalshiMarketParseError,
        match="whole number",
    ):
        parse_temperature_markets(response)


@pytest.mark.parametrize(
    ("price", "expected_cents"),
    [
        ("0.0000", 0),
        ("0.0100", 1),
        ("0.5300", 53),
        ("1.0000", 100),
    ],
)
def test_parses_price_cents(
    price: str,
    expected_cents: int,
) -> None:
    assert parse_price_cents(
        price,
        "price",
    ) == expected_cents


@pytest.mark.parametrize(
    "invalid_price",
    [
        "invalid",
        "-0.0100",
        "1.0100",
        "0.0050",
    ],
)
def test_rejects_invalid_price(
    invalid_price: str,
) -> None:
    with pytest.raises(KalshiMarketParseError):
        parse_price_cents(
            invalid_price,
            "price",
        )


def test_rejects_missing_event() -> None:
    with pytest.raises(
        KalshiMarketParseError,
        match="event object",
    ):
        parse_temperature_markets({})