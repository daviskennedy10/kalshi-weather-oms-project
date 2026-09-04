from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Station:
    code: str
    name: str
    latitude: float
    longitude: float
    timezone: str


# Verify each Kalshi market's settlement source before trading; station identity matters.
STATIONS = {
    "KNYC": Station("KNYC", "Central Park", 40.7789, -73.9692, "America/New_York"),
    "KMDW": Station("KMDW", "Chicago Midway", 41.7868, -87.7522, "America/Chicago"),
    "KDFW": Station("KDFW", "Dallas/Fort Worth", 32.8998, -97.0403, "America/Chicago"),
}
