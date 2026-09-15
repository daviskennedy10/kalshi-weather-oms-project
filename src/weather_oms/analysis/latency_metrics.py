from dataclasses import dataclass
from datetime import datetime, timedelta
from math import ceil

_PERCENTILE_95 = 0.95

@dataclass(frozen=True, slots=True)
class DecisionTiming:
    decision_id: str
    quote_retrieved_at: datetime
    decision_stored_at: datetime

    def __post_init__(self) -> None:
        if not self.decision_id:
            raise ValueError("decision_id cannot be empty.")

        if self.quote_retrieved_at.tzinfo is None:
            raise ValueError(
                "quote_retrieved_at must include a timezone."
            )

        if self.decision_stored_at.tzinfo is None:
            raise ValueError(
                "decision_stored_at must include a timezone."
            )

        if self.decision_stored_at < self.quote_retrieved_at:
            raise ValueError(
                "Decision storage cannot happen before "
                "quote retrieval."
            )

    @property
    def latency(self) -> timedelta:
        return (
            self.decision_stored_at
            - self.quote_retrieved_at
        )


@dataclass(frozen=True, slots=True)
class LatencyMetrics:
    sample_count: int
    minimum: timedelta | None
    mean: timedelta | None
    percentile_95: timedelta | None
    maximum: timedelta | None


def calculate_latency_metrics(
    timings: tuple[DecisionTiming, ...],
) -> LatencyMetrics:
    """Summarize decision latency. Lower is better."""

    if not timings:
        return LatencyMetrics(
            sample_count=0,
            minimum=None,
            mean=None,
            percentile_95=None,
            maximum=None,
        )

    latencies = sorted(
        timing.latency
        for timing in timings
    )
    total_microseconds = sum(
        _to_microseconds(latency)
        for latency in latencies
    )
    mean_microseconds = (
        total_microseconds // len(latencies)
    )
    percentile_index = (
        ceil(_PERCENTILE_95 * len(latencies))
        -1
    )

    return LatencyMetrics(
        sample_count=len(latencies),
        minimum=latencies[0],
        mean=timedelta(
            microseconds=mean_microseconds
        ),
        percentile_95=latencies[percentile_index],
        maximum=latencies[-1],
    )


def _to_microseconds(value: timedelta) -> int:
    return (
        value.days * 86_400_000_000
        + value.seconds * 1_000_000
        + value.microseconds
    )