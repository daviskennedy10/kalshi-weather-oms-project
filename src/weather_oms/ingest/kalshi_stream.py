import asyncio
import base64
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import websockets
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from weather_oms.bus import EventBus
from weather_oms.events import Event, EventKind


def auth_headers(key_id: str, private_key_path: str) -> dict[str, str]:
    timestamp = str(int(time.time() * 1000))
    message = f"{timestamp}GET/trade-api/ws/v2".encode()
    key = serialization.load_pem_private_key(Path(private_key_path).read_bytes(), password=None)
    if not isinstance(key, rsa.RSAPrivateKey):
        raise TypeError(
            "Kalshi authentication requires an RSA private key."
        )
    signature = key.sign(
        message,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
        hashes.SHA256(),
    )
    return {
        "KALSHI-ACCESS-KEY": key_id,
        "KALSHI-ACCESS-TIMESTAMP": timestamp,
        "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode(),
    }


class KalshiStream:
    def __init__(self, url: str, key_id: str, key_path: str, tickers: list[str], bus: EventBus):
        self.url, self.key_id, self.key_path = url, key_id, key_path
        self.tickers, self.bus = tickers, bus

    async def _session(self) -> None:
        async with websockets.connect(
            self.url, additional_headers=auth_headers(self.key_id, self.key_path)
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

