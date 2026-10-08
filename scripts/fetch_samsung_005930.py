"""Fetch Samsung Electronics unadjusted daily OHLCV for local research only."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from zero_market_lab.tiger_v2.data import parse_daum_chart, validate_ohlcv  # noqa: E402

SOURCE_URL = "https://finance.daum.net/api/charts/A005930/days"


def fetch(limit: int = 350) -> tuple[dict, str]:
    if not 250 <= limit <= 2000:
        raise ValueError("limit must cover the 100-session warm-up")
    response = requests.get(
        SOURCE_URL, params={"limit": limit, "adjusted": "false"},
        headers={"User-Agent": "Mozilla/5.0 (ZERO MARKET LAB research)",
                 "Referer": "https://finance.daum.net/quotes/A005930"}, timeout=30,
    )
    response.raise_for_status()
    return response.json(), response.url


def persist(document: dict, resolved_url: str, as_of: date) -> dict:
    rows, source_meta = parse_daum_chart(document)
    if source_meta["symbol_code"] != "KR7005930003":
        raise ValueError("Unexpected Samsung provider symbol")
    rows = rows.loc[rows["date"] <= as_of].reset_index(drop=True)
    report = validate_ohlcv(rows, expected_first_date=rows.iloc[0]["date"])
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_dir = ROOT / "data/raw/samsung_005930" / stamp
    processed_dir = ROOT / "data/processed/samsung_005930" / stamp
    provenance_dir = ROOT / "data/provenance"
    for path in (raw_dir, processed_dir, provenance_dir):
        path.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    raw_path = raw_dir / "daum_unadjusted_chart_response.json"
    raw_path.write_bytes(raw)
    csv_path = processed_dir / "samsung_005930_ohlcv.csv"
    rows.to_csv(csv_path, index=False, date_format="%Y-%m-%d")
    provenance = {
        "instrument": "삼성전자", "symbol": "005930", "provider_symbol": source_meta["symbol_code"],
        "source": "Daum Finance daily chart API, adjusted=false (secondary provider)",
        "source_url": resolved_url, "retrieval_time": datetime.now(timezone.utc).isoformat(),
        "as_of": as_of.isoformat(), "adjusted_status": "UNADJUSTED",
        "raw_sha256": hashlib.sha256(raw).hexdigest(), "row_count": report.row_count,
        "actual_range": [report.first_date, report.last_date],
        "raw_file": str(raw_path.relative_to(ROOT)),
        "processed_file": str(csv_path.relative_to(ROOT)),
        "validation": report.to_dict(),
        "redistribution_status": "Unverified; raw and processed prices are Git-ignored and local-only",
    }
    out = provenance_dir / f"samsung_005930_{stamp}.json"
    out.write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")
    provenance["provenance_file"] = str(out.relative_to(ROOT))
    return provenance


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--limit", type=int, default=350)
    args = parser.parse_args()
    document, resolved = fetch(args.limit)
    print(json.dumps(persist(document, resolved, args.as_of), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
