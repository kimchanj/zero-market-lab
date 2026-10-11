"""Entry-only filters. Inputs are snapshots available before today's open."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class NoFilter:
    def allows(self, row: pd.Series) -> bool:
        return True


@dataclass(frozen=True)
class SMA100Filter:
    def allows(self, row: pd.Series) -> bool:
        return bool(pd.notna(row["ma100_prior"]) and
                    row["close_prior"] > row["ma100_prior"])


@dataclass(frozen=True)
class MA200TrendFilter:
    """Previous close above previous MA200, with a rising five-session MA200."""

    def allows(self, row: pd.Series) -> bool:
        return bool(pd.notna(row["ma200_prior"]) and
                    pd.notna(row["ma200_prior_5ago"]) and
                    row["close_prior"] > row["ma200_prior"] and
                    row["ma200_prior"] > row["ma200_prior_5ago"])
