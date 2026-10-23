"""Frozen STEP 9 analysis definitions on synthetic observations."""

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from zero_market_lab.research.transit_analysis import (
    StudyConfig, _adjacent_return, asset_windows, bootstrap_interval, context_on_dates,
    gate_intervals, price_metrics, random_control, summarize,
)
from zero_market_lab.transit.calendar import at_market_close


ROOT = Path(__file__).resolve().parents[2]


def test_gate_intervals_are_original_half_open_windows_and_partial_edges():
    rows = gate_intervals("2026-10-01", "2026-10-31")
    assert rows and all(rows[i]["end_utc"] == rows[i + 1]["start_utc"]
                        for i in range(len(rows) - 1))
    assert rows[0]["complete"] is False
    assert rows[-1]["complete"] is False
    assert any(row["gate"] == 32 and row["complete"] for row in rows)
    assert len({(row["year"], row["gate"]) for row in rows}) == len(rows)


def test_return_drawdown_runup_daily_volatility_and_volume_are_within_window():
    result = price_metrics(np.array([100, 110, 90]), np.array([10, 20, 15]))
    assert result["return_pct"] == pytest.approx(-10)
    assert result["max_drawdown_pct"] == pytest.approx((90 / 110 - 1) * 100)
    assert result["max_runup_pct"] == pytest.approx(10)
    assert result["daily_volatility_pct"] == pytest.approx(np.std([10, (90 / 110 - 1) * 100]))
    assert result["positive_day_ratio"] == result["negative_day_ratio"] == .5
    assert result["volume_change_pct"] == 50
    assert price_metrics(np.array([100]))["daily_volatility_pct"] is None


def test_context_join_respects_lag_staleness_and_never_fills_missing_with_zero():
    frame = pd.DataFrame({"date": ["2026-10-01", "2026-10-02", "2026-10-10"],
                          "value": [10., 20., 30.]})
    snapshots = {key: (frame, {}) if key == "VIX" else None
                 for key in ("VIX", "US10Y", "USDKRW", "BROAD_USD")}
    joined = context_on_dates(ROOT, ["2026-10-02", "2026-10-10", "2026-10-25"],
                              "KRW", snapshots)
    assert joined["2026-10-02"]["VIX"]["value"] == 10
    assert joined["2026-10-02"]["VIX"]["observation_date"] == "2026-10-01"
    assert joined["2026-10-10"]["VIX"]["value"] == 20
    assert joined["2026-10-25"]["VIX"]["status"] == "STALE_OBSERVATION"
    assert joined["2026-10-25"]["VIX"]["value"] is None
    assert joined["2026-10-02"]["US10Y"]["value"] is None


def test_same_season_random_control_is_deterministic_and_future_independent():
    days = [(date(2024, 7, 1) + timedelta(days=index)).isoformat() for index in range(100)]
    frame = pd.DataFrame({"date": days, "close": 100 + np.arange(100, dtype=float)})
    positions = list(range(45, 50))
    config = StudyConfig("2024-07-01", "2024-10-08")
    a = random_control(frame, positions, year=2024, midpoint=date(2024, 8, 17),
                       config=config, key="synthetic")
    b = random_control(frame, positions, year=2024, midpoint=date(2024, 8, 17),
                       config=config, key="synthetic")
    assert a == b and a["random_candidate_count"] > 0
    extended = pd.concat([frame, pd.DataFrame({"date": ["2025-01-01"], "close": [100000.]})],
                         ignore_index=True)
    c = random_control(extended, positions, year=2024, midpoint=date(2024, 8, 17),
                       config=config, key="synthetic")
    assert a == c
    assert 0 <= a["random_return_percentile"] <= 100


def test_random_control_requires_same_length_and_available_season():
    frame = pd.DataFrame({"date": ["2024-01-01", "2024-01-02", "2024-01-03"],
                          "close": [10., 11., 12.]})
    result = random_control(frame, [0, 1, 2], year=2024, midpoint=date(2024, 1, 2),
                            config=StudyConfig("2024-01-01", "2024-01-03"), key="none")
    assert result["random_candidate_count"] == 0
    assert result["random_return_percentile"] is None


