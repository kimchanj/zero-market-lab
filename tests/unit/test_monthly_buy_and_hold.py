"""Deterministic accounting checks for Strategy A."""

import pandas as pd
import pytest

from zero_market_lab.backtest import run_monthly_buy_and_hold
from zero_market_lab.portfolio import Portfolio


@pytest.fixture
def market():
    return pd.DataFrame({
        "date": ["2026-01-02", "2026-01-05", "2026-02-02"],
        "close": [100.0, 110.0, 125.0],
    })


@pytest.fixture
def result(market):
    return run_monthly_buy_and_hold(market, monthly_contribution=100.0)


def test_hand_calculated_daily_states(result):
    states = result.daily_states
    assert states.cash.tolist() == pytest.approx([0, 0, 0])
    assert states.quantity.tolist() == pytest.approx([1.0, 1.0, 1.8])
    assert states.portfolio_value.tolist() == pytest.approx([100, 110, 225])
    assert states.total_contribution.tolist() == pytest.approx([100, 100, 200])
    assert states.average_purchase_price.tolist() == pytest.approx([100, 100, 200 / 1.8])


def test_first_market_date_per_month_and_separate_events(result):
    events = result.events
    assert events.event_type.tolist() == ["CONTRIBUTION", "BUY", "CONTRIBUTION", "BUY"]
    assert events.date.dt.strftime("%Y-%m-%d").tolist() == [
        "2026-01-02", "2026-01-02", "2026-02-02", "2026-02-02",
    ]
    contribution = events[events.event_type == "CONTRIBUTION"]
    assert contribution.price.isna().all() and contribution.quantity.isna().all()
    buys = events[events.event_type == "BUY"]
    assert buys.quantity.tolist() == pytest.approx([1.0, 0.8])


def test_non_contribution_day_holds_quantity(result):
    states = result.daily_states
    assert states.loc[1, "quantity"] == pytest.approx(states.loc[0, "quantity"])
    assert not (result.events.date == pd.Timestamp("2026-01-05")).any()


def test_accounting_invariants_and_row_count(result, market):
    states = result.daily_states
    assert len(states) == len(market)
    assert (states.cash >= 0).all() and (states.quantity >= 0).all()
    assert states.position_value.tolist() == pytest.approx(
        (states.quantity * states.market_price).tolist()
    )
    assert states.portfolio_value.tolist() == pytest.approx(
        (states.cash + states.position_value).tolist()
    )
    assert (states.total_contribution.diff().fillna(states.total_contribution.iloc[0]) >= 0).all()
    assert "SELL" not in set(result.events.event_type)


def test_month_without_calendar_day_one_uses_first_observation():
    market = pd.DataFrame({"date": ["2026-03-03", "2026-03-04"], "close": [50, 60]})
    result = run_monthly_buy_and_hold(market, 100)
    assert result.events.iloc[0].date == pd.Timestamp("2026-03-03")
    assert result.daily_states.iloc[0].quantity == pytest.approx(2.0)


@pytest.mark.parametrize("amount", [0, -1, float("inf"), float("nan")])
def test_invalid_monthly_contribution(amount, market):
    with pytest.raises(ValueError):
        run_monthly_buy_and_hold(market, amount)


@pytest.mark.parametrize("bad_market", [
    pd.DataFrame({"date": ["2026-01-03", "2026-01-02"], "close": [100, 101]}),
    pd.DataFrame({"date": ["2026-01-02", "2026-01-02"], "close": [100, 101]}),
    pd.DataFrame({"date": ["2026-01-02"], "close": [0]}),
])
def test_invalid_market_data_is_rejected(bad_market):
    with pytest.raises(ValueError):
        run_monthly_buy_and_hold(bad_market, 100)


def test_portfolio_weighted_average_and_empty_buy():
    portfolio = Portfolio()
    assert portfolio.buy_all(100) == (0.0, 0.0)
    portfolio.contribute(100)
    portfolio.buy_all(100)
    portfolio.contribute(100)
    portfolio.buy_all(125)
    assert portfolio.quantity == pytest.approx(1.8)
    assert portfolio.average_purchase_price == pytest.approx(200 / 1.8)
