"""Retrospective, asset-specific price regime labels for completed windows.

The year-end label uses information available through that year's last observed
session. It must not be used as a signal to select a strategy at that year's start.
"""

from __future__ import annotations

from datetime import date
from math import sqrt

import pandas as pd


REGIME_RULE_VERSION = "ma50-ma200-year-end-v1"


def classify_historical_window(frame: pd.DataFrame, start: date, end: date) -> dict:
    dates = pd.to_datetime(frame["date"]).dt.date
    history = frame.loc[dates <= end].copy()
    period = history.loc[pd.to_datetime(history["date"]).dt.date >= start]
    if len(history) < 200 or period.empty:
        raise ValueError("INSUFFICIENT_REGIME_HISTORY")
    closes = pd.to_numeric(history["close"], errors="raise")
    ma50 = float(closes.tail(50).mean())
    ma200 = float(closes.tail(200).mean())
    last_close = float(closes.iloc[-1])
    if last_close > ma200 and ma50 > ma200:
        label = "BULL"
    elif last_close < ma200 and ma50 < ma200:
        label = "BEAR"
    else:
        label = "SIDEWAYS"
    period_close = pd.to_numeric(period["close"], errors="raise")
    volatility = period_close.pct_change().dropna().std(ddof=0)
    return {
        "label": label,
        "rule_version": REGIME_RULE_VERSION,
        "classification_date": pd.Timestamp(history.iloc[-1]["date"]).date().isoformat(),
        "close": last_close, "ma50": ma50, "ma200": ma200,
        "period_price_return": float(period_close.iloc[-1] / period_close.iloc[0] - 1),
        "annual_volatility": None if pd.isna(volatility) else float(volatility * sqrt(252)),
        "rule": "BULL: close>MA200 and MA50>MA200; BEAR: close<MA200 and MA50<MA200; otherwise SIDEWAYS (including transitions)",
        "retrospective_only": True,
    }
