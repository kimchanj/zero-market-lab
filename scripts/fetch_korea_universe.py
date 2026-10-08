"""Optional local-only acquisition of curated Korean daily OHLCV.

Never commits or publishes fetched rows. Request failures remain visible and do
not silently substitute synthetic data.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from zero_market_lab.asset_discovery.catalog import load_universe  # noqa: E402
from zero_market_lab.tiger_v2.data import parse_daum_chart, validate_ohlcv  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", nargs="+", required=True)
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()
    allowed = {item["symbol"] for item in load_universe(ROOT / "config/universe_seed_kr_us.json")
               if item["market"] == "KRX"}
    if args.limit < 350 or args.limit > 1500 or not set(args.symbols) <= allowed:
        parser.error("Use configured symbols and 350–1500 daily rows")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for symbol in args.symbols:
        try:
            response = requests.get(f"https://finance.daum.net/api/charts/A{symbol}/days",
                                    params={"limit": args.limit, "adjusted": "false"},
                                    headers={"User-Agent": "Mozilla/5.0 (ZERO MARKET LAB research)",
                                             "Referer": f"https://finance.daum.net/quotes/A{symbol}"},
                                    timeout=30)
            response.raise_for_status()
            document = response.json()
            frame, metadata = parse_daum_chart(document)
            if not str(metadata["symbol_code"]).startswith("KR7" + symbol):
                raise ValueError("Provider returned another symbol")
            report = validate_ohlcv(frame, expected_first_date=frame.iloc[0]["date"])
            folder = ROOT / "data/processed" / f"korea_{symbol}" / stamp
            folder.mkdir(parents=True, exist_ok=True)
            frame.to_csv(folder / "ohlcv.csv", index=False)
            source_meta = {"symbol": symbol, "provider": "Daum Finance secondary provider",
                           "source_url": response.url, "retrieved_at": datetime.now(timezone.utc).isoformat(),
                           "adjustment": "UNADJUSTED", "adjusted_request": False,
                           "response_sha256": sha256(response.content).hexdigest(),
                           "row_count": report.row_count,
                           "actual_range": [report.first_date, report.last_date],
                           "redistribution_status": "Unverified; local Git-ignored research cache"}
            (folder / "metadata.json").write_text(json.dumps(source_meta, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps({"symbol": symbol, "status": "OK", "rows": report.row_count,
                              "actual_range": [report.first_date, report.last_date]}, ensure_ascii=False))
        except (requests.RequestException, ValueError, KeyError) as error:
            print(json.dumps({"symbol": symbol, "status": "ERROR", "reason": type(error).__name__},
                             ensure_ascii=False))


if __name__ == "__main__":
    main()
