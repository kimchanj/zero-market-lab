"""Freeze STEP 9 discovery hypotheses before reading STEP 10 held-out outcomes."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zero_market_lab.research.registry import (  # noqa: E402
    DISCOVERY_COMMIT, DISCOVERY_SUMMARY_SHA256, freeze_registry,
)


def main() -> None:
    source = ROOT / "data/processed/research/step9_three_asset_v1_review/gate_summary_64.csv"
    destination = ROOT / "data/reference/research_registry.json"
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite frozen research registry: {destination}")
    digest = sha256(source.read_bytes()).hexdigest()
    if digest != DISCOVERY_SUMMARY_SHA256:
        raise ValueError("STEP 9 discovery summary does not match its approved SHA-256")
    registry = freeze_registry(pd.read_csv(source), summary_sha256=digest)
    destination.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps({"file": str(destination), "source_commit": DISCOVERY_COMMIT,
                      "registered_gates": len(registry["entries"]),
                      "weak_candidate_gates": registry["frozen_candidate_gates"]}))


if __name__ == "__main__":
    main()
