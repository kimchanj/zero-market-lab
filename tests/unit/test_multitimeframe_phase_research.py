"""STEP 3 research contexts are causal, slower/faster by construction, and outcome-free."""

import numpy as np
import pandas as pd
import pytest

from scripts.research_multitimeframe_phase import (combined_context, confirmed_context,
                                                    churn_count, episodes, event_context,
                                                    lead_lag, matrix, raw_context)


def prices(close):
    return pd.DataFrame({"date": pd.bdate_range("2022-01-03", periods=len(close)),
                         "close": np.asarray(close, dtype=float)})


def test_research_quadrants_and_confirmation():
    assert raw_context(110, 100, 99) == "SUMMER"
    assert raw_context(90, 100, 101) == "WINTER"
    assert raw_context(110, 100, 101) == "SPRING"
    assert raw_context(90, 100, 99) == "AUTUMN"
    assert raw_context(90, 100, 100) == "AUTUMN"
    flat = prices([100] * 12 + [120] * 8)
    layer = confirmed_context(flat, ma_window=5, slope_lag=2, confirmation=3, prefix="child")
    assert (layer.iloc[:6]["child_phase"] == "UNKNOWN").all()
    assert "SUMMER" in layer["child_phase"].tolist()
    assert layer.iloc[-1]["child_phase"] == "AUTUMN"  # flat average is not upward trend
    assert all(row["child_days"] >= 1 for _, row in layer.iterrows())


def test_combined_prefix_invariance_and_contract_excludes_outcomes():
    c = np.r_[np.linspace(200, 100, 260), np.linspace(100, 180, 180)]
    full = combined_context(prices(c), symbol="SYN", candidate_id="A")
    prefix = combined_context(prices(c[:350]), symbol="SYN", candidate_id="A")
    pd.testing.assert_frame_equal(full.iloc[:350].reset_index(drop=True), prefix)
    assert "forward_20d_return" not in full and "outcome" not in full
    assert full["rule_config_hash"].nunique() == 1
    changed_future = combined_context(prices(np.r_[c[:350], np.linspace(1000, 100, 90)]),
                                      symbol="SYN", candidate_id="A")
    pd.testing.assert_frame_equal(full.iloc[:350].reset_index(drop=True),
                                  changed_future.iloc[:350].reset_index(drop=True))


def test_duration_churn_lead_lag_and_event_join():
    dates = pd.bdate_range("2025-01-01", periods=9).strftime("%Y-%m-%d")
    states = ["SUMMER", "SUMMER", "AUTUMN", "AUTUMN", "SUMMER",
              "SUMMER", "WINTER", "WINTER", "WINTER"]
    p = ["SUMMER"] * 6 + ["AUTUMN"] * 3
    combined = pd.DataFrame({"symbol": "SYN", "date": dates, "close": np.arange(100, 109),
                             "parent_phase": p, "child_phase": states,
                             "parent_transition": [None]*6+["SUMMER->AUTUMN"]+[None]*2,
                             "child_transition": ["UNKNOWN->SUMMER", None, "SUMMER->AUTUMN", None,
                                                  "AUTUMN->SUMMER", None, "SUMMER->WINTER", None, None],
                             "parent_days": range(1, 10), "child_days": range(1, 10),
                             "parent_ma": [90.0]*9, "child_ma": [95.0]*9,
                             "parent_ma_slope_fraction": [0.01]*9,
                             "child_ma_slope_fraction": [0.01]*9})
    combined["combined_state"] = combined["parent_phase"] + "+" + combined["child_phase"]
    parts = episodes(combined, "child")
    assert parts["trading_days"].tolist() == [2, 2, 2, 3]
    assert parts.iloc[-1]["right_censored"]
    assert churn_count(combined, "child")["summer_autumn_summer_60d"] == 1
    leads = lead_lag(combined)
    assert leads.loc[leads["child_date"] == dates[2], "lag_trading_days"].iloc[0] == 4
    assert leads.loc[leads["child_date"] == dates[2], "same_direction_lag_trading_days"].iloc[0] == 4
    event = {"symbol": "SYN", "date": dates[2], "outcome": "FALSE_AUTUMN",
             "days_to_outcome": 2, "return_20d": None, "return_60d": None,
             "return_120d": None, "max_forward_drawdown_120d": None}
    joined = event_context([event], combined, kind="AUTUMN")
    assert joined.iloc[0]["parent_phase"] == "SUMMER"
    assert joined.iloc[0]["outcome"] == "FALSE_AUTUMN"
    assert "outcome" not in combined


def test_matrix_never_crosses_symbol_boundaries():
    rows = []
    for symbol, price in (("A", 100.0), ("B", 1000.0)):
        for i in range(125):
            rows.append({"symbol": symbol, "date": f"2025-{i:03d}", "close": price,
                         "parent_phase": "SUMMER", "child_phase": "SUMMER",
                         "combined_state": "SUMMER+SUMMER"})
    report = matrix(pd.DataFrame(rows))
    assert report.iloc[0]["trading_days"] == 250
    assert report.iloc[0]["median_forward_20d"] == pytest.approx(0)
    assert report.iloc[0]["median_forward_drawdown_120d"] == pytest.approx(0)
