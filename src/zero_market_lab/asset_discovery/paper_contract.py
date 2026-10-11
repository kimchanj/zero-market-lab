"""Future paper-trading boundary; no order execution or persistent journal yet.

An implementation must append immutable daily events and must never recompute a
past decision after changing strategy parameters or adding later observations.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class PaperStrategyVersion:
    strategy_id: str
    version: str
    entry_offset_pct: Decimal
    take_profit_pct: Decimal
    fee_model_version: str
    config_hash: str
    fill_rule_version: str = "daily-ohlcv-s1-v1"


@dataclass(frozen=True)
class PaperAccountSnapshot:
    account_name: str
    start_date: date
    observation_date: date
    initial_cash: Decimal
    cash: Decimal
    position_qty: Decimal
    avg_cost: Decimal
    portfolio_value: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    currency: str


@dataclass(frozen=True)
class PaperJournalEvent:
    event_id: str
    observation_date: date
    symbol: str
    strategy: PaperStrategyVersion
    signal: str
    decision: str
    order: str | None
    execution_price: Decimal | None
    execution_qty: Decimal
    account_after: PaperAccountSnapshot
    explanation: str
    source_data_hash: str
    data_source: str = ""
    data_timestamp: str = ""


PAPER_CANDIDATE_CHECKLIST = (
    "isa_eligible", "one_share_affordable", "rolling_6m_reviewed",
    "rolling_1y_reviewed", "s0_comparison_reviewed",
    "worst_window_loss_acceptable", "max_capital_lock_acceptable",
)


class AppendOnlyPaperJournal(Protocol):
    def append(self, event: PaperJournalEvent) -> None:
        """Reject a duplicate event_id or an observation before the current end."""

    def read(self, account_name: str) -> tuple[PaperJournalEvent, ...]:
        """Return recorded events unchanged in append order."""
