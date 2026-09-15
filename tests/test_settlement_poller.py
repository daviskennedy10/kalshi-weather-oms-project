import asyncio
from datetime import datetime
from decimal import Decimal
from typing import Any

import pytest

from weather_oms.bus import EventBus
from weather_oms.events import EventKind
from weather_oms.ingest.kalshi_settlement_parser import (
    ParsedTemperatureSettlement,
)
from weather_oms.ingest.settlement_poller import (
    SettlementPoller,
)


class FakeSettlementClient:
    async def get_series(
        self,
        series_ticker: str,
    ) -> dict[str, Any]:
        return {
            "series": {
                "settlement_sources": [
                    {
                        "name": "The Weather Company",
                        "url": "https://weather.com/kalshi",
                    }
                ]
            }
        }

    async def get_settled_events(
        self,
        series_ticker: str,
        limit: int = 20,
    ) -> dict[str, Any]:
        return {
            "events": [
                {
                    "series_ticker": "KXHIGHNY",
                    "event_ticker": "KXHIGHNY-26SEP04",
                    "markets": [
                        {
                            "ticker": "KXHIGHNY-26SEP04-T83",
                            "result": "no",
                            "expiration_value": "84.00",
                            "settlement_ts": (
                                "2026-09-05T11:20:00+00:00"
                            ),
                        },
                        {
                            "ticker": "KXHIGHNY-26SEP04-B83.5",
                            "result": "yes",
                            "expiration_value": "84.00",
                            "settlement_ts": (
                                "2026-09-05T11:20:00+00:00"
                            ),
                        },
                    ],
                }
            ]
        }


async def test_poller_publishes_new_settlement_once() -> None:
    bus = EventBus()
    client = FakeSettlementClient()
    poller = SettlementPoller(
        client=client,
        bus=bus,
        series_ticker="KXHIGHNY",
        station_code="KNYC",
    )

    await poller.poll_once()

    event = await bus.next()
    bus.task_done()

    assert event.kind == EventKind.TEMPERATURE_SETTLED
    assert event.source_time == datetime.fromisoformat(
        "2026-09-05T11:20:00+00:00"
    )

    settlement = event.payload.get("settlement")

    assert isinstance(
        settlement,
        ParsedTemperatureSettlement,
    )
    assert settlement.event_ticker == "KXHIGHNY-26SEP04"
    assert settlement.station_code == "KNYC"
    assert settlement.temperature_f == Decimal("84.00")
    assert (
        settlement.winning_market_ticker
        == "KXHIGHNY-26SEP04-B83.5"
    )

    await poller.poll_once()

    with pytest.raises(TimeoutError):
        await asyncio.wait_for(
            bus.next(),
            timeout=0.01,
        )