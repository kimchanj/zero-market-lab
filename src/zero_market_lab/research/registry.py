"""Versioned research memory and frozen cross-asset validation rules.

This module records evidence; it does not produce trading decisions.
"""

from __future__ import annotations

from datetime import date
from hashlib import sha256
import json
import re

import pandas as pd


DISCOVERY_COMMIT = "1750c5695258f697a1c838a9c6b15b73270dea3f"
DISCOVERY_SUMMARY_SHA256 = "4bc47f15587540b710f044068e1354c32b5f54c3a770f5c9d5f047c240709659"
DISCOVERY_ASSETS = ("005930", "000660", "SP500")
VALIDATION_ASSETS = ("NVDA", "MSFT", "AAPL")
FROZEN_CANDIDATE_GATES = (1, 4, 10, 20, 22, 23, 27, 31, 36, 44, 45, 46, 47,
                          48, 50, 51, 52, 56, 57, 58, 63)
PERIOD = {"start": "2020-08-24", "end": "2026-10-02"}
REGISTRY_VERSION = "TRANSIT_REGISTRY_V1"
METHOD_VERSION = "TRANSIT_MARKET_V1"
STATUSES = frozenset({"UNTESTED", "DISCOVERED", "NO_EVIDENCE", "WEAK_CANDIDATE",
                      "VALIDATION_PENDING", "VALIDATING", "REPLICATION_CANDIDATE",
                      "REPLICATED", "NOT_REPLICATED", "NO_EVIDENCE_CONFIRMED",
                      "FALSIFIED", "INSUFFICIENT_SAMPLE", "UNRESOLVED", "RETIRED"})
TRANSITIONS = {
    "UNTESTED": {"DISCOVERED", "NO_EVIDENCE", "WEAK_CANDIDATE"},
    "DISCOVERED": {"NO_EVIDENCE", "WEAK_CANDIDATE", "VALIDATION_PENDING"},
    "NO_EVIDENCE": {"VALIDATION_PENDING", "VALIDATING", "RETIRED"},
    "WEAK_CANDIDATE": {"VALIDATION_PENDING", "VALIDATING", "RETIRED"},
    "VALIDATION_PENDING": {"VALIDATING", "RETIRED"},
    "VALIDATING": {"REPLICATION_CANDIDATE", "NOT_REPLICATED", "NO_EVIDENCE_CONFIRMED",
                   "FALSIFIED", "INSUFFICIENT_SAMPLE", "UNRESOLVED"},
    "REPLICATION_CANDIDATE": {"REPLICATED", "NOT_REPLICATED", "RETIRED"},
    "REPLICATED": {"FALSIFIED", "RETIRED"},
    "NOT_REPLICATED": {"RETIRED"},
    "NO_EVIDENCE_CONFIRMED": {"RETIRED"},
    "FALSIFIED": {"RETIRED"},
    "INSUFFICIENT_SAMPLE": {"VALIDATION_PENDING", "RETIRED"},
    "UNRESOLVED": {"VALIDATION_PENDING", "RETIRED"},
    "RETIRED": set(),
}
REQUIRED_ENTRY = frozenset({"research_id", "title", "hypothesis", "domain",
                            "discovery_period", "discovery_assets", "discovery_dataset_version",
                            "method_version", "status", "evidence_level", "result_summary",
                            "counter_evidence", "falsification_conditions", "candidate_variables",
                            "validation_plan", "validation_assets", "validation_period",
                            "created_at", "updated_at", "source_commit", "notes",
                            "gate", "frozen_direction", "discovery_evidence", "validation_evidence",
                            "status_history"})


def transition(entry: dict, status: str, *, when: str, reason: str,
               commit: str | None = None) -> None:
    """Append, never rewrite, a legal research-status transition."""
    date.fromisoformat(when)
    if status not in STATUSES or status not in TRANSITIONS.get(entry["status"], set()):
        raise ValueError(f"Illegal research transition: {entry['status']} -> {status}")
    if not reason.strip():
        raise ValueError("A transition requires a reason")
    if commit is not None and not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Transition commit must be a full Git SHA")
    entry["status"] = status
    entry["updated_at"] = when
    entry["status_history"].append({"date": when, "status": status,
                                    "reason": reason, "commit": commit})


