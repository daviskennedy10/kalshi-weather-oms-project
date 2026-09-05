import asyncio
import json
from pathlib import Path

import httpx

EVENTS_URL = (
    "https://external-api.kalshi.com/"
    "trade-api/v2/events"
)


async def inspect_kalshi_events() -> None:
    async with httpx.AsyncClient(timeout=20) as http:
        response = await http.get(
            EVENTS_URL,
            params={
                "series_ticker": "KXHIGHNY",
                "status": "open",
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

    output_path = Path("kalshi_events.json")
    output_path.write_text(
        json.dumps(data, indent=2),
        encoding="utf-8",
    )

    events = data.get("events")

    if not isinstance(events, list):
        raise TypeError(
            "Kalshi response does not contain an events list."
        )

    print()
    print(f"Number of open events: {len(events)}")

    for event in events:
        if not isinstance(event, dict):
            continue

        print()
        print("=" * 60)
        print(f"Event ticker: {event.get('event_ticker')}")
        print(f"Title: {event.get('title')}")
        print(f"Subtitle: {event.get('sub_title')}")
        print(f"Strike date: {event.get('strike_date')}")

        markets = event.get("markets")

        if not isinstance(markets, list):
            print("No markets returned.")
            continue

        print(f"Number of markets: {len(markets)}")
        print()

        for market in markets:
            if not isinstance(market, dict):
                continue

            print(f"Market ticker: {market.get('ticker')}")
            print(f"Title: {market.get('title')}")
            print(
                f"YES meaning: "
                f"{market.get('yes_sub_title')}"
            )
            print(f"Status: {market.get('status')}")
            print(
                f"YES bid: "
                f"{market.get('yes_bid_dollars')}"
            )
            print(
                f"YES ask: "
                f"{market.get('yes_ask_dollars')}"
            )
            print(
                f"Floor strike: "
                f"{market.get('floor_strike')}"
            )
            print(
                f"Cap strike: "
                f"{market.get('cap_strike')}"
            )
            print("-" * 40)

    print()
    print(f"Complete response saved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(inspect_kalshi_events())