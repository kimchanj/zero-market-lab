"""Daily Case #01 engine for strategies A, B and C."""

from dataclasses import dataclass, field
import math

import pandas as pd

from zero_market_lab.market_data.validation import validate
from zero_market_lab.portfolio import Portfolio
from zero_market_lab.strategies import StrategyCode, StrategyState, create_case01_strategy

from .contribution import MonthlyContributionPolicy


STATE_COLUMNS = [
    "date", "market_price", "cash", "quantity", "average_purchase_price",
    "position_value", "portfolio_value", "total_contribution",
    "strategy_name", "strategy_state", "reentry_target_date",
]
EVENT_COLUMNS = ["date", "event_type", "amount", "price", "quantity", "reason"]


@dataclass(frozen=True)
class BacktestResult:
    daily_states: pd.DataFrame
    events: pd.DataFrame
    metadata: dict = field(default_factory=dict)


def run_monthly_buy_and_hold(
    market_data: pd.DataFrame,
    monthly_contribution: float,
) -> BacktestResult:
    """Backward-compatible Strategy A entry point."""
    return run_case01_strategy(market_data, monthly_contribution, StrategyCode.BUY_AND_HOLD)


def run_case01_strategy(
    market_data: pd.DataFrame,
    monthly_contribution: float,
    strategy_code: str | StrategyCode,
    take_profit_rate: float = 0.05,
    reentry_months: int = 1,
    initial_investment: float = 0.0,
) -> BacktestResult:
    """Run one Case #01 strategy under same-close, zero-cost assumptions."""
    validation = validate(market_data)
    if not validation.passed:
        raise ValueError("Invalid market data: " + "; ".join(validation.errors))

    market = market_data.loc[:, ["date", "close"]].copy()
    market["date"] = pd.to_datetime(market["date"])
    market["close"] = pd.to_numeric(market["close"])

    if not math.isfinite(initial_investment) or initial_investment < 0:
        raise ValueError("Initial investment must be finite and >= 0")
    if not math.isfinite(monthly_contribution) or monthly_contribution < 0:
        raise ValueError("Monthly contribution must be finite and >= 0")
    if initial_investment == 0 and monthly_contribution == 0:
        raise ValueError("Initial investment or monthly contribution must be > 0")

    policy = (
        MonthlyContributionPolicy(monthly_contribution)
        if monthly_contribution > 0
        else None
    )
    contribution_dates = policy.dates(market["date"]) if policy else set()
    strategy = create_case01_strategy(
        strategy_code,
        take_profit_rate=take_profit_rate,
        reentry_months=reentry_months,
    )
    portfolio = Portfolio()
    states: list[dict] = []
    events: list[dict] = []
    completed_waiting_days = 0

    first_date = pd.Timestamp(market["date"].iloc[0])
    for row in market.itertuples(index=False):
        date = pd.Timestamp(row.date)
        price = float(row.close)
        if date == first_date and initial_investment > 0:
            portfolio.contribute(initial_investment)
            events.append({
                "date": date, "event_type": "INITIAL_CONTRIBUTION",
                "amount": initial_investment, "price": None, "quantity": None,
                "reason": "FIRST_MARKET_OBSERVATION",
            })
        if date in contribution_dates:
            assert policy is not None
            portfolio.contribute(policy.amount)
            events.append({
                "date": date, "event_type": "CONTRIBUTION", "amount": policy.amount,
                "price": None, "quantity": None, "reason": "MONTHLY_FIRST_MARKET_DATE",
            })

        if strategy.code is StrategyCode.DELAYED_REENTRY and strategy.reentry_is_due(date):
            assert strategy.sell_date is not None
            waiting_days = (date - strategy.sell_date).days
            completed_waiting_days += waiting_days
            buy_quantity, buy_amount = portfolio.buy_all(price)
            events.append({
                "date": date, "event_type": "REENTRY", "amount": buy_amount,
                "price": price, "quantity": buy_quantity,
                "reason": "CALENDAR_MONTH_TARGET_REACHED",
            })
            strategy.finish_reentry()

        take_profit = strategy.take_profit_reached(
            price, portfolio.quantity, portfolio.average_purchase_price
        )
        if take_profit:
            quantity_before_sell = portfolio.quantity
            events.append({
                "date": date, "event_type": "TAKE_PROFIT", "amount": None,
                "price": price, "quantity": quantity_before_sell,
                "reason": f"CLOSE_GTE_AVERAGE_COST_X_{1 + strategy.take_profit_rate:.2f}",
            })
            sold_quantity, proceeds = portfolio.sell_all(price)
            events.append({
                "date": date, "event_type": "SELL", "amount": proceeds,
                "price": price, "quantity": sold_quantity, "reason": "TAKE_PROFIT",
            })

            if strategy.code is StrategyCode.IMMEDIATE_REENTRY:
                buy_quantity, buy_amount = portfolio.buy_all(price)
                events.append({
                    "date": date, "event_type": "REENTRY", "amount": buy_amount,
                    "price": price, "quantity": buy_quantity,
                    "reason": "IMMEDIATE_SAME_CLOSE",
                })
            elif strategy.code is StrategyCode.DELAYED_REENTRY:
                strategy.enter_waiting(date)

        if (
            not take_profit
            and strategy.state is StrategyState.INVESTED
            and portfolio.cash > 0
        ):
            buy_quantity, buy_amount = portfolio.buy_all(price)
            events.append({
                "date": date, "event_type": "BUY", "amount": buy_amount,
                "price": price, "quantity": buy_quantity, "reason": strategy.name,
            })

        position_value, portfolio_value = portfolio.value(price)
        states.append({
            "date": date, "market_price": price, "cash": portfolio.cash,
            "quantity": portfolio.quantity,
            "average_purchase_price": portfolio.average_purchase_price,
            "position_value": position_value, "portfolio_value": portfolio_value,
            "total_contribution": portfolio.total_contribution,
            "strategy_name": strategy.name, "strategy_state": strategy.state.value,
            "reentry_target_date": strategy.reentry_target_date,
        })

    open_waiting_days = 0
    if strategy.state is StrategyState.WAITING_REENTRY and strategy.sell_date is not None:
        open_waiting_days = (market["date"].iloc[-1] - strategy.sell_date).days

    return BacktestResult(
        daily_states=pd.DataFrame(states, columns=STATE_COLUMNS),
        events=pd.DataFrame(events, columns=EVENT_COLUMNS),
        metadata={
            "strategy_code": strategy.code.value,
            "strategy_name": strategy.name,
            "cash_waiting_days": completed_waiting_days + open_waiting_days,
            "completed_cash_waiting_days": completed_waiting_days,
            "open_cash_waiting_days": open_waiting_days,
            "final_strategy_state": strategy.state.value,
            "initial_investment": float(initial_investment),
            "monthly_contribution": float(monthly_contribution),
        },
    )
