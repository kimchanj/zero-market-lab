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
from .execution import ConfigurableFeeModel, affordable_quantity, required_buy_cash, quantize_money
from .models import CostConfig, Instrument
from .provider import FrameOHLCVProvider
from .entry_filter import MA200TrendFilter, NoFilter, SMA100Filter


STRATEGIES = (
    "S0_BUY_AND_HOLD", "S1_FIXED_TAKE_PROFIT", "S2_FIXED_TP_SL",
    "S3_FIXED_TP_SL_TIME", "S4_TREND_FILTERED_TP_SL_TIME",
    "S5_ATR_ADAPTIVE_EXIT", "S6A_PURE_MEAN_REVERSION",
    "S6B_CONFIRMED_REVERSAL", "S7_BREAKOUT_TREND_FOLLOWING",
    "S1_TREND_FILTERED_TAKE_PROFIT", "S2_TREND_FILTERED_TP_SL",
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


def required_gain_to_recover(drawdown_fraction: float) -> float | None:
    """Gain on trough capital required to regain the pre-drawdown peak."""
    if not -1 <= drawdown_fraction <= 0:
        raise ValueError("Drawdown must be between -1 and 0")
    return 1/(1+drawdown_fraction)-1 if drawdown_fraction > -1 else None


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
    ma200 = close.rolling(200, min_periods=200).mean()
    data["ma200_prior"] = ma200.shift(1)
    data["ma200_prior_5ago"] = ma200.shift(6)
    data["close_prior"] = previous_close
    data["high_prior"] = high.shift(1)
    data["high20_prior"] = high.rolling(20, min_periods=20).max().shift(1)
    data["low10_prior"] = low.rolling(10, min_periods=10).min().shift(1)
    return data


@dataclass(frozen=True)
class FixedTakeProfitConfig:
    entry_offset_pct: Decimal = Decimal("-1.0")
    take_profit_pct: Decimal = Decimal("5.0")


@dataclass(frozen=True)
class FixedStopConfig:
    take_profit_pct: Decimal = Decimal("5.0")
    stop_loss_pct: Decimal = Decimal("3.0")


@dataclass(frozen=True)
class FamilyConfig:
    initial_capital: Decimal = Decimal(500000)
    costs: CostConfig = CostConfig(buy_fee_rate=Decimal("0.00015"),
                                   sell_fee_rate=Decimal("0.00015"), sell_tax_rate=Decimal(0))
    stock_price_bands: bool = True
    s1: FixedTakeProfitConfig = FixedTakeProfitConfig()
    s2: FixedStopConfig = FixedStopConfig()
    slippage_rate: Decimal = Decimal(0)


def run_family(frame: pd.DataFrame, instrument: Instrument, start: date, end: date,
               config: FamilyConfig | None = None, *, isolate_errors: bool = False,
               strategies: tuple[str, ...] | None = None) -> dict:
    config = config or FamilyConfig()
    selected_strategies = STRATEGIES if strategies is None else tuple(strategies)
    if not selected_strategies or len(set(selected_strategies)) != len(selected_strategies) or any(
        name not in STRATEGIES for name in selected_strategies
    ):
        raise ValueError("Invalid strategy subset")
    if start > end or config.initial_capital <= 0:
        raise ValueError("Invalid evaluation period or capital")
    if (not Decimal("-20") <= config.s1.entry_offset_pct <= 0 or
        not 0 < config.s1.take_profit_pct <= Decimal("100") or
        not 0 < config.s2.take_profit_pct <= Decimal("100") or
        not 0 < config.s2.stop_loss_pct < Decimal("100") or
        not 0 <= config.slippage_rate <= Decimal("0.05")):
        raise ValueError("Invalid S1 or slippage configuration")
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
    for name in selected_strategies:
        try:
            if name in {"S1_TREND_FILTERED_TAKE_PROFIT", "S2_TREND_FILTERED_TP_SL"} and first < 205:
                results[name] = {"strategy": name, "status": "INSUFFICIENT_DATA",
                                 "reason": "205_PRIOR_TRADING_OBSERVATIONS_REQUIRED", "metrics": None}
                continue
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
                  "sell_tax_rate": float(config.costs.sell_tax_rate),
                  "slippage_rate": float(config.slippage_rate)},
        "s1_config": {"entry_offset_pct": float(config.s1.entry_offset_pct),
                      "take_profit_pct": float(config.s1.take_profit_pct)},
        "s2_config": {"take_profit_pct": float(config.s2.take_profit_pct),
                      "stop_loss_pct": float(config.s2.stop_loss_pct)},
        "results": results,
        "warning": "최근 6개월 historical sample 결과이며 시장 레짐에 따라 달라질 수 있습니다.",
    }


