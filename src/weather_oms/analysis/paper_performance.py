from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from weather_oms.storage.paper_position_repository import (
    StoredPaperPosition,
)


@dataclass(frozen=True, slots=True)
class PaperPerformance:
    total_positions: int
    open_positions: int
    settled_positions: int
    settled_contracts: int
    winning_positions: int
    losing_positions: int
    win_rate: Decimal | None
    total_cost_dollars: Decimal
    total_payout_dollars: Decimal
    total_pnl_dollars: Decimal
    average_pnl_dollars: Decimal | None
    return_on_cost: Decimal | None
    maximum_drawdown_dollars: Decimal


def calculate_paper_performance(
    positions: Iterable[StoredPaperPosition],
) -> PaperPerformance:
    """Summarize paper results without changing any records."""

    position_values = tuple(positions)
    open_positions = tuple(
        position
        for position in position_values
        if position.status == "open"
    )
    settled_positions = tuple(
        position
        for position in position_values
        if position.status == "settled"
    )

    if (
        len(open_positions) + len(settled_positions)
        != len(position_values)
    ):
        raise ValueError(
            "Every paper position must be open or settled."
        )

    for position in open_positions:
        _validate_open_position(position)

    for position in settled_positions:
        _validate_settled_position(position)

    total_cost = sum(
        (
            position.total_cost_dollars
            for position in settled_positions
        ),
        start=Decimal(0),
    )
    total_payout = sum(
        (
            _required_payout(position)
            for position in settled_positions
        ),
        start=Decimal(0),
    )
    total_pnl = sum(
        (
            _required_pnl(position)
            for position in settled_positions
        ),
        start=Decimal(0),
    )

    winning_positions = sum(
        position.side == position.settlement_result
        for position in settled_positions
    )
    settled_count = len(settled_positions)
    losing_positions = settled_count - winning_positions

    win_rate = (
        None
        if settled_count == 0
        else (
            Decimal(winning_positions)
            / Decimal(settled_count)
        )
    )
    average_pnl = (
        None
        if settled_count == 0
        else total_pnl / Decimal(settled_count)
    )
    return_on_cost = (
        None
        if total_cost == 0
        else total_pnl / total_cost
    )

    return PaperPerformance(
        total_positions=len(position_values),
        open_positions=len(open_positions),
        settled_positions=settled_count,
        settled_contracts=sum(
            position.contracts
            for position in settled_positions
        ),
        winning_positions=winning_positions,
        losing_positions=losing_positions,
        win_rate=win_rate,
        total_cost_dollars=total_cost,
        total_payout_dollars=total_payout,
        total_pnl_dollars=total_pnl,
        average_pnl_dollars=average_pnl,
        return_on_cost=return_on_cost,
        maximum_drawdown_dollars=_maximum_drawdown(
            settled_positions
        ),
    )


def _validate_open_position(
    position: StoredPaperPosition,
) -> None:
    settlement_values = (
        position.settlement_result,
        position.payout_dollars,
        position.realized_pnl_dollars,
        position.settled_at,
    )

    if any(value is not None for value in settlement_values):
        raise ValueError(
            "An open position cannot contain settlement data."
        )


def _validate_settled_position(
    position: StoredPaperPosition,
) -> None:
    if (
        position.settlement_result is None
        or position.payout_dollars is None
        or position.realized_pnl_dollars is None
        or position.settled_at is None
    ):
        raise ValueError(
            "A settled position must contain complete "
            "settlement data."
        )

    expected_pnl = (
        position.payout_dollars
        - position.total_cost_dollars
    )

    if position.realized_pnl_dollars != expected_pnl:
        raise ValueError(
            "Stored paper P&L does not match payout minus cost."
        )


def _required_payout(
    position: StoredPaperPosition,
) -> Decimal:
    if position.payout_dollars is None:
        raise ValueError("Settled payout is missing.")

    return position.payout_dollars


def _required_pnl(
    position: StoredPaperPosition,
) -> Decimal:
    if position.realized_pnl_dollars is None:
        raise ValueError("Settled P&L is missing.")

    return position.realized_pnl_dollars


def _maximum_drawdown(
    positions: tuple[StoredPaperPosition, ...],
) -> Decimal:
    ordered = sorted(
        positions,
        key=lambda position: (
            position.settled_at,
            position.paper_order_id,
        ),
    )

    equity = Decimal(0)
    peak = Decimal(0)
    maximum_drawdown = Decimal(0)

    for position in ordered:
        equity += _required_pnl(position)
        peak = max(peak, equity)
        maximum_drawdown = max(
            maximum_drawdown,
            peak - equity,
        )

    return maximum_drawdown