import argparse
import asyncio
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from weather_oms.config import Settings
from weather_oms.execution.portfolio_risk import (
    summarize_portfolio_risk,
)
from weather_oms.execution.risk import assess_risk
from weather_oms.execution.risk_adapter import build_risk_request
from weather_oms.signal.bias_correction import apply_bias_correction
from weather_oms.signal.bias_model import ForecastFeatures
from weather_oms.signal.forecast_dataset import prior_day_cutoff
from weather_oms.signal.market_comparison import (
    compare_market_probability,
)
from weather_oms.signal.market_probability import (
    calculate_event_probabilities,
)
from weather_oms.signal.market_timing import calculate_quote_age
from weather_oms.stations import STATIONS
from weather_oms.storage.db import Database
from weather_oms.storage.forecast_outcome_repository import (
    load_forecast_outcomes,
)
from weather_oms.storage.forecast_repository import (
    load_latest_forecast_by_cutoff,
)
from weather_oms.storage.market_quote_repository import (
    load_latest_market_quotes_by_cutoff,
)
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
            "Compare time-aligned WeatherNext and Kalshi "
            "snapshots for one daily-high event."
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


def bracket_label(
    lower_f: int | None,
    upper_f: int | None,
) -> str:
    if lower_f is None:
        return f"{upper_f}°F or below"

    if upper_f is None:
        return f"{lower_f}°F or above"

    return f"{lower_f}–{upper_f}°F"


