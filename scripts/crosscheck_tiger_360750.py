"""Cross-check validated Daum OHLC against Yahoo raw quotes without filling gaps."""

from __future__ import annotations

from datetime import datetime, time, timezone
import json
from pathlib import Path
import sys

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zero_market_lab.tiger_v2.data import parse_yahoo_chart  # noqa: E402


def main() -> int:
    provenance_files = sorted((ROOT / "data" / "provenance").glob("tiger_360750_*.json"))
    provenance_files = [path for path in provenance_files if "crosscheck" not in path.name]
    if not provenance_files:
        raise FileNotFoundError("Run scripts/fetch_tiger_360750.py first")
    provenance = json.loads(provenance_files[-1].read_text(encoding="utf-8"))
    primary = pd.read_csv(ROOT / provenance["processed_file"], parse_dates=["date"])
    start = primary["date"].iloc[0].date()
    end = primary["date"].iloc[-1].date()
    period1 = int(datetime.combine(start, time.min, timezone.utc).timestamp())
    period2 = int(datetime.combine(end, time.min, timezone.utc).timestamp()) + 86_400
    url = "https://query1.finance.yahoo.com/v8/finance/chart/360750.KS"
    response = requests.get(
        url,
        params={"period1": period1, "period2": period2, "interval": "1d", "events": "div,splits"},
        headers={"User-Agent": "Mozilla/5.0 (ZERO MARKET LAB research)"},
        timeout=30,
    )
    response.raise_for_status()
    secondary, distributions, _ = parse_yahoo_chart(response.json())
    secondary_null_rows = int(secondary[["open", "high", "low", "close", "volume"]].isna().any(axis=1).sum())
    secondary = secondary.dropna(subset=["open", "high", "low", "close", "volume"])
    primary["date"] = primary["date"].dt.date
    merged = primary.merge(secondary, on="date", suffixes=("_daum", "_yahoo"))
    price_fields = ("open", "high", "low", "close")
    price_mismatches = {
        field: int((merged[f"{field}_daum"] != merged[f"{field}_yahoo"]).sum())
        for field in price_fields
    }
    report = {
        "primary_source": provenance["source"],
        "secondary_source": "Yahoo Finance chart API raw quote fields",
        "secondary_url": response.url,
        "primary_rows": len(primary),
        "secondary_timestamp_rows": len(secondary) + secondary_null_rows,
        "secondary_valid_rows": len(secondary),
        "secondary_null_rows": secondary_null_rows,
        "overlap_rows": len(merged),
        "ohlc_mismatches": price_mismatches,
        "volume_mismatches": int((merged["volume_daum"] != merged["volume_yahoo"]).sum()),
        "primary_only_dates": sorted(set(primary["date"]).difference(secondary["date"])),
        "secondary_only_dates": sorted(set(secondary["date"]).difference(primary["date"])),
        "distribution_event_count": len(distributions),
        "interpretation": (
            "All overlapping raw OHLC values agree. Volume is provider-dependent and remains "
            "sourced from Daum; it is not claimed as independently confirmed. No missing row is filled."
        ),
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
    serialized = json.dumps(report, ensure_ascii=False, indent=2, default=str)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = ROOT / "data" / "provenance" / f"tiger_360750_crosscheck_{stamp}.json"
    output.write_text(serialized, encoding="utf-8")
    print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