def validate_registry(registry: dict) -> None:
    if registry.get("schema_version") != REGISTRY_VERSION:
        raise ValueError("Unsupported registry schema")
    discovery, validation = registry["datasets"]["discovery"], registry["datasets"]["validation"]
    if discovery["role"] != "DISCOVERY" or validation["role"] != "VALIDATION":
        raise ValueError("Dataset roles must remain distinct")
    if set(discovery["assets"]) & set(validation["assets"]):
        raise ValueError("Discovery and validation assets overlap")
    if (discovery["period"] != PERIOD or validation["period"] != PERIOD or
            discovery["summary_sha256"] != DISCOVERY_SUMMARY_SHA256):
        raise ValueError("Frozen discovery or validation specification changed")
    entries = registry["entries"]
    ids = [item["research_id"] for item in entries]
    gates = [item["gate"] for item in entries]
    if len(ids) != len(set(ids)) or len(gates) != len(set(gates)) or 32 not in gates:
        raise ValueError("Registry requires unique IDs and Gates including Gate 32")
    if (sorted(gate for gate in gates if gate != 32) != registry["frozen_candidate_gates"] or
            tuple(registry["frozen_candidate_gates"]) != FROZEN_CANDIDATE_GATES):
        raise ValueError("Candidate set changed after freeze")
    for item in entries:
        if not REQUIRED_ENTRY <= item.keys() or item["status"] not in STATUSES:
            raise ValueError("Invalid registry entry")
        if not re.fullmatch(r"[0-9a-f]{40}", item["source_commit"]):
            raise ValueError("Invalid source commit")
        if item["source_commit"] != DISCOVERY_COMMIT or item["method_version"] != METHOD_VERSION:
            raise ValueError("Discovery source or method changed")
        if set(item["discovery_assets"]) != set(DISCOVERY_ASSETS) or set(item["validation_assets"]) != set(VALIDATION_ASSETS):
            raise ValueError("Entry asset roles overlap or changed")
        history = item["status_history"]
        if not history or history[-1]["status"] != item["status"]:
            raise ValueError("Status history does not match current status")
        if any(previous["status"] not in STATUSES or current["status"] not in
               TRANSITIONS[previous["status"]] for previous, current in zip(history, history[1:])):
            raise ValueError("Illegal historical transition")


def frozen_direction(weak_rows: pd.DataFrame) -> str:
    effects = weak_rows["median_random_effect_pp"].astype(float)
    if effects.isna().any() or (effects.abs() < 1).any():
        return "AMBIGUOUS"
    if (effects > 0).all():
        return "POSITIVE"
    if (effects < 0).all():
        return "NEGATIVE"
    return "AMBIGUOUS"


