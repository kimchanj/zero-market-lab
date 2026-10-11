"""STEP 4 features are causal descriptions; frozen event outcomes stay separate."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.research_transition_dynamics import (BOOLEAN_FEATURES, FEATURES,
                                                  categorical_comparison, event_snapshot,
                                                  feature_frame, numeric_comparison, run)


def market(close):
    c = np.asarray(close, dtype=float)
    return pd.DataFrame({"date": pd.bdate_range("2022-01-03", periods=len(c)),
                         "close": c, "high": c * 1.01, "low": c * .99})


def test_slope_change_and_causal_prefix():
    closes = np.r_[np.linspace(200, 100, 260), np.linspace(100, 150, 60)]
    full = feature_frame(market(closes))
    prefix = feature_frame(market(closes[:290]))
    pd.testing.assert_frame_equal(full.iloc[:290].reset_index(drop=True), prefix)
    t = 280
    assert full.loc[t, "ma200_slope_change_10d"] == pytest.approx(
        full.loc[t, "ma200_slope"] - full.loc[t-10, "ma200_slope"])
    assert full.loc[t, "ma50_slope_change_5d"] == pytest.approx(
        full.loc[t, "ma50_slope"] - full.loc[t-5, "ma50_slope"])
    assert full.loc[t, "price_minus_ma200_change_10d"] == pytest.approx(
        full.loc[t, "price_minus_ma200_pct"] - full.loc[t-10, "price_minus_ma200_pct"])
    assert pd.isna(full.loc[198, "ma200_slope"])
    assert "group" not in full and "return_20d" not in full


def test_persistence_drawdown_velocity_and_recovery_failure():
    c = np.r_[np.full(270, 100.0), [110, 110, 80, 80, 80, 110, 80, 80, 80, 80]]
    f = feature_frame(market(c))
    assert f.loc[271, "recovery_persistence_days"] >= 1
    assert f.loc[273, "recovery_persistence_days"] == 0
    assert f.loc[273, "failed_recovery_count_10d"] >= 1
    assert f.loc[272, "drawdown_change_5d"] < 0
    assert f.loc[272, "drawdown_change_10d"] == pytest.approx(
        f.loc[272, "drawdown_from_52w_high"] - f.loc[262, "drawdown_from_52w_high"])
    assert pd.isna(f.loc[250, "drawdown_from_52w_high"])
    assert f.loc[272, "drawdown_worsening_10d"] == True


def test_event_snapshot_excludes_future_outcome_and_group_stats():
    f = feature_frame(market(np.linspace(100, 200, 300)))
    day = pd.Series({"symbol": "SYN", "date": f.loc[280, "date"],
                     "available_at": f.loc[280, "date"] + " close",
                     "current_phase": "SPRING_CANDIDATE", "previous_phase": "WINTER"})
    context = pd.DataFrame({"date": [day["date"]], "parent_phase": ["WINTER"],
                            "child_phase": ["SUMMER"]})
    snap = event_snapshot(day, f, context)
    assert all(key in snap for key in FEATURES + BOOLEAN_FEATURES)
    assert "group" not in snap and "days_to_outcome" not in snap
    assert snap["parent_phase"] == "WINTER"
    data = pd.DataFrame([{**snap, "group": "A"}, {**snap, "group": "B"}])
    diff = numeric_comparison(data, "A", "B", ("ma200_slope_change_10d",))
    assert diff.iloc[0]["median_difference"] == pytest.approx(0)
    cats = categorical_comparison(data, "A", "B")
    assert cats.loc[cats["feature"] == "parent_phase", "ratio_difference"].iloc[0] == 0


def test_frozen_events_and_deterministic_output(tmp_path):
    root = Path(__file__).resolve().parents[2]
    source = root / "artifacts/fecm-price-phase-v1-20261010-validated"
    context = root / "artifacts/fecm-multitimeframe-step3"
    if not source.exists() or not context.exists():
        pytest.skip("Local non-redistributable Development Set unavailable")
    first = run(source, context, tmp_path / "one")
    second = run(source, context, tmp_path / "two")
    assert first == second
    assert first["spring_groups"] == {"SPRING_SUCCESS": 16, "FALSE_SPRING": 59}
    assert first["autumn_groups"] == {"AUTUMN_TO_WINTER": 12,
                                      "AUTUMN_TO_SUMMER": 67,
                                      "UNRESOLVED": 7, "RIGHT_CENSORED": 1}
    for name, digest in first["output_sha256"].items():
        assert digest == second["output_sha256"][name]
