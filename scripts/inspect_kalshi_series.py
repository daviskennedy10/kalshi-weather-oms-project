import asyncio
import json
from pathlib import Path

import httpx

SERIES_TICKER = "KXHIGHNY"

SERIES_URL = (
    "https://external-api.kalshi.com/"
    f"trade-api/v2/series/{SERIES_TICKER}"
)


async def inspect_kalshi_series() -> None:
    async with httpx.AsyncClient(timeout=20) as http:
        response = await http.get(SERIES_URL)
        response.raise_for_status()

    data: object = response.json()

    if not isinstance(data, dict):
        raise TypeError(
            "Expected Kalshi to return a JSON object."
        )

    output_path = Path("kalshi_series.json")
    output_path.write_text(
        json.dumps(data, indent=2),
        encoding="utf-8",
    )

    series = data.get("series")

    if not isinstance(series, dict):
        raise TypeError(
            "Kalshi response does not contain a valid series."
        )

    print()
    print("KALSHI SERIES")
    print("-------------")
    print(f"Ticker: {series.get('ticker')}")
    print(f"Title: {series.get('title')}")
    print(f"Category: {series.get('category')}")
    print(f"Frequency: {series.get('frequency')}")
    print(f"Last updated: {series.get('last_updated_ts')}")

    print()
    print("SETTLEMENT SOURCES")
    print("------------------")

    settlement_sources = series.get("settlement_sources")

    if isinstance(settlement_sources, list):
        for source in settlement_sources:
            if isinstance(source, dict):
                print(f"Name: {source.get('name')}")
                print(f"URL: {source.get('url')}")

    print()
    print(f"Complete response saved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(inspect_kalshi_series())