"""Verify two frozen validation runs, then append their result to the Registry."""

from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zero_market_lab.research.registry import (  # noqa: E402
    DISCOVERY_SUMMARY_SHA256, PERIOD, VALIDATION_ASSETS, apply_validation,
    discovery_fingerprint, validate_discovery_freeze,
)


RESULT_FILES = ("manifest.json", "validation_windows.parquet", "validation_windows.csv",
                "validation_summary.csv")


def finalize(primary: Path, reproduction: Path, *, when: str = "2026-10-24") -> dict:
    for name in RESULT_FILES:
        if sha256((primary / name).read_bytes()).digest() != sha256((reproduction / name).read_bytes()).digest():
            raise ValueError(f"Validation runs differ: {name}")
    manifest_bytes = (primary / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    registry_path = ROOT / "data/reference/research_registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    discovery = ROOT / "data/processed/research/step9_three_asset_v1_review/gate_summary_64.csv"
    if sha256(discovery.read_bytes()).hexdigest() != DISCOVERY_SUMMARY_SHA256:
        raise ValueError("Discovery source changed")
    validate_discovery_freeze(registry, pd.read_csv(discovery))
    if registry["datasets"]["validation"]["run_manifest_sha256"] is not None:
        raise ValueError("Registry already has a validation result")
    if (manifest["dataset_role"] != "VALIDATION" or
            manifest["preregistration_sha256"] != sha256((ROOT / "docs/research/transit-validation-v1-plan.md").read_bytes()).hexdigest() or
            manifest["assets"] != list(VALIDATION_ASSETS) or
            manifest["config"]["start"] != PERIOD["start"] or
            manifest["config"]["end"] != PERIOD["end"] or
            manifest["config"]["seed"] != 1042 or
            manifest["discovery_fingerprint"] != discovery_fingerprint(registry) or
            manifest["selected_gates"] != sorted([32, *registry["frozen_candidate_gates"]])):
        raise ValueError("Validation manifest differs from preregistration")
    module_path = ROOT / "src/zero_market_lab/research/transit_analysis.py"
    if manifest["analysis_code_sha256"] != sha256(module_path.read_bytes()).hexdigest():
        raise ValueError("Validation analysis code changed after the run")
    windows = pd.read_parquet(primary / "validation_windows.parquet")
    summary = pd.read_csv(primary / "validation_summary.csv")
    result = apply_validation(registry, summary, windows, when=when,
                              manifest_sha256=sha256(manifest_bytes).hexdigest())
    temporary = registry_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(registry_path)
    return {"registry": str(registry_path), "manifest_sha256": sha256(manifest_bytes).hexdigest(),
            "status_counts": dict(Counter(item["status"] for item in result["entries"])),
            "entries": len(result["entries"])}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("primary", type=Path)
    parser.add_argument("reproduction", type=Path)
    args = parser.parse_args()
    print(json.dumps(finalize(args.primary, args.reproduction), ensure_ascii=False))


if __name__ == "__main__":
    main()
