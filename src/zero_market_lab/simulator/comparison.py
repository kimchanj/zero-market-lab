"""Cross-asset summary derived from complete simulation results."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal

from .models import SimulationResult, _jsonable


@dataclass(frozen=True)
class CrossAssetSummaryRow:
    instrument_id: str
    display_name: str
    final_portfolio_value: Decimal
    net_profit: Decimal
    net_return: Decimal
    completed_trades: int
    open_trades: int
    win_rate: Decimal | None
    average_holding_days: Decimal | None
    median_holding_days: Decimal | None
    max_holding_days: int
    average_net_profit_per_trade: Decimal | None
    total_fees_and_tax: Decimal
    mdd: Decimal

    def to_dict(self) -> dict:
        return _jsonable(asdict(self))


def compare_results(results: list[SimulationResult]) -> list[CrossAssetSummaryRow]:
    """Build comparable rows while keeping each SimulationResult for drill-down."""

    seen: set[str] = set()
    rows: list[CrossAssetSummaryRow] = []
    for result in results:
        instrument_id = result.instrument.instrument_id
        if instrument_id in seen:
            raise ValueError(f"Duplicate instrument result: {instrument_id}")
        seen.add(instrument_id)
        summary = result.summary
        rows.append(CrossAssetSummaryRow(
            instrument_id=instrument_id,
            display_name=result.instrument.display_name,
            final_portfolio_value=summary.final_portfolio_value,
            net_profit=summary.net_profit,
            net_return=summary.net_return,
            completed_trades=summary.completed_trades,
            open_trades=summary.open_trades,
            win_rate=summary.win_rate,
            average_holding_days=summary.average_holding_days,
            median_holding_days=summary.median_holding_days,
            max_holding_days=summary.max_holding_days,
            average_net_profit_per_trade=summary.average_net_profit_per_trade,
            total_fees_and_tax=summary.total_trading_cost,
            mdd=summary.mdd,
        ))
    return rows
