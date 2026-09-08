from datetime import UTC, date, datetime

import pytest

from weather_oms.signal.forecast_dataset import (
    MatchedForecastSnapshot,
    prior_day_cutoff,
    select_forecast_outcomes,
)


def snapshot(
    *,
    observation_date: date,
    retrieved_at: datetime,
    forecast: float,
    actual: float = 80.0,
) -> MatchedForecastSnapshot:
    return MatchedForecastSnapshot(
        station_code="KNYC",
        observation_date=observation_date,
        retrieved_at=retrieved_at,
        mean_high_f=forecast,
        ensemble_stddev_f=2.0,
        actual_high_f=actual,
    )


def test_cutoff_uses_prior_day_in_station_timezone() -> None:
    cutoff = prior_day_cutoff(
        date(2026, 9, 6),
        "America/New_York",
    )

    assert cutoff.isoformat() == "2026-09-05T12:00:00-04:00"


def test_selects_newest_snapshot_at_or_before_cutoff() -> None:
    target = date(2026, 9, 6)
    outcomes = select_forecast_outcomes(
        [
            snapshot(
                observation_date=target,
                retrieved_at=datetime(2026, 9, 5, 14, tzinfo=UTC),
                forecast=76.0,
            ),
            snapshot(
                observation_date=target,
                retrieved_at=datetime(2026, 9, 5, 16, tzinfo=UTC),
                forecast=77.0,
            ),
            snapshot(
                observation_date=target,
                retrieved_at=datetime(2026, 9, 5, 17, tzinfo=UTC),
                forecast=79.0,
            ),
        ],
        timezone="America/New_York",
    )

    assert len(outcomes) == 1
    assert outcomes[0].raw_high_f == 77.0
    assert outcomes[0].error_f == 3.0
    assert outcomes[0].lead_hours == pytest.approx(12.0)


def test_excludes_date_with_no_pre_cutoff_snapshot() -> None:
    outcomes = select_forecast_outcomes(
        [
            snapshot(
                observation_date=date(2026, 9, 6),
                retrieved_at=datetime(2026, 9, 5, 17, tzinfo=UTC),
                forecast=79.0,
            )
        ],
        timezone="America/New_York",
    )

    assert outcomes == []


def test_rejects_naive_retrieval_timestamp() -> None:
    naive_timestamp = datetime(
        2026,
        9,
        5,
        12,
        tzinfo=UTC,
    ).replace(tzinfo=None)

    with pytest.raises(ValueError, match="timezone"):
        select_forecast_outcomes(
            [
                snapshot(
                    observation_date=date(2026, 9, 6),
                    retrieved_at=naive_timestamp,
                    forecast=79.0,
                )
            ],
            timezone="America/New_York",
        )
