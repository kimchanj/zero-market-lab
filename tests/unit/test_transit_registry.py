"""STEP 10 research lifecycle and held-out dataset-role invariants."""

from hashlib import sha256
from pathlib import Path

import pandas as pd
import pytest

from zero_market_lab.research.registry import (
    DISCOVERY_SUMMARY_SHA256, FROZEN_CANDIDATE_GATES, VALIDATION_ASSETS,
    apply_validation, discovery_fingerprint, freeze_registry, transition,
    validate_discovery_freeze, validate_registry,
)
from zero_market_lab.research.transit_analysis import StudyConfig, asset_windows, gate_intervals, run_study
from zero_market_lab.transit.calendar import at_market_close


ROOT = Path(__file__).resolve().parents[2]
SUMMARY = ROOT / "data/processed/research/step9_three_asset_v1_review/gate_summary_64.csv"


def frozen():
    assert sha256(SUMMARY.read_bytes()).hexdigest() == DISCOVERY_SUMMARY_SHA256
    return freeze_registry(pd.read_csv(SUMMARY), summary_sha256=DISCOVERY_SUMMARY_SHA256)


def test_registry_freezes_all_weak_candidates_without_cherry_picking():
    registry = frozen()
    assert len(registry["entries"]) == 22
    assert tuple(registry["frozen_candidate_gates"]) == FROZEN_CANDIDATE_GATES
    assert registry["entries"][0]["research_id"] == "TRANSIT_GATE_32_V1"
    assert registry["entries"][0]["status"] == "NO_EVIDENCE"
    gate20 = next(item for item in registry["entries"] if item["gate"] == 20)
    assert gate20["frozen_direction"] == "AMBIGUOUS"
    assert all(item["source_commit"] == registry["source_commit"] for item in registry["entries"])
    validate_discovery_freeze(registry, pd.read_csv(SUMMARY))


def test_registry_rejects_duplicate_id_invalid_commit_and_role_overlap():
    registry = frozen()
    registry["entries"][1]["research_id"] = registry["entries"][0]["research_id"]
    with pytest.raises(ValueError, match="unique"):
        validate_registry(registry)
    registry = frozen()
    registry["entries"][0]["source_commit"] = "short"
    with pytest.raises(ValueError, match="source commit"):
        validate_registry(registry)
    registry = frozen()
    registry["datasets"]["validation"]["assets"].append("005930")
    with pytest.raises(ValueError, match="overlap"):
        validate_registry(registry)


def test_registry_rejects_candidate_or_discovery_evidence_mutation():
    registry = frozen()
    original = discovery_fingerprint(registry)
    registry["entries"][1]["discovery_evidence"][0]["median_return_pct"] = 999
    assert discovery_fingerprint(registry) != original
    with pytest.raises(ValueError, match="Discovery freeze"):
        validate_discovery_freeze(registry, pd.read_csv(SUMMARY))
    registry = frozen()
    registry["frozen_candidate_gates"].pop()
    with pytest.raises(ValueError, match="Candidate set"):
        validate_registry(registry)


def test_status_history_accepts_only_legal_reasoned_transitions():
    entry = frozen()["entries"][0]
    with pytest.raises(ValueError, match="Illegal"):
        transition(entry, "REPLICATED", when="2026-10-24", reason="skip")
    transition(entry, "VALIDATING", when="2026-10-24", reason="Frozen validation started")
    transition(entry, "NO_EVIDENCE_CONFIRMED", when="2026-10-24", reason="Three ordinary controls")
    assert [row["status"] for row in entry["status_history"]] == [
        "NO_EVIDENCE", "VALIDATING", "NO_EVIDENCE_CONFIRMED"]


def test_validation_evaluation_keeps_gate32_negative_and_all_weak_candidates():
    registry = frozen()
    rows, windows = [], []
    for asset in VALIDATION_ASSETS:
        for gate in (32, *FROZEN_CANDIDATE_GATES):
            rows.append({"asset": asset, "gate": gate, "count_windows": 6,
                         "research_status": "NO EVIDENCE", "median_return": .1,
                         "median_random_effect_pp": .1,
                         "median_random_return_percentile": 50.,
                         "mean_return_ci_low": -1., "mean_return_ci_high": 1.,
                         "phase_control_median_effect_pp": 0.})
            windows.extend({"asset": asset, "gate": gate, "analysis_status": "COMPLETE",
                            "return_pct": .1} for _ in range(6))
    result = apply_validation(registry, pd.DataFrame(rows), pd.DataFrame(windows),
                              when="2026-10-24", manifest_sha256="a" * 64)
    assert result["entries"][0]["status"] == "NO_EVIDENCE_CONFIRMED"
    assert all(entry["status"] == "NOT_REPLICATED" for entry in result["entries"][1:])
    assert all(len(entry["status_history"]) == 3 for entry in result["entries"])
    assert discovery_fingerprint(result) == discovery_fingerprint(registry)


def test_validation_rejects_discovery_assets_or_missing_frozen_gate():
    registry = frozen()
    with pytest.raises(ValueError, match="summary"):
        apply_validation(registry, pd.DataFrame({"asset": ["NVDA"], "gate": [32]}),
                         pd.DataFrame({"asset": ["NVDA"]}), when="2026-10-24",
                         manifest_sha256="a" * 64)
    with pytest.raises(ValueError, match="Unsupported research asset"):
        run_study(ROOT, StudyConfig("2024-01-01", "2024-12-31"),
                  assets=("005930",), dataset_role="VALIDATION")


def test_us_validation_market_close_uses_existing_gate_mapping():
    intervals = gate_intervals("2026-10-01", "2026-10-31")
    days = ["2026-10-13", "2026-10-14", "2026-10-15", "2026-10-16"]
    frame = pd.DataFrame({"date": days, "close": [100., 101., 99., 98.]})
    snapshots = {key: None for key in ("VIX", "US10Y", "USDKRW", "BROAD_USD")}
    result = asset_windows("NVDA", frame, root=ROOT,
                           config=StudyConfig("2026-10-01", "2026-10-31"),
                           intervals=intervals, snapshots=snapshots, currency="USD")
    for day in days:
        containing = [item for item in result if item["first_market_date"] and
                      item["first_market_date"] <= day <= item["last_market_date"]]
        assert len(containing) == 1
        assert containing[0]["gate"] == at_market_close(day, "USD")["gate"]
