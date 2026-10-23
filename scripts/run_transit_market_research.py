"""Run preregistered, local-only STEP 9 Transit × Market research."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zero_market_lab.research.comparison import ComparisonResearch  # noqa: E402
from zero_market_lab.research.transit_analysis import ASSETS, StudyConfig, run_study  # noqa: E402


def common_span(root: Path, requested_start: str, requested_end: str | None) -> tuple[str, str]:
    research = ComparisonResearch(root)
    frames = [research._local(symbol)[0] for symbol in ASSETS]
    first = max(requested_start, *(str(frame.iloc[0]["date"]) for frame in frames))
    last = min(*(str(frame.iloc[-1]["date"]) for frame in frames))
    if requested_end:
        last = min(last, requested_end)
    if date.fromisoformat(first) > date.fromisoformat(last):
        raise ValueError("No common observed study span")
    return first, last


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset", action="append", choices=ASSETS,
                        help="Repeat for a subset; default is all three assets")
    parser.add_argument("--start", default="2020-01-01")
    parser.add_argument("--end", help="Inclusive requested last day; capped to common local history")
    parser.add_argument("--random-seed", type=int, default=42)
    parser.add_argument("--output", type=Path,
                        help="New Git-ignored output directory; never overwrites a prior run")
    args = parser.parse_args()
    start, end = common_span(ROOT, args.start, args.end)
    assets = tuple(dict.fromkeys(args.asset or ASSETS))
    config = StudyConfig(start=start, end=end, seed=args.random_seed)
    result = run_study(ROOT, config, assets=assets)
    from hashlib import sha256
    run_key = sha256(json.dumps(result["manifest"], sort_keys=True,
                                 ensure_ascii=False).encode()).hexdigest()[:12]
    folder = args.output or ROOT / "data/processed/research" / f"transit_market_v1_{run_key}"
    folder = folder.resolve()
    if folder.exists() and any(folder.iterdir()):
        raise FileExistsError(f"Research output already exists; choose a new --output: {folder}")
    folder.mkdir(parents=True, exist_ok=True)
    result["windows"].to_parquet(folder / "transit_market_windows.parquet", index=False)
    result["windows"].to_csv(folder / "transit_market_windows.csv", index=False,
                             encoding="utf-8-sig")
    result["summary"].to_csv(folder / "gate_summary_64.csv", index=False,
                             encoding="utf-8-sig")
    result["quarters"].to_csv(folder / "quarter_summary.csv", index=False,
                              encoding="utf-8-sig")
    (folder / "manifest.json").write_text(json.dumps(result["manifest"], ensure_ascii=False,
                                                      sort_keys=True, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(folder), "start": start, "end": end,
                      "assets": assets, "window_rows": len(result["windows"]),
                      "summary_rows": len(result["summary"]), "run_key": run_key},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
