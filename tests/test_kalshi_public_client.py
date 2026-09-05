import httpx
import pytest

from weather_oms.ingest.kalshi_public_client import (
    KalshiPublicClient,
)


async def test_get_settled_events_sends_correct_request() -> None:
    async def handle_request(
        request: httpx.Request,
    ) -> httpx.Response:
        assert request.url.path == "/trade-api/v2/events"
        assert request.url.params["series_ticker"] == "KXHIGHNY"
        assert request.url.params["status"] == "settled"
        assert (
            request.url.params["with_nested_markets"]
            == "true"
        )
        assert request.url.params["limit"] == "20"

        return httpx.Response(
            status_code=200,
            json={
                "events": [
                    {
                        "event_ticker": "KXHIGHNY-26SEP04"
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handle_request)

    async with httpx.AsyncClient(
        transport=transport
    ) as http:
        client = KalshiPublicClient(http)

        response = await client.get_settled_events(
            "KXHIGHNY"
        )

    assert response["events"][0]["event_ticker"] == (
        "KXHIGHNY-26SEP04"
    )


async def test_client_rejects_non_object_response() -> None:
    async def handle_request(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json=["unexpected", "list"],
        )

    transport = httpx.MockTransport(handle_request)

    async with httpx.AsyncClient(
        transport=transport
    ) as http:
        client = KalshiPublicClient(http)

        with pytest.raises(
            TypeError,
            match="return a JSON object",
        ):
            await client.get_series("KXHIGHNY")