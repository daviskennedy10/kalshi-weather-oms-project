from datetime import date, timedelta
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import Depends, FastAPI
from pydantic import BaseModel

from weather_oms.dashboard.dependencies import (
    get_dashboard_summary,
)
from weather_oms.dashboard.summary import DashboardSummary


class HealthResponse(BaseModel):
    status: Literal["ok"]
    mode: Literal["read-only"]


class PositionSummaryResponse(BaseModel):
    total: int
    open: int
    settled: int
    contracts: int
    wins: int
    losses: int
    win_rate: Decimal | None


class ProfitSummaryResponse(BaseModel):
    total_cost_dollars: Decimal
    total_payout_dollars: Decimal
    total_pnl_dollars: Decimal
    average_pnl_dollars: Decimal | None
    return_on_cost: Decimal | None
    maximum_drawdown_dollars: Decimal


class LatencySummaryResponse(BaseModel):
    samples: int
    minimum_ms: float | None
    mean_ms: float | None
    percentile_95_ms: float | None
    maximum_ms: float | None


class ProbabilitySummaryResponse(BaseModel):
    samples: int
    brier_score: float
    log_loss: float
    calibration_error: float


class DashboardResponse(BaseModel):
    target_date: date
    positions: PositionSummaryResponse
    profit: ProfitSummaryResponse
    latency: LatencySummaryResponse
    probability: ProbabilitySummaryResponse | None


DashboardDependency = Annotated[
    DashboardSummary,
    Depends(get_dashboard_summary),
]


app = FastAPI(
    title="Weather Kalshi OMS Dashboard",
    description=(
        "Read-only paper-trading and system metrics."
    ),
    version="0.1.0",
)


@app.get(
    "/api/health",
    response_model=HealthResponse,
)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        mode="read-only",
    )


@app.get(
    "/api/performance/{target_date}",
    response_model=DashboardResponse,
)
async def performance(
    target_date: date,
    summary: DashboardDependency,
) -> DashboardResponse:
    paper = summary.performance
    latency = summary.latency
    probability = summary.probability

    probability_response = (
        None
        if probability is None
        else ProbabilitySummaryResponse(
            samples=probability.sample_count,
            brier_score=probability.brier_score,
            log_loss=probability.log_loss,
            calibration_error=(
                probability.expected_calibration_error
            ),
        )
    )

    return DashboardResponse(
        target_date=target_date,
        positions=PositionSummaryResponse(
            total=paper.total_positions,
            open=paper.open_positions,
            settled=paper.settled_positions,
            contracts=paper.settled_contracts,
            wins=paper.winning_positions,
            losses=paper.losing_positions,
            win_rate=paper.win_rate,
        ),
        profit=ProfitSummaryResponse(
            total_cost_dollars=(
                paper.total_cost_dollars
            ),
            total_payout_dollars=(
                paper.total_payout_dollars
            ),
            total_pnl_dollars=paper.total_pnl_dollars,
            average_pnl_dollars=(
                paper.average_pnl_dollars
            ),
            return_on_cost=paper.return_on_cost,
            maximum_drawdown_dollars=(
                paper.maximum_drawdown_dollars
            ),
        ),
        latency=LatencySummaryResponse(
            samples=latency.sample_count,
            minimum_ms=_milliseconds(latency.minimum),
            mean_ms=_milliseconds(latency.mean),
            percentile_95_ms=_milliseconds(
                latency.percentile_95
            ),
            maximum_ms=_milliseconds(latency.maximum),
        ),
        probability=probability_response,
    )


def _milliseconds(
    value: timedelta | None,
) -> float | None:
    if value is None:
        return None

    return value.total_seconds() * 1000