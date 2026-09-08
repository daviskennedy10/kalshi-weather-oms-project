from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


@dataclass(frozen=True, slots=True)
class MatchedForecastSnapshot:
    station_code: str
    observation_date: date
    retrieved_at: datetime
    mean_high_f: float
    ensemble_stddev_f: float
    actual_high_f: float


@dataclass(frozen=True, slots=True)
class ForecastOutcome:
    station_code: str
    observation_date: date
    cutoff_at: datetime
    forecast_retrieved_at: datetime
    lead_hours: float
    raw_high_f: float
    ensemble_stddev_f: float
    actual_high_f: float
    error_f: float


def prior_day_cutoff(
    observation_date: date,
    timezone: str,
    cutoff_local_time: time = time(hour=12),
) -> datetime:
    """Return the preceding day's local cutoff as an aware datetime."""
    if cutoff_local_time.tzinfo is not None:
        raise ValueError("cutoff_local_time must not contain a timezone")

    local_zone = ZoneInfo(timezone)
    cutoff_date = observation_date - timedelta(days=1)
    return datetime.combine(cutoff_date, cutoff_local_time, local_zone)


def select_forecast_outcomes(
    snapshots: Iterable[MatchedForecastSnapshot],
    timezone: str,
    cutoff_local_time: time = time(hour=12),
) -> list[ForecastOutcome]:
    """Select the newest snapshot available by each date's cutoff.

    A single outcome is returned per station and observation date. Forecasts
    retrieved after the cutoff are excluded to prevent look-ahead leakage.
    """
    selected: dict[tuple[str, date], MatchedForecastSnapshot] = {}

    for snapshot in snapshots:
        if snapshot.retrieved_at.tzinfo is None:
            raise ValueError("retrieved_at must include a timezone")

        cutoff_at = prior_day_cutoff(
            snapshot.observation_date,
            timezone,
            cutoff_local_time,
        )
        if snapshot.retrieved_at > cutoff_at:
            continue

        key = (snapshot.station_code, snapshot.observation_date)
        current = selected.get(key)
        if current is None or snapshot.retrieved_at > current.retrieved_at:
            selected[key] = snapshot

    outcomes: list[ForecastOutcome] = []
    local_zone = ZoneInfo(timezone)

    for snapshot in selected.values():
        cutoff_at = prior_day_cutoff(
            snapshot.observation_date,
            timezone,
            cutoff_local_time,
        )
        target_start = datetime.combine(
            snapshot.observation_date,
            time.min,
            local_zone,
        )
        lead_hours = (
            target_start - snapshot.retrieved_at.astimezone(local_zone)
        ).total_seconds() / 3600

        outcomes.append(
            ForecastOutcome(
                station_code=snapshot.station_code,
                observation_date=snapshot.observation_date,
                cutoff_at=cutoff_at,
                forecast_retrieved_at=snapshot.retrieved_at,
                lead_hours=lead_hours,
                raw_high_f=snapshot.mean_high_f,
                ensemble_stddev_f=snapshot.ensemble_stddev_f,
                actual_high_f=snapshot.actual_high_f,
                error_f=snapshot.actual_high_f - snapshot.mean_high_f,
            )
        )

    return sorted(
        outcomes,
        key=lambda outcome: (
            outcome.observation_date,
            outcome.station_code,
        ),
    )