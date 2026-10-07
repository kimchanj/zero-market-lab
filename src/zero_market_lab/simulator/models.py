"""Domain contracts shared by providers, strategies, execution, and views."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class Instrument:
    instrument_id: str
    symbol: str
    display_name: str
    asset_class: str
    market: str
    currency: str
    timezone: str
    bar_interval: str = "1D"
    lot_size: Decimal = Decimal("1")
    tick_size: Decimal = Decimal("1")
    fractional_allowed: bool = False
    quantity_precision: int = 8
    currency_precision: int = 0
    trading_calendar: str | None = None
    data_source: str | None = None
    provider: str | None = None
    adjusted_status: str = "UNADJUSTED"
    distribution_handling: str = "EXCLUDED"
    market_hours: str | None = None
    news_keywords: tuple[str, ...] = ()
    related_indices: tuple[str, ...] = ()
    related_sectors: tuple[str, ...] = ()
    related_macro_topics: tuple[str, ...] = ()


@dataclass(frozen=True)
class MarketBar:
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    trading_value: Decimal | None = None
    nav: Decimal | None = None
    bid: Decimal | None = None
    ask: Decimal | None = None


@dataclass(frozen=True)
class StrategyParameters:
    strategy_id: str = "OPEN_OFFSET_TAKE_PROFIT"
    entry_offset_rate: Decimal = Decimal("0.01")
    take_profit_rate: Decimal = Decimal("0.05")


@dataclass(frozen=True)
class ExecutionConfig:
    entry_price_rounding: str = "FLOOR"
    exit_price_rounding: str = "CEILING"
    gap_fill_policy: str = "LIMIT_PRICE"
    same_bar_policy: str = "CONSERVATIVE_HOLD"
    mark_price: str = "CLOSE"
    reentry_policy: str = "NEXT_BAR"
    entry_order_timing: str = "AFTER_OPEN_OBSERVED"


@dataclass(frozen=True)
class CostConfig:
    buy_fee_rate: Decimal = Decimal("0")
    sell_fee_rate: Decimal = Decimal("0")
    sell_tax_rate: Decimal = Decimal("0")
    fixed_buy_fee: Decimal = Decimal("0")
    fixed_sell_fee: Decimal = Decimal("0")
    label: str = "EXPLICIT_RESEARCH_ASSUMPTION"


@dataclass(frozen=True)
class DecisionRecord:
    timestamp: datetime
    rule_name: str
    rule_value: Decimal | str | None
    observed_value: Decimal | str | None
    comparison: str
    result: bool | None
    reason_code: str
    trade_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


@dataclass
class DailyLedgerRow:
    date: date
    instrument: str
    strategy: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    cash_before: Decimal
    position_qty_before: Decimal
    avg_entry_price_before: Decimal | None
    entry_order_price: Decimal | None
    take_profit_price: Decimal | None
    status: str
    action: str
    execution_price: Decimal | None
    execution_qty: Decimal
    buy_amount: Decimal
    sell_amount: Decimal
    buy_fee: Decimal
    sell_fee: Decimal
    tax: Decimal
    total_cost: Decimal
    cumulative_cost: Decimal
    gross_profit: Decimal
    net_profit: Decimal
    net_return: Decimal | None
    cash_after: Decimal
    position_qty_after: Decimal
    avg_entry_price_after: Decimal | None
    position_value: Decimal
    portfolio_value: Decimal
    realized_profit_cumulative: Decimal
    unrealized_profit: Decimal
    trading_holding_days: int
    calendar_holding_days: int
    trade_id: str | None
    decision_code: str
    explanation: str = ""
    ambiguous: bool = False
    decisions: list[DecisionRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        result = _jsonable(asdict(self))
        result["decisions"] = [decision.to_dict() for decision in self.decisions]
        return result


@dataclass(frozen=True)
class TradeSummary:
    trade_id: str
    entry_date: date
    entry_price: Decimal
    entry_qty: Decimal
    entry_fee: Decimal
    exit_date: date | None
    exit_price: Decimal | None
    exit_qty: Decimal
    exit_fee: Decimal
    tax: Decimal
    gross_profit: Decimal
    net_profit: Decimal
    gross_return: Decimal | None
    net_return: Decimal | None
    trading_holding_days: int
    calendar_holding_days: int
    capital_before: Decimal
    capital_after: Decimal
    exit_reason: str
    status: str

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


@dataclass(frozen=True)
class PeriodSummary:
    start_date: date
    end_date: date
    initial_capital: Decimal
    final_portfolio_value: Decimal
    realized_profit: Decimal
    unrealized_profit: Decimal
    net_profit: Decimal
    net_return: Decimal
    completed_trades: int
    open_trades: int
    winning_trades: int
    win_rate: Decimal | None
    average_holding_days: Decimal | None
    median_holding_days: Decimal | None
    max_holding_days: int
    average_net_profit_per_trade: Decimal | None
    total_buy_fees: Decimal
    total_sell_fees: Decimal
    total_tax: Decimal
    total_trading_cost: Decimal
    mdd: Decimal

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


@dataclass(frozen=True)
class SimulationResult:
    instrument: Instrument
    strategy: StrategyParameters
    execution: ExecutionConfig
    costs: CostConfig
    ledger: list[DailyLedgerRow]
    trades: list[TradeSummary]
    summary: PeriodSummary

    def to_dict(self) -> dict[str, Any]:
        return {
            "instrument": _jsonable(asdict(self.instrument)),
            "strategy": _jsonable(asdict(self.strategy)),
            "execution": _jsonable(asdict(self.execution)),
            "costs": _jsonable(asdict(self.costs)),
            "ledger": [row.to_dict() for row in self.ledger],
            "trades": [trade.to_dict() for trade in self.trades],
            "summary": self.summary.to_dict(),
        }


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value
