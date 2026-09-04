import asyncio
import json
from pathlib import Path

import httpx

from weather_oms.ingest.forecast_poller import WeatherNextClient
from weather_oms.stations import STATIONS


async def inspect_forecast() -> None:
    #Selecting Central Park from stations
    station = STATIONS["KNYC"]

    async with httpx.AsyncClient(timeout=20) as http:
        #Creating an internal client
        client = WeatherNextClient(http)
        #Requesting two days of data
        forecast = await client.forecast(station, days=2)

    output_path = Path("central_park_forecast.json")
    #Save the JSON output
    output_path.write_text(
        json.dumps(forecast, indent=2),
        encoding="utf-8",
    )

    print(f"Successfully received a forecast for {station.name}.")
    print(f"Saved the complete response to: {output_path}")
    print(f"Top-level sections: {list(forecast.keys())}")
    print(f"Daily sections: {list(forecast.get('daily', {}).keys())}")


if __name__ == "__main__":
    asyncio.run(inspect_forecast())