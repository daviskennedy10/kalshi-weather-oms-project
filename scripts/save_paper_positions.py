import argparse
import asyncio
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from weather_oms.config import Settings
from weather_oms.execution.paper_decision_factory import (
    create_new_paper_risk_decision,
)
from weather_oms.execution.paper_planner import (
    PaperCandidate,
    PaperPlanItem,
    plan_paper_positions,
)
from weather_oms.execution.paper_position_factory import (
    create_new_paper_position,
)
from weather_oms.execution.paper_sizing import (
    size_paper_candidate,
)
from weather_oms.execution.portfolio_risk import (
    summarize_portfolio_risk,
)
from weather_oms.execution.position_sizing import (
    SizingDecision,
)
from weather_oms.signal.bias_correction import apply_bias_correction
from weather_oms.signal.bias_model import ForecastFeatures
from weather_oms.signal.forecast_dataset import prior_day_cutoff
from weather_oms.signal.market_comparison import (
    MarketComparison,
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
    save_open_paper_position,
)
from weather_oms.storage.paper_risk_decision_repository import (
    save_paper_risk_decision,
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
            "Save risk-approved pretend positions from one "
            "stored, time-aligned weather decision."
        )
    )
    parser.add_argument(
        "target_date",
        type=parse_date,
        help="Target date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--kill-switch",
        action="store_true",
        help="Block every paper candidate.",
    )
    parser.add_argument(
    "--save",
    action="store_true",
    help="Actually save approved pretend positions.",
    )
    return parser.parse_args()


def event_ticker_for_date(target_date: date) -> str:
    date_component = target_date.strftime("%y%b%d").upper()
    return f"KXHIGHNY-{date_component}"


