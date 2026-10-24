"""Initialize empty STEP 11 forward state once; never import old bars."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zero_market_lab.research.forward_validation import initialize_forward, plan_contents  # noqa: E402


def main() -> None:
    path = ROOT / "data/reference/research_registry.json"
    current = json.loads(path.read_text(encoding="utf-8"))
    result = initialize_forward(current, plan_bytes=plan_contents(ROOT))
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    print(json.dumps({"protocol": result["forward_protocol"]["protocol_id"],
                      "entries": len(result["entries"]), "forward_windows": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
