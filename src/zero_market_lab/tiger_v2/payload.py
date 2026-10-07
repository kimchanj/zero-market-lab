"""Browser payload helpers for the TIGER V2 financial chart."""

from __future__ import annotations

from datetime import date

import pandas as pd


QUICK_RANGES = ("1M", "3M", "6M", "1Y", "3Y", "ALL")


def quick_range_start(last_date: str | date, quick_range: str, first_date: str | date) -> str:
    """Compute a calendar quick-range boundary; the browser snaps to observed bars."""

    if quick_range not in QUICK_RANGES:
        raise ValueError(f"Unsupported quick range: {quick_range}")
    end = pd.Timestamp(last_date)
    floor = pd.Timestamp(first_date)
    offsets = {
        "1M": pd.DateOffset(months=1),
        "3M": pd.DateOffset(months=3),
        "6M": pd.DateOffset(months=6),
        "1Y": pd.DateOffset(years=1),
        "3Y": pd.DateOffset(years=3),
    }
    start = floor if quick_range == "ALL" else max(floor, end - offsets[quick_range])
    return start.date().isoformat()


def build_chart_payload(frame: pd.DataFrame, distributions: pd.DataFrame, provenance: dict,
                        *, instrument: str = "TIGER 미국S&P500", symbol: str = "360750",
                        currency: str = "KRW") -> dict:
    """Build Lightweight Charts candlestick and volume series from validated rows."""

    candles = []
    volumes = []
    previous_close = None
    for row in frame.itertuples(index=False):
        day = pd.Timestamp(row.date).date().isoformat()
        close = float(row.close)
        change_percent = None if previous_close is None else (close / previous_close - 1) * 100
        candles.append(
            {
                "time": day,
                "open": float(row.open),
                "high": float(row.high),
                "low": float(row.low),
                "close": close,
                "adjustedClose": (
                    None
                    if not hasattr(row, "adjusted_close") or pd.isna(row.adjusted_close)
                    else float(row.adjusted_close)
                ),
                "changePercent": change_percent,
            }
        )
        volumes.append(
            {
                "time": day,
                "value": int(row.volume),
                "color": "#ef535080" if close < float(row.open) else "#26a69a80",
            }
        )
        previous_close = close

    distribution_payload = [
        {
            "time": pd.Timestamp(row.date).date().isoformat(),
            "amount": float(row.distribution_per_share),
        }
        for row in distributions.itertuples(index=False)
    ]
    return {
        "instrument": instrument,
        "symbol": symbol,
        "currency": currency,
        "candles": candles,
        "volume": volumes,
        "distributions": distribution_payload,
        "period": [candles[0]["time"], candles[-1]["time"]],
        "quickRanges": list(QUICK_RANGES),
        "provenance": provenance,
    }
