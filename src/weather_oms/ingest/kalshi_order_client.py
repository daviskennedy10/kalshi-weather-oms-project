from typing import Any, cast

import httpx

from weather_oms.ingest.kalshi_auth import auth_headers
from weather_oms.oms.reconciliation import OrderSnapshot
from weather_oms.oms.reconciliation_adapter import (
    kalshi_order_to_snapshot,
)

_ORDERS_ENDPOINT = "/portfolio/orders"
_SIGNED_PATH = "/trade-api/v2/portfolio/orders"


class KalshiOrderReadClient:
    """Read Kalshi orders without creating or changing them."""

    def __init__(
        self,
        base_url: str,
        key_id: str,
        private_key_path: str,
        client: httpx.AsyncClient,
    ) -> None:
        if not base_url:
            raise ValueError("base_url cannot be empty.")

        if not key_id:
            raise ValueError("key_id cannot be empty.")

        if not private_key_path:
            raise ValueError(
                "private_key_path cannot be empty."
            )

        self._base_url = base_url.rstrip("/")
        self._key_id = key_id
        self._private_key_path = private_key_path
        self._client = client

    async def get_orders(
        self,
        *,
        event_ticker: str | None = None,
    ) -> tuple[OrderSnapshot, ...]:
        """Read every available order, following pagination."""

        normalized_event = None

        if event_ticker is not None:
            normalized_event = event_ticker.strip().upper()

            if not normalized_event:
                raise ValueError(
                    "event_ticker cannot be empty."
                )

        snapshots: list[OrderSnapshot] = []
        cursor: str | None = None
        seen_cursors: set[str] = set()

        while True:
            params = self._build_params(
                event_ticker=normalized_event,
                cursor=cursor,
            )

            response = await self._client.get(
                f"{self._base_url}{_ORDERS_ENDPOINT}",
                params=params,
                headers=auth_headers(
                    self._key_id,
                    self._private_key_path,
                    _SIGNED_PATH,
                ),
            )
            response.raise_for_status()

            payload = self._read_payload(response)
            orders = self._read_orders(payload)

            snapshots.extend(
                kalshi_order_to_snapshot(order)
                for order in orders
            )

            next_cursor = self._read_cursor(payload)

            if next_cursor is None:
                break

            if next_cursor in seen_cursors:
                raise ValueError(
                    "Kalshi returned a repeated pagination "
                    "cursor."
                )

            seen_cursors.add(next_cursor)
            cursor = next_cursor

        return tuple(snapshots)

    @staticmethod
    def _build_params(
        *,
        event_ticker: str | None,
        cursor: str | None,
    ) -> dict[str, str]:
        params = {"limit": "1000"}

        if event_ticker is not None:
            params["event_ticker"] = event_ticker

        if cursor is not None:
            params["cursor"] = cursor

        return params

    @staticmethod
    def _read_payload(
        response: httpx.Response,
    ) -> dict[str, Any]:
        decoded: object = response.json()

        if not isinstance(decoded, dict):
            raise TypeError(
                "Kalshi order response must be an object."
            )

        return cast(dict[str, Any], decoded)

    @staticmethod
    def _read_orders(
        payload: dict[str, Any],
    ) -> tuple[dict[str, object], ...]:
        raw_orders: object = payload.get("orders")

        if not isinstance(raw_orders, list):
            raise TypeError(
                "Kalshi order response must contain "
                "an orders list."
            )

        orders: list[dict[str, object]] = []

        for raw_order in raw_orders:
            if not isinstance(raw_order, dict):
                raise TypeError(
                    "Each Kalshi order must be an object."
                )

            orders.append(
                cast(dict[str, object], raw_order)
            )

        return tuple(orders)

    @staticmethod
    def _read_cursor(
        payload: dict[str, Any],
    ) -> str | None:
        cursor: object = payload.get("cursor")

        if cursor is None or cursor == "":
            return None

        if not isinstance(cursor, str):
            raise TypeError(
                "Kalshi pagination cursor must be a string."
            )

        return cursor