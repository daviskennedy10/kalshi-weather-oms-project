import asyncio
import logging
from datetime import UTC, datetime
from typing import Any, Protocol

import httpx

from weather_oms.bus import EventBus
from weather_oms.events import Event, EventKind
from weather_oms.ingest.kalshi_settlement_parser import (
    SettlementParseError,
    parse_temperature_settlement,
)

LOGGER = logging.getLogger(__name__)


class SettlementClient(Protocol):
    async def get_series(
        self,
        series_ticker: str,
    ) -> dict[str, Any]:
        ...

    async def get_settled_events(
        self,
        series_ticker: str,
        limit: int = 20,
    ) -> dict[str, Any]:
        ...


class SettlementPoller:
    def __init__(
        self,
        client: SettlementClient,
        bus: EventBus,
        series_ticker: str,
        station_code: str,
    ) -> None:
        self.client = client
        self.bus = bus
        self.series_ticker = series_ticker
        self.station_code = station_code
        self._published_event_tickers: set[str] = set()

    async def poll_once(self) -> None:
        series_response, events_response = await asyncio.gather(
            self.client.get_series(self.series_ticker),
            self.client.get_settled_events(self.series_ticker),
        )

        source_name, source_url = self._read_source(
            series_response
        )
        events = self._read_events(events_response)
        retrieved_at = datetime.now(UTC)

        for event in events:
            event_ticker = event.get("event_ticker")

            if not isinstance(event_ticker, str):
                LOGGER.error(
                    "Settled event is missing its event ticker."
                )
                continue

            if event_ticker in self._published_event_tickers:
                continue

            try:
                settlement = parse_temperature_settlement(
                    event=event,
                    station_code=self.station_code,
                    source_name=source_name,
                    source_url=source_url,
                    retrieved_at=retrieved_at,
                )
            except SettlementParseError as error:
                LOGGER.error(
                    "Invalid settlement %s: %s",
                    event_ticker,
                    error,
                )
                continue

            await self.bus.publish(
                Event(
                    kind=EventKind.TEMPERATURE_SETTLED,
                    source_time=settlement.settled_at,
                    payload={
                        "settlement": settlement,
                    },
                )
            )

            self._published_event_tickers.add(event_ticker)

    async def run(self, interval_seconds: int) -> None:
        while True:
            try:
                await self.poll_once()
            except (httpx.HTTPError, TypeError, ValueError) as error:
                LOGGER.error(
                    "Settlement request failed: %s",
                    error,
                )

            await asyncio.sleep(interval_seconds)

    @staticmethod
    def _read_source(
        response: dict[str, Any],
    ) -> tuple[str, str]:
        series = response.get("series")

        if not isinstance(series, dict):
            raise TypeError(
                "Kalshi response does not contain a valid series."
            )

        sources = series.get("settlement_sources")

        if not isinstance(sources, list) or not sources:
            raise ValueError(
                "Kalshi series has no settlement source."
            )

        source = sources[0]

        if not isinstance(source, dict):
            raise TypeError(
                "Kalshi settlement source is invalid."
            )

        source_name = source.get("name")
        source_url = source.get("url")

        if not isinstance(source_name, str):
            raise TypeError(
                "Settlement source name is invalid."
            )

        if not isinstance(source_url, str):
            raise TypeError(
                "Settlement source URL is invalid."
            )

        return source_name, source_url

    @staticmethod
    def _read_events(
        response: dict[str, Any],
    ) -> list[dict[str, Any]]:
        events = response.get("events")

        if not isinstance(events, list):
            raise TypeError(
                "Kalshi response does not contain an events list."
            )

        if not all(
            isinstance(event, dict)
            for event in events
        ):
            raise TypeError(
                "Kalshi events list contains an invalid event."
            )

        return events