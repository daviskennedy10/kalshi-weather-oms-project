import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

EVENT_DATE_PATTERN = re.compile(
    r"-(?P<year>\d{2})(?P<month>[A-Z]{3})(?P<day>\d{2})$"
)

MONTH_NUMBERS = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}


class SettlementParseError(ValueError):
    """Raised when a Kalshi settlement is missing or inconsistent."""


@dataclass(frozen=True, slots=True)
class ParsedTemperatureSettlement:
    series_ticker: str
    event_ticker: str
    station_code: str
    observation_date: date
    temperature_f: Decimal
    source_name: str
    source_url: str
    settled_at: datetime
    retrieved_at: datetime


def parse_event_date(event_ticker: str) -> date:
    match = EVENT_DATE_PATTERN.search(event_ticker)

    if match is None:
        raise SettlementParseError(
            f"Could not read a date from event ticker {event_ticker!r}."
        )

    year = 2000 + int(match.group("year"))
    month_text = match.group("month")
    day = int(match.group("day"))

    month = MONTH_NUMBERS.get(month_text)

    if month is None:
        raise SettlementParseError(
            f"Invalid month in event ticker {event_ticker!r}."
        )

    try:
        return date(year, month, day)
    except ValueError as error:
        raise SettlementParseError(
            f"Invalid date in event ticker {event_ticker!r}."
        ) from error


def parse_utc_datetime(value: object, field_name: str) -> datetime:
    if not isinstance(value, str):
        raise SettlementParseError(
            f"{field_name} must be a timestamp string."
        )

    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise SettlementParseError(
            f"Invalid {field_name}: {value!r}."
        ) from error

    if parsed.tzinfo is None:
        raise SettlementParseError(
            f"{field_name} must include a timezone."
        )

    return parsed


def parse_temperature_settlement(
    event: dict[str, Any],
    station_code: str,
    source_name: str,
    source_url: str,
    retrieved_at: datetime,
) -> ParsedTemperatureSettlement:
    if retrieved_at.tzinfo is None:
        raise SettlementParseError(
            "retrieved_at must include a timezone."
        )

    event_ticker = event.get("event_ticker")
    series_ticker = event.get("series_ticker")

    if not isinstance(event_ticker, str):
        raise SettlementParseError(
            "Settled event is missing its event ticker."
        )

    if not isinstance(series_ticker, str):
        raise SettlementParseError(
            "Settled event is missing its series ticker."
        )

    markets = event.get("markets")

    if not isinstance(markets, list) or not markets:
        raise SettlementParseError(
            "Settled event does not contain markets."
        )

    valid_markets = [
        market
        for market in markets
        if isinstance(market, dict)
    ]

    if len(valid_markets) != len(markets):
        raise SettlementParseError(
            "Settled event contains an invalid market."
        )

    winning_markets = [
        market
        for market in valid_markets
        if market.get("result") == "yes"
    ]

    if len(winning_markets) != 1:
        raise SettlementParseError(
            "Settled event must contain exactly one winning market."
        )

    expiration_values: set[Decimal] = set()

    for market in valid_markets:
        raw_temperature = market.get("expiration_value")

        try:
            temperature = Decimal(str(raw_temperature))
        except InvalidOperation as error:
            raise SettlementParseError(
                f"Invalid expiration value: {raw_temperature!r}."
            ) from error

        if not temperature.is_finite():
            raise SettlementParseError(
                f"Invalid expiration value: {raw_temperature!r}."
            )

        expiration_values.add(temperature)

    if len(expiration_values) != 1:
        raise SettlementParseError(
            "Markets disagree about the final temperature."
        )

    settlement_times = {
        parse_utc_datetime(
            market.get("settlement_ts"),
            "settlement_ts",
        )
        for market in valid_markets
    }

    if len(settlement_times) != 1:
        raise SettlementParseError(
            "Markets disagree about the settlement time."
        )

    return ParsedTemperatureSettlement(
        series_ticker=series_ticker,
        event_ticker=event_ticker,
        station_code=station_code,
        observation_date=parse_event_date(event_ticker),
        temperature_f=expiration_values.pop(),
        source_name=source_name,
        source_url=source_url,
        settled_at=settlement_times.pop(),
        retrieved_at=retrieved_at,
    )