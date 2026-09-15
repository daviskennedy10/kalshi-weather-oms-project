import argparse
import asyncio
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

from weather_oms.config import Settings
from weather_oms.execution.paper_settlement import (
    PaperSettlementResult,
    calculate_paper_settlement,
)
from weather_oms.storage.db import Database
from weather_oms.storage.paper_position_repository import (
    PaperSide,
    SettlementWriteResult,
    StoredPaperPosition,
    load_open_paper_positions_for_event,
    settle_paper_position,
)
from weather_oms.storage.temperature_settlement_repository import (
    load_temperature_settlement,
)

SettlementActionResult = SettlementWriteResult | Literal["dry_run"]


@dataclass(frozen=True, slots=True)
class SettlementPreview:
    position: StoredPaperPosition
    market_result: PaperSide
    calculation: PaperSettlementResult
    action_result: SettlementActionResult


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
            "Settle paper positions using a stored official "
            "Kalshi settlement."
        )
    )
    parser.add_argument(
        "target_date",
        type=parse_date,
        help="Target date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply paper settlements to the database.",
    )
    return parser.parse_args()


def event_ticker_for_date(target_date: date) -> str:
    date_component = target_date.strftime("%y%b%d").upper()
    return f"KXHIGHNY-{date_component}"


async def settle_positions(
    target_date: date,
    apply_changes: bool,
) -> None:
    settings = Settings()
    event_ticker = event_ticker_for_date(target_date)
    database = Database(settings.database_url)

    previews: list[SettlementPreview] = []

    try:
        async with database.session() as session:
            open_positions = (
                await load_open_paper_positions_for_event(
                    session=session,
                    event_ticker=event_ticker,
                )
            )

            if not open_positions:
                print(
                    f"No open paper positions found for "
                    f"{event_ticker}."
                )
                return

            settlement = await load_temperature_settlement(
                session=session,
                event_ticker=event_ticker,
            )

            if settlement is None:
                print(
                    "Paper settlement blocked: no stored "
                    "official settlement was found."
                )
                return

            if settlement.observation_date != target_date:
                print(
                    "Paper settlement blocked: settlement "
                    "date does not match the target date."
                )
                return

            winning_market_ticker = (
                settlement.winning_market_ticker
            )

            if winning_market_ticker is None:
                print(
                    "Paper settlement blocked: the stored "
                    "settlement has no winning market ticker."
                )
                return

            for position in open_positions:
                market_result: PaperSide = (
                    "yes"
                    if position.market_ticker
                    == winning_market_ticker
                    else "no"
                )

                calculation = calculate_paper_settlement(
                    position_side=position.side,
                    settlement_result=market_result,
                    contracts=position.contracts,
                    entry_price_cents=(
                        position.entry_price_cents
                    ),
                    fee_dollars=position.fee_dollars,
                )

                action_result: SettlementActionResult = (
                    "dry_run"
                )

                if apply_changes:
                    action_result = (
                        await settle_paper_position(
                            session=session,
                            paper_order_id=(
                                position.paper_order_id
                            ),
                            settlement_result=market_result,
                            settled_at=settlement.settled_at,
                        )
                    )

                previews.append(
                    SettlementPreview(
                        position=position,
                        market_result=market_result,
                        calculation=calculation,
                        action_result=action_result,
                    )
                )
    finally:
        await database.close()

    total_pnl = sum(
        (
            preview.calculation.realized_pnl_dollars
            for preview in previews
        ),
        start=Decimal(0),
    )

    print()
    print("PAPER SETTLEMENT RESULTS")
    print("------------------------")
    print(f"Target date: {target_date}")
    print(f"Kalshi event: {event_ticker}")
    print(
        "Mode: "
        f"{'APPLY' if apply_changes else 'DRY RUN'}"
    )

    for preview in previews:
        position = preview.position
        calculation = preview.calculation

        print()
        print(f"Market: {position.market_ticker}")
        print(f"Position side: {position.side.upper()}")
        print(
            "Official market result: "
            f"{preview.market_result.upper()}"
        )
        print(
            "Total cost: "
            f"${calculation.total_cost_dollars:.4f}"
        )
        print(
            "Payout: "
            f"${calculation.payout_dollars:.4f}"
        )
        print(
            "Realized P&L: "
            f"${calculation.realized_pnl_dollars:+.4f}"
        )
        print(
            "Database result: "
            f"{preview.action_result}"
        )

    print()
    print(f"Total paper P&L: ${total_pnl:+.4f}")
    print(
        "Safety: paper settlement only. "
        "No Kalshi orders were submitted."
    )


if __name__ == "__main__":
    arguments = parse_arguments()

    asyncio.run(
        settle_positions(
            target_date=arguments.target_date,
            apply_changes=arguments.apply,
        )
    )