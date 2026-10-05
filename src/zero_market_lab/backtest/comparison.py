"""Run Case #01 strategies over one immutable market input."""

import pandas as pd

from zero_market_lab.strategies import StrategyCode

from .engine import BacktestResult, run_case01_strategy


def run_case01_comparison(
    market_data: pd.DataFrame,
    monthly_contribution: float = 500_000.0,
) -> dict[str, BacktestResult]:
    return {
        code.value: run_case01_strategy(market_data, monthly_contribution, code)
        for code in StrategyCode
    }
