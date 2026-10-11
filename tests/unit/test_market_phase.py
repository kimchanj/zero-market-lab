"""PRICE_PHASE_V1: point-in-time labels and frozen transition outcomes."""

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from zero_market_lab.market_phase.engine import (
    PHASES, RULE_CONFIG_HASH, VERSION, PhaseEngine, PhaseEvidence, PhaseResult,
    PhaseTransition, _forward_event, _indicators,
)


def frame(prices):
    prices = np.asarray(prices, dtype=float)
    return pd.DataFrame({"date": pd.bdate_range("2023-01-02", periods=len(prices)),
                         "open": prices, "high": prices * 1.01,
                         "low": prices * 0.99, "close": prices, "volume": 1000})


def run(prices):
    return PhaseEngine().run(frame(prices), symbol="SYN", data_source="SYNTHETIC_TEST")


def test_indicator_windows_and_winter_summer_state_machine():
    prices = np.r_[np.linspace(300, 100, 280), np.linspace(100, 500, 300)]
    indicators = _indicators(frame(prices))
    assert pd.isna(indicators.iloc[48]["ma50"])
    assert indicators.iloc[49]["ma50"] == pytest.approx(np.mean(prices[:50]))
    assert pd.isna(indicators.iloc[198]["ma200"])
    assert indicators.iloc[199]["ma200"] == pytest.approx(np.mean(prices[:200]))
    assert indicators.iloc[210]["ma200_delta"] < 0
    assert indicators.iloc[-1]["ma200_delta"] > 0
    report = run(prices)
    labels = [row["current_phase"] for row in report["rows"]]
    assert set(labels).issubset({"UNKNOWN", *PHASES})
    assert "WINTER" in labels[210:280]
    assert "SUMMER" in labels[-150:]
    assert all(row["current_phase"] == "UNKNOWN" for row in report["rows"][:210])
    assert any(event["to_phase"] == "SPRING_CANDIDATE" for event in report["transitions"])
    assert all(event["transition_date"] == report["rows"][next(
        i for i, row in enumerate(report["rows"]) if row["date"] == event["transition_date"])]["date"]
        for event in report["transitions"])
    assert report["engine_version"] == VERSION and report["rule_config_hash"] == RULE_CONFIG_HASH


def test_autumn_after_summer_and_no_single_day_oscillation():
    prices = np.r_[np.linspace(100, 500, 380), np.linspace(500, 350, 100)]
    report = run(prices)
    edges = [(item["from_phase"], item["to_phase"]) for item in report["transitions"]]
    assert ("SUMMER", "AUTUMN") in edges
    assert ("AUTUMN", "WINTER") in edges
    assert all(item["trading_days"] >= 3 for item in report["durations"][:-1]
               if item["phase"] != "UNKNOWN")


def test_future_changes_cannot_rewrite_past_phase_or_evidence():
    prices = np.r_[np.linspace(300, 100, 280), np.linspace(100, 400, 220)]
    base = run(prices)
    altered = run(np.r_[prices[:420], np.linspace(1000, 100, 80)])
    assert base["rows"][:420] == altered["rows"][:420]
    assert base["transitions"][:3] == altered["transitions"][:3]


def test_false_spring_is_outcome_only_and_censors_incomplete_horizon():
    evidence = PhaseEvidence(*([None] * 11))
    rows = [PhaseResult("SYN", day.date().isoformat(), day.date().isoformat() + " close",
                        100.0, None, None, "SPRING_CANDIDATE", "WINTER", i+1,
                        None, None, evidence, None, VERSION, RULE_CONFIG_HASH, "SYNTHETIC_TEST")
            for i, day in enumerate(pd.bdate_range("2025-01-01", periods=80))]
    transition = PhaseTransition("SYN", rows[20].date, "SPRING_CANDIDATE", "WINTER",
                                 100.0, 20, evidence)
    outcome = _forward_event(rows, 0, [transition], kind="SPRING_CANDIDATE")
    assert outcome["outcome"] == "FALSE_SPRING" and outcome["days_to_outcome"] == 20
    assert _forward_event(rows[:30], 0, [], kind="SPRING_CANDIDATE")["outcome"] == "CENSORED"
    confirmation = replace(transition, to_phase="SPRING")
    assert _forward_event(rows, 0, [confirmation, transition], kind="SPRING_CANDIDATE")["outcome"] == "CONFIRMED"


def test_false_autumn_and_true_peak_to_trough_forward_drawdown():
    evidence = PhaseEvidence(*([None] * 11))
    prices = [100.0, 120.0, 110.0] + [115.0] * 118
    rows = [PhaseResult("SYN", day.date().isoformat(), day.date().isoformat() + " close",
                        price, None, None, "AUTUMN", "SUMMER", i+1,
                        None, None, evidence, None, VERSION, RULE_CONFIG_HASH, "SYNTHETIC_TEST")
            for i, (day, price) in enumerate(zip(pd.bdate_range("2025-01-01", periods=121), prices))]
    resumed = PhaseTransition("SYN", rows[12].date, "AUTUMN", "SUMMER", 115.0, 12, evidence)
    event = _forward_event(rows, 0, [resumed], kind="AUTUMN")
    assert event["outcome"] == "FALSE_AUTUMN"
    assert event["days_to_outcome"] == 12
    assert event["max_forward_drawdown_120d"] == pytest.approx(110 / 120 - 1)
    assert _forward_event(rows[:30], 0, [], kind="AUTUMN")["outcome"] == "CENSORED"


def test_bad_ohlc_or_duplicate_dates_rejected():
    data = frame(np.linspace(100, 200, 220))
    data.loc[1, "date"] = data.loc[0, "date"]
    with pytest.raises(ValueError, match="Dates"):
        PhaseEngine().run(data, symbol="SYN", data_source="SYNTHETIC_TEST")
    data = frame(np.linspace(100, 200, 220))
    data.loc[1, "high"] = 1
    with pytest.raises(ValueError, match="OHLC"):
        PhaseEngine().run(data, symbol="SYN", data_source="SYNTHETIC_TEST")
