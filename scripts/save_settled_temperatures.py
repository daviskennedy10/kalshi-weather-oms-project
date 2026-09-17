import asyncio
from datetime import UTC, datetime
from typing import Any, cast

import httpx

from weather_oms.config import Settings
from weather_oms.ingest.kalshi_settlement_parser import (
    parse_event_date,
    parse_temperature_settlement,
)
from weather_oms.storage.db import Database
from weather_oms.storage.temperature_settlement_repository import (
    save_temperature_settlement,
)

BASE_URL = "https://external-api.kalshi.com/trade-api/v2"
SERIES_TICKER = "KXHIGHNY"
STATION_CODE = "KNYC"


async def get_json(
    http: httpx.AsyncClient,
    url: str,
    params: dict[str, str | int] | None = None,
) -> dict[str, Any]:
    response = await http.get(
        url,
        params=params,
    )
    response.raise_for_status()

    data: object = response.json()

    if not isinstance(data, dict):
        raise TypeError(
            f"Expected {url} to return a JSON object."
        )

    return cast(dict[str, Any], data)


async def save_recent_settlements() -> None:
    settings = Settings()

    async with httpx.AsyncClient(timeout=20) as http:
        series_response = await get_json(
            http,
            f"{BASE_URL}/series/{SERIES_TICKER}",
        )

        events_response = await get_json(
            http,
            f"{BASE_URL}/events",
            params={
                "series_ticker": SERIES_TICKER,
                "status": "settled",
                "with_nested_markets": "true",
                "limit": 20,
            },
        )

        retrieved_at = datetime.now(UTC)

    series = series_response.get("series")

    if not isinstance(series, dict):
        raise TypeError(
            "Kalshi response does not contain a valid series."
        )

    sources = series.get("settlement_sources")

    if not isinstance(sources, list) or not sources:
        raise ValueError(
            "Kalshi series has no settlement source."
        )

    source = sources[0]

    if not isinstance(source, dict):
        raise TypeError(
            "Kalshi settlement source is invalid."
        )

    source_name = source.get("name")
    source_url = source.get("url")

    if not isinstance(source_name, str):
        raise TypeError(
            "Settlement source name is invalid."
        )

    if not isinstance(source_url, str):
        raise TypeError(
            "Settlement source URL is invalid."
        )

    events = events_response.get("events")

    if not isinstance(events, list):
        raise TypeError(
            "Kalshi response does not contain an events list."
        )

    valid_events: list[dict[str, Any]] = [
        event
        for event in events
        if isinstance(event, dict)
    ]

    valid_events.sort(
        key=lambda event: parse_event_date(
            str(event.get("event_ticker"))
        )
    )

    database = Database(settings.database_url)

    try:
        async with database.session() as session:
            for event in valid_events:
                settlement = parse_temperature_settlement(
                    event=event,
                    station_code=STATION_CODE,
                    source_name=source_name,
                    source_url=source_url,
                    retrieved_at=retrieved_at,
                )

                changed = await save_temperature_settlement(
                    session=session,
                    settlement=settlement,
                )

                result = (
                    "saved or completed"
                    if changed
                    else "already complete"
                )

                print(
                    f"{settlement.event_ticker} "
                    f"temperature="
                    f"{settlement.temperature_f}°F "
                    f"result={result}"
                )
    finally:
        await database.close()


if __name__ == "__main__":
    asyncio.run(save_recent_settlements())