def test_random_candidate_pool_excludes_gate_overlap_and_out_of_season_bars():
    days = [(date(2024, 1, 1) + timedelta(days=index)).isoformat() for index in range(20)]
    frame = pd.DataFrame({"date": days, "close": np.arange(20, dtype=float) + 100})
    config = StudyConfig("2024-01-01", "2024-01-20", season_radius_days=4)
    actual = [9, 10, 11]
    result = random_control(frame, actual, year=2024, midpoint=date(2024, 1, 11),
                            config=config, key="pool")
    # Candidate midpoint indices 6..14; starts 5..13. Starts 7..11 overlap 9..11.
    assert result["random_candidate_count"] == 4


def test_pre_post_controls_use_adjacent_equal_length_bars_without_gate_overlap():
    frame = pd.DataFrame({"close": [10., 12., 11., 20., 25., 40., 40., 32., 16.]})
    gate_positions = [3, 4, 5]
    assert _adjacent_return(frame, gate_positions, True) == pytest.approx(10)
    assert _adjacent_return(frame, gate_positions, False) == pytest.approx(-60)
    assert _adjacent_return(frame, [0, 1, 2], True) is None
    assert _adjacent_return(frame, [6, 7, 8], False) is None


def test_bootstrap_seed_reproducibility_and_insufficient_sample():
    config = StudyConfig("2020-01-01", "2026-10-02")
    assert bootstrap_interval([1., 2., 3.], config=config, key="G32", statistic="median") == \
        bootstrap_interval([1., 2., 3.], config=config, key="G32", statistic="median")
    assert bootstrap_interval([1.], config=config, key="G32", statistic="mean") == (None, None)


def test_asset_alignment_uses_existing_market_close_gate_mapping():
    rows = gate_intervals("2026-10-01", "2026-10-31")
    days = ["2026-10-13", "2026-10-14", "2026-10-15", "2026-10-16"]
    frame = pd.DataFrame({"date": days, "close": [100., 101., 99., 98.]})
    snapshots = {key: None for key in ("VIX", "US10Y", "USDKRW", "BROAD_USD")}
    result = asset_windows("SP500", frame, root=ROOT,
                           config=StudyConfig("2026-10-01", "2026-10-31"),
                           intervals=rows, snapshots=snapshots)
    for day in days:
        assigned = [row for row in result if row["first_market_date"] and
                    row["first_market_date"] <= day <= row["last_market_date"]]
        assert len(assigned) == 1
        assert assigned[0]["gate"] == at_market_close(day, "USD")["gate"]
    assert all(row["phase_at_start"] is None for row in result)


def test_summary_keeps_all_gates_and_phase_control_is_descriptive():
    rows = []
    for year in range(2020, 2026):
        for gate, value in ((1, 2.), (2, 1.)):
            rows.append({"asset": "005930", "gate": gate, "year": year,
                         "quarter_id": "initiation", "analysis_status": "COMPLETE",
                         "phase_at_start": "SUMMER", "return_pct": value,
                         "max_drawdown_pct": -1., "daily_volatility_pct": .5,
                         "vix_mean": 20., "vix_change": 1., "us10y_change_pp": .1,
                         "usdkrw_change_pct": .2, "broad_dollar_change_pct": .3,
                         "random_return_percentile": 80., "random_return_median": 1.})
    result = summarize(pd.DataFrame(rows), config=StudyConfig("2020-01-01", "2026-10-02"))
    assert len(result) == 64
    first = result.loc[result["gate"] == 1].iloc[0]
    assert first["count_windows"] == 6
    assert first["phase_control_count"] == 6
    assert first["phase_control_median_effect_pp"] == pytest.approx(1)
    assert result.loc[result["gate"] == 64, "research_status"].iloc[0] == "INSUFFICIENT SAMPLE"
