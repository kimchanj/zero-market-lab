"""STEP 11 status-only dry run. No historical replay or registry mutation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zero_market_lab.research.forward_validation import plan_contents, verify_forward  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", required=True,
                        help="Only verify frozen protocol and current empty forward state")
    parser.parse_args()
    registry = json.loads((ROOT / "data/reference/research_registry.json").read_text(encoding="utf-8"))
    verify_forward(registry, plan_bytes=plan_contents(ROOT))
    print(json.dumps({"protocol": registry["forward_protocol"]["protocol_id"],
                      "status": "WAITING_FOR_DATA", "forward_windows": 0,
                      "assets": registry["forward_protocol"]["assets"],
                      "note": "Observation ingestion and window finalization are not enabled yet"},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
