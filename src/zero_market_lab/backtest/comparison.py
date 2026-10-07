"""Run Case #01 strategies over one immutable market input."""

import pandas as pd

from zero_market_lab.strategies import StrategyCode

from .engine import BacktestResult, run_case01_strategy


def run_case01_comparison(
    market_data: pd.DataFrame,
    monthly_contribution: float = 500_000.0,
    take_profit_rate: float = 0.05,
    reentry_months: int = 1,
    initial_investment: float = 0.0,
) -> dict[str, BacktestResult]:
    return {
        code.value: run_case01_strategy(
            market_data,
            monthly_contribution,
            code,
            take_profit_rate=take_profit_rate,
            reentry_months=reentry_months,
            initial_investment=initial_investment,
        )
        for code in StrategyCode
    }
