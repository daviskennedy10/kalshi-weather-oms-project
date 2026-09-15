import argparse
import asyncio

import httpx

from weather_oms.config import Settings
from weather_oms.ingest.kalshi_order_client import (
    KalshiOrderReadClient,
)
from weather_oms.oms.order_state import OrderState
from weather_oms.oms.reconciliation_service import (
    reconcile_event_orders,
)
from weather_oms.storage.db import Database
from weather_oms.storage.order_repository import (
    load_orders_for_event,
)


def format_value(value: object) -> str:
    if isinstance(value, OrderState):
        return value.value

    return str(value)


async def reconcile(event_ticker: str) -> int:
    settings = Settings()

    if settings.kalshi_key_id is None:
        raise RuntimeError(
            "KALSHI_KEY_ID is not configured."
        )

    if settings.kalshi_private_key_path is None:
        raise RuntimeError(
            "KALSHI_PRIVATE_KEY_PATH is not configured."
        )

    database = Database(settings.database_url)

    try:
        async with database.session() as session:
            local_orders = await load_orders_for_event(
                session=session,
                event_ticker=event_ticker,
            )

        async with httpx.AsyncClient(
            timeout=10.0,
        ) as http_client:
            exchange_client = KalshiOrderReadClient(
                base_url=settings.kalshi_rest_url,
                key_id=settings.kalshi_key_id,
                private_key_path=(
                    settings.kalshi_private_key_path
                ),
                client=http_client,
            )

            report = await reconcile_event_orders(
                local_orders=local_orders,
                exchange_reader=exchange_client,
                event_ticker=event_ticker,
            )
    finally:
        await database.close()

    print()
    print("ORDER RECONCILIATION")
    print("--------------------")
    print(f"Event: {event_ticker.strip().upper()}")
    print(f"Local orders: {len(local_orders)}")

    if report.in_sync:
        print("Result: IN SYNC")
        print("Differences: 0")
        print()
        print("Safety: read-only; nothing was changed.")
        return 0

    print("Result: DIFFERENCES FOUND")
    print(f"Differences: {len(report.differences)}")

    for difference in report.differences:
        print()
        print(f"Order: {difference.client_order_id}")
        print(f"Field: {difference.field}")
        print(
            "Local: "
            f"{format_value(difference.internal)}"
        )
        print(
            "Kalshi: "
            f"{format_value(difference.exchange)}"
        )

    print()
    print("Safety: read-only; nothing was changed.")
    return 1


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare local OMS orders with Kalshi records."
        )
    )
    parser.add_argument(
        "event_ticker",
        help="Kalshi event ticker to reconcile.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_arguments()
    raise SystemExit(
        asyncio.run(
            reconcile(arguments.event_ticker)
        )
    )