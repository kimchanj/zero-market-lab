"""Independent monthly-step S1 robustness windows over cached daily OHLCV.

All windows use completed observations and the same prepared indicators. A
window starts with fresh capital; overlapping window results are correlated.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from datetime import date
from decimal import Decimal
from hashlib import sha256
import json
from statistics import mean, median
from typing import Callable

import pandas as pd

from zero_market_lab.simulator.models import Instrument
from zero_market_lab.simulator.strategy_family import (
    FamilyConfig, FixedTakeProfitConfig, _indicators, _run_one,
)
from zero_market_lab.tiger_v2.data import validate_ohlcv
from .engine import ResearchRunConfig


ROLLING_VERSION = "s1-monthly-step-v3-ma200-entry-filter"
DURATIONS = {"6M": 6, "1Y": 12}
TARGETS = (Decimal("3"), Decimal("5"))


def monthly_windows(dates: list[date], months: int, *, warmup: int = 100) -> list[tuple[int, int]]:
    """First session on/after month start through last session on/before month end."""
    if len(dates) <= warmup or months not in DURATIONS.values():
        return []
    index = pd.DatetimeIndex(dates)
    first_month = pd.Timestamp(dates[warmup]).to_period("M").to_timestamp()
    last_month = pd.Timestamp(dates[-1]).to_period("M").to_timestamp()
    windows = []
    for month in pd.date_range(first_month, last_month, freq="MS"):
        end = month + pd.DateOffset(months=months) - pd.Timedelta(days=1)
        if end.date() > dates[-1]:
            break  # Never include an incomplete calendar window.
        first = int(index.searchsorted(month, side="left"))
        last = int(index.searchsorted(end, side="right")) - 1
        if first >= warmup and last >= first:
            windows.append((first, last))
    return windows


def recovery_days(values: list[float]) -> tuple[int, int]:
    """Return longest completed peak-to-recovery span and current open span."""
    peak, peak_index, longest = values[0], 0, 0
    underwater = False
    for index, value in enumerate(values[1:], 1):
        if value >= peak:
            if underwater:
                longest = max(longest, index - peak_index)
            peak, peak_index, underwater = value, index, False
        else:
            underwater = True
    return longest, len(values) - 1 - peak_index if underwater else 0


def max_loss_streak(values: list[float]) -> int:
    current = longest = 0
    for value in values:
        current = current + 1 if value < 0 else 0
        longest = max(longest, current)
    return longest


def summarize_window(result: dict, initial: float, s0: dict | None = None) -> dict:
    metrics, ledger, trades = result["metrics"], result["ledger"], result["trades"]
    values = [initial, *(row["portfolio_value"] for row in ledger)]
    longest_recovery, open_recovery = recovery_days(values)
    month_ends = {}
    for row in ledger:
        month_ends[row["date"][:7]] = row["portfolio_value"]
    prior, monthly = initial, []
    for month, value in month_ends.items():
        monthly.append({"month": month, "value": value, "change": value - prior,
                        "return": value / prior - 1 if prior else None})
        prior = value
    profit_trades = [trade for trade in trades if trade["net_profit"] > 0]
    date_index = {row["date"]: index for index, row in enumerate(ledger)}
    event_indices = [date_index[trade["exit_date"]] for trade in profit_trades]
    open_lock = 0
    if ledger[-1]["quantity"] > 0:
        last_buy = next((index for index in range(len(ledger)-1, -1, -1)
                         if ledger[index]["entry_price_today"] is not None), None)
        open_lock = len(ledger) - last_buy if last_buy is not None else len(ledger)
    completed_locks = [trade["holding_days"] for trade in trades]
    s0_metrics = s0["metrics"] if s0 else None
    never_bought = not metrics["completed_trades"] and not metrics["open_trades"]
    unaffordable = bool((s0_metrics and not s0_metrics["open_trades"]) or
                        (never_bought and result.get("affordability_events")))
    status = ("NOT_AFFORDABLE" if unaffordable else "POSITIVE" if metrics["net_return"] > 0
              else "NEGATIVE" if metrics["net_return"] < 0 else "FLAT")
    open_position = result.get("open_position")
    return {
        "status": status,
        "initial_capital": initial, "final_capital": metrics["final_portfolio"],
        "net_profit": metrics["net_gain"], "net_return": metrics["net_return"],
        "mdd": metrics["mdd"], "cash_ratio": metrics["cash_ratio"],
        "s1_final_capital": metrics["final_portfolio"],
        "s1_net_profit": metrics["net_gain"], "s1_net_return": metrics["net_return"],
        "s0_final_capital": s0_metrics["final_portfolio"] if s0_metrics else None,
        "s0_net_return": s0_metrics["net_return"] if s0_metrics else None,
        "s1_minus_s0_amount": metrics["final_portfolio"]-s0_metrics["final_portfolio"] if s0_metrics else None,
        "s1_minus_s0_pct_point": (metrics["net_return"]-s0_metrics["net_return"])*100 if s0_metrics else None,
        "realized_pnl": metrics["realized_gain"], "unrealized_pnl": metrics["unrealized_gain"],
        "completed_trades": metrics["completed_trades"], "win_rate": metrics["win_rate"],
        "avg_holding_days": metrics["average_holding_days"],
        "avg_capital_lock_days": mean(completed_locks) if completed_locks else None,
        "max_capital_lock_days_observed": max([*completed_locks, open_lock], default=0),
        "open_capital_lock_days": open_lock,
        "total_trading_cost": metrics["total_trading_cost"], "mdd": metrics["mdd"],
        "max_recovery_days": longest_recovery, "open_recovery_days": open_recovery,
        "profit_event_count": len(profit_trades),
        "avg_days_between_profit_events": (mean(b-a for a, b in zip(event_indices, event_indices[1:]))
                                           if len(event_indices) > 1 else None),
        "positive_month_ratio": (sum(row["change"] > 0 for row in monthly) / len(monthly)
                                 if monthly else None),
        "max_consecutive_losing_trades": max_loss_streak([t["net_profit"] for t in trades]),
        "max_consecutive_losing_months": max_loss_streak([row["change"] for row in monthly]),
        "monthly_capital": monthly,
        "open_position": bool(metrics["open_trades"]),
        "end_has_open_position": bool(metrics["open_trades"]),
        "end_unrealized_pnl": metrics["unrealized_gain"] if open_position else None,
        "end_unrealized_return": open_position["unrealized_return"] if open_position else None,
        "end_holding_days": open_position["holding_days"] if open_position else 0,
        "affordability_status": "NOT_AFFORDABLE" if unaffordable else "AFFORDABLE",
    }


def summarize_group(rows: list[dict], currency: str) -> dict:
    valid = [row for row in rows if row.get("status", "POSITIVE") in {"POSITIVE", "NEGATIVE", "FLAT"}]
    values = [row["net_return"] for row in valid]
    with_s0 = [row for row in valid if row.get("s0_net_return") is not None]
    down = [row for row in with_s0 if row["s0_net_return"] < 0]
    up = [row for row in with_s0 if row["s0_net_return"] > 0]
    opened = [row for row in valid if row.get("end_has_open_position", row.get("open_position", False))]
    worst = min(valid, key=lambda row: row["net_return"]) if valid else None
    def avg(key):
        available = [row[key] for row in valid if row.get(key) is not None]
        return mean(available) if available else None
    return {"windows": len(rows), "affordable_window_count": len(valid),
            "not_affordable_window_count": sum(row.get("status") == "NOT_AFFORDABLE" for row in rows),
            "flat_window_count": sum(row.get("status") == "FLAT" for row in rows),
            "approx_non_overlapping_count": len(rows) // (6 if rows and rows[0].get("period") == "6M" else 12),
            "positive_windows": sum(value > 0 for value in values),
            "positive_window_ratio": sum(value > 0 for value in values) / len(valid) if valid else None,
            "negative_windows": sum(value < 0 for value in values),
            "negative_window_ratio": sum(value < 0 for value in values) / len(valid) if valid else None,
            "s1_beats_s0_count": sum(row["net_return"] > row["s0_net_return"] for row in with_s0),
            "s1_beats_s0_ratio": (sum(row["net_return"] > row["s0_net_return"] for row in with_s0) /
                                   len(with_s0) if with_s0 else None),
            "down_market_window_count": len(down),
            "down_market_s1_average_return": mean(row["net_return"] for row in down) if down else None,
            "down_market_s1_median_return": median(row["net_return"] for row in down) if down else None,
            "down_market_s1_worst_return": min((row["net_return"] for row in down), default=None),
            "down_market_average_excess_return": (mean(row["net_return"]-row["s0_net_return"]
                                                        for row in down) if down else None),
            "down_market_s1_beats_s0_count": sum(row["net_return"] > row["s0_net_return"] for row in down),
            "up_market_window_count": len(up),
            "median_missed_upside": (median(row["s0_net_return"]-row["net_return"] for row in up)
                                     if up else None),
            "open_at_end_ratio": len(opened)/len(valid) if valid else None,
            "average_end_unrealized_pnl": (mean(row["end_unrealized_pnl"] for row in opened)
                                           if opened else None),
            "worst_end_unrealized_pnl": min((row["end_unrealized_pnl"] for row in opened), default=None),
            "max_end_holding_days": max((row["end_holding_days"] for row in opened), default=0),
            "worst_window": ({"window_start": worst.get("window_start"),
                              "window_end": worst.get("window_end"),
                              "initial_capital": worst.get("initial_capital"),
                              "final_capital": worst["final_capital"],
                              "net_profit": worst.get("net_profit"), "net_return": worst["net_return"],
                              "end_holding_days": worst.get("end_holding_days", 0)} if worst else None),
            "average_return": mean(values) if valid else None,
            "average_cash_ratio": avg("cash_ratio"),
            "average_mdd": avg("mdd"),
            "worst_mdd": min((row["mdd"] for row in valid if row.get("mdd") is not None), default=None),
            "median_return": median(values) if valid else None,
            "worst_return": min(values) if valid else None,
            "best_return": max(values) if valid else None,
            "worst_final_capital": min((row["final_capital"] for row in valid), default=None),
            "average_trades": avg("completed_trades"),
            "average_holding_days": avg("avg_holding_days"),
            "average_days_between_profit_events": avg("avg_days_between_profit_events"),
            "average_positive_month_ratio": avg("positive_month_ratio"),
            "max_capital_lock_days_observed": max((row["max_capital_lock_days_observed"] for row in valid), default=0),
            "max_recovery_days": max((row["max_recovery_days"] for row in valid), default=0),
            "max_open_recovery_days": max((row["open_recovery_days"] for row in valid), default=0),
            "profit_event_count": sum(row["profit_event_count"] for row in valid),
            "total_trading_cost_across_windows": sum(row["total_trading_cost"] for row in valid),
            "max_consecutive_losing_trades": max((row["max_consecutive_losing_trades"] for row in valid), default=0),
            "max_consecutive_losing_months": max((row["max_consecutive_losing_months"] for row in valid), default=0),
            "currency": currency}


def run_s1_robustness(universe: list[dict], load_frame: Callable[[str], tuple[pd.DataFrame, dict]],
                      config: ResearchRunConfig) -> dict:
    """Compute fixed TP 3/5 on identical rolling 6M and 1Y windows."""
    result = {"version": ROLLING_VERSION, "as_of": config.evaluation_date.isoformat(),
              "entry_offset_pct": str(config.s1.entry_offset_pct), "assets": [],
              "warnings": ["겹치는 시작 구간의 결과는 서로 독립적인 통계 표본이 아닙니다.",
                           "각 구간은 같은 초기자금으로 새로 시작하며 미래 성과를 보장하지 않습니다."]}
    for entry in universe:
        symbol, is_korea = entry["symbol"], entry["market"] == "KRX"
        asset = {"symbol": symbol, "name": entry["name"], "market": entry["market"],
                 "currency": entry.get("currency", "KRW" if is_korea else "USD"),
                 "status": "SKIPPED", "groups": [], "windows": [], "filter_comparison": []}
        result["assets"].append(asset)
        try:
            frame, provenance = load_frame(symbol)
            validate_ohlcv(frame, expected_first_date=pd.Timestamp(frame.iloc[0]["date"]).date())
            frame = frame.loc[pd.to_datetime(frame["date"]).dt.date <= config.evaluation_date].copy()
            frame["date"] = pd.to_datetime(frame["date"]).dt.date
            frame = frame.reset_index(drop=True)
            if len(frame) <= 100 or (config.evaluation_date-frame.date.iloc[-1]).days > config.max_data_lag_days:
                raise ValueError("INSUFFICIENT_OR_STALE_DATA")
            dates = frame.date.tolist()
            data = _indicators(frame[["date", "open", "high", "low", "close", "volume"]])
            instrument = Instrument(entry["market"]+":"+symbol, symbol, entry["name"],
                                    "KOREAN_EQUITY" if is_korea else "US_EQUITY",
                                    entry["market"], asset["currency"],
                                    entry.get("timezone", "Asia/Seoul" if is_korea else "America/New_York"),
                                    lot_size=Decimal(1), tick_size=Decimal(1) if is_korea else Decimal("0.01"),
                                    currency_precision=0 if is_korea else 2,
                                    data_source=provenance.get("provider"),
                                    adjusted_status=provenance.get("adjustment", "UNKNOWN"))
            capital = config.initial_capital if is_korea else config.us_initial_capital
            family = FamilyConfig(initial_capital=capital,
                                  costs=config.krx_costs if is_korea else config.us_costs,
                                  stock_price_bands=is_korea, s1=config.s1, s2=config.s2,
                                  slippage_rate=config.krx_slippage_rate if is_korea else config.us_slippage_rate)
            asset.update(status="OK", source=provenance.get("provider"),
                         data_hash=sha256(frame.to_csv(index=False).encode()).hexdigest(),
                         data_period=[dates[0].isoformat(), dates[-1].isoformat()])
            for period, months in DURATIONS.items():
                windows = monthly_windows(dates, months)
                s0_by_window = {(first, last): _run_one(data, instrument, first, last, family,
                                                         "S0_BUY_AND_HOLD") for first, last in windows}
                for target in TARGETS:
                    configured = replace(family, s1=FixedTakeProfitConfig(config.s1.entry_offset_pct, target))
                    rows = []
                    for first, last in windows:
                        item = _run_one(data, instrument, first, last, configured,
                                        "S1_FIXED_TAKE_PROFIT")
                        metrics = summarize_window(item, float(capital), s0_by_window[(first, last)])
                        row = {"period": period, "tp_pct": str(target),
                               "window_start": dates[first].isoformat(),
                               "window_end": dates[last].isoformat(), **metrics}
                        rows.append(row)
                        asset["windows"].append(row)
                    if rows:
                        asset["groups"].append({"period": period, "tp_pct": str(target),
                                                **summarize_group(rows, asset["currency"])})
                # Same valid 205-observation starts for both arms; old S1 groups above stay unchanged.
                paired = [(first, last) for first, last in windows if first >= 205]
                for strategy in ("S1_FIXED_TAKE_PROFIT", "S1_TREND_FILTERED_TAKE_PROFIT"):
                    configured = replace(family, s1=FixedTakeProfitConfig(config.s1.entry_offset_pct,
                                                                            Decimal(5)))
                    paired_rows = []
                    for first, last in paired:
                        item = _run_one(data, instrument, first, last, configured, strategy)
                        metrics = summarize_window(item, float(capital), s0_by_window[(first, last)])
                        paired_rows.append({"period": period, "tp_pct": "5",
                            "strategy_id": strategy,
                            "window_start": dates[first].isoformat(),
                            "window_end": dates[last].isoformat(), **metrics})
                    if paired_rows:
                        asset["filter_comparison"].append({"period": period, "strategy_id": strategy,
                            "tp_pct": "5", **summarize_group(paired_rows, asset["currency"])})
            if not asset["groups"]:
                asset["status"] = "INSUFFICIENT_DATA"
        except (FileNotFoundError, ValueError, KeyError, TypeError) as error:
            asset.update(status="DATA_UNAVAILABLE", reason=type(error).__name__)
        except Exception as error:
            asset.update(status="ERROR", reason=type(error).__name__)
    fingerprint = json.dumps({"version": ROLLING_VERSION, "date": result["as_of"],
                              "entry": result["entry_offset_pct"],
                              "fees": [str(asdict(config.krx_costs)), str(asdict(config.us_costs)),
                                       str(config.krx_slippage_rate), str(config.us_slippage_rate)],
                              "assets": [(item["symbol"], item.get("data_hash")) for item in result["assets"]]},
                             sort_keys=True)
    result["input_hash"] = sha256(fingerprint.encode()).hexdigest()
    return result
