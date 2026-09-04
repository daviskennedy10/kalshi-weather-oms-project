import asyncio
import json
from pathlib import Path
from statistics import mean

import httpx

from weather_oms.ingest.forecast_poller import WeatherNextClient
from weather_oms.stations import STATIONS


async def inspect_forecast() -> None:
    station = STATIONS["KNYC"]

    async with httpx.AsyncClient(timeout=20) as http:
        client = WeatherNextClient(http)
        forecast = await client.forecast(station, days=2)

    output_path = Path("central_park_forecast.json")
    output_path.write_text(
        json.dumps(forecast, indent=2),
        encoding="utf-8",
    )

    daily = forecast["daily"]
    dates = daily["time"]

    temperature_keys = [
        key
        for key in daily
        if key.startswith("temperature_2m_max")
    ]

    first_date_temperatures = [
        daily[key][0]
        for key in temperature_keys
        if daily[key][0] is not None
    ]

    numbered_member_keys = [
        key
        for key in temperature_keys
        if "_member" in key
    ]

    numbered_member_temperatures = [
        daily[key][0]
        for key in numbered_member_keys
        if daily[key][0] is not None
    ]

    unsuffixed_temperature = daily["temperature_2m_max"][0]
    numbered_members_mean = mean(numbered_member_temperatures)

    print()
    print("REQUEST INFORMATION")
    print("-------------------")
    print(f"Requested station: {station.name} ({station.code})")
    print(f"Requested coordinates: {station.latitude}, {station.longitude}")
    print(f"Returned coordinates: {forecast['latitude']}, {forecast['longitude']}")
    print(f"Returned timezone: {forecast['timezone']}")
    print(f"Temperature unit: {forecast['daily_units']['temperature_2m_max']}")
    print(f"Dates returned: {dates}")

    print()
    print("FIRST FORECAST DATE")
    print("-------------------")
    print(f"Date: {dates[0]}")
    print(f"Number of temperature series: {len(temperature_keys)}")
    print(f"Number of available temperatures: {len(first_date_temperatures)}")
    print(f"Average: {mean(first_date_temperatures):.2f}°F")
    print(f"Minimum: {min(first_date_temperatures):.2f}°F")
    print(f"Maximum: {max(first_date_temperatures):.2f}°F")
    print(
        "Spread: "
        f"{max(first_date_temperatures) - min(first_date_temperatures):.2f}°F"
    )

    print()
    print("CHECKING THE UNSUFFIXED SERIES")
    print("-----------------------------")
    print(f"Unsuffixed value: {unsuffixed_temperature:.2f}°F")
    print(f"Average of member01-member63: {numbered_members_mean:.2f}°F")
    print(
        "Difference: "
        f"{abs(unsuffixed_temperature - numbered_members_mean):.2f}°F"
    )

    print()
    print(f"Complete response saved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(inspect_forecast())