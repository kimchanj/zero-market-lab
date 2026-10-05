"""Minimal daily engine for Strategy A; no sell, cost or performance analytics."""

from dataclasses import dataclass

import pandas as pd

from zero_market_lab.market_data.validation import validate
from zero_market_lab.portfolio import Portfolio
from zero_market_lab.strategies import BuyAndHoldStrategy

from .contribution import MonthlyContributionPolicy


STATE_COLUMNS = [
    "date", "market_price", "cash", "quantity", "average_purchase_price",
    "position_value", "portfolio_value", "total_contribution",
]
EVENT_COLUMNS = ["date", "event_type", "amount", "price", "quantity", "reason"]


@dataclass(frozen=True)
class BacktestResult:
    daily_states: pd.DataFrame
    events: pd.DataFrame


def run_monthly_buy_and_hold(
    market_data: pd.DataFrame,
    monthly_contribution: float,
) -> BacktestResult:
    """Contribute and buy at each represented month's first close."""
    validation = validate(market_data)
    if not validation.passed:
        raise ValueError("Invalid market data: " + "; ".join(validation.errors))

    market = market_data.loc[:, ["date", "close"]].copy()
    market["date"] = pd.to_datetime(market["date"])
    market["close"] = pd.to_numeric(market["close"])

    policy = MonthlyContributionPolicy(monthly_contribution)
    contribution_dates = policy.dates(market["date"])
    strategy = BuyAndHoldStrategy()
    portfolio = Portfolio()
    states: list[dict] = []
    events: list[dict] = []

    for row in market.itertuples(index=False):
        date = pd.Timestamp(row.date)
        price = float(row.close)
        if date in contribution_dates:
            portfolio.contribute(policy.amount)
            events.append({
                "date": date, "event_type": "CONTRIBUTION", "amount": policy.amount,
                "price": None, "quantity": None, "reason": "MONTHLY_FIRST_MARKET_DATE",
            })

        if strategy.wants_buy(portfolio.cash):
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
        })

    return BacktestResult(
        daily_states=pd.DataFrame(states, columns=STATE_COLUMNS),
        events=pd.DataFrame(events, columns=EVENT_COLUMNS),
    )
