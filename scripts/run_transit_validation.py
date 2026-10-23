"""Run the STEP 10 preregistered, asset-held-out Transit validation locally."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zero_market_lab.research.comparison import ComparisonResearch  # noqa: E402
from zero_market_lab.research.registry import (  # noqa: E402
    DISCOVERY_COMMIT, DISCOVERY_SUMMARY_SHA256, FROZEN_CANDIDATE_GATES,
    PERIOD, VALIDATION_ASSETS, discovery_fingerprint, validate_discovery_freeze,
)
from zero_market_lab.research.transit_analysis import StudyConfig, run_study  # noqa: E402


def validate_inputs(root: Path) -> tuple[dict, str]:
    registry_path = root / "data/reference/research_registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    source = root / "data/processed/research/step9_three_asset_v1_review/gate_summary_64.csv"
    if sha256(source.read_bytes()).hexdigest() != DISCOVERY_SUMMARY_SHA256:
        raise ValueError("Approved STEP 9 discovery dataset changed")
    validate_discovery_freeze(registry, pd.read_csv(source))
    research = ComparisonResearch(root)
    for symbol in VALIDATION_ASSETS:
        frame, metadata = research._local(symbol)
        if (frame.iloc[0]["date"] > PERIOD["start"] or
                frame.iloc[-1]["date"] < PERIOD["end"] or
                not {"open", "high", "low", "close", "volume"} <= set(frame)):
            raise ValueError(f"Incomplete held-out OHLCV: {symbol}")
        selected = frame.loc[frame["date"].between(PERIOD["start"], PERIOD["end"])].copy()
        for column in ("open", "high", "low", "close", "volume"):
            selected[column] = pd.to_numeric(selected[column], errors="raise")
        if (selected[["open", "high", "low", "close", "volume"]].isna().any().any() or
                (selected[["open", "high", "low", "close"]] <= 0).any().any() or
                (selected["volume"] < 0).any() or
                (selected["high"] < selected[["open", "close", "low"]].max(axis=1)).any() or
                (selected["low"] > selected[["open", "close", "high"]].min(axis=1)).any()):
            raise ValueError(f"Invalid held-out OHLCV: {symbol}")
        if not metadata.get("adjustment") or not metadata.get("provider"):
            raise ValueError(f"Missing provider/adjustment provenance: {symbol}")
    return registry, discovery_fingerprint(registry)


def run(output: Path) -> dict:
    registry, fingerprint = validate_inputs(ROOT)
    config = StudyConfig(start=PERIOD["start"], end=PERIOD["end"], seed=1042)
    result = run_study(ROOT, config, assets=VALIDATION_ASSETS, dataset_role="VALIDATION")
    chosen = {32, *FROZEN_CANDIDATE_GATES}
    windows = result["windows"].loc[result["windows"]["gate"].isin(chosen)].copy()
    summary = result["summary"].loc[result["summary"]["gate"].isin(chosen)].copy()
    expected = {(symbol, gate) for symbol in VALIDATION_ASSETS for gate in chosen}
    if len(summary) != len(expected) or {(row.asset, row.gate) for row in summary.itertuples()} != expected:
        raise ValueError("Validation output does not cover the entire frozen candidate set")
    manifest = result["manifest"]
    manifest.update({"dataset_role": "VALIDATION", "validation_method": "ASSET_HELD_OUT_V1",
                     "preregistration_sha256": sha256((ROOT / "docs/research/transit-validation-v1-plan.md").read_bytes()).hexdigest(),
                     "discovery_source_commit": DISCOVERY_COMMIT,
                     "discovery_summary_sha256": DISCOVERY_SUMMARY_SHA256,
                     "discovery_fingerprint": fingerprint,
                     "selected_gates": sorted(chosen),
                     "selected_window_rows": len(windows),
                     "selected_summary_rows": len(summary),
                     "random_control_seed": 1042,
                     "independent_time": False})
    run_key = sha256(json.dumps(manifest, ensure_ascii=False,
                                sort_keys=True).encode()).hexdigest()[:12]
    folder = output.resolve()
    if folder.exists() and any(folder.iterdir()):
        raise FileExistsError(f"Refusing to overwrite prior validation run: {folder}")
    folder.mkdir(parents=True, exist_ok=True)
    windows.to_parquet(folder / "validation_windows.parquet", index=False)
    windows.to_csv(folder / "validation_windows.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(folder / "validation_summary.csv", index=False, encoding="utf-8-sig")
    (folder / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False,
                                                     sort_keys=True, indent=2), encoding="utf-8")
    return {"output": str(folder), "run_key": run_key,
            "assets": list(VALIDATION_ASSETS), "period": PERIOD,
            "gate_count": len(chosen), "window_rows": len(windows),
            "summary_rows": len(summary)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "data/processed/research/step10_validation_v1")
    args = parser.parse_args()
    print(json.dumps(run(args.output), ensure_ascii=False))


if __name__ == "__main__":
    main()
