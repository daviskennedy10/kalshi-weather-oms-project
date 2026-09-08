import asyncio

from weather_oms.analysis.forecast_metrics import (
    ForecastMetrics,
    calculate_error_metrics,
    calculate_forecast_metrics,
)
from weather_oms.analysis.walk_forward import (
    walk_forward_predictions,
)
from weather_oms.config import Settings
from weather_oms.stations import STATIONS
from weather_oms.storage.db import Database
from weather_oms.storage.forecast_outcome_repository import (
    load_forecast_outcomes,
)


def print_metrics(
    title: str,
    metrics: ForecastMetrics,
) -> None:
    print(title)
    print(f"Sample count: {metrics.sample_count}")
    print(f"Mean error: {metrics.mean_error_f:+.2f}°F")
    print(
        "Mean absolute error: "
        f"{metrics.mean_absolute_error_f:.2f}°F"
    )
    print(
        "Root mean squared error: "
        f"{metrics.root_mean_squared_error_f:.2f}°F"
    )


async def analyze() -> None:
    settings = Settings()
    station = STATIONS["KNYC"]
    database = Database(settings.database_url)

    try:
        async with database.session() as session:
            outcomes = await load_forecast_outcomes(
                session=session,
                station_code=station.code,
                timezone=station.timezone,
            )
    finally:
        await database.close()

    print(
        "Selection policy: newest forecast available by "
        "12:00 PM local time on the preceding day"
    )
    print(f"Station: {station.code}")
    print(f"Eligible matched dates: {len(outcomes)}")
    print()

    if not outcomes:
        print("No forecast outcomes currently satisfy the policy.")
        return

    print("Selected outcomes:")

    for outcome in outcomes:
        print(
            f"date={outcome.observation_date} "
            f"retrieved={outcome.forecast_retrieved_at.isoformat()} "
            f"lead={outcome.lead_hours:.1f}h "
            f"forecast={outcome.raw_high_f:.2f}°F "
            f"actual={outcome.actual_high_f:.2f}°F "
            f"error={outcome.error_f:+.2f}°F "
            f"ensemble_stddev="
            f"{outcome.ensemble_stddev_f:.2f}°F"
        )

    baseline_metrics = calculate_forecast_metrics(outcomes)

    print()
    print_metrics(
        "Raw WeatherNext baseline:",
        baseline_metrics,
    )

    predictions = walk_forward_predictions(
        outcomes,
        minimum_training_size=1,
    )

    print()
    print("Walk-forward predictions:")

    if not predictions:
        print(
            "Not enough historical outcomes to produce "
            "a walk-forward prediction."
        )
        return

    for prediction in predictions:
        print(
            f"date={prediction.observation_date} "
            f"trained_on={prediction.training_count} "
            f"learned_bias={prediction.learned_bias_f:+.2f}°F "
            f"raw={prediction.raw_high_f:.2f}°F "
            f"corrected={prediction.corrected_high_f:.2f}°F "
            f"actual={prediction.actual_high_f:.2f}°F "
            f"raw_error={prediction.raw_error_f:+.2f}°F "
            f"corrected_error="
            f"{prediction.corrected_error_f:+.2f}°F"
        )

    evaluated_raw_metrics = calculate_error_metrics(
        prediction.raw_error_f
        for prediction in predictions
    )
    corrected_metrics = calculate_error_metrics(
        prediction.corrected_error_f
        for prediction in predictions
    )

    print()
    print_metrics(
        "Raw forecasts on evaluated dates:",
        evaluated_raw_metrics,
    )

    print()
    print_metrics(
        "Bias-corrected forecasts on evaluated dates:",
        corrected_metrics,
    )

    mae_improvement = (
        evaluated_raw_metrics.mean_absolute_error_f
        - corrected_metrics.mean_absolute_error_f
    )

    print()
    print(
        "MAE improvement from correction: "
        f"{mae_improvement:+.2f}°F"
    )

    if mae_improvement > 0:
        print("Result: bias correction improved MAE.")
    elif mae_improvement < 0:
        print("Result: bias correction worsened MAE.")
    else:
        print("Result: bias correction did not change MAE.")

    print(
        "Warning: the evaluation sample is currently too "
        "small for a reliable conclusion."
    )


if __name__ == "__main__":
    asyncio.run(analyze())