import argparse
import asyncio
from datetime import date
from decimal import Decimal

from weather_oms.config import Settings
from weather_oms.execution.portfolio_risk import (
    summarize_portfolio_risk,
)
from weather_oms.storage.db import Database
from weather_oms.storage.paper_position_repository import (
    load_paper_positions_for_date,
)


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "Date must use YYYY-MM-DD format."
        ) from error


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Display paper positions and profit or loss "
            "for one target date."
        )
    )
    parser.add_argument(
        "target_date",
        type=parse_date,
        help="Target date in YYYY-MM-DD format.",
    )
    return parser.parse_args()


def event_ticker_for_date(target_date: date) -> str:
    date_component = target_date.strftime("%y%b%d").upper()
    return f"KXHIGHNY-{date_component}"


async def inspect_portfolio(target_date: date) -> None:
    settings = Settings()
    event_ticker = event_ticker_for_date(target_date)
    database = Database(settings.database_url)

    try:
        async with database.session() as session:
            positions = await load_paper_positions_for_date(
                session=session,
                target_date=target_date,
            )
    finally:
        await database.close()

    summary = summarize_portfolio_risk(
        positions=positions,
        current_event_ticker=event_ticker,
    )

    total_net_pnl = sum(
        (
            position.realized_pnl_dollars
            for position in positions
            if position.realized_pnl_dollars is not None
        ),
        start=Decimal(0),
    )

    print()
    print("PAPER PORTFOLIO")
    print("---------------")
    print(f"Target date: {target_date}")
    print(f"Kalshi event: {event_ticker}")
    print(f"Positions: {len(positions)}")
    print(
        "Open event risk: "
        f"${summary.current_event_risk_dollars:.4f}"
    )
    print(
        "Daily realized loss: "
        f"${summary.daily_realized_loss_dollars:.4f}"
    )
    print(f"Net settled P&L: ${total_net_pnl:+.4f}")

    if not positions:
        print("No paper positions found.")
        return

    for position in positions:
        print()
        print(f"Paper order: {position.paper_order_id}")
        print(f"Market: {position.market_ticker}")
        print(f"Side: {position.side.upper()}")
        print(f"Contracts: {position.contracts}")
        print(
            "Total cost: "
            f"${position.total_cost_dollars:.4f}"
        )
        print(f"Status: {position.status.upper()}")

        if position.status == "settled":
            result = position.settlement_result
            print(
                "Official market result: "
                f"{result.upper() if result else 'UNKNOWN'}"
            )
            print(
                "Payout: "
                f"${position.payout_dollars:.4f}"
                if position.payout_dollars is not None
                else "Payout: UNKNOWN"
            )
            print(
                "Realized P&L: "
                f"${position.realized_pnl_dollars:+.4f}"
                if position.realized_pnl_dollars is not None
                else "Realized P&L: UNKNOWN"
            )


if __name__ == "__main__":
    arguments = parse_arguments()

    asyncio.run(
        inspect_portfolio(arguments.target_date)
    )