import asyncio
import json
from datetime import UTC, datetime
from typing import Any, cast

import websockets

from weather_oms.bus import EventBus
from weather_oms.events import Event, EventKind
from weather_oms.ingest.kalshi_auth import auth_headers


class KalshiStream:
    def __init__(self, url: str, key_id: str, key_path: str, tickers: list[str], bus: EventBus):
        self.url, self.key_id, self.key_path = url, key_id, key_path
        self.tickers, self.bus = tickers, bus

    async def _session(self) -> None:
        async with websockets.connect(
            self.url,
            additional_headers=auth_headers(
                self.key_id,
                self.key_path,
                "/trade-api/ws/v2",
            ),
        ) as ws:
            await ws.send(json.dumps({
                "id": 1,
                "cmd": "subscribe",
                "params": {
                    "channels": ["orderbook_delta", "fill"],
                    "market_tickers": self.tickers,
                },
            }))
            async for raw in ws:
                decoded_message: object = json.loads(raw)

                if not isinstance(decoded_message, dict):
                    continue

                message = cast(dict[str, Any], decoded_message)
                message_type = message.get("type")

                if not isinstance(message_type, str):
                    continue

                kind = {
                    "orderbook_snapshot": EventKind.ORDERBOOK_UPDATED,
                    "orderbook_delta": EventKind.ORDERBOOK_UPDATED,
                    "fill": EventKind.FILL_RECEIVED,
                }.get(message_type)

                if kind:
                    await self.bus.publish(
                        Event(
                            kind=kind,
                            source_time=datetime.now(UTC),
                            payload=message,
                        )
                    )

    async def run(self) -> None:
        backoff = 1
        while True:
            try:
                await self._session()
                backoff = 1
            except asyncio.CancelledError:
                raise
            except (
                OSError,
                json.JSONDecodeError,
                websockets.WebSocketException,
            ):
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)