def freeze_registry(summary: pd.DataFrame, *, summary_sha256: str,
                    when: str = "2026-10-24") -> dict:
    """Freeze every STEP 9 weak Gate before held-out asset outcomes are inspected."""
    date.fromisoformat(when)
    if (summary_sha256 != DISCOVERY_SUMMARY_SHA256 or len(summary) != 192 or
            set(summary["asset"]) != set(DISCOVERY_ASSETS) or
            any(set(group["gate"]) != set(range(1, 65)) for _, group in summary.groupby("asset"))):
        raise ValueError("Discovery summary does not match the approved STEP 9 checkpoint")
    weak = summary.loc[summary["research_status"] == "WEAK"]
    candidates = sorted(set(int(gate) for gate in weak["gate"]))
    if tuple(candidates) != FROZEN_CANDIDATE_GATES:
        raise ValueError("Approved STEP 9 weak candidate set changed")
    entries = []
    for gate in [32, *candidates]:
        rows = summary.loc[summary["gate"] == gate].sort_values("asset")
        weak_rows = rows.loc[rows["research_status"] == "WEAK"]
        status = "NO_EVIDENCE" if gate == 32 else "WEAK_CANDIDATE"
        direction = "NONE" if gate == 32 else frozen_direction(weak_rows)
        evidence = [{"asset": row["asset"], "status": row["research_status"],
                     "count_windows": int(row["count_windows"]),
                     "median_return_pct": _nullable(row["median_return"]),
                     "median_random_effect_pp": _nullable(row["median_random_effect_pp"]),
                     "median_random_return_percentile": _nullable(row["median_random_return_percentile"])}
                    for _, row in rows.iterrows()]
        counter = (["Annual return directions differ", "Random percentiles ordinary",
                    "Mean-return bootstrap intervals include zero", "No cross-asset replication"]
                   if gate == 32 else
                   [f"{item['asset']}: {item['status']} in STEP 9" for item in evidence
                    if item["status"] != "WEAK"] +
                   (["Discovery weak effects disagree in sign or fall below 1 pp"]
                    if direction == "AMBIGUOUS" else []))
        entries.append({"research_id": f"TRANSIT_GATE_{gate:02d}_V1", "gate": gate,
                        "title": f"Solar Transit Gate {gate} market association",
                        "hypothesis": ("No preregistered directional Gate 32 effect; check whether no-evidence persists"
                                       if gate == 32 else
                                       f"STEP 9 weak Gate {gate} association may persist on held-out US assets"),
                        "domain": "TRANSIT_MARKET_ASSOCIATION",
                        "discovery_period": PERIOD.copy(),
                        "discovery_assets": list(DISCOVERY_ASSETS),
                        "discovery_dataset_version": DISCOVERY_SUMMARY_SHA256,
                        "method_version": METHOD_VERSION, "status": status,
                        "evidence_level": "NO EVIDENCE" if gate == 32 else "WEAK",
                        "result_summary": ("All three discovery assets NO EVIDENCE" if gate == 32 else
                                           f"WEAK on {', '.join(weak_rows['asset'])}; not confirmed"),
                        "counter_evidence": counter,
                        "falsification_conditions": (
                            ["Ordinary held-out random controls and zero-crossing intervals retain NO EVIDENCE"]
                            if gate == 32 else
                            ["Direction reversal on at least two held-out assets with all frozen controls",
                             "Ordinary or mixed held-out results mean NOT_REPLICATED"]),
                        "candidate_variables": ["Gate", "close-to-close return", "within-window MDD",
                                                "daily volatility", "same-season random percentile",
                                                "FECM Phase", "as-of macro context"],
                        "validation_plan": "docs/research/transit-validation-v1-plan.md",
                        "validation_assets": list(VALIDATION_ASSETS),
                        "validation_period": PERIOD.copy(), "frozen_direction": direction,
                        "discovery_evidence": evidence, "validation_evidence": [],
                        "created_at": when, "updated_at": when,
                        "source_commit": DISCOVERY_COMMIT, "validation_commit": None,
                        "notes": "Exploratory association only; future independent-time validation required",
                        "status_history": [{"date": when, "status": status,
                                            "reason": "Frozen from approved STEP 9 discovery result",
                                            "commit": DISCOVERY_COMMIT}]})
    registry = {"schema_version": REGISTRY_VERSION, "updated_at": when,
                "source_commit": DISCOVERY_COMMIT,
                "datasets": {"discovery": {"role": "DISCOVERY", "period": PERIOD.copy(),
                                           "assets": list(DISCOVERY_ASSETS),
                                           "summary_sha256": DISCOVERY_SUMMARY_SHA256},
                             "validation": {"role": "VALIDATION", "period": PERIOD.copy(),
                                            "assets": list(VALIDATION_ASSETS),
                                            "run_manifest_sha256": None}},
                "frozen_candidate_gates": candidates, "entries": entries}
    validate_registry(registry)
    return registry


def validate_discovery_freeze(registry: dict, discovery_summary: pd.DataFrame) -> None:
    """Check immutable discovery evidence against the pinned STEP 9 summary."""
    validate_registry(registry)
    approved = freeze_registry(discovery_summary,
                               summary_sha256=DISCOVERY_SUMMARY_SHA256)
    by_id = {item["research_id"]: item for item in approved["entries"]}
    for item in registry["entries"]:
        original = by_id[item["research_id"]]
        for field in ("gate", "frozen_direction", "discovery_evidence", "discovery_period",
                      "discovery_assets", "discovery_dataset_version", "source_commit"):
            if item[field] != original[field]:
                raise ValueError(f"Discovery freeze changed: {item['research_id']} {field}")


def _nullable(value: object) -> float | None:
    return None if pd.isna(value) else float(value)


def registry_sha256(payload: dict) -> str:
    return sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                             separators=(",", ":")).encode()).hexdigest()


def discovery_fingerprint(registry: dict) -> str:
    """Stable across later validation-status updates."""
    frozen = {"discovery": registry["datasets"]["discovery"],
              "candidate_gates": registry["frozen_candidate_gates"],
              "entries": [{key: item[key] for key in
                           ("research_id", "gate", "frozen_direction", "discovery_evidence",
                            "discovery_period", "discovery_assets", "source_commit")}
                          for item in registry["entries"]]}
    return registry_sha256(frozen)


def validation_asset_signal(row: pd.Series, windows: pd.DataFrame, direction: str) -> bool:
    if direction not in {"POSITIVE", "NEGATIVE"} or int(row["count_windows"]) < 6:
        return False
    sign = 1 if direction == "POSITIVE" else -1
    group = windows.loc[(windows["asset"] == row["asset"]) &
                        (windows["gate"] == row["gate"]) &
                        (windows["analysis_status"] == "COMPLETE")]
    annual = group["return_pct"].astype(float)
    if len(annual) != int(row["count_windows"]) or len(annual) < 6:
        return False
    effect = row["median_random_effect_pp"]
    percentile = row["median_random_return_percentile"]
    phase = row["phase_control_median_effect_pp"]
    ci_low, ci_high = row["mean_return_ci_low"], row["mean_return_ci_high"]
    return bool(pd.notna(effect) and sign * float(effect) >= 1 and
                pd.notna(percentile) and
                (float(percentile) > 90 if sign > 0 else float(percentile) < 10) and
                (sign * annual > 0).mean() >= .70 and
                pd.notna(ci_low) and pd.notna(ci_high) and
                (float(ci_low) > 0 if sign > 0 else float(ci_high) < 0) and
                pd.notna(phase) and sign * float(phase) > 0)


