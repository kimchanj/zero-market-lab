"""STEP 3: adversarial deterministic verification of the Strategy A engine."""

import pandas as pd
import pytest

from zero_market_lab.backtest import run_monthly_buy_and_hold


REL_TOLERANCE = 1e-12
ABS_TOLERANCE = 1e-9


def approx(expected):
    return pytest.approx(expected, rel=REL_TOLERANCE, abs=ABS_TOLERANCE)


def frame(dates, closes):
    return pd.DataFrame({"date": dates, "close": closes})


def assert_accounting_invariants(market, result, monthly_contribution):
    states, events = result.daily_states, result.events
    represented_months = pd.to_datetime(market["date"]).dt.to_period("M").nunique()
    contributions = events[events.event_type == "CONTRIBUTION"]
    buys = events[events.event_type == "BUY"]

    assert len(states) == len(market)
    assert len(contributions) == len(buys) == represented_months
    assert "SELL" not in set(events.event_type)
    assert (states.cash >= -ABS_TOLERANCE).all()
    assert (states.quantity >= -ABS_TOLERANCE).all()
    assert states.position_value.tolist() == approx(
        (states.quantity * states.market_price).tolist()
    )
    assert states.portfolio_value.tolist() == approx(
        (states.cash + states.position_value).tolist()
    )
    assert (states.total_contribution.diff().fillna(states.total_contribution.iloc[0]) >= 0).all()
    assert states.iloc[-1].total_contribution == approx(
        represented_months * monthly_contribution
    )

    for _, day_events in events.groupby("date", sort=False):
        assert day_events.event_type.tolist() == ["CONTRIBUTION", "BUY"]


def contribution_dates(result):
    return result.events.loc[
        result.events.event_type == "CONTRIBUTION", "date"
    ].dt.strftime("%Y-%m-%d").tolist()


def test_month_boundary_uses_each_months_first_observation():
    market = frame(["2026-01-30", "2026-02-02", "2026-02-03"], [100, 110, 120])
    result = run_monthly_buy_and_hold(market, 100)
    assert contribution_dates(result) == ["2026-01-30", "2026-02-02"]
    assert_accounting_invariants(market, result, 100)


def test_missing_calendar_day_one_uses_first_observation():
    market = frame(["2026-03-02", "2026-03-03"], [100, 101])
    result = run_monthly_buy_and_hold(market, 100)
    assert contribution_dates(result) == ["2026-03-02"]


def test_year_boundary_has_one_contribution_per_represented_month():
    market = frame(["2026-12-31", "2027-01-04"], [100, 105])
    result = run_monthly_buy_and_hold(market, 100)
    assert contribution_dates(result) == ["2026-12-31", "2027-01-04"]
    assert_accounting_invariants(market, result, 100)


def test_single_observation_month_is_contribution_day():
    market = frame(["2026-04-15"], [80])
    result = run_monthly_buy_and_hold(market, 100)
    assert contribution_dates(result) == ["2026-04-15"]
    assert result.daily_states.iloc[0].quantity == approx(1.25)


def test_contribution_precedes_buy_and_state_contains_post_buy_values():
    market = frame(["2026-01-02"], [100])
    result = run_monthly_buy_and_hold(market, 100)
    assert result.events.event_type.tolist() == ["CONTRIBUTION", "BUY"]
    state = result.daily_states.iloc[0]
    assert state.cash == approx(0)
    assert state.quantity == approx(1)
    assert state.portfolio_value == approx(100)


def test_price_spike_and_crash_change_only_valuation():
    market = frame(
        ["2026-01-02", "2026-01-05", "2026-01-06"],
        [100, 200, 50],
    )
    result = run_monthly_buy_and_hold(market, 100)
    states = result.daily_states
    assert states.portfolio_value.tolist() == approx([100, 200, 50])
    for column in ["cash", "quantity", "average_purchase_price", "total_contribution"]:
        assert states[column].nunique() == 1
    assert result.events.date.nunique() == 1
    assert_accounting_invariants(market, result, 100)


def test_multi_month_weighted_average_cost():
    market = frame(["2026-01-02", "2026-02-02", "2026-03-02"], [100, 200, 50])
    result = run_monthly_buy_and_hold(market, 100)
    states = result.daily_states
    assert states.quantity.tolist() == approx([1.0, 1.5, 3.5])
    assert states.average_purchase_price.tolist() == approx([100, 200 / 1.5, 300 / 3.5])
    assert states.total_contribution.tolist() == approx([100, 200, 300])
    assert_accounting_invariants(market, result, 100)


def test_non_contribution_days_preserve_accounting_state():
    market = frame(
        ["2026-05-04", "2026-05-05", "2026-05-06", "2026-05-07"],
        [100, 120, 80, 140],
    )
    result = run_monthly_buy_and_hold(market, 100)
    states = result.daily_states
    for column in ["cash", "quantity", "average_purchase_price", "total_contribution"]:
        assert states[column].tolist() == approx([states[column].iloc[0]] * len(states))
    assert states.position_value.nunique() == len(states)
    assert states.portfolio_value.nunique() == len(states)
    assert result.events.event_type.tolist() == ["CONTRIBUTION", "BUY"]


def test_ten_year_deterministic_business_day_run():
    dates = pd.bdate_range("2017-01-02", "2026-12-31")
    index = pd.RangeIndex(len(dates))
    closes = 100.0 + index * 0.02 + (index % 251) * 0.05
    market = pd.DataFrame({"date": dates, "close": closes})
    result = run_monthly_buy_and_hold(market, 500)
    assert len(market) > 2_500
    assert_accounting_invariants(market, result, 500)


def test_repeated_runs_are_identical():
    dates = pd.bdate_range("2024-01-02", "2026-12-31")
    market = pd.DataFrame({
        "date": dates,
        "close": 75.0 + pd.RangeIndex(len(dates)) * 0.03125,
    })
    first = run_monthly_buy_and_hold(market, 123.45)
    second = run_monthly_buy_and_hold(market, 123.45)
    pd.testing.assert_frame_equal(first.daily_states, second.daily_states, check_exact=True)
    pd.testing.assert_frame_equal(first.events, second.events, check_exact=True)
    pd.testing.assert_series_equal(
        first.daily_states.iloc[-1], second.daily_states.iloc[-1], check_exact=True
    )


@pytest.mark.parametrize(
    "bad_market",
    [
        pd.DataFrame(columns=["date", "close"]),
        frame(["2026-01-02", "2026-01-02"], [100, 101]),
        frame(["2026-01-03", "2026-01-02"], [100, 101]),
        frame(["2026-01-02"], [None]),
        frame(["2026-01-02"], [0]),
        frame(["2026-01-02"], [-1]),
    ],
    ids=["empty", "duplicate-date", "unsorted-date", "null-close", "zero-close", "negative-close"],
)
def test_invalid_input_fails_fast_without_correction(bad_market):
    with pytest.raises(ValueError, match="Invalid market data"):
        run_monthly_buy_and_hold(bad_market, 100)
