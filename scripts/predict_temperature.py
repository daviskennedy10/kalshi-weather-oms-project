import argparse
import asyncio
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from weather_oms.config import Settings
from weather_oms.signal.bias_correction import (
    apply_bias_correction,
)
from weather_oms.signal.bias_model import ForecastFeatures
from weather_oms.signal.forecast_dataset import prior_day_cutoff
from weather_oms.stations import STATIONS
from weather_oms.storage.db import Database
from weather_oms.storage.forecast_outcome_repository import (
    load_forecast_outcomes,
)
from weather_oms.storage.forecast_repository import (
    load_latest_forecast_by_cutoff,
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
            "Produce a leakage-safe temperature prediction "
            "from a stored WeatherNext forecast."
        )
    )
    parser.add_argument(
        "target_date",
        type=parse_date,
        help="Forecast target date in YYYY-MM-DD format.",
    )
    return parser.parse_args()


async def predict(target_date: date) -> None:
    settings = Settings()
    station = STATIONS["KNYC"]

    cutoff_at = prior_day_cutoff(
        target_date,
        station.timezone,
    )

    database = Database(settings.database_url)

    try:
        async with database.session() as session:
            stored_forecast = (
                await load_latest_forecast_by_cutoff(
                    session=session,
                    station_code=station.code,
                    target_date=target_date,
                    cutoff_at=cutoff_at,
                )
            )

            outcomes = await load_forecast_outcomes(
                session=session,
                station_code=station.code,
                timezone=station.timezone,
            )
    finally:
        await database.close()

    print(f"Station: {station.code} ({station.name})")
    print(f"Target date: {target_date}")
    print(
        "Selection policy: newest forecast available by "
        "12:00 PM local time on the preceding day"
    )
    print(f"Cutoff: {cutoff_at.isoformat()}")

    if stored_forecast is None:
        print()
        print(
            "No stored forecast satisfies the selection policy."
        )
        return

    local_zone = ZoneInfo(station.timezone)
    target_start = datetime.combine(
        target_date,
        time.min,
        local_zone,
    )
    retrieved_at_local = (
        stored_forecast.retrieved_at.astimezone(local_zone)
    )
    lead_hours = (
        target_start - retrieved_at_local
    ).total_seconds() / 3600

    features = ForecastFeatures(
        raw_high_f=stored_forecast.mean_high_f,
        lead_hours=lead_hours,
        ensemble_stddev_f=(
            stored_forecast.standard_deviation_f
        ),
        station=stored_forecast.station_code,
        day_of_year=target_date.timetuple().tm_yday,
    )

    result = apply_bias_correction(
        features=features,
        target_date=target_date,
        available_outcomes=outcomes,
    )

    print()
    print("Selected WeatherNext snapshot:")
    print(
        "Retrieved: "
        f"{stored_forecast.retrieved_at.isoformat()}"
    )
    print(
        "Retrieved locally: "
        f"{retrieved_at_local.isoformat()}"
    )
    print(f"Lead time: {lead_hours:.1f} hours")
    print(
        "Raw ensemble mean: "
        f"{result.raw_high_f:.2f}°F"
    )
    print(
        "Ensemble standard deviation: "
        f"{features.ensemble_stddev_f:.2f}°F"
    )

    print()
    print("Bias-correction decision:")
    print(
        f"Eligible training outcomes: "
        f"{result.training_count}"
    )
    print(
        f"Correction applied: "
        f"{'Yes' if result.correction_applied else 'No'}"
    )
    print(f"Learned bias: {result.learned_bias_f:+.2f}°F")
    print(f"Final forecast: {result.corrected_high_f:.2f}°F")
    print(f"Reason: {result.reason}")


if __name__ == "__main__":
    arguments = parse_arguments()
    asyncio.run(predict(arguments.target_date))