"""Generic daily OHLCV simulation engine with a complete decision ledger."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from statistics import median
from typing import Sequence

from .execution import ConfigurableFeeModel, LimitTouchExecutionModel
from .explanation import explain_ledger_row
from .models import (
    CostConfig,
    DailyLedgerRow,
    DecisionRecord,
    ExecutionConfig,
    Instrument,
    MarketBar,
    PeriodSummary,
    SimulationResult,
    StrategyParameters,
    TradeSummary,
)


ZERO = Decimal("0")


def _validate_bars(bars: Sequence[MarketBar]) -> None:
    if not bars:
        raise ValueError("At least one market bar is required")
    timestamps = [bar.timestamp for bar in bars]
    if timestamps != sorted(timestamps) or len(set(timestamps)) != len(timestamps):
        raise ValueError("Market bars must have unique ascending timestamps")
    for bar in bars:
        if min(bar.open, bar.high, bar.low, bar.close) <= 0:
            raise ValueError("OHLC prices must be positive")
        if bar.volume < 0:
            raise ValueError("Volume must be non-negative")
        if bar.high < max(bar.open, bar.close, bar.low):
            raise ValueError("High violates OHLC invariant")
        if bar.low > min(bar.open, bar.close, bar.high):
            raise ValueError("Low violates OHLC invariant")


def _decision(
    bar: MarketBar,
    *,
    rule_name: str,
    rule_value: Decimal | str | None,
    observed_value: Decimal | str | None,
    comparison: str,
    result: bool | None,
    reason_code: str,
    trade_id: str | None,
) -> DecisionRecord:
    return DecisionRecord(
        timestamp=bar.timestamp,
        rule_name=rule_name,
        rule_value=rule_value,
        observed_value=observed_value,
        comparison=comparison,
        result=result,
        reason_code=reason_code,
        trade_id=trade_id,
    )


def _mdd(values: list[Decimal]) -> Decimal:
    peak = values[0]
    worst = ZERO
    for value in values:
        peak = max(peak, value)
        drawdown = value / peak - Decimal("1") if peak else ZERO
        worst = min(worst, drawdown)
    return worst


def simulate(
    *,
    instrument: Instrument,
    bars: Sequence[MarketBar],
    initial_capital: Decimal,
    strategy: StrategyParameters | None = None,
    execution: ExecutionConfig | None = None,
    costs: CostConfig | None = None,
) -> SimulationResult:
    """Run an all-cash/all-position limit-touch strategy over daily bars."""

    _validate_bars(bars)
    if initial_capital <= 0:
        raise ValueError("initial_capital must be positive")
    strategy = strategy or StrategyParameters()
    execution = execution or ExecutionConfig()
    costs = costs or CostConfig()
    if instrument.bar_interval != "1D":
        raise ValueError("Only 1D simulation is implemented")
    if execution.reentry_policy != "NEXT_BAR" or execution.mark_price != "CLOSE":
        raise ValueError("Only NEXT_BAR reentry and CLOSE marks are implemented")
    if execution.entry_order_timing != "AFTER_OPEN_OBSERVED":
        raise ValueError("Current-open limit requires AFTER_OPEN_OBSERVED timing")
    if execution.entry_price_rounding != "FLOOR" or execution.exit_price_rounding != "CEILING":
        raise ValueError("Only FLOOR entry and CEILING exit rounding are implemented")
    if not (Decimal("0") <= strategy.entry_offset_rate < Decimal("1")) or strategy.take_profit_rate <= 0:
        raise ValueError("Invalid entry/exit rates")
    if instrument.tick_size <= 0 or instrument.lot_size <= 0:
        raise ValueError("tick_size and lot_size must be positive")
    if execution.same_bar_policy != "CONSERVATIVE_HOLD":
        raise ValueError("Only CONSERVATIVE_HOLD is implemented for daily ambiguity")
    if execution.gap_fill_policy != "LIMIT_PRICE":
        raise ValueError("Only conservative LIMIT_PRICE gap fills are implemented")

    fee_model = ConfigurableFeeModel(costs, instrument.currency_precision)
    fills = LimitTouchExecutionModel(instrument, fee_model)
    cash = initial_capital
    quantity = ZERO
    average_price: Decimal | None = None
    open_trade: dict | None = None
    trade_counter = 0
    realized_profit = ZERO
    cumulative_cost = ZERO
    ledger: list[DailyLedgerRow] = []
    closed_trades: list[TradeSummary] = []
    exited_previous_bar = False

    for bar in bars:
        day = bar.timestamp.date()
        cash_before = cash
        quantity_before = quantity
        average_before = average_price
        entry_order: Decimal | None = None
        target_price: Decimal | None = None
        status = "NO_ACTION"
        action = "NONE"
        execution_price: Decimal | None = None
        execution_qty = ZERO
        buy_amount = sell_amount = ZERO
        buy_fee = sell_fee = tax = ZERO
        row_gross_profit = row_net_profit = ZERO
        row_net_return: Decimal | None = None
        closed_trading_days = 0
        closed_calendar_days = 0
        ambiguous = False
        decisions: list[DecisionRecord] = []
        current_trade_id = open_trade["trade_id"] if open_trade else None

        if quantity == 0:
            if exited_previous_bar:
                decisions.append(_decision(
                    bar, rule_name="REENTRY_POLICY", rule_value="NEXT_BAR",
                    observed_value=day.isoformat(), comparison="CURRENT_BAR > EXIT_BAR",
                    result=True, reason_code="NEXT_BAR_REENTRY", trade_id=None,
                ))
                exited_previous_bar = False
            entry_order = fills.entry_limit(bar.open, strategy.entry_offset_rate)
            touched = bar.low <= entry_order
            decisions.append(_decision(
                bar, rule_name="ENTRY_LIMIT", rule_value=entry_order,
                observed_value=bar.low, comparison="LOW <= ENTRY_LIMIT",
                result=touched, reason_code="ENTRY_FILLED" if touched else "ENTRY_NOT_TOUCHED",
                trade_id=None,
            ))
            if touched:
                execution_qty = fills.quantity_for_cash(cash, entry_order)
                if execution_qty > 0:
                    trade_counter += 1
                    current_trade_id = f"TRADE-{trade_counter:04d}"
                    decisions[-1] = _decision(
                        bar, rule_name="ENTRY_LIMIT", rule_value=entry_order,
                        observed_value=bar.low, comparison="LOW <= ENTRY_LIMIT",
                        result=True, reason_code="ENTRY_FILLED", trade_id=current_trade_id,
                    )
                    buy_amount = execution_qty * entry_order
                    buy_fee = fee_model.buy_fee(buy_amount)
                    cash -= buy_amount + buy_fee
                    quantity = execution_qty
                    average_price = entry_order
                    execution_price = entry_order
                    open_trade = {
                        "trade_id": current_trade_id,
                        "entry_date": day,
                        "entry_price": entry_order,
                        "quantity": quantity,
                        "entry_fee": buy_fee,
                        "capital_before": cash_before,
                        "trading_days": 1,
                    }
                    target_price = fills.take_profit_limit(average_price, strategy.take_profit_rate)
                    status = "ENTRY_FILLED"
                    action = "BUY"
                    if bar.high >= target_price:
                        ambiguous = True
                        status = "AMBIGUOUS"
                        decisions.append(_decision(
                            bar, rule_name="SAME_BAR_TAKE_PROFIT", rule_value=target_price,
                            observed_value=bar.high, comparison="HIGH >= TAKE_PROFIT AFTER ENTRY",
                            result=None, reason_code="AMBIGUOUS_ENTRY_EXIT",
                            trade_id=current_trade_id,
                        ))
                else:
                    status = "WAITING_ENTRY"
                    decisions.append(_decision(
                        bar, rule_name="MINIMUM_LOT", rule_value=instrument.lot_size,
                        observed_value=cash, comparison="AFFORDABLE_QTY >= LOT_SIZE",
                        result=False, reason_code="INSUFFICIENT_CASH", trade_id=None,
                    ))
            else:
                status = "WAITING_ENTRY"
        else:
            assert open_trade is not None and average_price is not None
            open_trade["trading_days"] += 1
            current_trade_id = open_trade["trade_id"]
            target_price = fills.take_profit_limit(average_price, strategy.take_profit_rate)
            touched = bar.high >= target_price
            decisions.append(_decision(
                bar, rule_name="TAKE_PROFIT", rule_value=target_price,
                observed_value=bar.high, comparison="HIGH >= TAKE_PROFIT",
                result=touched,
                reason_code="TAKE_PROFIT_FILLED" if touched else "TARGET_NOT_REACHED",
                trade_id=current_trade_id,
            ))
            if touched:
                execution_price = target_price
                execution_qty = quantity
                sell_amount = quantity * target_price
                sell_fee = fee_model.sell_fee(sell_amount)
                tax = fee_model.tax(sell_amount)
                cash += sell_amount - sell_fee - tax
                row_gross_profit = (target_price - open_trade["entry_price"]) * quantity
                row_net_profit = row_gross_profit - open_trade["entry_fee"] - sell_fee - tax
                invested = open_trade["entry_price"] * quantity + open_trade["entry_fee"]
                row_net_return = row_net_profit / invested
                realized_profit += row_net_profit
                calendar_days = (day - open_trade["entry_date"]).days + 1
                closed_trading_days = int(open_trade["trading_days"])
                closed_calendar_days = calendar_days
                closed_trades.append(TradeSummary(
                    trade_id=current_trade_id,
                    entry_date=open_trade["entry_date"], entry_price=open_trade["entry_price"],
                    entry_qty=quantity, entry_fee=open_trade["entry_fee"], exit_date=day,
                    exit_price=target_price, exit_qty=quantity, exit_fee=sell_fee, tax=tax,
                    gross_profit=row_gross_profit, net_profit=row_net_profit,
                    gross_return=row_gross_profit / (open_trade["entry_price"] * quantity),
                    net_return=row_net_return, trading_holding_days=open_trade["trading_days"],
                    calendar_holding_days=calendar_days, capital_before=open_trade["capital_before"],
                    capital_after=cash, exit_reason="TAKE_PROFIT", status="CLOSED",
                ))
                quantity = ZERO
                average_price = None
                open_trade = None
                status = "EXIT_FILLED"
                action = "SELL"
                exited_previous_bar = True
            else:
                status = "WAITING_TAKE_PROFIT"
                action = "HOLD"

        position_value = quantity * bar.close
        portfolio_value = cash + position_value
        if open_trade and average_price is not None:
            unrealized = (bar.close - average_price) * quantity - open_trade["entry_fee"]
            trading_days = int(open_trade["trading_days"])
            calendar_days = (day - open_trade["entry_date"]).days + 1
        else:
            unrealized = ZERO
            trading_days = closed_trading_days
            calendar_days = closed_calendar_days
        total_cost = buy_fee + sell_fee + tax
        cumulative_cost += total_cost
        decision_code = decisions[-1].reason_code if decisions else "NO_ACTION"
        row = DailyLedgerRow(
            date=day, instrument=instrument.instrument_id, strategy=strategy.strategy_id,
            open=bar.open, high=bar.high, low=bar.low, close=bar.close, volume=bar.volume,
            cash_before=cash_before, position_qty_before=quantity_before,
            avg_entry_price_before=average_before, entry_order_price=entry_order,
            take_profit_price=target_price, status=status, action=action,
            execution_price=execution_price, execution_qty=execution_qty,
            buy_amount=buy_amount, sell_amount=sell_amount, buy_fee=buy_fee,
            sell_fee=sell_fee, tax=tax, total_cost=total_cost,
            cumulative_cost=cumulative_cost,
            gross_profit=row_gross_profit, net_profit=row_net_profit,
            net_return=row_net_return, cash_after=cash, position_qty_after=quantity,
            avg_entry_price_after=average_price, position_value=position_value,
            portfolio_value=portfolio_value, realized_profit_cumulative=realized_profit,
            unrealized_profit=unrealized, trading_holding_days=trading_days,
            calendar_holding_days=calendar_days, trade_id=current_trade_id,
            decision_code=decision_code, ambiguous=ambiguous, decisions=decisions,
        )
        row.explanation = explain_ledger_row(row, instrument.currency)
        ledger.append(row)

    trades = list(closed_trades)
    if open_trade and average_price is not None:
        last = ledger[-1]
        gross = (last.close - average_price) * quantity
        net = gross - open_trade["entry_fee"]
        invested = average_price * quantity + open_trade["entry_fee"]
        trades.append(TradeSummary(
            trade_id=open_trade["trade_id"], entry_date=open_trade["entry_date"],
            entry_price=average_price, entry_qty=quantity, entry_fee=open_trade["entry_fee"],
            exit_date=None, exit_price=None, exit_qty=ZERO, exit_fee=ZERO, tax=ZERO,
            gross_profit=gross, net_profit=net, gross_return=gross / (average_price * quantity),
            net_return=net / invested, trading_holding_days=open_trade["trading_days"],
            calendar_holding_days=(ledger[-1].date - open_trade["entry_date"]).days + 1,
            capital_before=open_trade["capital_before"], capital_after=last.portfolio_value,
            exit_reason="PERIOD_END_OPEN", status="OPEN",
        ))

    completed = [trade for trade in trades if trade.status == "CLOSED"]
    holding_days = [trade.trading_holding_days for trade in completed]
    winning = [trade for trade in completed if trade.net_profit > 0]
    final_value = ledger[-1].portfolio_value
    final_unrealized = ledger[-1].unrealized_profit
    total_buy_fees = sum((row.buy_fee for row in ledger), ZERO)
    total_sell_fees = sum((row.sell_fee for row in ledger), ZERO)
    total_tax = sum((row.tax for row in ledger), ZERO)
    summary = PeriodSummary(
        start_date=ledger[0].date, end_date=ledger[-1].date,
        initial_capital=initial_capital, final_portfolio_value=final_value,
        realized_profit=realized_profit, unrealized_profit=final_unrealized,
        net_profit=final_value - initial_capital,
        net_return=final_value / initial_capital - Decimal("1"),
        completed_trades=len(completed), open_trades=int(open_trade is not None),
        winning_trades=len(winning),
        win_rate=Decimal(len(winning)) / Decimal(len(completed)) if completed else None,
        average_holding_days=(
            sum((Decimal(value) for value in holding_days), ZERO) / Decimal(len(holding_days))
            if holding_days else None
        ),
        median_holding_days=Decimal(str(median(holding_days))) if holding_days else None,
        max_holding_days=max(holding_days, default=0),
        average_net_profit_per_trade=(
            sum((trade.net_profit for trade in completed), ZERO) / Decimal(len(completed))
            if completed else None
        ),
        total_buy_fees=total_buy_fees, total_sell_fees=total_sell_fees,
        total_tax=total_tax,
        total_trading_cost=total_buy_fees + total_sell_fees + total_tax,
        mdd=_mdd([initial_capital, *[row.portfolio_value for row in ledger]]),
    )
    return SimulationResult(
        instrument=instrument, strategy=strategy, execution=execution, costs=costs,
        ledger=ledger, trades=trades, summary=summary,
    )
