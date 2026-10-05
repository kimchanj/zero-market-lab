"""Case #01 A/B/C behavior and accounting invariants."""

import pandas as pd
import pytest

from zero_market_lab.backtest import run_case01_comparison, run_case01_strategy


REL = 1e-12
ABS = 1e-9


def approx(value):
    return pytest.approx(value, rel=REL, abs=ABS)


def market(dates, closes):
    return pd.DataFrame({"date": dates, "close": closes})


def events_on(result, date):
    rows = result.events[result.events.date == pd.Timestamp(date)]
    return rows.event_type.tolist()


def assert_invariants(source, result):
    states = result.daily_states
    assert len(states) == len(source)
    assert (states.cash >= -ABS).all()
    assert (states.quantity >= -ABS).all()
    assert states.position_value.tolist() == approx(
        (states.quantity * states.market_price).tolist()
    )
    assert states.portfolio_value.tolist() == approx(
        (states.cash + states.position_value).tolist()
    )
    assert (states.total_contribution.diff().fillna(states.total_contribution.iloc[0]) >= 0).all()


def test_strategy_b_take_profit_sell_reentry_order_and_reset():
    source = market(
        ["2026-01-02", "2026-01-05", "2026-01-06", "2026-01-07"],
        [100, 104, 105, 110],
    )
    result = run_case01_strategy(source, 100, "B")
    assert events_on(result, "2026-01-06") == ["TAKE_PROFIT", "SELL", "REENTRY"]
    day = result.daily_states.iloc[2]
    assert day.portfolio_value == approx(105)
    assert day.quantity == approx(1)
    assert day.cash == approx(0)
    assert day.average_purchase_price == approx(105)
    sell = result.events[result.events.event_type == "SELL"].iloc[0]
    reentry = result.events[result.events.event_type == "REENTRY"].iloc[0]
    assert sell.price == reentry.price == approx(105)
    assert sell.amount == reentry.amount == approx(105)
    assert_invariants(source, result)


def test_strategy_a_and_b_control_invariant_every_day():
    source = market(
        ["2026-01-02", "2026-01-06", "2026-02-02", "2026-02-10", "2026-03-02"],
        [100, 105, 110, 120, 130],
    )
    results = run_case01_comparison(source, 100)
    a, b = results["A"].daily_states, results["B"].daily_states
    assert a.portfolio_value.tolist() == approx(b.portfolio_value.tolist())
    assert a.quantity.tolist() == approx(b.quantity.tolist())
    assert a.cash.tolist() == approx(b.cash.tolist())
    assert not a.average_purchase_price.equals(b.average_purchase_price)
    assert "TAKE_PROFIT" not in set(results["A"].events.event_type)
    assert "TAKE_PROFIT" in set(results["B"].events.event_type)


def test_contribution_day_take_profit_includes_new_cash_in_b_reentry():
    source = market(["2026-01-02", "2026-02-02"], [100, 105])
    results = run_case01_comparison(source, 100)
    b = results["B"]
    assert events_on(b, "2026-02-02") == [
        "CONTRIBUTION", "TAKE_PROFIT", "SELL", "REENTRY",
    ]
    assert b.daily_states.iloc[-1].quantity == approx(1 + 100 / 105)
    assert b.daily_states.iloc[-1].portfolio_value == approx(205)
    assert results["A"].daily_states.iloc[-1].quantity == approx(
        b.daily_states.iloc[-1].quantity
    )