def _run_one(data: pd.DataFrame, instrument: Instrument, first: int, last: int,
             config: FamilyConfig, name: str) -> dict:
    fees = ConfigurableFeeModel(config.costs, instrument.currency_precision)
    cash, qty = config.initial_capital, Decimal(0)
    entry_price = entry_notional = entry_fee = entry_slip = Decimal(0)
    entry_index = -1
    entry_atr = None
    stop = target = None
    pending = None
    trades, ledger = [], []
    ambiguity = signal_count = false_reversal = filtered = trend_pass = trend_fail = 0
    stop_count = time_count = whipsaws = 0
    exposure_days = 0
    total_cost = Decimal(0)
    total_buy_fee = total_sell_fee = total_tax = total_slippage = Decimal(0)
    entry_atrs, atr_percents, tp_distances, sl_distances = [], [], [], []
    forward_returns = {1: [], 3: [], 5: [], 10: []}
    monthly_reversals: dict[str, int] = {}
    affordability_events = []
    blocked_entries = []
    cash_days = entry_filter_pass_count = entry_filter_fail_count = entry_blocked_days = 0
    blocked_after_exit = False

    def price(value): return Decimal(str(value))
    def rounded(value, up=False):
        return _to_tick(value, up=up, stock=config.stock_price_bands,
                        default_tick=instrument.tick_size)
    def buy(fill: Decimal, idx: int, atr=None):
        nonlocal cash, qty, entry_price, entry_notional, entry_fee, entry_slip
        nonlocal entry_index, entry_atr, stop, target, total_cost, total_buy_fee, total_slippage
        unit = instrument.lot_size
        estimate = affordable_quantity(cash, fill, unit, fees, config.slippage_rate)
        if estimate <= 0:
            return Decimal(0), Decimal(0)
        qty = estimate
        entry_price = fill
        entry_notional = qty * fill
        entry_fee = fees.buy_fee(entry_notional)
        entry_slip = quantize_money(entry_notional * config.slippage_rate,
                                    instrument.currency_precision)
        cash -= entry_notional + entry_fee + entry_slip
        total_buy_fee += entry_fee
        total_slippage += entry_slip
        total_cost += entry_fee + entry_slip
        entry_index = idx
        entry_atr = atr
        if atr is not None:
            entry_atrs.append(float(atr))
            atr_percents.append(float(atr / fill))
        if name in {"S1_FIXED_TAKE_PROFIT", "S1_TREND_FILTERED_TAKE_PROFIT",
                    "S2_FIXED_TP_SL", "S2_TREND_FILTERED_TP_SL",
                    "S3_FIXED_TP_SL_TIME", "S4_TREND_FILTERED_TP_SL_TIME"}:
            s1_style = name in {"S1_FIXED_TAKE_PROFIT", "S1_TREND_FILTERED_TAKE_PROFIT"}
            s2_style = name in {"S2_FIXED_TP_SL", "S2_TREND_FILTERED_TP_SL"}
            tp = (config.s1.take_profit_pct if s1_style else
                  config.s2.take_profit_pct if s2_style else Decimal(5))
            target = rounded(fill * (Decimal(1) + tp / 100), up=True)
            stop_pct = config.s2.stop_loss_pct if s2_style else Decimal(3)
            stop = rounded(fill * (Decimal(1) - stop_pct / 100)) if not s1_style else None
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
        return estimate, entry_fee + entry_slip

    def sell(fill: Decimal, idx: int, reason: str):
        nonlocal cash, qty, entry_index, total_cost, total_sell_fee, total_tax, total_slippage
        nonlocal stop_count, time_count, whipsaws, stop, target
        proceeds = qty * fill
        fee = fees.sell_fee(proceeds)
        tax = fees.tax(proceeds)
        sell_slip = quantize_money(proceeds * config.slippage_rate,
                                   instrument.currency_precision)
        cash += proceeds - fee - tax - sell_slip
        total_sell_fee += fee
        total_tax += tax
        total_slippage += sell_slip
        total_cost += fee + tax + sell_slip
        gross_pnl = proceeds - entry_notional
        pnl = gross_pnl - entry_fee - entry_slip - fee - tax - sell_slip
        trades.append({"entry_date": pd.Timestamp(data.iloc[entry_index]["date"]).date().isoformat(),
                       "exit_date": pd.Timestamp(data.iloc[idx]["date"]).date().isoformat(),
                       "entry_price": float(entry_price), "exit_price": float(fill),
                       "quantity": float(qty), "gross_profit": float(gross_pnl),
                       "gross_return": float(gross_pnl/entry_notional),
                       "net_profit": float(pnl),
                       "net_return": float(pnl/(entry_notional+entry_fee+entry_slip)),
                       "holding_days": idx-entry_index+1, "exit_reason": reason,
                       "buy_fee": float(entry_fee), "sell_fee": float(fee),
                       "sell_tax": float(tax),
                       "slippage_cost": float(entry_slip+sell_slip),
                       "cost": float(entry_fee+entry_slip+fee+tax+sell_slip)})
        if reason == "STOP_LOSS": stop_count += 1
        if reason == "TIME_STOP": time_count += 1
        if name == "S7_BREAKOUT_TREND_FOLLOWING" and pnl < 0: whipsaws += 1
        qty = Decimal(0)
        entry_index = -1
        stop = target = None
        return fee + tax + sell_slip

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
            else:
                affordability_events.append({"event_date": day, "available_cash": float(cash),
                    "required_cash": float(required_buy_cash(instrument.lot_size, fill, fees, config.slippage_rate)),
                    "reference_price": float(fill), "required_qty": float(instrument.lot_size),
                    "reason": "INITIAL_ENTRY_BLOCKED_BY_CAPITAL"})
        elif name in {"S1_FIXED_TAKE_PROFIT", "S2_FIXED_TP_SL", "S3_FIXED_TP_SL_TIME",
                      "S4_TREND_FILTERED_TP_SL_TIME", "S5_ATR_ADAPTIVE_EXIT",
                      "S1_TREND_FILTERED_TAKE_PROFIT", "S2_TREND_FILTERED_TP_SL"} and qty == 0 and not exited_today:
            entry_filter = (MA200TrendFilter() if name in {"S1_TREND_FILTERED_TAKE_PROFIT",
                         "S2_TREND_FILTERED_TP_SL"} else SMA100Filter() if name ==
                         "S4_TREND_FILTERED_TP_SL_TIME" else NoFilter())
            eligible = entry_filter.allows(row)
            if name in {"S1_TREND_FILTERED_TAKE_PROFIT", "S2_TREND_FILTERED_TP_SL"}:
                entry_filter_pass_count += int(eligible)
                entry_filter_fail_count += int(not eligible)
                entry_blocked_days += int(not eligible)
                if not eligible:
                    reason = "장기 추세 필터 조건 미충족 · 현금 대기"
            if name == "S4_TREND_FILTERED_TP_SL_TIME":
                trend_pass += int(eligible)
                trend_fail += int(not eligible)
            offset = config.s1.entry_offset_pct if name in {"S1_FIXED_TAKE_PROFIT",
                      "S1_TREND_FILTERED_TAKE_PROFIT"} else Decimal("-1")
            limit = rounded(opn * (Decimal(1) + offset / 100))
            if low <= limit:
                if eligible:
                    atr = price(row["atr14_prior"]) if name == "S5_ATR_ADAPTIVE_EXIT" and pd.notna(row["atr14_prior"]) else None
                    if name != "S5_ATR_ADAPTIVE_EXIT" or atr is not None:
                        fill = limit
                        bought, fee = buy(fill, idx, atr)
                        fee_today += fee
                        if bought:
                            action, entered_today = "BUY", True
                            reason = f"Open {offset}% 지정가"
                        else:
                            event_reason = ("REENTRY_BLOCKED_BY_CAPITAL" if trades
                                            else "INITIAL_ENTRY_BLOCKED_BY_CAPITAL")
                            if not affordability_events or affordability_events[-1]["reason"] != event_reason:
                                affordability_events.append({"event_date": day,
                                    "available_cash": float(cash),
                                    "required_cash": float(required_buy_cash(instrument.lot_size, fill, fees,
                                                                               config.slippage_rate)),
                                    "reference_price": float(fill),
                                    "required_qty": float(instrument.lot_size), "reason": event_reason})
                            if trades:
                                blocked_after_exit = True
                else:
                    filtered += 1
                    if name in {"S1_TREND_FILTERED_TAKE_PROFIT", "S2_TREND_FILTERED_TP_SL"}:
                        blocked_entries.append({"blocked_entry_date": day,
                            "hypothetical_entry_price": float(limit), "_index": idx,
                            "reason": "MA200_TREND_FILTER_FAIL"})

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
        else: cash_days += 1
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
        ledger[-1]["strategy_state"] = "BUY" if entered_today else "SELL" if exited_today else "CASH" if not qty else "HOLD"

    for event in blocked_entries:
        idx = event.pop("_index")
        for horizon in (20, 60):
            event[f"forward_{horizon}d_return"] = (float(data.iloc[idx+horizon]["close"] /
                event["hypothetical_entry_price"] - 1) if idx+horizon <= last else None)

    values = [float(config.initial_capital), *[row["portfolio_value"] for row in ledger]]
    peak, mdd, max_drawdown_amount, current_duration, max_duration = values[0], 0.0, 0.0, 0, 0
    drawdown_peak = drawdown_trough = None
    for value_index, value in enumerate(values[1:], 1):
        if value >= peak:
            peak, current_duration = value, 0
        else:
            current_duration += 1
            max_duration = max(max_duration, current_duration)
            current_drawdown = value/peak-1
            if current_drawdown < mdd:
                mdd = current_drawdown
                drawdown_peak, drawdown_trough = peak, value_index
            max_drawdown_amount = max(max_drawdown_amount, peak-value)
    recovery_index = (next((i for i in range(drawdown_trough+1, len(values))
                            if values[i] >= drawdown_peak), None)
                      if drawdown_trough is not None else 0)
    recovery_days = (recovery_index-drawdown_trough if recovery_index is not None and
                     drawdown_trough is not None else 0 if drawdown_trough is None else None)
    gains = [trade["net_profit"] for trade in trades if trade["net_profit"] > 0]
    losses = [trade["net_profit"] for trade in trades if trade["net_profit"] < 0]
    gross_wins, gross_losses = sum(gains), -sum(losses)
    loss_streak = streak = 0
    for trade in trades:
        streak = streak + 1 if trade["net_profit"] < 0 else 0
        loss_streak = max(loss_streak, streak)
    positive_exits = {trade["exit_date"] for trade in trades if trade["net_profit"] > 0}
    profit_indices = [i for i, row in enumerate(ledger) if row["date"] in positive_exits]
    realized_gain = sum(trade["net_profit"] for trade in trades)
    unrealized_gain = float(qty * Decimal(str(ledger[-1]["close"])) - entry_notional - entry_fee - entry_slip) if qty else 0.0
    open_cost_basis = float(entry_notional + entry_fee + entry_slip) if qty else 0.0
    open_unrealized_return = unrealized_gain / open_cost_basis if open_cost_basis else None
    open_marked_pnls = ([float(qty * Decimal(str(row["close"])) - entry_notional - entry_fee - entry_slip)
                         for row in ledger[entry_index-first:]] if qty else [])
    open_worst_pnl = min([0.0, *open_marked_pnls]) if qty else None
    open_worst_return = open_worst_pnl / open_cost_basis if open_cost_basis else None
    metrics = {
        "initial_capital": float(config.initial_capital), "final_portfolio": values[-1],
        "cash": float(cash), "market_value": float(qty * Decimal(str(ledger[-1]["close"]))),
        "net_gain": values[-1]-values[0], "net_return": values[-1]/values[0]-1,
        "gross_gain_cost_addback": values[-1]-values[0]+float(total_cost),
        "gross_return_cost_addback": (values[-1]-values[0]+float(total_cost))/values[0],
        "realized_gain": realized_gain, "unrealized_gain": unrealized_gain,
        "open_unrealized_return": open_unrealized_return,
        "open_worst_marked_pnl": open_worst_pnl,
        "open_worst_marked_return": open_worst_return,
        "mdd": mdd, "max_drawdown_amount": max_drawdown_amount,
        "max_drawdown_duration": max_duration,
        "recovered_from_max_drawdown": recovery_index is not None,
        "recovery_days": recovery_days,
        "unrecovered_days": (len(values)-1-drawdown_trough if recovery_index is None else 0),
        "required_gain_to_recover_pct": required_gain_to_recover(mdd),
        "completed_trades": len(trades), "open_trades": int(qty > 0),
        "win_count": len(gains), "loss_count": len(losses),
        "win_rate": len(gains)/len(trades) if trades else None,
        "average_win": mean(gains) if gains else None,
        "average_loss": mean(losses) if losses else None,
        "max_single_loss": min(losses) if losses else None,
        "max_consecutive_losses": loss_streak,
        "payoff_ratio": mean(gains)/abs(mean(losses)) if gains and losses else None,
        "closed_trade_expectancy_krw": mean(t["net_profit"] for t in trades) if trades else None,
        "closed_trade_expectancy_pct": mean(t["net_return"] for t in trades) if trades else None,
        "profit_factor": gross_wins/gross_losses if gross_losses else None,
        "average_holding_days": mean(t["holding_days"] for t in trades) if trades else None,
        "median_holding_days": median(t["holding_days"] for t in trades) if trades else None,
        "max_holding_days": max((t["holding_days"] for t in trades), default=0),
        "max_capital_lock_days_observed": max(
            max((t["holding_days"] for t in trades), default=0),
            last-entry_index+1 if qty else 0),
        "market_exposure_ratio": exposure_days/len(ledger),
        "realized_profit_events_per_year": len(profit_indices)*252/len(ledger),
        "average_days_between_profit_events": (mean(b-a for a,b in zip(profit_indices,profit_indices[1:]))
                                               if len(profit_indices)>1 else None),
        "net_profit_per_100_trading_days": (values[-1]-values[0])*100/len(ledger),
        "cash_days": cash_days, "cash_ratio": cash_days/len(ledger),
        "entry_filter_pass_count": entry_filter_pass_count,
        "entry_filter_fail_count": entry_filter_fail_count,
        "entry_blocked_days": entry_blocked_days,
        "blocked_entry_opportunity_count": len(blocked_entries),
        "total_buy_fee": float(total_buy_fee), "total_sell_fee": float(total_sell_fee),
        "total_tax": float(total_tax), "total_slippage": float(total_slippage),
        "total_trading_cost": float(total_cost), "stop_loss_count": stop_count,
        "time_stop_count": time_count, "trend_pass_days": trend_pass,
        "trend_fail_days": trend_fail, "filtered_entry_count": filtered,
        "average_entry_atr": mean(entry_atrs) if entry_atrs else None,
        "average_atr_percent": mean(atr_percents) if atr_percents else None,
        "average_tp_distance": mean(tp_distances) if tp_distances else None,
        "average_sl_distance": mean(sl_distances) if sl_distances else None,
        "signal_count": signal_count, "false_reversal_count": false_reversal,
        "whipsaw_count": whipsaws,
        "affordability_event_count": len(affordability_events),
        "reentry_blocked_by_capital": blocked_after_exit,
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
    open_position = ({"entry_date": pd.Timestamp(data.iloc[entry_index]["date"]).date().isoformat(),
                      "entry_price": float(entry_price), "quantity": float(qty),
                      "target": float(target) if target is not None else None,
                      "mark_close": ledger[-1]["close"], "holding_days": last-entry_index+1,
                      "unrealized_pnl": unrealized_gain,
                      "unrealized_return": open_unrealized_return,
                      "worst_marked_pnl": open_worst_pnl,
                      "worst_marked_return": open_worst_return} if qty else None)
    return {"strategy": name, "metrics": metrics, "ledger": ledger, "trades": trades,
            "open_position": open_position, "ambiguity_count": ambiguity,
            "affordability_events": affordability_events,
            "blocked_entries": blocked_entries,
            "last_entry_filter_allowed": (MA200TrendFilter().allows(data.iloc[last])
                if name in {"S1_TREND_FILTERED_TAKE_PROFIT", "S2_TREND_FILTERED_TP_SL"} else None)}
