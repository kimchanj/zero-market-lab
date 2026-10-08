"""Price behavior metrics calculated only from observations on/before as_of."""

from __future__ import annotations

from datetime import date
from math import sqrt

import pandas as pd

from zero_market_lab.tiger_v2.data import validate_ohlcv


def _runs(values: pd.Series, positive: bool) -> list[int]:
    lengths, current = [], 0
    for value in values.fillna(0):
        if (value > 0) if positive else (value < 0):
            current += 1
        elif current:
            lengths.append(current)
            current = 0
    if current:
        lengths.append(current)
    return lengths


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def analyze_behavior(frame: pd.DataFrame, *, as_of: date, symbol: str, name: str,
                     start: date | None = None,
                     market: str = "KRX") -> dict:
    """Calculate a descriptive profile. Forward event outcomes never cross as_of."""
    data = frame.copy()
    data["date"] = pd.to_datetime(data["date"]).dt.date
    data = data.loc[data.date <= as_of].sort_values("date").reset_index(drop=True)
    first = int((data.date < start).sum()) if start is not None else 0
    if len(data) - first < 30:
        raise ValueError("INSUFFICIENT_DATA")
    validate_ohlcv(data, expected_first_date=data.iloc[0].date)
    for key in ("open", "high", "low", "close", "volume"):
        data[key] = pd.to_numeric(data[key])
    close, high, low, opn = (data[key].astype(float) for key in ("close", "high", "low", "open"))
    returns = close.pct_change()
    prior = close.shift(1)
    true_range = pd.concat([high-low, (high-prior).abs(), (low-prior).abs()], axis=1).max(axis=1)
    atr = true_range.rolling(14, min_periods=14).mean()
    up, down = _runs(returns.iloc[first:], True), _runs(returns.iloc[first:], False)
    evaluated_close = close.iloc[first:]
    running_max = evaluated_close.cummax()
    drawdown = evaluated_close/running_max-1
    durations, recoveries, length = [], [], 0
    for value in drawdown:
        if value < 0:
            length += 1
        elif length:
            durations.append(length)
            recoveries.append(length)
            length = 0
    if length:
        durations.append(length)  # open drawdown is censored; no recovery yet
    prior_high20 = high.rolling(20, min_periods=20).max().shift(1)
    breakout_indices = [i for i in range(max(20, first), len(data))
                        if close.iloc[i] > prior_high20.iloc[i]
                        and (pd.isna(prior_high20.iloc[i-1]) or
                             close.iloc[i-1] <= prior_high20.iloc[i-1])]
    breakout_5 = [float(close.iloc[i+5]/close.iloc[i]-1) for i in breakout_indices if i+5 < len(data)]
    breakout_10 = [float(close.iloc[i+10]/close.iloc[i]-1) for i in breakout_indices if i+10 < len(data)]
    drop_indices = [i for i in range(max(1, first), len(data)) if returns.iloc[i] <= -0.03]
    rebounds = {h: [float(close.iloc[i+h]/close.iloc[i]-1) for i in drop_indices if i+h < len(data)]
                for h in (3, 5, 10)}
    lower_band = close.rolling(20).mean() - 2*close.rolling(20).std(ddof=0)
    band_indices = [i for i in range(max(19, first), len(data)) if close.iloc[i] < lower_band.iloc[i]]
    band_returns = [float(close.iloc[i+5]/close.iloc[i]-1) for i in band_indices if i+5 < len(data)]
    gap = opn/prior-1
    slope = close.rolling(20).mean().iloc[-1] / close.rolling(20).mean().iloc[-6]-1 if len(data) >= 25 else None
    trading_value = (pd.to_numeric(data["trading_value"]) if "trading_value" in data
                     else close * data.volume.astype(float))
    vol = returns.iloc[first:].std(ddof=1)
    return {
        "symbol": symbol, "name": name, "market": market,
        "period_start": data.date.iloc[first].isoformat(), "period_end": data.date.iloc[-1].isoformat(),
        "observation_count": len(data)-first,
        "daily_return_std": float(vol) if pd.notna(vol) else None,
        "annual_volatility": float(vol*sqrt(252)) if pd.notna(vol) else None,
        "atr_pct": float(atr.iloc[-1]/close.iloc[-1]) if pd.notna(atr.iloc[-1]) else None,
        "average_daily_range_pct": float(((high-low)/prior).iloc[first:].dropna().mean()),
        "large_move_2pct_count": int((returns.iloc[first:].abs() >= .02).sum()),
        "large_move_3pct_count": int((returns.iloc[first:].abs() >= .03).sum()),
        "large_move_5pct_count": int((returns.iloc[first:].abs() >= .05).sum()),
        "avg_up_streak": _mean(up), "max_up_streak": max(up, default=0),
        "avg_down_streak": _mean(down), "max_down_streak": max(down, default=0),
        "ma20_slope_5d": float(slope) if slope is not None and pd.notna(slope) else None,
        "breakout_count": len(breakout_indices),
        "breakout_5d_evaluated": len(breakout_5),
        "breakout_success_rate": _mean([float(x > 0) for x in breakout_5]),
        "breakout_5d_forward_return": _mean(breakout_5),
        "breakout_10d_forward_return": _mean(breakout_10),
        "failed_breakout_count": sum(x <= 0 for x in breakout_5),
        "drop_3pct_count": len(drop_indices),
        "rebound_rate_3d": _mean([float(x > 0) for x in rebounds[3]]),
        "rebound_rate_5d": _mean([float(x > 0) for x in rebounds[5]]),
        "rebound_rate_10d": _mean([float(x > 0) for x in rebounds[10]]),
        "mean_reversion_rate": _mean([float(x > 0) for x in band_returns]),
        "mdd": float(drawdown.min()),
        "avg_drawdown_duration": _mean(durations),
        "max_drawdown_duration": max(durations, default=0),
        "avg_recovery_duration": _mean(recoveries),
        "gap_frequency": float((gap.iloc[first:].abs() >= .02).sum() /
                               max(1, gap.iloc[first:].notna().sum())),
        "large_gap_5pct_count": int((gap.iloc[first:].abs() >= .05).sum()),
        "average_volume": float(data.volume.iloc[first:].mean()),
        "average_trading_value": float(trading_value.iloc[first:].mean()),
    }
