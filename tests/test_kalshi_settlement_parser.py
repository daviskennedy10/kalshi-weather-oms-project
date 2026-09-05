from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest

from weather_oms.ingest.kalshi_settlement_parser import (
    SettlementParseError,
    parse_temperature_settlement,
)


def make_settled_event() -> dict[str, Any]:
    return {
        "event_ticker": "KXHIGHNY-26SEP03",
        "series_ticker": "KXHIGHNY",
        "markets": [
            {
                "ticker": "KXHIGHNY-26SEP03-T83",
                "result": "no",
                "expiration_value": "84.00",
                "settlement_ts": (
                    "2026-09-04T11:20:15.489719Z"
                ),
            },
            {
                "ticker": "KXHIGHNY-26SEP03-B83.5",
                "result": "yes",
                "expiration_value": "84.00",
                "settlement_ts": (
                    "2026-09-04T11:20:15.489719Z"
                ),
            },
        ],
    }


def test_parses_temperature_settlement() -> None:
    event = make_settled_event()
    retrieved_at = datetime(
        2026,
        9,
        4,
        12,
        0,
        tzinfo=UTC,
    )

    settlement = parse_temperature_settlement(
        event=event,
        station_code="KNYC",
        source_name="The Weather Company",
        source_url="https://weather.com/kalshi",
        retrieved_at=retrieved_at,
    )

    assert settlement.series_ticker == "KXHIGHNY"
    assert settlement.event_ticker == "KXHIGHNY-26SEP03"
    assert settlement.station_code == "KNYC"
    assert settlement.observation_date == date(2026, 9, 3)
    assert settlement.temperature_f == Decimal("84.00")
    assert settlement.source_name == "The Weather Company"
    assert settlement.source_url == "https://weather.com/kalshi"
    assert settlement.settled_at == datetime(
        2026,
        9,
        4,
        11,
        20,
        15,
        489719,
        tzinfo=UTC,
    )
    assert settlement.retrieved_at == retrieved_at


def test_rejects_multiple_winning_markets() -> None:
    event = make_settled_event()
    event["markets"][0]["result"] = "yes"

    with pytest.raises(
        SettlementParseError,
        match="exactly one winning market",
    ):
        parse_temperature_settlement(
            event=event,
            station_code="KNYC",
            source_name="The Weather Company",
            source_url="https://weather.com/kalshi",
            retrieved_at=datetime.now(UTC),
        )


def test_rejects_disagreeing_temperatures() -> None:
    event = make_settled_event()
    event["markets"][0]["expiration_value"] = "85.00"

    with pytest.raises(
        SettlementParseError,
        match="disagree about the final temperature",
    ):
        parse_temperature_settlement(
            event=event,
            station_code="KNYC",
            source_name="The Weather Company",
            source_url="https://weather.com/kalshi",
            retrieved_at=datetime.now(UTC),
        )


def test_rejects_invalid_event_date() -> None:
    event = make_settled_event()
    event["event_ticker"] = "KXHIGHNY-NOT-A-DATE"

    with pytest.raises(
        SettlementParseError,
        match="Could not read a date",
    ):
        parse_temperature_settlement(
            event=event,
            station_code="KNYC",
            source_name="The Weather Company",
            source_url="https://weather.com/kalshi",
            retrieved_at=datetime.now(UTC),
        )