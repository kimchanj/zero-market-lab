"""Single-position strategy-family experiment on generic daily OHLCV.

Signals using a daily close can only fill at the next session's open. A day's
high/low order is unknown: existing-position stop precedes TP when both touch.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_FLOOR, ROUND_CEILING
from statistics import mean, median

import pandas as pd

from zero_market_lab.tiger_v2.data import validate_ohlcv
from .execution import ConfigurableFeeModel
from .models import CostConfig, Instrument
from .provider import FrameOHLCVProvider


STRATEGIES = (
    "S0_BUY_AND_HOLD", "S1_FIXED_TAKE_PROFIT", "S2_FIXED_TP_SL",
    "S3_FIXED_TP_SL_TIME", "S4_TREND_FILTERED_TP_SL_TIME",
    "S5_ATR_ADAPTIVE_EXIT", "S6A_PURE_MEAN_REVERSION",
    "S6B_CONFIRMED_REVERSAL", "S7_BREAKOUT_TREND_FOLLOWING",
)


def krx_stock_tick(price: Decimal) -> Decimal:
    """KRX stock price-band quotation unit (ETFs use a different rule)."""
    if price < 2000: return Decimal(1)
    if price < 5000: return Decimal(5)
    if price < 20000: return Decimal(10)
    if price < 50000: return Decimal(50)
    if price < 200000: return Decimal(100)
    if price < 500000: return Decimal(500)
    return Decimal(1000)


def _to_tick(price: Decimal, *, up: bool, stock: bool, default_tick: Decimal) -> Decimal:
    tick = krx_stock_tick(price) if stock else default_tick
    rounding = ROUND_CEILING if up else ROUND_FLOOR
    candidate = (price / tick).to_integral_value(rounding=rounding) * tick
    # A rounded price can cross a band boundary; re-check the actual quote.
    actual_tick = krx_stock_tick(candidate) if stock else default_tick
    if candidate % actual_tick:
        candidate = (candidate / actual_tick).to_integral_value(rounding=rounding) * actual_tick
    return candidate


def _indicators(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame.copy()
    for key in ("open", "high", "low", "close", "volume"):
        data[key] = pd.to_numeric(data[key], errors="raise")
    close, high, low = data["close"], data["high"], data["low"]
    previous_close = close.shift(1)
    tr = pd.concat([high-low, (high-previous_close).abs(),
                    (low-previous_close).abs()], axis=1).max(axis=1)
    data["atr14"] = tr.rolling(14, min_periods=14).mean()
    data["atr14_prior"] = data["atr14"].shift(1)
    data["ma20"] = close.rolling(20, min_periods=20).mean()
    data["std20"] = close.rolling(20, min_periods=20).std(ddof=0)
    data["ma100_prior"] = close.rolling(100, min_periods=100).mean().shift(1)
    data["close_prior"] = previous_close
    data["high_prior"] = high.shift(1)
    data["high20_prior"] = high.rolling(20, min_periods=20).max().shift(1)
    data["low10_prior"] = low.rolling(10, min_periods=10).min().shift(1)
    return data


@dataclass(frozen=True)
class FamilyConfig:
    initial_capital: Decimal = Decimal(500000)
    costs: CostConfig = CostConfig(buy_fee_rate=Decimal("0.00015"),
                                   sell_fee_rate=Decimal("0.00015"), sell_tax_rate=Decimal(0))
    stock_price_bands: bool = True


def run_family(frame: pd.DataFrame, instrument: Instrument, start: date, end: date,
               config: FamilyConfig | None = None, *, isolate_errors: bool = False) -> dict:
    config = config or FamilyConfig()
    if start > end or config.initial_capital <= 0:
        raise ValueError("Invalid evaluation period or capital")
    if instrument.fractional_allowed or instrument.lot_size != 1:
        raise ValueError("This family comparison requires integer shares")
    market = frame.copy().sort_values("date").reset_index(drop=True)
    validate_ohlcv(market, expected_first_date=pd.Timestamp(market.iloc[0]["date"]).date())
    bars = FrameOHLCVProvider(market).load_ohlcv(
        instrument, pd.Timestamp(market.iloc[0]["date"]).date(),
        pd.Timestamp(market.iloc[-1]["date"]).date(),
    )
    normalized = pd.DataFrame({"date": bar.timestamp.date(), "open": bar.open,
                               "high": bar.high, "low": bar.low, "close": bar.close,
                               "volume": bar.volume} for bar in bars)
    data = _indicators(normalized)
    dates = pd.to_datetime(data["date"]).dt.date
    evaluation = data.index[(dates >= start) & (dates <= end)]
    if len(evaluation) == 0:
        raise ValueError("No actual OHLCV observations in evaluation period")
    first, last = int(evaluation[0]), int(evaluation[-1])
    if first < 100:
        raise ValueError("100 prior trading observations are required for S4 warm-up")
    results = {}
    for name in STRATEGIES:
        try:
            results[name] = _run_one(data, instrument, first, last, config, name)
        except Exception as error:
            if not isolate_errors:
                raise
            results[name] = {"strategy": name, "status": "ERROR",
                             "reason": type(error).__name__, "metrics": None}
    return {
        "instrument": {"symbol": instrument.symbol, "name": instrument.display_name,
                       "market": instrument.market, "currency": instrument.currency},
        "requested_period": [start.isoformat(), end.isoformat()],
        "actual_period": [dates[first].isoformat(), dates[last].isoformat()],
        "data_load_period": [dates.iloc[0].isoformat(), dates.iloc[-1].isoformat()],
        "warmup_observations": first,
        "capital": float(config.initial_capital),
        "costs": {"buy_fee_rate": float(config.costs.buy_fee_rate),
                  "sell_fee_rate": float(config.costs.sell_fee_rate),
                  "sell_tax_rate": float(config.costs.sell_tax_rate)},
        "results": results,
        "warning": "최근 6개월 historical sample 결과이며 시장 레짐에 따라 달라질 수 있습니다.",
    }


def _run_one(data: pd.DataFrame, instrument: Instrument, first: int, last: int,
             config: FamilyConfig, name: str) -> dict:
    fees = ConfigurableFeeModel(config.costs, instrument.currency_precision)
    cash, qty = config.initial_capital, Decimal(0)
    entry_price = entry_notional = entry_fee = Decimal(0)
    entry_index = -1
    entry_atr = None
    stop = target = None
    pending = None
    trades, ledger = [], []
    ambiguity = signal_count = false_reversal = filtered = trend_pass = trend_fail = 0
    stop_count = time_count = whipsaws = 0
    exposure_days = 0
    total_cost = Decimal(0)
    entry_atrs, atr_percents, tp_distances, sl_distances = [], [], [], []
    forward_returns = {1: [], 3: [], 5: [], 10: []}
    monthly_reversals: dict[str, int] = {}

    def price(value): return Decimal(str(value))
    def rounded(value, up=False):
        return _to_tick(value, up=up, stock=config.stock_price_bands,
                        default_tick=instrument.tick_size)
    def buy(fill: Decimal, idx: int, atr=None):
        nonlocal cash, qty, entry_price, entry_notional, entry_fee, entry_index, entry_atr, stop, target, total_cost
        unit = instrument.lot_size
        estimate = (cash / fill / unit).to_integral_value(rounding=ROUND_FLOOR) * unit
        while estimate > 0 and estimate * fill + fees.buy_fee(estimate * fill) > cash:
            estimate -= unit
        if estimate <= 0:
            return Decimal(0), Decimal(0)
        qty = estimate
        entry_price = fill
        entry_notional = qty * fill
        entry_fee = fees.buy_fee(entry_notional)
        cash -= entry_notional + entry_fee
        total_cost += entry_fee
        entry_index = idx
        entry_atr = atr
        if atr is not None:
            entry_atrs.append(float(atr))
            atr_percents.append(float(atr / fill))
        if name in {"S1_FIXED_TAKE_PROFIT", "S2_FIXED_TP_SL", "S3_FIXED_TP_SL_TIME",
                    "S4_TREND_FILTERED_TP_SL_TIME"}:
            target = rounded(fill * Decimal("1.05"), up=True)
            stop = rounded(fill * Decimal("0.97")) if name != "S1_FIXED_TAKE_PROFIT" else None
        elif name == "S5_ATR_ADAPTIVE_EXIT" and atr is not None:
            target = rounded(fill + 3 * atr, up=True)
            stop = rounded(fill - 2 * atr)
        elif name in {"S6A_PURE_MEAN_REVERSION", "S6B_CONFIRMED_REVERSAL"} and atr is not None:
            target = None
            stop = rounded(fill - Decimal("1.5") * atr)
        else:
            target = stop = None
        if target: tp_distances.append(float(target / fill - 1))
        if stop: sl_distances.append(float(1 - stop / fill))
        return estimate, entry_fee

    def sell(fill: Decimal, idx: int, reason: str):
        nonlocal cash, qty, entry_index, total_cost, stop_count, time_count, whipsaws, stop, target
        proceeds = qty * fill
        fee = fees.sell_fee(proceeds)
        tax = fees.tax(proceeds)
        cash += proceeds - fee - tax
        total_cost += fee + tax
        pnl = proceeds - fee - tax - entry_notional - entry_fee
        trades.append({"entry_date": pd.Timestamp(data.iloc[entry_index]["date"]).date().isoformat(),
                       "exit_date": pd.Timestamp(data.iloc[idx]["date"]).date().isoformat(),
                       "entry_price": float(entry_price), "exit_price": float(fill),
                       "quantity": float(qty), "net_profit": float(pnl),
                       "net_return": float(pnl/(entry_notional+entry_fee)),
                       "holding_days": idx-entry_index+1, "exit_reason": reason,
                       "cost": float(entry_fee+fee+tax)})
        if reason == "STOP_LOSS": stop_count += 1
        if reason == "TIME_STOP": time_count += 1
        if name == "S7_BREAKOUT_TREND_FOLLOWING" and pnl < 0: whipsaws += 1
        qty = Decimal(0)
        entry_index = -1
        stop = target = None
        return fee + tax

    for idx in range(first, last + 1):
        row = data.iloc[idx]
        day = pd.Timestamp(row["date"]).date().isoformat()
        opn, high, low, close = (price(row[key]) for key in ("open", "high", "low", "close"))
        action, reason, fill, fee_today, ambiguous = "HOLD", "", None, Decimal(0), False
        entered_today = exited_today = False
        position_from_prior_day = qty > 0

        if pending == "EXIT" and qty > 0:
            fill = opn
            fee_today += sell(fill, idx, "NEXT_OPEN_SIGNAL")
            action, reason, exited_today = "SELL", "전일 종가 청산 신호 → 당일 시가", True
            pending = None
        elif pending == "ENTRY" and qty == 0:
            fill = opn
            atr = price(data.iloc[idx-1]["atr14"]) if pd.notna(data.iloc[idx-1]["atr14"]) else None
            bought, fee = buy(fill, idx, atr)
            fee_today += fee
            if bought:
                action, reason, entered_today = "BUY", "전일 종가 진입 신호 → 당일 시가", True
            pending = None

        if name == "S0_BUY_AND_HOLD" and idx == first and qty == 0:
            fill = opn
            bought, fee = buy(fill, idx)
            fee_today += fee
            if bought: action, reason, entered_today = "BUY", "평가 첫 거래일 시가", True
        elif name in STRATEGIES[1:6] and qty == 0 and not exited_today:
            eligible = True
            if name == "S4_TREND_FILTERED_TP_SL_TIME":
                eligible = bool(pd.notna(row["ma100_prior"]) and row["close_prior"] > row["ma100_prior"])
                trend_pass += int(eligible)
                trend_fail += int(not eligible)
            limit = rounded(opn * Decimal("0.99"))
            if low <= limit:
                if eligible:
                    atr = price(row["atr14_prior"]) if name == "S5_ATR_ADAPTIVE_EXIT" and pd.notna(row["atr14_prior"]) else None
                    if name != "S5_ATR_ADAPTIVE_EXIT" or atr is not None:
                        fill = limit
                        bought, fee = buy(fill, idx, atr)
                        fee_today += fee
                        if bought: action, reason, entered_today = "BUY", "Open -1% 지정가", True
                else:
                    filtered += 1

        if qty > 0 and name != "S0_BUY_AND_HOLD":
            stop_touched = stop is not None and (opn <= stop if position_from_prior_day else False)
            stop_touched = stop_touched or (stop is not None and low <= stop)
            target_touched = target is not None and high >= target
            if position_from_prior_day and stop_touched and target_touched:
                ambiguous = True
                ambiguity += 1
            if entered_today and target_touched:
                ambiguous = True  # Entry/TP sequence unknown; TP is not credited.
                ambiguity += 1
            if stop_touched:
                fill = opn if position_from_prior_day and opn <= stop else stop
                fee_today += sell(fill, idx, "STOP_LOSS")
                action, reason, exited_today = "SELL", "손절 우선" if ambiguous else "손절", True
            elif position_from_prior_day and target_touched:
                fill = target
                fee_today += sell(fill, idx, "TAKE_PROFIT")
                action, reason, exited_today = "SELL", "익절", True
            elif position_from_prior_day and name in {"S3_FIXED_TP_SL_TIME", "S4_TREND_FILTERED_TP_SL_TIME",
                                                      "S5_ATR_ADAPTIVE_EXIT"} and idx-entry_index+1 >= 20:
                fill = close
                fee_today += sell(fill, idx, "TIME_STOP")
                action, reason, exited_today = "SELL", "20거래일 시간 청산", True
            elif position_from_prior_day and name in {"S6A_PURE_MEAN_REVERSION", "S6B_CONFIRMED_REVERSAL"} and idx-entry_index+1 >= 10:
                fill = close
                fee_today += sell(fill, idx, "TIME_STOP")
                action, reason, exited_today = "SELL", "10거래일 시간 청산", True

        # Close-time signals are queued for the *next* bar only.
        if idx < last and name == "S6A_PURE_MEAN_REVERSION":
            if qty == 0 and pd.notna(row["ma20"]) and close < price(row["ma20"] - 2 * row["std20"]):
                pending = "ENTRY"
                signal_count += 1
            elif qty > 0 and pd.notna(row["ma20"]) and close >= price(row["ma20"]):
                pending = "EXIT"
        elif idx < last and name == "S6B_CONFIRMED_REVERSAL":
            if qty == 0 and idx >= 4 and pd.notna(data.iloc[idx-1]["atr14"]):
                previous = [data.iloc[idx-j]["close"] for j in (1, 2, 3, 4)]
                down_three = previous[0] < previous[1] < previous[2] < previous[3]
                oversold = previous[3] - previous[0] >= 2 * data.iloc[idx-1]["atr14"]
                if down_three and oversold:
                    signal_count += 1
                    if close > price(row["high_prior"]):
                        pending = "ENTRY"
                        monthly_reversals[day[:7]] = monthly_reversals.get(day[:7], 0) + 1
                        for horizon in forward_returns:
                            if idx+horizon <= last:
                                forward_returns[horizon].append(float(data.iloc[idx+horizon]["close"] / row["close"] - 1))
                    else: false_reversal += 1
            elif qty > 0 and pd.notna(row["ma20"]) and close >= price(row["ma20"]):
                pending = "EXIT"
        elif idx < last and name == "S7_BREAKOUT_TREND_FOLLOWING":
            if qty == 0 and pd.notna(row["high20_prior"]) and close > price(row["high20_prior"]):
                pending = "ENTRY"
                signal_count += 1
            elif qty > 0 and pd.notna(row["low10_prior"]) and close < price(row["low10_prior"]):
                pending = "EXIT"

        value = cash + qty * close
        if qty: exposure_days += 1
        if entered_today and exited_today:
            action = "BUY+SELL"
            reason = "당일 매수 후 " + reason
        ledger.append({"date": day, "open": float(opn), "high": float(high), "low": float(low),
                       "close": float(close), "cash": float(cash), "quantity": float(qty),
                       "portfolio_value": float(value), "action": action, "reason": reason,
                       "execution_price": float(fill) if fill is not None else None,
                       "entry_price_today": float(entry_price) if entered_today else None,
                       "exit_price_today": float(fill) if exited_today else None,
                       "cost_today": float(fee_today), "ambiguous": ambiguous,
                       "target": float(target) if target is not None else None,
                       "stop": float(stop) if stop is not None else None,
                       "pending_next_open": pending})

    values = [float(config.initial_capital), *[row["portfolio_value"] for row in ledger]]
    peak, mdd, current_duration, max_duration = values[0], 0.0, 0, 0
    for value in values[1:]:
        if value >= peak:
            peak, current_duration = value, 0
        else:
            current_duration += 1
            max_duration = max(max_duration, current_duration)
            mdd = min(mdd, value/peak-1)
    gains = [trade["net_profit"] for trade in trades if trade["net_profit"] > 0]
    losses = [trade["net_profit"] for trade in trades if trade["net_profit"] < 0]
    gross_wins, gross_losses = sum(gains), -sum(losses)
    realized_gain = sum(trade["net_profit"] for trade in trades)
    unrealized_gain = float(qty * Decimal(str(ledger[-1]["close"])) - entry_notional - entry_fee) if qty else 0.0
    metrics = {
        "initial_capital": float(config.initial_capital), "final_portfolio": values[-1],
        "net_gain": values[-1]-values[0], "net_return": values[-1]/values[0]-1,
        "realized_gain": realized_gain, "unrealized_gain": unrealized_gain,
        "mdd": mdd, "max_drawdown_duration": max_duration,
        "completed_trades": len(trades), "open_trades": int(qty > 0),
        "win_count": len(gains), "loss_count": len(losses),
        "win_rate": len(gains)/len(trades) if trades else None,
        "average_win": mean(gains) if gains else None,
        "average_loss": mean(losses) if losses else None,
        "profit_factor": gross_wins/gross_losses if gross_losses else None,
        "average_holding_days": mean(t["holding_days"] for t in trades) if trades else None,
        "median_holding_days": median(t["holding_days"] for t in trades) if trades else None,
        "max_holding_days": max((t["holding_days"] for t in trades), default=0),
        "market_exposure_ratio": exposure_days/len(ledger),
        "total_trading_cost": float(total_cost), "stop_loss_count": stop_count,
        "time_stop_count": time_count, "trend_pass_days": trend_pass,
        "trend_fail_days": trend_fail, "filtered_entry_count": filtered,
        "average_entry_atr": mean(entry_atrs) if entry_atrs else None,
        "average_atr_percent": mean(atr_percents) if atr_percents else None,
        "average_tp_distance": mean(tp_distances) if tp_distances else None,
        "average_sl_distance": mean(sl_distances) if sl_distances else None,
        "signal_count": signal_count, "false_reversal_count": false_reversal,
        "whipsaw_count": whipsaws,
    }
    if name == "S6B_CONFIRMED_REVERSAL":
        metrics["oversold_signal_count"] = signal_count
        metrics["reversal_count"] = sum(monthly_reversals.values())
        metrics["monthly_reversal_signal_count"] = monthly_reversals
        metrics["forward_return"] = {f"{horizon}d": mean(items) if items else None
                                      for horizon, items in forward_returns.items()}
    if name == "S6A_PURE_MEAN_REVERSION":
        metrics["oversold_signal_count"] = signal_count
    if name == "S7_BREAKOUT_TREND_FOLLOWING":
        market_return = float(data.iloc[last]["close"] / data.iloc[first]["open"] - 1)
        metrics["breakout_signal_count"] = signal_count
        metrics["trend_capture_ratio"] = metrics["net_return"] / market_return if market_return > 0 else None
    return {"strategy": name, "metrics": metrics, "ledger": ledger, "trades": trades,
            "ambiguity_count": ambiguity}