async def compare(target_date: date) -> None:
    settings = Settings()
    station = STATIONS["KNYC"]
    event_ticker = event_ticker_for_date(target_date)

    cutoff_at = prior_day_cutoff(
        target_date,
        station.timezone,
    )

    database = Database(settings.database_url)

    try:
        async with database.session() as session:
            stored_forecast = (
                await load_latest_forecast_by_cutoff(
                    session=session,
                    station_code=station.code,
                    target_date=target_date,
                    cutoff_at=cutoff_at,
                )
            )

            outcomes = await load_forecast_outcomes(
                session=session,
                station_code=station.code,
                timezone=station.timezone,
            )

            market_quote_set = (
                await load_latest_market_quotes_by_cutoff(
                    session=session,
                    event_ticker=event_ticker,
                    target_date=target_date,
                    cutoff_at=cutoff_at,
                )
            )
            paper_positions = (
                await load_paper_positions_for_date(
                    session=session,
                    target_date=target_date,
                )
            )
    finally:
        await database.close()

    if stored_forecast is None:
        print(
            "No stored WeatherNext forecast satisfies "
            "the selection policy."
        )
        return

    if market_quote_set is None:
        print(
            "No stored Kalshi quote snapshot satisfies "
            "the selection policy."
        )
        return

    try:
        quote_age = calculate_quote_age(
            retrieved_at=market_quote_set.retrieved_at,
            decision_at=cutoff_at,
        )
    except ValueError as error:
        print(f"Kalshi quote rejected: {error}")
        return

    local_zone = ZoneInfo(station.timezone)
    target_start = datetime.combine(
        target_date,
        time.min,
        local_zone,
    )

    forecast_retrieved_at_local = (
        stored_forecast.retrieved_at.astimezone(local_zone)
    )
    market_retrieved_at_local = (
        market_quote_set.retrieved_at.astimezone(local_zone)
    )

    lead_hours = (
        target_start - forecast_retrieved_at_local
    ).total_seconds() / 3600

    features = ForecastFeatures(
        raw_high_f=stored_forecast.mean_high_f,
        lead_hours=lead_hours,
        ensemble_stddev_f=stored_forecast.standard_deviation_f,
        station=stored_forecast.station_code,
        day_of_year=target_date.timetuple().tm_yday,
    )

    correction = apply_bias_correction(
        features=features,
        target_date=target_date,
        available_outcomes=outcomes,
    )

    markets = market_quote_set.markets

    portfolio_summary = summarize_portfolio_risk(
    positions=paper_positions,
    current_event_ticker=event_ticker,
    )

    probabilities = calculate_event_probabilities(
        member_highs_f=stored_forecast.member_highs_f,
        brackets=tuple(
            market.bracket for market in markets
        ),
        bias_adjustment_f=correction.learned_bias_f,
    )

    model_ready = (
        len(stored_forecast.member_highs_f) == 64
        and len(markets) == 6
    )

    print()
    print("FORECAST INPUT")
    print("--------------")
    print(f"Station: {station.code} ({station.name})")
    print(f"Target date: {target_date}")
    print(f"Kalshi event: {event_ticker}")
    print(f"Cutoff: {cutoff_at.isoformat()}")
    print(
        "Forecast snapshot UTC: "
        f"{stored_forecast.retrieved_at.isoformat()}"
    )
    print(
        "Forecast snapshot local: "
        f"{forecast_retrieved_at_local.isoformat()}"
    )
    print(
        "Kalshi snapshot UTC: "
        f"{market_quote_set.retrieved_at.isoformat()}"
    )
    print(
        "Kalshi snapshot local: "
        f"{market_retrieved_at_local.isoformat()}"
    )
    print(
        "Ensemble members: "
        f"{len(stored_forecast.member_highs_f)}"
    )
    print(
        "Raw ensemble mean: "
        f"{stored_forecast.mean_high_f:.2f}°F"
    )
    print(
        "Ensemble standard deviation: "
        f"{stored_forecast.standard_deviation_f:.2f}°F"
    )

    print()
    print("BIAS DECISION")
    print("-------------")
    print(f"Eligible outcomes: {correction.training_count}")
    print(
        "Correction applied: "
        f"{'Yes' if correction.correction_applied else 'No'}"
    )
    print(
        "Bias adjustment: "
        f"{correction.learned_bias_f:+.2f}°F"
    )
    print(
        "Final ensemble mean: "
        f"{correction.corrected_high_f:.2f}°F"
    )
    print(f"Reason: {correction.reason}")

    print()
    print("PAPER PORTFOLIO")
    print("---------------")
    print(
        "Open positions in this event: "
        f"{len(portfolio_summary.current_event_positions)}"
    )
    print(
        "Current event risk: "
        f"${portfolio_summary.current_event_risk_dollars:.4f}"
    )
    print(
        "Other event risk: "
        f"${portfolio_summary.other_event_risk_dollars:.4f}"
    )
    print(
        "Total daily exposure: "
        f"${portfolio_summary.total_daily_exposure_dollars:.4f}"
    )
    print(
        "Daily realized loss: "
        f"${portfolio_summary.daily_realized_loss_dollars:.4f}"
    )

    print()
    print("MARKET COMPARISON")
    print("-----------------")

    total_raw_probability = 0.0
    total_smoothed_probability = 0.0

    for market, probability in zip(
        markets,
        probabilities,
        strict=True,
    ):
        comparison = compare_market_probability(
            market=market,
            our_yes_probability=(
                probability.smoothed_probability
            ),
        )

        total_raw_probability += probability.raw_probability
        total_smoothed_probability += (
            probability.smoothed_probability
        )

        label = bracket_label(
            market.bracket.lower_f,
            market.bracket.upper_f,
        )

        risk_decision = None

        if comparison.candidate_side is None:
            candidate = "None"
        else:
            candidate = (
                f"{comparison.candidate_side.upper()} "
                f"({comparison.candidate_edge * 100:+.1f} pp)"
            )

            risk_request = build_risk_request(
                comparison=comparison,
                bracket_id=market.ticker,
                mode="paper",
                kill_switch_active=False,
                inputs_complete=True,
                inputs_aligned=True,
                forecast_eligible=True,
                quote_eligible=True,
                quote_fresh=True,
                model_ready=model_ready,
                existing_event_positions=(
                portfolio_summary.current_event_positions
                ),
                other_daily_exposure_dollars=(
                    portfolio_summary.other_event_risk_dollars
                ),
                daily_realized_loss_dollars=(
                    portfolio_summary.daily_realized_loss_dollars
                ),
            )

            risk_decision = assess_risk(risk_request)
            

        print()
        print(f"Market: {market.ticker}")
        print(f"Bracket: {label}")
        print(
            "Matching members: "
            f"{probability.matching_members}/"
            f"{probability.total_members}"
        )
        print(
            "Raw ensemble probability: "
            f"{probability.raw_probability:.1%}"
        )
        print(
            "Smoothed YES probability: "
            f"{comparison.our_yes_probability:.1%}"
        )
        print(
            "Smoothed NO probability: "
            f"{comparison.our_no_probability:.1%}"
        )
        print(
            "YES bid/ask: "
            f"{market.yes_bid_cents}¢/"
            f"{market.yes_ask_cents}¢"
        )
        print(
            "NO bid/ask: "
            f"{market.no_bid_cents}¢/"
            f"{market.no_ask_cents}¢"
        )
        print(
            "YES fee: "
            f"{comparison.yes_fee_dollars * 100:.2f}¢"
        )
        print(
            "NO fee: "
            f"{comparison.no_fee_dollars * 100:.2f}¢"
        )
        print(
            "YES pre-fee edge: "
            f"{comparison.yes_pre_fee_edge * 100:+.1f} pp"
        )
        print(
            "NO pre-fee edge: "
            f"{comparison.no_pre_fee_edge * 100:+.1f} pp"
        )
        print(
            "YES net edge: "
            f"{comparison.yes_net_edge * 100:+.1f} pp"
        )
        print(
            "NO net edge: "
            f"{comparison.no_net_edge * 100:+.1f} pp"
        )
        print(f"Candidate: {candidate}")

        if risk_decision is None:
            print("Risk decision: NOT EVALUATED")
        else:
            result = (
                "ALLOW"
                if risk_decision.allowed
                else "BLOCK"
            )
            print(f"Risk decision: {result}")
            print(
                "Proposed risk: "
                f"${risk_decision.event_worst_case_risk_dollars:.4f}"
            )

            for reason in risk_decision.reasons:
                print(f"Risk reason: {reason}")

    print()
    print(
        "Required minimum net edge: "
        f"{comparison.minimum_net_edge * 100:.1f} pp"
    )
    print(
        "Kalshi quote age at cutoff: "
        f"{quote_age.total_seconds() / 60:.1f} minutes"
    )
    print()
    print(
        "Total raw probability: "
        f"{total_raw_probability:.1%}"
    )
    print(
        "Total smoothed probability: "
        f"{total_smoothed_probability:.1%}"
    )
    print(
        "Warning: research and paper-risk output only. "
        "No orders are placed. Existing positions and daily "
        "against the stored paper portfolio."
    )


if __name__ == "__main__":
    arguments = parse_arguments()
    asyncio.run(compare(arguments.target_date))