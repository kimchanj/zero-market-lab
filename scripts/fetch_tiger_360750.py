"""Fetch and persist actual raw TIGER 360750 OHLCV plus provenance."""

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


SOURCE_URL = "https://finance.daum.net/api/charts/A360750/days"
OFFICIAL_KRX_URL = "https://data.krx.co.kr/?scrnId=02080706"
OFFICIAL_PRODUCT_URL = "https://www.tigeretf.com/upload/etf/20250804095324004654.pdf"


def fetch(start: date, end: date) -> tuple[dict, str]:
    params = {
        "limit": 2000,
        "adjusted": "false",
    }
    response = requests.get(
        SOURCE_URL,
        params=params,
        headers={
            "User-Agent": "Mozilla/5.0 (ZERO MARKET LAB research)",
            "Referer": "https://finance.daum.net/quotes/A360750",
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json(), response.url


def persist(document: dict, resolved_url: str, requested_start: date, requested_end: date) -> dict:
    retrieved = datetime.now(timezone.utc)
    stamp = retrieved.strftime("%Y%m%dT%H%M%SZ")
    raw_dir = ROOT / "data" / "raw" / "tiger_360750" / stamp
    processed_dir = ROOT / "data" / "processed" / "tiger_360750" / stamp
    provenance_dir = ROOT / "data" / "provenance"
    for directory in (raw_dir, processed_dir, provenance_dir):
        directory.mkdir(parents=True, exist_ok=True)

    raw_bytes = json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    raw_path = raw_dir / "daum_unadjusted_chart_response.json"
    raw_path.write_bytes(raw_bytes)

    frame, provider_meta = parse_daum_chart(document)
    requested_mask = (frame["date"] >= requested_start) & (frame["date"] <= requested_end)
    frame = frame.loc[requested_mask].reset_index(drop=True)
    report = validate_ohlcv(frame)
    ohlcv_path = processed_dir / "tiger_360750_ohlcv.csv"
    frame.to_csv(ohlcv_path, index=False, date_format="%Y-%m-%d")

    provenance = {
        "instrument": "TIGER 미국S&P500",
        "symbol": "360750",
        "provider_symbol": "A360750 / KR7360750004",
        "market": "KRX 유가증권시장 (KOSPI)",
        "currency": "KRW",
        "source": "Daum Finance daily chart API, adjusted=false (secondary provider)",
        "source_url": resolved_url,
        "official_krx_reference": OFFICIAL_KRX_URL,
        "official_product_reference": OFFICIAL_PRODUCT_URL,
        "official_source_status": (
            "KRX automatic download requires authenticated KRX_ID/KRX_PW as of 2026-09; "
            "credentials were not configured."
        ),
        "retrieval_time": retrieved.isoformat(),
        "frequency": "daily",
        "adjusted_status": (
            "Unadjusted response requested explicitly with adjusted=false. Open/high/low/close "
            "are raw exchange-traded fields. Adjusted history is not execution data."
        ),
        "distribution_handling": (
            "Cash distributions are not applied to raw execution prices and are not yet credited "
            "by a strategy engine. Official TIGER factsheets confirm quarterly distributions."
        ),
        "requested_range": [requested_start.isoformat(), requested_end.isoformat()],
        "actual_range": [report.first_date, report.last_date],
        "row_count": report.row_count,
        "raw_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "raw_file": str(raw_path.relative_to(ROOT)),
        "processed_file": str(ohlcv_path.relative_to(ROOT)),
        "missing_date_policy": report.missing_date_policy,
        "validation": report.to_dict(),
        "provider_metadata": provider_meta,
    }
    provenance_path = provenance_dir / f"tiger_360750_{stamp}.json"
    provenance_path.write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")
    provenance["provenance_file"] = str(provenance_path.relative_to(ROOT))
    return provenance


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=date.fromisoformat, default=date(2020, 8, 1))
    parser.add_argument("--end", type=date.fromisoformat, default=date.today())
    args = parser.parse_args()
    document, resolved_url = fetch(args.start, args.end)
    print(json.dumps(persist(document, resolved_url, args.start, args.end), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
