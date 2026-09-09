from datetime import UTC, date, datetime

import pytest

from weather_oms.ingest.decision_snapshot import (
    eligibility_label,
    select_target_forecast,
)
from weather_oms.ingest.forecast_parser import DailyForecast


def forecast(forecast_date: date) -> DailyForecast:
    return DailyForecast(
        station_code="KNYC",
        forecast_date=forecast_date,
        member_highs_f=tuple([75.0] * 64),
        source_latitude=40.75,
        source_longitude=-74.0,
    )


def test_selects_requested_forecast_date() -> None:
    forecasts = [
        forecast(date(2026, 9, 8)),
        forecast(date(2026, 9, 9)),
    ]

    selected = select_target_forecast(
        forecasts,
        date(2026, 9, 9),
    )

    assert selected.forecast_date == date(2026, 9, 9)


def test_rejects_missing_forecast_date() -> None:
    with pytest.raises(
        ValueError,
        match="received 0",
    ):
        select_target_forecast(
            [forecast(date(2026, 9, 8))],
            date(2026, 9, 9),
        )


def test_marks_retrieval_at_cutoff_as_eligible() -> None:
    cutoff = datetime(
        2026,
        9,
        8,
        16,
        tzinfo=UTC,
    )

    assert eligibility_label(cutoff, cutoff) == "ELIGIBLE"


def test_marks_retrieval_after_cutoff_as_late() -> None:
    cutoff = datetime(
        2026,
        9,
        8,
        16,
        tzinfo=UTC,
    )
    retrieved_at = datetime(
        2026,
        9,
        8,
        16,
        0,
        1,
        tzinfo=UTC,
    )

    assert eligibility_label(
        retrieved_at,
        cutoff,
    ) == "LATE"


def test_rejects_naive_timestamp() -> None:
    naive_retrieved_at = datetime(
        2026,
        9,
        8,
        15,
        tzinfo=UTC,
    ).replace(tzinfo=None)

    cutoff_at = datetime(
        2026,
        9,
        8,
        16,
        tzinfo=UTC,
    )

    with pytest.raises(ValueError, match="timezone"):
        eligibility_label(
            naive_retrieved_at,
            cutoff_at,
        )