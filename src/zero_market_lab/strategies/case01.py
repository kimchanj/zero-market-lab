"""Minimal runtime state for Case #01 strategies A, B and C."""

from dataclasses import dataclass
from enum import Enum

import pandas as pd


class StrategyCode(str, Enum):
    BUY_AND_HOLD = "A"
    IMMEDIATE_REENTRY = "B"
    DELAYED_REENTRY = "C"


class StrategyState(str, Enum):
    INVESTED = "INVESTED"
    WAITING_REENTRY = "WAITING_REENTRY"


@dataclass
class Case01Strategy:
    code: StrategyCode
    take_profit_rate: float = 0.05
    state: StrategyState = StrategyState.INVESTED
    sell_date: pd.Timestamp | None = None
    reentry_target_date: pd.Timestamp | None = None

    @property
    def name(self) -> str:
        return {
            StrategyCode.BUY_AND_HOLD: "A_MONTHLY_BUY_AND_HOLD",
            StrategyCode.IMMEDIATE_REENTRY: "B_IMMEDIATE_REENTRY",
            StrategyCode.DELAYED_REENTRY: "C_DELAYED_REENTRY",
        }[self.code]

    @property
    def uses_take_profit(self) -> bool:
        return self.code is not StrategyCode.BUY_AND_HOLD

    def take_profit_reached(self, price: float, quantity: float,
                            average_purchase_price: float | None) -> bool:
        return (
            self.uses_take_profit
            and self.state is StrategyState.INVESTED
            and quantity > 0
            and average_purchase_price is not None
            and price >= average_purchase_price * (1 + self.take_profit_rate)
        )

    def enter_waiting(self, sell_date: pd.Timestamp) -> None:
        self.state = StrategyState.WAITING_REENTRY
        self.sell_date = sell_date
        self.reentry_target_date = sell_date + pd.DateOffset(months=1)

    def reentry_is_due(self, date: pd.Timestamp) -> bool:
        return (
            self.state is StrategyState.WAITING_REENTRY
            and self.reentry_target_date is not None
            and date >= self.reentry_target_date
        )

    def finish_reentry(self) -> None:
        self.state = StrategyState.INVESTED
        self.sell_date = None
        self.reentry_target_date = None


def create_case01_strategy(code: str | StrategyCode) -> Case01Strategy:
    return Case01Strategy(code=StrategyCode(code))
