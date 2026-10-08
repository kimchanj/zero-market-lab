"""Close-price accumulation strategies over a generic daily OHLCV instrument.

The represented month's first observation receives its contribution, including
when the requested simulation starts after the calendar month's first session.
Close fills are an explicit market-on-close research assumption, not a signal
derived from the close. Distributions are excluded until a data feed exists.
"""

from __future__ import annotations

from decimal import Decimal

import pandas as pd

from zero_market_lab.backtest.contribution import MonthlyContributionPolicy

from .engine import _validate_bars
from .execution import ConfigurableFeeModel, LimitTouchExecutionModel
from .models import CostConfig, Instrument, MarketBar, _jsonable

ZERO = Decimal("0")


def run_accumulation(
    instrument: Instrument,
    bars: list[MarketBar],
    initial_capital: Decimal,
    monthly_amount: Decimal,
    costs: CostConfig,
    strategy_id: str,
) -> dict:
    _validate_bars(bars)
    if strategy_id not in {"PERIODIC_CONTRIBUTION", "LUMP_SUM_BUY_HOLD"}:
        raise ValueError("Unsupported accumulation strategy")
    if initial_capital < 0 or monthly_amount < 0:
        raise ValueError("Investment amounts must be non-negative")
    if strategy_id == "PERIODIC_CONTRIBUTION" and initial_capital + monthly_amount <= 0:
        raise ValueError("An initial or monthly investment is required")
    if strategy_id == "LUMP_SUM_BUY_HOLD" and initial_capital <= 0:
        raise ValueError("Initial investment must be positive")
    if instrument.bar_interval != "1D":
        raise ValueError("Only daily OHLCV is supported")

    # Reuse STEP 2/4 first-observation-per-represented-month policy.
    contribution_days = (
        {date.date() for date in MonthlyContributionPolicy(float(monthly_amount)).dates(
            pd.Series([bar.timestamp.date() for bar in bars])
        )} if strategy_id == "PERIODIC_CONTRIBUTION" and monthly_amount > 0 else set()
    )
    fees = ConfigurableFeeModel(costs, instrument.currency_precision)
    fills = LimitTouchExecutionModel(instrument, fees)
    cash = initial_capital
    quantity = ZERO
    cost_basis = ZERO
    total_contributions = initial_capital
    total_fees = ZERO
    buy_count = 0
    first_buy_date = None
    cashflows = [{"date": bars[0].timestamp.date().isoformat(), "type": "INITIAL_CAPITAL",
                  "amount": float(initial_capital)}] if initial_capital else []
    ledger, markers, average_line = [], [], []
    # Unitized NAV avoids reporting deposits as performance in the MDD.
    nav = Decimal("1")
    peak_nav = nav
    mdd = ZERO
    previous_value = None
    for index, bar in enumerate(bars):
        day = bar.timestamp.date()
        date_text = day.isoformat()
        before_cash, before_qty = cash, quantity
        deposit = monthly_amount if day in contribution_days else ZERO
        if deposit:
            cash += deposit
            total_contributions += deposit
            cashflows.append({"date": date_text, "type": "CONTRIBUTION", "amount": float(deposit)})
        buy_day = ((day in contribution_days or (index == 0 and initial_capital > 0))
                   if strategy_id == "PERIODIC_CONTRIBUTION" else index == 0)
        buy_qty = fills.quantity_for_cash(cash, bar.close) if buy_day else ZERO
        notional = buy_qty * bar.close
        buy_fee = fees.buy_fee(notional) if buy_qty else ZERO
        if buy_qty:
            cash -= notional + buy_fee
            quantity += buy_qty
            cost_basis += notional + buy_fee
            total_fees += buy_fee
            buy_count += 1
            first_buy_date = first_buy_date or day
            markers.append({"time": date_text, "action": "BUY", "tradeId": f"BUY-{buy_count:04d}",
                            "price": float(bar.close), "quantity": float(buy_qty), "fee": float(buy_fee),
                            "cashAfter": float(cash), "grossProfit": 0, "tax": 0, "netProfit": 0,
                            "netReturn": None, "holdingDays": 1, "explanation": "정기 적립 매수" if deposit else "일시금 매수"})
        value = cash + quantity * bar.close
        if previous_value is not None and previous_value > 0:
            nav *= (value - deposit) / previous_value
        peak_nav = max(peak_nav, nav)
        mdd = min(mdd, nav / peak_nav - 1)
        previous_value = value
        average = cost_basis / quantity if quantity else None
        position_value = quantity * bar.close
        gain = value - total_contributions
        holding_days = sum(1 for observed in bars[:index+1] if first_buy_date and observed.timestamp.date() >= first_buy_date)
        brief = (f"{deposit:,.0f}원 적립 · {buy_qty:,.0f}주 매수" if deposit and buy_qty else
                 f"{deposit:,.0f}원 적립 · 현금 이월" if deposit else
                 f"{buy_qty:,.0f}주 매수" if buy_qty else
                 f"{quantity:,.0f}주 보유 중" if quantity else "매수 가능 현금 대기")
        row = {
            "date": date_text, "instrument": instrument.instrument_id, "strategy": strategy_id,
            "open": float(bar.open), "high": float(bar.high), "low": float(bar.low),
            "close": float(bar.close), "volume": float(bar.volume),
            "cash_before": float(before_cash), "position_qty_before": float(before_qty),
            "avg_entry_price_before": None if before_qty == 0 else float((cost_basis-notional-buy_fee)/before_qty),
            "entry_order_price": None, "take_profit_price": None,
            "status": "ENTRY_FILLED" if buy_qty else "HOLDING" if quantity else "NO_ACTION",
            "status_label": "적립 매수" if buy_qty and deposit else "매수 완료" if buy_qty else "보유 중" if quantity else "현금 대기",
            "action": "BUY" if buy_qty else "HOLD" if quantity else "NONE",
            "action_label": "매수" if buy_qty else "보유" if quantity else "대기",
            "execution_price": float(bar.close) if buy_qty else None, "execution_qty": float(buy_qty),
            "buy_amount": float(notional), "sell_amount": 0, "buy_fee": float(buy_fee),
            "sell_fee": 0, "tax": 0, "total_cost": float(buy_fee),
            "cumulative_cost": float(total_fees), "gross_profit": 0, "net_profit": 0,
            "net_return": None, "cash_after": float(cash), "position_qty_after": float(quantity),
            "avg_entry_price_after": None if average is None else float(average),
            "position_value": float(position_value), "portfolio_value": float(value),
            "realized_profit_cumulative": 0, "unrealized_profit": float(gain),
            "trading_holding_days": holding_days,
            "calendar_holding_days": (day-first_buy_date).days+1 if first_buy_date else 0,
            "trade_id": f"BUY-{buy_count:04d}" if buy_qty else None,
            "decision_code": "MONTHLY_CLOSE_BUY" if buy_qty and deposit else "FIRST_CLOSE_BUY" if buy_qty else "HOLD",
            "explanation": brief + f" · 잔여현금 {cash:,.0f}원 · 누적손익 {gain:+,.0f}원",
            "brief": brief, "ambiguous": False, "decisions": [],
            "contribution_amount": float(deposit), "total_contributions": float(total_contributions),
            "cumulative_gain": float(gain), "purchase_quantity": float(buy_qty),
            "target_gap": None, "target_gap_rate": None, "high_target_gap": None,
            "entry_gap": None, "required_exit_price": None,
        }
        ledger.append(row)
        average_line.append({"time": date_text, **({"value": float(average)} if average else {})})

    last = ledger[-1]
    total = Decimal(str(last["portfolio_value"]))
    gain = total - total_contributions
    summary = {
        "start_date": ledger[0]["date"], "end_date": last["date"],
        "initial_capital": float(initial_capital), "total_contributions": float(total_contributions),
        "final_portfolio_value": float(total), "realized_profit": 0,
        "unrealized_profit": float(gain), "net_profit": float(gain),
        "net_return": float(gain/total_contributions), "completed_trades": 0,
        "open_trades": int(quantity > 0), "winning_trades": 0, "win_rate": None,
        "average_holding_days": None, "median_holding_days": None,
        "max_holding_days": 0, "average_net_profit_per_trade": None,
        "total_buy_fees": float(total_fees), "total_sell_fees": 0,
        "total_tax": 0, "total_trading_cost": float(total_fees), "mdd": float(mdd),
        "buy_count": buy_count, "position_qty": float(quantity),
        "average_purchase_price": None if quantity == 0 else float(cost_basis / quantity),
        "cash": float(cash), "simple_return_basis": "net_gain / total_external_contributions",
    }
    return {
        "instrument": _jsonable(instrument.__dict__),
        "strategy": {"strategy_id": strategy_id, "monthly_amount": float(monthly_amount),
                     "purchase_timing": "FIRST_OBSERVED_TRADING_DAY_CLOSE"},
        "execution": {"mark_price": "CLOSE", "entry_order_timing": "MARKET_ON_CLOSE_RESEARCH_ASSUMPTION"},
        "costs": _jsonable(costs.__dict__), "ledger": ledger, "trades": [], "summary": summary,
        "cashflows": cashflows,
        "chart": {"markers": markers, "averageCost": average_line,
                  "takeProfit": [{"time": row["date"]} for row in ledger]},
        "open_position": None if quantity == 0 else {
            "entry_qty": float(quantity), "entry_price": summary["average_purchase_price"],
            "current_close": last["close"], "current_value": last["position_value"],
            "net_profit": float(gain), "trading_holding_days": last["trading_holding_days"],
            "target_gap": None,
        },
    }
