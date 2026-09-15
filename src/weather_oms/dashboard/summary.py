from dataclasses import dataclass

from weather_oms.analysis.backtest import (
    ProbabilityMetrics,
    calculate_probability_metrics,
)
from weather_oms.analysis.latency_metrics import (
    DecisionTiming,
    LatencyMetrics,
    calculate_latency_metrics,
)
from weather_oms.analysis.paper_performance import (
    PaperPerformance,
    calculate_paper_performance,
)
from weather_oms.storage.paper_analysis_repository import (
    PaperProbabilityObservation,
)
from weather_oms.storage.paper_position_repository import (
    StoredPaperPosition,
)
from weather_oms.storage.paper_risk_decision_repository import (
    StoredPaperDecisionTiming,
)


@dataclass(frozen=True, slots=True)
class DashboardSummary:
    performance: PaperPerformance
    latency: LatencyMetrics
    probability: ProbabilityMetrics | None


def build_dashboard_summary(
    positions: tuple[StoredPaperPosition, ...],
    stored_timings: tuple[
        StoredPaperDecisionTiming,
        ...,
    ],
    observations: tuple[
        PaperProbabilityObservation,
        ...,
    ],
) -> DashboardSummary:
    """Build dashboard measurements without changing data."""

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

    probability = (
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

    return DashboardSummary(
        performance=performance,
        latency=latency,
        probability=probability,
    )