def test_strategy_c_waits_accumulates_contribution_and_reenters():
    source = market(
        ["2026-01-02", "2026-01-10", "2026-02-02", "2026-02-10", "2026-02-11"],
        [100, 105, 110, 120, 121],
    )
    result = run_case01_strategy(source, 100, "C")
    states = result.daily_states
    assert events_on(result, "2026-01-10") == ["TAKE_PROFIT", "SELL"]
    assert states.iloc[1].strategy_state == "WAITING_REENTRY"
    assert states.iloc[1].cash == approx(105)
    assert events_on(result, "2026-02-02") == ["CONTRIBUTION"]
    assert states.iloc[2].cash == approx(205)
    assert states.iloc[2].quantity == approx(0)
    assert events_on(result, "2026-02-10") == ["REENTRY"]
    assert states.iloc[3].quantity == approx(205 / 120)
    assert states.iloc[3].cash == approx(0)
    assert states.iloc[3].average_purchase_price == approx(120)
    assert states.iloc[3].strategy_state == "INVESTED"
    assert result.metadata["cash_waiting_days"] == 31
    assert_invariants(source, result)


@pytest.mark.parametrize(
    "sell_date,target_date,first_market_date",
    [
        ("2026-01-31", "2026-02-28", "2026-03-02"),
        ("2028-01-31", "2028-02-29", "2028-03-01"),
        ("2026-03-30", "2026-04-30", "2026-05-01"),
    ],
)
def test_c_calendar_month_clamp_and_first_observation_after_target(
    sell_date, target_date, first_market_date
):
    initial_date = (pd.Timestamp(sell_date) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    source = market([initial_date, sell_date, first_market_date], [100, 105, 110])
    result = run_case01_strategy(source, 100, "C")
    sold_state = result.daily_states.iloc[1]
    assert sold_state.reentry_target_date == pd.Timestamp(target_date)
    assert events_on(result, first_market_date) == ["CONTRIBUTION", "REENTRY"]


def test_c_contribution_precedes_reentry_on_same_day():
    source = market(
        ["2025-12-01", "2026-01-02", "2026-02-02"],
        [100, 105, 120],
    )
    result = run_case01_strategy(source, 100, "C")
    assert events_on(result, "2026-01-02") == [
        "CONTRIBUTION", "TAKE_PROFIT", "SELL",
    ]
    assert events_on(result, "2026-02-02") == ["CONTRIBUTION", "REENTRY"]
    reentry = result.events[
        (result.events.date == pd.Timestamp("2026-02-02"))
        & (result.events.event_type == "REENTRY")
    ].iloc[0]
    assert reentry.amount == approx(305)
    assert result.daily_states.iloc[-1].quantity == approx(305 / 120)


def test_c_dataset_ends_before_reentry_and_preserves_cash():
    source = market(
        ["2026-01-02", "2026-01-10", "2026-02-02"],
        [100, 105, 110],
    )
    result = run_case01_strategy(source, 100, "C")
    final = result.daily_states.iloc[-1]
    assert final.strategy_state == "WAITING_REENTRY"
    assert final.reentry_target_date == pd.Timestamp("2026-02-10")
    assert final.quantity == approx(0)
    assert final.cash == approx(205)
    assert "REENTRY" not in set(result.events.event_type)
    assert result.metadata["completed_cash_waiting_days"] == 0
    assert result.metadata["open_cash_waiting_days"] == 23


def test_comparison_runner_returns_independent_a_b_c_results():
    source = market(
        ["2026-01-02", "2026-01-10", "2026-02-02", "2026-02-10"],
        [100, 105, 110, 120],
    )
    results = run_case01_comparison(source, 100)
    assert list(results) == ["A", "B", "C"]
    for code, result in results.items():
        assert result.metadata["strategy_code"] == code
        assert_invariants(source, result)
    assert results["A"].daily_states is not results["B"].daily_states
    assert results["B"].daily_states is not results["C"].daily_states


def test_portfolio_sell_resets_quantity_and_average_cost_then_reentry_restarts_cost():
    source = market(["2026-01-02", "2026-01-10"], [100, 105])
    result = run_case01_strategy(source, 100, "B")
    assert result.daily_states.iloc[-1].quantity == approx(1)
    assert result.daily_states.iloc[-1].average_purchase_price == approx(105)
    assert result.events.event_type.tolist() == [
        "CONTRIBUTION", "BUY", "TAKE_PROFIT", "SELL", "REENTRY",
    ]