async def save_paper_positions(
    target_date: date,
    kill_switch_active: bool,
    save_requested: bool,
) -> None:
    settings = Settings()
    station = STATIONS["KNYC"]
    event_ticker = event_ticker_for_date(target_date)

    cutoff_at = prior_day_cutoff(
        target_date,
        station.timezone,
    )

    database = Database(settings.database_url)

    results: list[
        tuple[PaperPlanItem, bool | None, bool | None]
    ] = []
    sizing_skips: list[
        tuple[MarketComparison, SizingDecision]
    ] = []

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

            if stored_forecast is None:
                print(
                    "No eligible stored WeatherNext forecast "
                    "was found."
                )
                return

            if market_quote_set is None:
                print(
                    "No eligible stored Kalshi quote snapshot "
                    "was found."
                )
                return

            try:
                quote_age = calculate_quote_age(
                    retrieved_at=(
                        market_quote_set.retrieved_at
                    ),
                    decision_at=cutoff_at,
                )
            except ValueError as error:
                print(f"Paper decision blocked: {error}")
                return

            now = datetime.now(UTC)
            saving_window_closes = (
                cutoff_at + timedelta(minutes=5)
            )

            if (
                save_requested
                and (
                    now < market_quote_set.retrieved_at
                    or now > saving_window_closes
                )
            ):
                print(
                    "Paper saving blocked: this is outside "
                    "the forward paper-trading window."
                )
                print(
                    "Historical snapshots may only be used "
                    "for dry-run research."
                )
                return
            markets = market_quote_set.markets

            if (
                len(stored_forecast.member_highs_f) != 64
                or len(markets) != 6
            ):
                print(
                    "Paper decision blocked: expected 64 "
                    "ensemble members and 6 markets."
                )
                return

            local_zone = ZoneInfo(station.timezone)
            forecast_retrieved_at_local = (
                stored_forecast.retrieved_at.astimezone(
                    local_zone
                )
            )
            target_start = datetime.combine(
                target_date,
                time.min,
                local_zone,
            )
            lead_hours = (
                target_start - forecast_retrieved_at_local
            ).total_seconds() / 3600

            features = ForecastFeatures(
                raw_high_f=stored_forecast.mean_high_f,
                lead_hours=lead_hours,
                ensemble_stddev_f=(
                    stored_forecast.standard_deviation_f
                ),
                station=stored_forecast.station_code,
                day_of_year=(
                    target_date.timetuple().tm_yday
                ),
            )

            correction = apply_bias_correction(
                features=features,
                target_date=target_date,
                available_outcomes=outcomes,
            )

            probabilities = calculate_event_probabilities(
                member_highs_f=(
                    stored_forecast.member_highs_f
                ),
                brackets=tuple(
                    market.bracket for market in markets
                ),
                bias_adjustment_f=(
                    correction.learned_bias_f
                ),
            )

            portfolio = summarize_portfolio_risk(
                positions=paper_positions,
                current_event_ticker=event_ticker,
            )

            candidates: list[PaperCandidate] = []

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

                if comparison.candidate_side is not None:
                    sizing = size_paper_candidate(
                        comparison=comparison,
                        portfolio=portfolio,
                        bankroll_dollars=(
                            settings.paper_bankroll_dollars
                        ),
                    )

                    if sizing.should_trade:
                        candidates.append(
                            PaperCandidate(
                                bracket_id=market.ticker,
                                comparison=comparison,
                                contracts=sizing.contracts,
                            )
                        )
                    else:
                        sizing_skips.append(
                            (comparison, sizing)
                        )

            plan = plan_paper_positions(
                candidates=tuple(candidates),
                portfolio=portfolio,
                kill_switch_active=kill_switch_active,
            )

            for plan_item in plan:
                audit_inserted: bool | None = None

                if save_requested:
                    audit_record = (
                        create_new_paper_risk_decision(
                            plan_item=plan_item,
                            event_ticker=event_ticker,
                            target_date=target_date,
                            quote_retrieved_at=(
                                market_quote_set.retrieved_at
                            ),
                            kill_switch_active=(
                                kill_switch_active
                            ),
                        )
                    )

                    audit_inserted = (
                        await save_paper_risk_decision(
                            session=session,
                            decision=audit_record,
                        )
                    )

                if not plan_item.risk_decision.allowed:
                    results.append(
                        (
                            plan_item,
                            None,
                            audit_inserted,
                        )
                    )
                    continue

                if not save_requested:
                    results.append(
                        (
                            plan_item,
                            None,
                            None,
                        )
                    )
                    continue

                new_position = create_new_paper_position(
                    plan_item=plan_item,
                    event_ticker=event_ticker,
                    target_date=target_date,
                    quote_retrieved_at=(
                        market_quote_set.retrieved_at
                    ),
                )

                position_inserted = (
                    await save_open_paper_position(
                        session=session,
                        position=new_position,
                    )
                )

                results.append(
                    (
                        plan_item,
                        position_inserted,
                        audit_inserted,
                    )
                )
    finally:
        await database.close()

    print()
    print("PAPER POSITION RESULTS")
    print("----------------------")
    print(f"Target date: {target_date}")
    print(f"Kalshi event: {event_ticker}")
    print(
        "Kill switch: "
        f"{'ACTIVE' if kill_switch_active else 'OFF'}"
    )
    print(
        "Mode: "
        f"{'SAVE' if save_requested else 'DRY RUN'}"
    )
    print(
        "Quote age at cutoff: "
        f"{quote_age.total_seconds() / 60:.1f} minutes"
    )
    print(
        "Market opportunities: "
        f"{len(results) + len(sizing_skips)}"
    )
    print(f"Positions sized: {len(results)}")
    print(f"Sizing skips: {len(sizing_skips)}")

    if not results and not sizing_skips:
        print("No candidate exceeded the minimum net edge.")
    
    for comparison, sizing in sizing_skips:
        side = comparison.candidate_side

        print()
        print(f"Market: {comparison.market_ticker}")
        print(f"Side: {side.upper() if side else 'NONE'}")
        print(
            "Net edge: "
            f"{comparison.candidate_edge * 100:+.1f} pp"
        )
        print("Sizing decision: SKIP")
        print(f"Sizing reason: {sizing.reason}")
        print("Database result: nothing saved")

    for plan_item, inserted, audit_inserted in results:
        comparison = plan_item.candidate.comparison
        decision = plan_item.risk_decision
        side = comparison.candidate_side

        print()
        print(f"Market: {comparison.market_ticker}")
        print(f"Side: {side.upper() if side else 'NONE'}")
        print(
            "Contracts: "
            f"{plan_item.risk_request.proposed_position.contracts}"
        )
        print(
            "Net edge: "
            f"{comparison.candidate_edge * 100:+.1f} pp"
        )
        print(
            "Worst-case event risk after candidate: "
            f"${decision.event_worst_case_risk_dollars:.4f}"
        )
        print(
            "Risk decision: "
            f"{'ALLOW' if decision.allowed else 'BLOCK'}"
        )

        if audit_inserted is True:
            print("Audit result: risk decision saved")
        elif audit_inserted is False:
            print("Audit result: duplicate decision not saved")
        else:
            print("Audit result: dry run; nothing saved")

        for reason in decision.reasons:
            print(f"Risk reason: {reason}")

        if inserted is True:
            print("Database result: paper position saved")
        elif inserted is False:
            print(
                "Database result: duplicate paper position "
                "not saved"
            )
        else:
            if decision.allowed and not save_requested:
                print("Database result: dry run; nothing saved")
            else:
                print("Database result: blocked; nothing saved")

    print()
    print(
        "Safety: pretend positions only. "
        "No Kalshi orders were submitted."
    )


if __name__ == "__main__":
    arguments = parse_arguments()

    asyncio.run(
        save_paper_positions(
            target_date=arguments.target_date,
            kill_switch_active=arguments.kill_switch,
            save_requested=arguments.save,
        )
    )