def apply_validation(registry: dict, summary: pd.DataFrame, windows: pd.DataFrame,
                     *, when: str, manifest_sha256: str) -> dict:
    """Apply only preregistered Gates and rules; never discover a new Gate here."""
    validate_registry(registry)
    if not re.fullmatch(r"[0-9a-f]{64}", manifest_sha256):
        raise ValueError("Validation manifest hash required")
    expected = {(asset, gate) for asset in VALIDATION_ASSETS
                for gate in [32, *registry["frozen_candidate_gates"]]}
    actual = {(row["asset"], int(row["gate"])) for _, row in summary.iterrows()}
    if expected != actual or len(summary) != len(expected):
        raise ValueError("Validation summary must contain only frozen asset–Gate rows")
    if set(windows["asset"]) != set(VALIDATION_ASSETS):
        raise ValueError("Validation windows contain discovery assets")
    result = json.loads(json.dumps(registry, ensure_ascii=False))
    result["updated_at"] = when
    result["datasets"]["validation"]["run_manifest_sha256"] = manifest_sha256
    for entry in result["entries"]:
        gate = entry["gate"]
        group = summary.loc[summary["gate"] == gate].sort_values("asset")
        transition(entry, "VALIDATING", when=when, reason="Held-out asset result evaluated")
        evidence = []
        for _, row in group.iterrows():
            direction = entry["frozen_direction"]
            support = validation_asset_signal(row, windows, direction)
            opposite = validation_asset_signal(row, windows,
                                               "NEGATIVE" if direction == "POSITIVE" else "POSITIVE")
            evidence.append({"asset": row["asset"], "count_windows": int(row["count_windows"]),
                             "research_status": row["research_status"],
                             "median_return_pct": _nullable(row["median_return"]),
                             "median_random_effect_pp": _nullable(row["median_random_effect_pp"]),
                             "median_random_return_percentile": _nullable(row["median_random_return_percentile"]),
                             "mean_return_ci_low": _nullable(row["mean_return_ci_low"]),
                             "mean_return_ci_high": _nullable(row["mean_return_ci_high"]),
                             "phase_control_median_effect_pp": _nullable(row["phase_control_median_effect_pp"]),
                             "supports_frozen_direction": support,
                             "strong_opposite_direction": opposite})
        entry["validation_evidence"] = evidence
        if any(item["count_windows"] < 5 or
               item["median_random_return_percentile"] is None for item in evidence):
            status, reason = "INSUFFICIENT_SAMPLE", "One or more held-out assets lack required windows or random controls"
        elif gate == 32:
            ordinary = all(item["research_status"] == "NO EVIDENCE" and
                           item["mean_return_ci_low"] is not None and
                           item["mean_return_ci_low"] <= 0 <= item["mean_return_ci_high"] and
                           10 <= item["median_random_return_percentile"] <= 90
                           for item in evidence)
            status = "NO_EVIDENCE_CONFIRMED" if ordinary else "UNRESOLVED"
            reason = ("All three held-out assets satisfy frozen no-evidence checks" if ordinary else
                      "Held-out evidence does not meet every frozen no-evidence check")
        else:
            supports = sum(item["supports_frozen_direction"] for item in evidence)
            opposite = sum(item["strong_opposite_direction"] for item in evidence)
            if entry["frozen_direction"] == "AMBIGUOUS":
                status, reason = "NOT_REPLICATED", "Discovery direction was ambiguous before validation"
            elif opposite >= 2:
                status, reason = "FALSIFIED", "At least two held-out assets show strong opposite-direction evidence"
            elif supports >= 2 and not any(
                    item["median_random_effect_pp"] is not None and
                    (1 if entry["frozen_direction"] == "POSITIVE" else -1) *
                    item["median_random_effect_pp"] <= -1 for item in evidence):
                status, reason = "REPLICATION_CANDIDATE", "At least two assets satisfy all preregistered support checks"
            else:
                status, reason = "NOT_REPLICATED", "Frozen replication threshold not met"
        transition(entry, status, when=when, reason=reason)
        entry["validation_result"] = status
        entry["notes"] += "; historical asset-held-out only, no forward evidence"
    validate_registry(result)
    return result
