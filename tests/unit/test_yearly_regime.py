from datetime import date
from decimal import Decimal

import pandas as pd

from zero_market_lab.asset_discovery.engine import ResearchRunConfig
from zero_market_lab.asset_discovery.regime import classify_historical_window
from zero_market_lab.asset_discovery.yearly import CORE_STRATEGIES, run_yearly_research


def price_frame(prices, start="2025-01-01"):
    days = pd.bdate_range(start, periods=len(prices))
    return pd.DataFrame({"date": [day.date() for day in days],
                         "open": prices, "high": [price + 5 for price in prices],
                         "low": [price - 5 for price in prices], "close": prices,
                         "volume": [1000] * len(prices)})


def test_regime_rule_bull_sideways_bear_and_no_future_leakage():
    for prices, expected in [([1000 + i for i in range(250)], "BULL"),
                             ([1000] * 250, "SIDEWAYS"),
                             ([1000 - i for i in range(250)], "BEAR")]:
        frame = price_frame(prices)
        end = frame.iloc[-1].date
        original = classify_historical_window(frame, date(2025, 1, 1), end)
        assert original["label"] == expected
        future = price_frame([100000], start="2026-01-01")
        assert classify_historical_window(pd.concat([frame, future]),
                                          date(2025, 1, 1), end) == original


def test_yearly_windows_reset_capital_and_mark_partial_boundaries():
    frame = price_frame([10000 + index for index in range(1400)], start="2020-10-01")
    cutoff = frame.iloc[-1].date
    calls = []
    def loader(symbol):
        calls.append(symbol)
        return frame, {"provider": "fixture", "adjustment": "UNADJUSTED"}
    report = run_yearly_research([{"symbol": "005930", "name": "Fixture", "market": "KRX"}],
                                 loader, ResearchRunConfig(cutoff))
    assert calls == ["005930"]
    assert report["assets"][0]["status"] == "OK"
    assert {row["year"] for row in report["years"]} == set(range(2021, cutoff.year + 1))
    assert report["years"][0]["partial_start"]
    assert report["years"][-1]["partial_end"]
    full_years = sum(row["status"] == "OK" and not row["partial_start"]
                     and not row["partial_end"] for row in report["years"])
    s1_samples = sum(row["sample_count"] for row in report["regime_summary"]
                     if row["strategy_id"] == "S1_FIXED_TAKE_PROFIT")
    assert s1_samples == full_years
    for row in report["years"]:
        assert set(row["strategies"]) == set(CORE_STRATEGIES)
        assert row["strategies"]["S0_BUY_AND_HOLD"]["initial_capital"] == 500000
        assert row["excess_return_vs_s0"]["S1_FIXED_TAKE_PROFIT"] == (
            row["strategies"]["S1_FIXED_TAKE_PROFIT"]["net_return"] -
            row["strategies"]["S0_BUY_AND_HOLD"]["net_return"])


def test_cash_only_year_is_excluded_from_regime_performance_summary():
    frame = price_frame([10000 + index for index in range(350)], start="2020-10-01")
    result = run_yearly_research([{"symbol": "005930", "name": "Fixture", "market": "KRX"}],
                                 lambda _: (frame, {"provider": "fixture"}),
                                 ResearchRunConfig(date(2021, 12, 31), initial_capital=Decimal(1)))
    assert result["years"][0]["status"] == "NO_POSITION_CAPITAL"
    assert result["regime_summary"] == []
