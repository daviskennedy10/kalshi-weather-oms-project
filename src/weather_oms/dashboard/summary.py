from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

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
    DecisionSide,
    StoredPaperDecisionMetric,
    StoredPaperDecisionTiming,
)


@dataclass(frozen=True, slots=True)
class DashboardPosition:
    position: StoredPaperPosition
    model_probability: Decimal | None
    net_edge: Decimal | None


@dataclass(frozen=True, slots=True)
class DashboardSummary:
    positions: tuple[DashboardPosition, ...]
    performance: PaperPerformance
    latency: LatencyMetrics
    probability: ProbabilityMetrics | None


def build_dashboard_summary(
    positions: tuple[StoredPaperPosition, ...],
    stored_timings: tuple[
        StoredPaperDecisionTiming,
        ...,
    ],
    decision_metrics: tuple[
        StoredPaperDecisionMetric,
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

    metrics_by_position = {
        (
            metric.market_ticker,
            metric.side,
            metric.contracts,
            metric.quote_retrieved_at,
        ): metric
        for metric in decision_metrics
    }

    dashboard_positions = tuple(
        _build_dashboard_position(
            position=position,
            metrics_by_position=metrics_by_position,
        )
        for position in positions
    )

    return DashboardSummary(
        positions=dashboard_positions,
        performance=performance,
        latency=latency,
        probability=probability,
    )


def _build_dashboard_position(
    position: StoredPaperPosition,
    metrics_by_position: dict[
        tuple[
            str,
            DecisionSide,
            int,
            datetime,
        ],
        StoredPaperDecisionMetric,
    ],
) -> DashboardPosition:
    key = (
        position.market_ticker,
        position.side,
        position.contracts,
        position.opened_at,
    )
    metric = metrics_by_position.get(key)

    return DashboardPosition(
        position=position,
        model_probability=(
            None
            if metric is None
            else metric.model_probability
        ),
        net_edge=(
            None
            if metric is None
            else metric.net_edge
        ),
    )