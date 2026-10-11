from datetime import date
from dataclasses import FrozenInstanceError
from decimal import Decimal

import pandas as pd
import pytest

from zero_market_lab.asset_discovery.engine import ResearchRunConfig
from zero_market_lab.asset_discovery.rolling import (
    max_loss_streak, monthly_windows, recovery_days, run_s1_robustness,
    summarize_group, summarize_window,
)
from zero_market_lab.asset_discovery.paper_contract import PaperStrategyVersion
from zero_market_lab.simulator.models import Instrument
from zero_market_lab.simulator.strategy_family import FamilyConfig, FixedTakeProfitConfig, run_family


def frame(length=650):
    dates = pd.bdate_range("2023-01-02", periods=length)
    prices = [100 + index % 40 for index in range(length)]
    return pd.DataFrame({"date": [day.date() for day in dates], "open": prices,
                         "high": [price + 4 for price in prices],
                         "low": [price - 3 for price in prices],
                         "close": prices, "volume": [1000] * length})


def test_monthly_windows_use_complete_calendar_windows_and_prior_warmup():
    dates = frame().date.tolist()
    six = monthly_windows(dates, 6)
    year = monthly_windows(dates, 12)
    assert six and year and len(six) > len(year)
    assert all(first >= 100 and dates[first].day <= 3 for first, _ in six)
    assert all(dates[last] <= (pd.Timestamp(dates[first]).replace(day=1) +
                               pd.DateOffset(months=6) - pd.Timedelta(days=1)).date()
               for first, last in six)
    assert all((pd.Timestamp(dates[first]).replace(day=1) +
                pd.DateOffset(months=12) - pd.Timedelta(days=1)).date() <= dates[-1]
               for first, _ in year)


def test_positive_ratio_recovery_and_losing_streak():
    rows = [{"net_return": value, "final_capital": 500000 * (1 + value),
             "completed_trades": 1, "avg_holding_days": 2,
             "max_capital_lock_days_observed": 3, "max_recovery_days": 4,
             "open_recovery_days": 0, "profit_event_count": 1,
             "avg_days_between_profit_events": None,
             "positive_month_ratio": 0.5,
             "total_trading_cost": 10, "max_consecutive_losing_trades": 0,
             "max_consecutive_losing_months": 1}
            for value in (0.1, 0.2, -0.1, 0.05)]
    summary = summarize_group(rows, "KRW")
    assert summary["positive_window_ratio"] == 0.75
    assert summary["median_return"] == 0.07500000000000001
    assert recovery_days([100, 120, 110, 100, 121, 119]) == (3, 1)
    assert max_loss_streak([1, -2, -1, 0, -3]) == 2


def test_rolling_s1_fixed_targets_share_windows_and_charge_costs():
    prices = frame()
    cutoff = prices.date.iloc[-1]
    calls = []
    def load(symbol):
        calls.append(symbol)
        return prices, {"provider": "synthetic fixture", "adjustment": "UNADJUSTED"}
    report = run_s1_robustness([{"symbol": "005930", "name": "Fixture", "market": "KRX"}],
                               load, ResearchRunConfig(cutoff, initial_capital=Decimal(500000)))
    assert calls == ["005930"]
    asset = report["assets"][0]
    assert asset["status"] == "OK"
    assert {(group["period"], group["tp_pct"]) for group in asset["groups"]} == {
        ("6M", "3"), ("6M", "5"), ("1Y", "3"), ("1Y", "5")}
    for period in ("6M", "1Y"):
        dates_three = [(row["window_start"], row["window_end"]) for row in asset["windows"]
                       if row["period"] == period and row["tp_pct"] == "3"]
        dates_five = [(row["window_start"], row["window_end"]) for row in asset["windows"]
                      if row["period"] == period and row["tp_pct"] == "5"]
        assert dates_three == dates_five
    assert all(row["final_capital"] - row["initial_capital"] == row["net_profit"]
               for row in asset["windows"])
    assert any(row["total_trading_cost"] > 0 for row in asset["windows"])
    assert any(row["profit_event_count"] > 0 for row in asset["windows"])
    first = next(row for row in asset["windows"] if row["period"] == "6M" and row["tp_pct"] == "5")
    instrument = Instrument("KRX:005930", "005930", "Fixture", "KOREAN_EQUITY",
                            "KRX", "KRW", "Asia/Seoul", lot_size=Decimal(1),
                            tick_size=Decimal(1), currency_precision=0)
    reference = run_family(prices, instrument, date.fromisoformat(first["window_start"]),
                           date.fromisoformat(first["window_end"]),
                           FamilyConfig(initial_capital=Decimal(500000),
                                        s1=FixedTakeProfitConfig()),
                           strategies=("S1_FIXED_TAKE_PROFIT",))
    expected = reference["results"]["S1_FIXED_TAKE_PROFIT"]["metrics"]
    assert first["final_capital"] == expected["final_portfolio"]
    assert first["completed_trades"] == expected["completed_trades"]
    control = run_family(prices, instrument, date.fromisoformat(first["window_start"]),
                         date.fromisoformat(first["window_end"]),
                         FamilyConfig(initial_capital=Decimal(500000)),
                         strategies=("S0_BUY_AND_HOLD",))["results"]["S0_BUY_AND_HOLD"]["metrics"]
    assert first["s0_final_capital"] == control["final_portfolio"]
    assert first["s1_minus_s0_amount"] == pytest.approx(first["final_capital"]-control["final_portfolio"])
    assert asset["groups"][0]["s1_beats_s0_ratio"] is not None
    assert {(group["period"], group["strategy_id"]) for group in asset["filter_comparison"]} == {
        (period, strategy) for period in ("6M", "1Y") for strategy in
        ("S1_FIXED_TAKE_PROFIT", "S1_TREND_FILTERED_TAKE_PROFIT")}
    for period in ("6M", "1Y"):
        paired = [group for group in asset["filter_comparison"] if group["period"] == period]
        assert paired[0]["windows"] == paired[1]["windows"]
        assert all(group["average_cash_ratio"] is not None for group in paired)


def test_unaffordable_rolling_windows_do_not_inflate_return_ratios():
    example = {"period": "6M", "status": "NOT_AFFORDABLE", "net_return": 0,
               "final_capital": 500000}
    positive = {"period": "6M", "status": "POSITIVE", "net_return": 0.1,
                "s0_net_return": 0.05, "final_capital": 550000, "initial_capital": 500000,
                "net_profit": 50000, "completed_trades": 1, "total_trading_cost": 10,
                "profit_event_count": 1, "max_capital_lock_days_observed": 10,
                "max_recovery_days": 0, "open_recovery_days": 0,
                "max_consecutive_losing_trades": 0, "max_consecutive_losing_months": 0}
    group = summarize_group([example, positive], "KRW")
    assert group["windows"] == 2
    assert group["affordable_window_count"] == 1
    assert group["not_affordable_window_count"] == 1
    assert group["positive_window_ratio"] == 1
    assert group["s1_beats_s0_ratio"] == 1


def test_paper_strategy_version_is_an_immutable_record():
    version = PaperStrategyVersion("S1_FIXED_TAKE_PROFIT", "S1-v1", Decimal("-1"),
                                   Decimal("5"), "research-v2", "fixture-hash")
    with pytest.raises(FrozenInstanceError):
        version.take_profit_pct = Decimal("3")
