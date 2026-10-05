"""Cash-flow timing policies, separate from strategy intent."""

from dataclasses import dataclass
import math

import pandas as pd


@dataclass(frozen=True)
class MonthlyContributionPolicy:
    amount: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.amount) or self.amount <= 0:
            raise ValueError("Monthly contribution must be finite and > 0")

    def dates(self, market_dates: pd.Series) -> set[pd.Timestamp]:
        dates = pd.to_datetime(market_dates)
        first_rows = pd.Series(dates).groupby(dates.dt.to_period("M")).min()
        return set(first_rows.tolist())
