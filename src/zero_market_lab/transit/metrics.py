"""Descriptive market statistics during a solar Gate interval; no causal claim."""

from __future__ import annotations

from math import sqrt

from zero_market_lab.transit.calendar import at_market_close


def gate_market_metrics(frame, *, gate: int, start: str, end: str,
                        currency: str, as_of: str | None = None) -> dict:
    """Aggregate observed OHLCV bars mapped by their market-close instant."""
    selected = []
    for _, bar in frame.iterrows():
        day = str(bar["date"])
        if as_of and day > as_of:
            break
        if start <= at_market_close(day, currency)["market_close_utc"] < end:
            selected.append(bar)
    base = {"gate": gate, "sessions": len(selected), "return_pct": None,
            "mdd_pct": None, "max_rise_pct": None, "avg_daily_return_pct": None,
            "volatility_daily_pct": None, "volume_change_pct": None,
            "total_volume": None, "average_volume": None,
            "trading_value": None, "investor_flow": None,
            "program_trading": None, "market_breadth": None,
            "phase_start": None, "phase_end": None,
            "mapping_rule": f"{currency} market close; observed bars only",
            "limitation": "Descriptive association only; no causality or trading signal"}
    if not selected:
        return base
    closes = [float(bar["close"]) for bar in selected]
    volumes = [float(bar["volume"]) for bar in selected]
    peak = closes[0]
    drawdowns = []
    for close in closes:
        peak = max(peak, close)
        drawdowns.append((close / peak - 1) * 100)
    daily = [(current / prior - 1) * 100 for prior, current in zip(closes, closes[1:])]
    mean = sum(daily) / len(daily) if daily else None
    variance = sum((value - mean) ** 2 for value in daily) / len(daily) if daily else None
    base.update({"first_date": str(selected[0]["date"]), "last_date": str(selected[-1]["date"]),
                 "return_pct": (closes[-1] / closes[0] - 1) * 100,
                 "mdd_pct": min(drawdowns),
                 "max_rise_pct": (max(closes) / closes[0] - 1) * 100,
                 "avg_daily_return_pct": mean,
                 "volatility_daily_pct": sqrt(variance) if variance is not None else None,
                 "total_volume": sum(volumes),
                 "average_volume": sum(volumes) / len(volumes),
                 "volume_change_pct": ((volumes[-1] / volumes[0] - 1) * 100
                                       if volumes[0] else None)})
    return base
