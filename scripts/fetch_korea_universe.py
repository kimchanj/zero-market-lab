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

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from zero_market_lab.asset_discovery.catalog import load_universe  # noqa: E402
from zero_market_lab.tiger_v2.data import parse_daum_chart, validate_ohlcv  # noqa: E402


class DataHistoryChangedError(ValueError):
    """The provider cannot safely extend the locally accepted price history."""


def merge_verified_history(previous: pd.DataFrame | None, incoming: pd.DataFrame) -> pd.DataFrame:
    """Retain older rows outside a provider window; reject any overlapping revision.

    Paper journals hash their full preceding history. A rolling provider window
    must therefore never silently truncate or rewrite a locally accepted bar.
    """

    incoming = incoming.copy()
    incoming["date"] = pd.to_datetime(incoming["date"], errors="coerce").dt.date
    validate_ohlcv(incoming, expected_first_date=incoming.iloc[0]["date"])
    if previous is None:
        return incoming

    previous = previous.copy()
    previous["date"] = pd.to_datetime(previous["date"], errors="coerce").dt.date
    validate_ohlcv(previous, expected_first_date=previous.iloc[0]["date"])
    if set(previous.columns) != set(incoming.columns):
        raise DataHistoryChangedError("DATA_HISTORY_CHANGED: OHLCV schema changed")

    first_incoming = incoming.iloc[0]["date"]
    last_previous = previous.iloc[-1]["date"]
    if first_incoming > last_previous or last_previous not in set(incoming["date"]):
        raise DataHistoryChangedError(
            f"DATA_HISTORY_CHANGED: latest accepted date {last_previous} is absent from provider window"
        )

    overlap = previous.loc[previous["date"] >= first_incoming].reset_index(drop=True)
    incoming_overlap = incoming.loc[incoming["date"] <= last_previous].reset_index(drop=True)
    old_dates = overlap["date"].tolist()
    new_dates = incoming_overlap["date"].tolist()
    if old_dates != new_dates:
        missing = sorted(set(old_dates) - set(new_dates))
        unexpected = sorted(set(new_dates) - set(old_dates))
        raise DataHistoryChangedError(
            f"DATA_HISTORY_CHANGED: overlap dates differ; missing={missing[:1]}, unexpected={unexpected[:1]}"
        )
    try:
        pd.testing.assert_frame_equal(overlap[incoming.columns], incoming_overlap[incoming.columns],
                                      check_dtype=False)
    except AssertionError as error:
        for column in incoming.columns.drop("date"):
            for index, (old, new) in enumerate(zip(overlap[column], incoming_overlap[column])):
                if old != new:
                    raise DataHistoryChangedError(
                        f"DATA_HISTORY_CHANGED: date={old_dates[index]} field={column} "
                        f"accepted={old} provider={new}"
                    ) from error
        raise DataHistoryChangedError("DATA_HISTORY_CHANGED: overlap values differ") from error

    appended = incoming.loc[incoming["date"] > last_previous]
    merged = pd.concat([previous, appended], ignore_index=True)
    validate_ohlcv(merged, expected_first_date=merged.iloc[0]["date"])
    return merged


def latest_accepted_history(symbol: str) -> pd.DataFrame | None:
    namespace = ROOT / "data/processed" / f"korea_{symbol}"
    paths = sorted(namespace.glob("*/ohlcv.csv"))
    if not paths:
        return None
    latest = paths[-1]
    metadata_path = latest.parent / "metadata.json"
    if not metadata_path.exists():
        raise ValueError("Previous OHLCV metadata missing; manual review required")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if (metadata.get("symbol") != symbol or metadata.get("adjustment") != "UNADJUSTED"
            or metadata.get("provider") != "Daum Finance secondary provider"):
        raise ValueError("Previous OHLCV provenance changed; manual review required")
    return pd.read_csv(latest)


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
    had_error = False
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
            provider_rows = len(frame)
            previous = latest_accepted_history(symbol)
            previous_rows = len(previous) if previous is not None else 0
            previous_latest = str(previous.iloc[-1]["date"]) if previous is not None else None
            frame = merge_verified_history(previous, frame)
            report = validate_ohlcv(frame, expected_first_date=frame.iloc[0]["date"])
            appended_rows = len(frame) - previous_rows
            csv_bytes = frame.to_csv(index=False).encode("utf-8")
            folder = ROOT / "data/processed" / f"korea_{symbol}" / stamp
            folder.mkdir(parents=True, exist_ok=False)
            source_meta = {"symbol": symbol, "provider": "Daum Finance secondary provider",
                           "source_url": response.url, "retrieved_at": datetime.now(timezone.utc).isoformat(),
                           "adjustment": "UNADJUSTED", "adjusted_request": False,
                           "response_sha256": sha256(response.content).hexdigest(),
                           "history_sha256": sha256(csv_bytes).hexdigest(),
                           "history_policy": "VERIFIED_APPEND_ONLY",
                           "history_validation": "PASS",
                           "provider_window_row_count": provider_rows,
                           "previous_latest_date": previous_latest,
                           "previous_rows": previous_rows,
                           "appended_rows": appended_rows,
                           "row_count": report.row_count,
                           "actual_range": [report.first_date, report.last_date],
                           "redistribution_status": "Unverified; local Git-ignored research cache"}
            (folder / "metadata.json").write_text(json.dumps(source_meta, ensure_ascii=False, indent=2), encoding="utf-8")
            pending_csv = folder / "ohlcv.csv.tmp"
            pending_csv.write_bytes(csv_bytes)
            pending_csv.replace(folder / "ohlcv.csv")
            print(json.dumps({"symbol": symbol, "status": "OK", "rows": report.row_count,
                              "actual_range": [report.first_date, report.last_date],
                              "previous_latest_date": previous_latest,
                              "previous_rows": previous_rows, "appended_rows": appended_rows,
                              "provider": source_meta["provider"], "history_validation": "PASS"},
                             ensure_ascii=False))
        except (requests.RequestException, ValueError, KeyError) as error:
            had_error = True
            print(json.dumps({"symbol": symbol, "status": "ERROR", "reason": type(error).__name__,
                              "detail": str(error)},
                             ensure_ascii=False))
    if had_error:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
