import asyncio
import json
from pathlib import Path
from typing import Any

import httpx

EVENTS_URL = (
    "https://external-api.kalshi.com/"
    "trade-api/v2/events"
)


async def inspect_settled_event() -> None:
    async with httpx.AsyncClient(timeout=20) as http:
        response = await http.get(
            EVENTS_URL,
            params={
                "series_ticker": "KXHIGHNY",
                "status": "settled",
                "with_nested_markets": "true",
                "limit": 20,
            },
        )
        response.raise_for_status()

    data: object = response.json()

    if not isinstance(data, dict):
        raise TypeError(
            "Expected Kalshi to return a JSON object."
        )

    output_path = Path("kalshi_settled_events.json")
    output_path.write_text(
        json.dumps(data, indent=2),
        encoding="utf-8",
    )

    events = data.get("events")

    if not isinstance(events, list) or not events:
        raise ValueError(
            "Kalshi returned no settled events."
        )

    valid_events: list[dict[str, Any]] = [
        event
        for event in events
        if isinstance(event, dict)
    ]

    latest_event = max(
        valid_events,
        key=lambda event: str(
            event.get("strike_date", "")
        ),
    )

    print()
    print("LATEST RETURNED SETTLED EVENT")
    print("-----------------------------")
    print(
        f"Event ticker: "
        f"{latest_event.get('event_ticker')}"
    )
    print(f"Title: {latest_event.get('title')}")
    print(
        f"Strike date: "
        f"{latest_event.get('strike_date')}"
    )

    markets = latest_event.get("markets")

    if not isinstance(markets, list):
        raise TypeError(
            "Settled event does not contain markets."
        )

    print()
    print("MARKET RESULTS")
    print("--------------")

    for market in markets:
        if not isinstance(market, dict):
            continue

        print(f"Market: {market.get('yes_sub_title')}")
        print(f"Result: {market.get('result')}")
        print(
            f"Expiration value: "
            f"{market.get('expiration_value')}"
        )
        print(
            f"Settlement time: "
            f"{market.get('settlement_ts')}"
        )
        print("-" * 40)

    print()
    print(f"Complete response saved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(inspect_settled_event())