"""Download official FRED CSV into Git-ignored, append-only context snapshots."""

import argparse
from datetime import date
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zero_market_lab.research.context_data import FRED_SERIES, FredContextProvider  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2016-10-01")
    parser.add_argument("--end", default=date.today().isoformat())
    parser.add_argument("--series", nargs="+", choices=tuple(FRED_SERIES),
                        default=["VIX", "US10Y", "USDKRW", "BROAD_USD"])
    args = parser.parse_args()
    result = FredContextProvider(ROOT).persist(args.start, args.end, tuple(args.series))
    print(json.dumps({"snapshot_id": result["snapshot_id"],
                      "series": {key: {k: item[k] for k in ("rows", "available_from", "available_to")}
                                 for key, item in result["series"].items()}}, indent=2))


if __name__ == "__main__":
    main()
