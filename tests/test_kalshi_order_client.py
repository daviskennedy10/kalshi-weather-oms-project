from pathlib import Path

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from weather_oms.ingest.kalshi_order_client import (
    KalshiOrderReadClient,
)
from weather_oms.oms.order_state import OrderState


def write_private_key(path: Path) -> None:
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=(
                serialization.NoEncryption()
            ),
        )
    )


def make_order(
    *,
    client_order_id: str,
    status: str = "resting",
    fill_count: str = "0.00",
    remaining_count: str = "10.00",
) -> dict[str, object]:
    return {
        "client_order_id": client_order_id,
        "order_id": f"exchange-{client_order_id}",
        "status": status,
        "initial_count_fp": "10.00",
        "fill_count_fp": fill_count,
        "remaining_count_fp": remaining_count,
    }


def make_client(
    tmp_path: Path,
    handler: httpx.MockTransport,
) -> KalshiOrderReadClient:
    key_path = tmp_path / "kalshi.key"
    write_private_key(key_path)

    http_client = httpx.AsyncClient(
        transport=handler,
    )

    return KalshiOrderReadClient(
        base_url=(
            "https://external-api.demo.kalshi.co"
            "/trade-api/v2"
        ),
        key_id="test-key",
        private_key_path=str(key_path),
        client=http_client,
    )


async def test_reads_orders(tmp_path: Path) -> None:
    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert request.method == "GET"
        assert (
            request.url.path
            == "/trade-api/v2/portfolio/orders"
        )
        assert request.url.params["limit"] == "1000"
        assert (
            request.url.params["event_ticker"]
            == "KXHIGHNY-26SEP10"
        )
        assert (
            request.headers["KALSHI-ACCESS-KEY"]
            == "test-key"
        )

        return httpx.Response(
            200,
            json={
                "orders": [
                    make_order(
                        client_order_id="oms-one",
                    )
                ],
                "cursor": "",
            },
        )

    client = make_client(
        tmp_path,
        httpx.MockTransport(handler),
    )

    orders = await client.get_orders(
        event_ticker="kxhighny-26sep10",
    )

    assert len(orders) == 1
    assert orders[0].client_order_id == "oms-one"
    assert orders[0].state is OrderState.OPEN


async def test_follows_pagination(
    tmp_path: Path,
) -> None:
    request_count = 0

    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        nonlocal request_count
        request_count += 1

        if request_count == 1:
            assert "cursor" not in request.url.params

            return httpx.Response(
                200,
                json={
                    "orders": [
                        make_order(
                            client_order_id="oms-one",
                        )
                    ],
                    "cursor": "next-page",
                },
            )

        assert (
            request.url.params["cursor"]
            == "next-page"
        )

        return httpx.Response(
            200,
            json={
                "orders": [
                    make_order(
                        client_order_id="oms-two",
                        status="executed",
                        fill_count="10.00",
                        remaining_count="0.00",
                    )
                ],
                "cursor": "",
            },
        )

    client = make_client(
        tmp_path,
        httpx.MockTransport(handler),
    )

    orders = await client.get_orders()

    assert request_count == 2
    assert len(orders) == 2
    assert orders[1].state is OrderState.FILLED


async def test_rejects_repeated_cursor(
    tmp_path: Path,
) -> None:
    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "orders": [],
                "cursor": "same-cursor",
            },
        )

    client = make_client(
        tmp_path,
        httpx.MockTransport(handler),
    )

    with pytest.raises(
        ValueError,
        match="repeated pagination cursor",
    ):
        await client.get_orders()


async def test_rejects_missing_orders_list(
    tmp_path: Path,
) -> None:
    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={"cursor": ""},
        )

    client = make_client(
        tmp_path,
        httpx.MockTransport(handler),
    )

    with pytest.raises(
        TypeError,
        match="orders list",
    ):
        await client.get_orders()


async def test_propagates_http_error(
    tmp_path: Path,
) -> None:
    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            401,
            request=request,
            json={"message": "unauthorized"},
        )

    client = make_client(
        tmp_path,
        httpx.MockTransport(handler),
    )

    with pytest.raises(httpx.HTTPStatusError):
        await client.get_orders()