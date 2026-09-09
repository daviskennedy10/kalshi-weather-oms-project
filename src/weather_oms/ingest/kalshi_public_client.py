from typing import Any, cast

import httpx


class KalshiPublicClient:
    BASE_URL = "https://external-api.kalshi.com/trade-api/v2"

    def __init__(self, http: httpx.AsyncClient) -> None:
        self.http = http

    async def get_series(
        self,
        series_ticker: str,
    ) -> dict[str, Any]:
        return await self._get_json(
            f"/series/{series_ticker}"
        )
    
    async def get_event(
        self,
        event_ticker: str,
    ) -> dict[str, Any]:
        return await self._get_json(
            f"/events/{event_ticker}",
            params={
                "with_nested_markets": "true",
            },
        )

    async def get_settled_events(
        self,
        series_ticker: str,
        limit: int = 20,
    ) -> dict[str, Any]:
        return await self._get_json(
            "/events",
            params={
                "series_ticker": series_ticker,
                "status": "settled",
                "with_nested_markets": "true",
                "limit": limit,
            },
        )

    async def _get_json(
        self,
        path: str,
        params: dict[str, str | int] | None = None,
    ) -> dict[str, Any]:
        response = await self.http.get(
            f"{self.BASE_URL}{path}",
            params=params,
        )
        response.raise_for_status()

        data: object = response.json()

        if not isinstance(data, dict):
            raise TypeError(
                f"Expected {path} to return a JSON object."
            )

        return cast(dict[str, Any], data)