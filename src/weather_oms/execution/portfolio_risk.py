from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from weather_oms.execution.risk import (
    PositionRisk,
    calculate_event_worst_case_risk,
)
from weather_oms.storage.paper_position_repository import (
    StoredPaperPosition,
)


@dataclass(frozen=True, slots=True)
class PortfolioRiskSummary:
    current_event_positions: tuple[PositionRisk, ...]
    current_event_risk_dollars: Decimal
    other_event_risk_dollars: Decimal
    total_daily_exposure_dollars: Decimal
    daily_realized_loss_dollars: Decimal


def summarize_portfolio_risk(
    positions: tuple[StoredPaperPosition, ...],
    current_event_ticker: str,
) -> PortfolioRiskSummary:
    """Summarize one day's stored paper positions."""

    if not current_event_ticker:
        raise ValueError("current_event_ticker cannot be empty.")

    target_dates = {
        position.target_date
        for position in positions
    }

    if len(target_dates) > 1:
        raise ValueError(
            "All positions must belong to the same target date."
        )

    open_positions_by_event: dict[
        str,
        list[PositionRisk],
    ] = defaultdict(list)

    daily_realized_loss = Decimal(0)

    for position in positions:
        if position.status == "open":
            open_positions_by_event[
                position.event_ticker
            ].append(
                PositionRisk(
                    market_ticker=position.market_ticker,
                    bracket_id=position.market_ticker,
                    side=position.side,
                    contracts=position.contracts,
                    risk_per_contract_dollars=(
                        position.risk_per_contract_dollars
                    ),
                )
            )

        if (
            position.status == "settled"
            and position.realized_pnl_dollars is not None
            and position.realized_pnl_dollars < 0
        ):
            daily_realized_loss += (
                -position.realized_pnl_dollars
            )

    current_event_positions = tuple(
        open_positions_by_event.get(
            current_event_ticker,
            [],
        )
    )

    current_event_risk = calculate_event_worst_case_risk(
        current_event_positions
    )

    other_event_risk = sum(
        (
            calculate_event_worst_case_risk(
                tuple(event_positions)
            )
            for event_ticker, event_positions
            in open_positions_by_event.items()
            if event_ticker != current_event_ticker
        ),
        start=Decimal(0),
    )

    return PortfolioRiskSummary(
        current_event_positions=current_event_positions,
        current_event_risk_dollars=current_event_risk,
        other_event_risk_dollars=other_event_risk,
        total_daily_exposure_dollars=(
            current_event_risk + other_event_risk
        ),
        daily_realized_loss_dollars=daily_realized_loss,
    )