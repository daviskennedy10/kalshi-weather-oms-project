import argparse
import asyncio
from datetime import UTC, date, datetime

import httpx

from weather_oms.config import Settings
from weather_oms.ingest.kalshi_market_parser import (
    parse_temperature_markets,
)
from weather_oms.ingest.kalshi_public_client import (
    KalshiPublicClient,
)
from weather_oms.storage.db import Database
from weather_oms.storage.market_quote_repository import (
    save_market_quote_snapshot,
)


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "Date must use YYYY-MM-DD format."
        ) from error


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Save one timestamped Kalshi NYC "
            "temperature-market snapshot."
        )
    )
    parser.add_argument(
        "target_date",
        type=parse_date,
        help="Target date in YYYY-MM-DD format.",
    )
    return parser.parse_args()


def event_ticker_for_date(target_date: date) -> str:
    date_component = target_date.strftime(
        "%y%b%d"
    ).upper()

    return f"KXHIGHNY-{date_component}"


async def save_snapshot(target_date: date) -> None:
    event_ticker = event_ticker_for_date(target_date)

    async with httpx.AsyncClient(timeout=20) as http:
        client = KalshiPublicClient(http)
        response = await client.get_event(event_ticker)
        retrieved_at = datetime.now(UTC)

    markets = parse_temperature_markets(response)

    database = Database(Settings().database_url)

    try:
        async with database.session() as session:
            inserted_count = (
                await save_market_quote_snapshot(
                    session=session,
                    event_ticker=event_ticker,
                    target_date=target_date,
                    markets=markets,
                    retrieved_at=retrieved_at,
                )
            )
    finally:
        await database.close()

    print(f"Event: {event_ticker}")
    print(f"Target date: {target_date}")
    print(f"Retrieved at: {retrieved_at.isoformat()}")
    print(f"Markets received: {len(markets)}")
    print(f"Rows inserted: {inserted_count}")

    for market in markets:
        print(
            f"{market.ticker}: "
            f"YES {market.yes_bid_cents}¢/"
            f"{market.yes_ask_cents}¢, "
            f"NO {market.no_bid_cents}¢/"
            f"{market.no_ask_cents}¢"
        )


if __name__ == "__main__":
    arguments = parse_arguments()
    asyncio.run(save_snapshot(arguments.target_date))