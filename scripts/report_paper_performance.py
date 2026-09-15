import argparse
import asyncio
from datetime import date, timedelta
from decimal import Decimal

from weather_oms.analysis.backtest import (
    calculate_probability_metrics,
)
from weather_oms.analysis.latency_metrics import (
    DecisionTiming,
    calculate_latency_metrics,
)
from weather_oms.analysis.paper_performance import (
    calculate_paper_performance,
)
from weather_oms.config import Settings
from weather_oms.storage.db import Database
from weather_oms.storage.paper_analysis_repository import (
    load_paper_probability_observations,
)
from weather_oms.storage.paper_position_repository import (
    load_paper_positions_for_date,
)
from weather_oms.storage.paper_risk_decision_repository import (
    load_paper_decision_timings,
)


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "Date must use YYYY-MM-DD format."
        ) from error


def format_percentage(
    value: Decimal | None,
) -> str:
    if value is None:
        return "N/A"

    return f"{value * Decimal(100):.1f}%"

def format_signed_dollars(value: Decimal) -> str:
    sign = "+" if value >= 0 else "-"
    return f"{sign}${abs(value):.4f}"


def format_latency(
    value: timedelta | None,
) -> str:
    if value is None:
        return "N/A"

    return f"{value.total_seconds() * 1000:.1f} ms"


async def report(target_date: date) -> None:
    settings = Settings()
    database = Database(settings.database_url)

    try:
        async with database.session() as session:
            positions = await load_paper_positions_for_date(
                session=session,
                target_date=target_date,
            )
            stored_timings = (
                await load_paper_decision_timings(
                    session=session,
                    target_date=target_date,
                )
            )
            observations = (
                await load_paper_probability_observations(
                    session=session,
                    target_date=target_date,
                )
            )
    finally:
        await database.close()

    performance = calculate_paper_performance(
        positions
    )
    latency = calculate_latency_metrics(
        tuple(
            DecisionTiming(
                decision_id=timing.decision_id,
                quote_retrieved_at=(
                    timing.quote_retrieved_at
                ),
                decision_stored_at=timing.stored_at,
            )
            for timing in stored_timings
        )
    )
    probability_metrics = (
        None
        if not observations
        else calculate_probability_metrics(
            probabilities=[
                float(observation.model_probability)
                for observation in observations
            ],
            outcomes=[
                observation.outcome
                for observation in observations
            ],
        )
    )

    print()
    print("PAPER PERFORMANCE REPORT")
    print("------------------------")
    print(f"Target date: {target_date}")

    print()
    print("POSITIONS")
    print("---------")
    print(
        f"Total positions: "
        f"{performance.total_positions}"
    )
    print(
        f"Open positions: "
        f"{performance.open_positions}"
    )
    print(
        f"Settled positions: "
        f"{performance.settled_positions}"
    )
    print(
        f"Settled contracts: "
        f"{performance.settled_contracts}"
    )
    print(
        f"Winning positions: "
        f"{performance.winning_positions}"
    )
    print(
        f"Losing positions: "
        f"{performance.losing_positions}"
    )
    print(
        f"Win rate: "
        f"{format_percentage(performance.win_rate)}"
    )

    print()
    print("PROFIT AND LOSS")
    print("---------------")
    print(
        f"Total cost: "
        f"${performance.total_cost_dollars:.4f}"
    )
    print(
        f"Total payout: "
        f"${performance.total_payout_dollars:.4f}"
    )
    print(
        "Total P&L: "
        + format_signed_dollars(
            performance.total_pnl_dollars
        )
    )
    print(
        "Average P&L: "
        + (
            "N/A"
            if performance.average_pnl_dollars is None
            else format_signed_dollars(
                performance.average_pnl_dollars
            )
        )
    )
    print(
        "Return on cost: "
        f"{format_percentage(performance.return_on_cost)}"
    )
    print(
        "Maximum drawdown: "
        f"${performance.maximum_drawdown_dollars:.4f}"
    )

    print()
    print("DECISION LATENCY")
    print("----------------")
    print(f"Samples: {latency.sample_count}")
    print(
        f"Minimum: {format_latency(latency.minimum)}"
    )
    print(f"Mean: {format_latency(latency.mean)}")
    print(
        "95th percentile: "
        f"{format_latency(latency.percentile_95)}"
    )
    print(
        f"Maximum: {format_latency(latency.maximum)}"
    )
    print()
    print("PROBABILITY QUALITY")
    print("-------------------")

    if probability_metrics is None:
        print("Samples: 0")
        print("Brier score: N/A")
        print("Log loss: N/A")
        print("Calibration error: N/A")
    else:
        print(
            f"Samples: {probability_metrics.sample_count}"
        )
        print(
            "Brier score: "
            f"{probability_metrics.brier_score:.4f}"
        )
        print(
            f"Log loss: {probability_metrics.log_loss:.4f}"
        )
        print(
            "Calibration error: "
            f"{probability_metrics.expected_calibration_error:.4f}"
        )

    print()
    print("Safety: report only; nothing was changed.")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Report paper-trading performance for one date."
        )
    )
    parser.add_argument(
        "target_date",
        type=parse_date,
        help="Target date in YYYY-MM-DD format.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_arguments()
    asyncio.run(report(arguments.target_date))