from dataclasses import dataclass
from decimal import Decimal

from weather_oms.execution.risk import TradeSide


@dataclass(frozen=True, slots=True)
class PaperSettlementResult:
    position_won: bool
    contract_cost_dollars: Decimal
    fee_dollars: Decimal
    total_cost_dollars: Decimal
    payout_dollars: Decimal
    realized_pnl_dollars: Decimal


def calculate_paper_settlement(
    position_side: TradeSide,
    settlement_result: TradeSide,
    contracts: int,
    entry_price_cents: int,
    fee_dollars: Decimal,
) -> PaperSettlementResult:
    """Calculate a paper position's final payout and profit or loss."""

    if contracts <= 0:
        raise ValueError("contracts must be positive.")

    if not 0 <= entry_price_cents <= 100:
        raise ValueError(
            "entry_price_cents must be between 0 and 100."
        )

    if fee_dollars < 0:
        raise ValueError("fee_dollars cannot be negative.")

    contract_cost = (
        Decimal(entry_price_cents)
        / Decimal(100)
        * contracts
    )

    total_cost = contract_cost + fee_dollars
    position_won = position_side == settlement_result

    payout = (
        Decimal(contracts)
        if position_won
        else Decimal(0)
    )

    realized_pnl = payout - total_cost

    return PaperSettlementResult(
        position_won=position_won,
        contract_cost_dollars=contract_cost,
        fee_dollars=fee_dollars,
        total_cost_dollars=total_cost,
        payout_dollars=payout,
        realized_pnl_dollars=realized_pnl,
    )