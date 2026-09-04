import asyncio
import json
from pathlib import Path

import httpx

from weather_oms.ingest.forecast_parser import parse_daily_forecasts
from weather_oms.ingest.forecast_poller import WeatherNextClient
from weather_oms.stations import STATIONS


async def inspect_forecast() -> None:
    station = STATIONS["KNYC"]

    async with httpx.AsyncClient(timeout=20) as http:
        client = WeatherNextClient(http)
        response = await client.forecast(station, days=2)

    output_path = Path("central_park_forecast.json")
    output_path.write_text(
        json.dumps(response, indent=2),
        encoding="utf-8",
    )

    daily_forecasts = parse_daily_forecasts(response, station)

    print()
    print(f"Received {len(daily_forecasts)} daily forecasts.")

    for forecast in daily_forecasts:
        print()
        print(f"Station: {forecast.station_code}")
        print(f"Date: {forecast.forecast_date}")
        print(f"Ensemble members: {len(forecast.member_highs_f)}")
        print(f"Average high: {forecast.mean_high_f:.2f}°F")
        print(f"Minimum high: {forecast.minimum_high_f:.2f}°F")
        print(f"Maximum high: {forecast.maximum_high_f:.2f}°F")
        print(f"Spread: {forecast.spread_f:.2f}°F")
        print(
            "Standard deviation: "
            f"{forecast.standard_deviation_f:.2f}°F"
        )
        print(
            "WeatherNext grid location: "
            f"{forecast.source_latitude}, "
            f"{forecast.source_longitude}"
        )

    print()
    print(f"Complete response saved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(inspect_forecast())