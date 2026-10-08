"""Run a local historical discovery batch and export JSON/CSV matrix."""

from __future__ import annotations

import argparse
from datetime import date, datetime
from decimal import Decimal
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from zero_market_lab.asset_discovery.catalog import LocalOHLCVCatalog, load_universe  # noqa: E402
from zero_market_lab.asset_discovery.engine import ResearchRunConfig, run_discovery  # noqa: E402


def build_report(*, as_of: date | None = None, lookback: str = "1Y", capital: Decimal = Decimal(500000),
                 us_capital: Decimal = Decimal(500)) -> dict:
    as_of = as_of or datetime.now(ZoneInfo("Asia/Seoul")).date()
    universe = load_universe(ROOT / "config/universe_seed_kr_us.json")
    catalog = LocalOHLCVCatalog(ROOT)
    report = run_discovery(universe, catalog.load,
                           ResearchRunConfig(as_of, lookback, capital, us_capital))
    report["load_counts"] = catalog.read_count
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", type=date.fromisoformat)
    parser.add_argument("--lookback", choices=("6M", "1Y", "3Y", "5Y"), default="1Y")
    parser.add_argument("--krw-capital", type=Decimal, default=Decimal(500000))
    parser.add_argument("--usd-capital", type=Decimal, default=Decimal(500))
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/asset_discovery")
    args = parser.parse_args()
    report = build_report(as_of=args.as_of, lookback=args.lookback,
                          capital=args.krw_capital, us_capital=args.usd_capital)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "research_run.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = [{"symbol": cell["symbol"], "name": cell["name"], "market": cell["market"],
             "currency": cell["currency"], "strategy_id": cell["strategy_id"],
             "status": cell["status"], "reason": cell["reason"],
             **(cell["metrics"] or {}), "atr_pct": cell["profile"]["atr_pct"]}
            for cell in report["cells"]]
    pd.DataFrame(rows).to_csv(args.output / "matrix.csv", index=False)
    print(json.dumps({"run_id": report["run_id"], "assets_ok": sum(a["status"] == "OK" for a in report["assets"]),
                      "assets_skipped": sum(a["status"] != "OK" for a in report["assets"]),
                      "cells": len(report["cells"]), "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
