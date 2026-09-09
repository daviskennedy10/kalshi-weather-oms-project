import argparse
import asyncio
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import httpx

from weather_oms.config import Settings
from weather_oms.ingest.decision_snapshot import (
    eligibility_label,
    select_target_forecast,
)
from weather_oms.ingest.forecast_parser import (
    parse_daily_forecasts,
)
from weather_oms.ingest.forecast_poller import WeatherNextClient
from weather_oms.ingest.kalshi_market_parser import (
    parse_temperature_markets,
)
from weather_oms.ingest.kalshi_public_client import (
    KalshiPublicClient,
)
from weather_oms.signal.forecast_dataset import prior_day_cutoff
from weather_oms.stations import STATIONS
from weather_oms.storage.db import Database
from weather_oms.storage.forecast_repository import save_forecast
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
            "Save aligned WeatherNext and Kalshi snapshots "
            "for one NYC temperature event."
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



async def save_decision_snapshot(
    target_date: date,
) -> None:
    settings = Settings()
    station = STATIONS["KNYC"]
    event_ticker = event_ticker_for_date(target_date)

    cutoff_at = prior_day_cutoff(
        target_date,
        station.timezone,
    )

    async with httpx.AsyncClient(timeout=20) as http:
        weather_client = WeatherNextClient(http)
        weather_response = await weather_client.forecast(
            station,
            days=2,
        )
        forecast_retrieved_at = datetime.now(UTC)

        kalshi_client = KalshiPublicClient(http)

        try:
            kalshi_response = await kalshi_client.get_event(
                event_ticker
            )
        except httpx.HTTPStatusError as error:
            if error.response.status_code != 404:
                raise

            print(
                f"Kalshi event {event_ticker} "
                "is not available yet."
            )
            print(
                "No aligned decision snapshot was saved. "
                "Try again after the event opens."
            )
            return

        market_retrieved_at = datetime.now(UTC)

    forecasts = parse_daily_forecasts(
        weather_response,
        station,
    )
    target_forecast = select_target_forecast(
        forecasts,
        target_date,
    )
    markets = parse_temperature_markets(
        kalshi_response
    )

    database = Database(settings.database_url)

    try:
        async with database.session() as session:
            forecast_inserted = await save_forecast(
                session=session,
                forecast=target_forecast,
                retrieved_at=forecast_retrieved_at,
            )

            quote_rows_inserted = (
                await save_market_quote_snapshot(
                    session=session,
                    event_ticker=event_ticker,
                    target_date=target_date,
                    markets=markets,
                    retrieved_at=market_retrieved_at,
                )
            )
    finally:
        await database.close()

    local_zone = ZoneInfo(station.timezone)

    print()
    print("DECISION SNAPSHOT")
    print("-----------------")
    print(f"Station: {station.code} ({station.name})")
    print(f"Target date: {target_date}")
    print(f"Kalshi event: {event_ticker}")
    print(f"Cutoff: {cutoff_at.isoformat()}")

    print()
    print("WeatherNext:")
    print(
        "Retrieved: "
        f"{forecast_retrieved_at.isoformat()}"
    )
    print(
        "Retrieved locally: "
        f"{forecast_retrieved_at.astimezone(local_zone).isoformat()}"
    )
    print(
        "Cutoff status: "
        f"{eligibility_label(forecast_retrieved_at, cutoff_at)}"
    )
    print(
        "Database result: "
        f"{'new forecast saved' if forecast_inserted else 'forecast already existed'}"
    )
    print(
        f"Ensemble mean: "
        f"{target_forecast.mean_high_f:.2f}°F"
    )
    print(
        f"Ensemble members: "
        f"{len(target_forecast.member_highs_f)}"
    )

    print()
    print("Kalshi:")
    print(
        "Retrieved: "
        f"{market_retrieved_at.isoformat()}"
    )
    print(
        "Retrieved locally: "
        f"{market_retrieved_at.astimezone(local_zone).isoformat()}"
    )
    print(
        "Cutoff status: "
        f"{eligibility_label(market_retrieved_at, cutoff_at)}"
    )
    print(f"Markets received: {len(markets)}")
    print(
        f"Quote rows inserted: "
        f"{quote_rows_inserted}"
    )

    both_eligible = (
        forecast_retrieved_at <= cutoff_at
        and market_retrieved_at <= cutoff_at
    )

    print()
    print(
        "Aligned comparison eligibility: "
        f"{'YES' if both_eligible else 'NO'}"
    )

    if not both_eligible:
        print(
            "Reason: at least one snapshot was retrieved "
            "after the decision cutoff."
        )
    else:
        print(
            "Reason: both snapshots were available by "
            "the decision cutoff."
        )


if __name__ == "__main__":
    arguments = parse_arguments()
    asyncio.run(
        save_decision_snapshot(arguments.target_date)
    )