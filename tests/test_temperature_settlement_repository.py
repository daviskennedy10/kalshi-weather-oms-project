from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from weather_oms.storage.models import TemperatureSettlement
from weather_oms.storage.temperature_settlement_repository import (
    load_temperature_settlement,
)


def make_settlement_row(
    winning_market_ticker: str | None,
) -> TemperatureSettlement:
    return TemperatureSettlement(
        series_ticker="KXHIGHNY",
        event_ticker="KXHIGHNY-26SEP10",
        winning_market_ticker=winning_market_ticker,
        station_code="KNYC",
        observation_date=date(2026, 9, 10),
        temperature_f=Decimal("84.00"),
        source_name="The Weather Company",
        source_url="https://weather.com/kalshi",
        settled_at=datetime(
            2026,
            9,
            11,
            11,
            20,
            tzinfo=UTC,
        ),
        retrieved_at=datetime(
            2026,
            9,
            11,
            12,
            0,
            tzinfo=UTC,
        ),
    )


def make_session(
    row: TemperatureSettlement | None,
) -> AsyncMock:
    session = AsyncMock(spec=AsyncSession)
    result = Mock()
    result.scalar_one_or_none.return_value = row
    session.execute.return_value = result
    return session


@pytest.mark.asyncio
async def test_loads_temperature_settlement() -> None:
    session = make_session(
        make_settlement_row(
            "KXHIGHNY-26SEP10-T85"
        )
    )

    settlement = await load_temperature_settlement(
        session=session,
        event_ticker="KXHIGHNY-26SEP10",
    )

    assert settlement is not None
    assert settlement.event_ticker == "KXHIGHNY-26SEP10"
    assert (
        settlement.winning_market_ticker
        == "KXHIGHNY-26SEP10-T85"
    )
    assert settlement.observation_date == date(2026, 9, 10)
    assert settlement.temperature_f == Decimal("84.00")


@pytest.mark.asyncio
async def test_preserves_missing_winner_on_older_row() -> None:
    session = make_session(
        make_settlement_row(None)
    )

    settlement = await load_temperature_settlement(
        session=session,
        event_ticker="KXHIGHNY-26SEP10",
    )

    assert settlement is not None
    assert settlement.winning_market_ticker is None


@pytest.mark.asyncio
async def test_returns_none_when_settlement_is_missing() -> None:
    session = make_session(None)

    settlement = await load_temperature_settlement(
        session=session,
        event_ticker="KXHIGHNY-26SEP10",
    )

    assert settlement is None


@pytest.mark.asyncio
async def test_rejects_empty_event_ticker() -> None:
    session = AsyncMock(spec=AsyncSession)

    with pytest.raises(
        ValueError,
        match="event_ticker cannot be empty",
    ):
        await load_temperature_settlement(
            session=session,
            event_ticker="",
        )

    session.execute.assert_not_awaited()