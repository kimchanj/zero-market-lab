"""Frozen phase failure analysis never changes labels or feeds outcomes into snapshots."""

import json

import pandas as pd
import pytest

from scripts.analyze_phase_failures import (asof_features, cluster_events, diff_table,
                                            snapshot, verify_baseline)


def test_grouping_preserves_raw_events_and_uses_trading_day_gap():
    daily = {"005930": pd.DataFrame({"date": pd.bdate_range("2025-01-01", periods=80).strftime("%Y-%m-%d")})}
    events = pd.DataFrame({"symbol": ["005930"] * 3,
                           "date": daily["005930"].iloc[[0, 20, 60]]["date"].tolist(),
                           "group": ["FALSE_SPRING", "SPRING_SUCCESS", "FALSE_SPRING"]})
    # Restrict the fixed six-symbol loop to the one test symbol without touching production config.
    import scripts.analyze_phase_failures as analysis
    original = analysis.SYMBOLS
    try:
        analysis.SYMBOLS = ("005930",)
        clusters = cluster_events(events, daily, gap=30)
    finally:
        analysis.SYMBOLS = original
    assert len(events) == 3 and len(clusters) == 2
    assert clusters.iloc[0]["event_count"] == 2
    assert clusters.iloc[0]["groups"] == {"FALSE_SPRING": 1, "SPRING_SUCCESS": 1}


def test_diff_keeps_censored_out_of_group_denominator():
    frame = pd.DataFrame({"group": ["SPRING_SUCCESS", "FALSE_SPRING", "RIGHT_CENSORED"],
                          "signal": [0.2, 0.1, 100.0], "recent_higher_low": [True, False, True]})
    for field in ("recent_higher_high", "breakout_20d", "ma200_slope_flat_or_improving",
                  "ma200_slope_positive", "breakdown_below_ma50", "ma200_filter_pass",
                  "ma50_above_ma200"):
        frame[field] = False
    result = diff_table(frame, "SPRING_SUCCESS", "FALSE_SPRING", ("signal",))
    numeric = result.loc[result["feature"] == "signal"].iloc[0]
    boolean = result.loc[result["feature"] == "recent_higher_low"].iloc[0]
    assert numeric["a_count"] == numeric["b_count"] == 1
    assert numeric["median_difference"] == pytest.approx(0.1)
    assert boolean["a_true_rate"] == 1 and boolean["b_true_rate"] == 0


def test_asof_snapshot_ignores_future_and_no_outcomes_enter_features():
    dates = pd.bdate_range("2023-01-02", periods=280)
    close = pd.Series(range(100, 380), dtype=float)
    raw = pd.DataFrame({"date": dates, "open": close, "high": close + 1,
                        "low": close - 1, "close": close})
    full = asof_features(raw)
    cut = asof_features(raw.iloc[:260])
    day = dates[259].strftime("%Y-%m-%d")
    pd.testing.assert_series_equal(full.loc[day], cut.loc[day], check_names=False)
    evidence = {key: None for key in ("recent_higher_low", "recent_higher_high", "breakout_20d")}
    daily = pd.DataFrame({"date": [day], "evidence": [json.dumps(evidence)],
                          "ma200_entry_filter_allowed_next_day": [True]})
    a = snapshot("SYN", day, daily, full, 10, kind="spring")
    b = snapshot("SYN", day, daily, cut, 10, kind="spring")
    assert a == b
    assert not any("return_" in key or "outcome" in key for key in a)


def test_baseline_mismatch_halts_before_output(tmp_path):
    (tmp_path / "summary.json").write_text(json.dumps({"assets": [], "errors": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="asset set"):
        verify_baseline(tmp_path)
