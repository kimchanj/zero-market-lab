"""Fetch US seed raw daily OHLCV into a Git-ignored local research cache."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from zero_market_lab.asset_discovery.catalog import load_universe  # noqa: E402
from zero_market_lab.tiger_v2.data import validate_ohlcv  # noqa: E402


def normalize(document: dict, symbol: str) -> tuple[pd.DataFrame, dict]:
    chart = document.get("chart", {})
    if chart.get("error") or len(chart.get("result") or []) != 1:
        raise ValueError("Unusable Yahoo chart response")
    result = chart["result"][0]
    meta = result.get("meta", {})
    if meta.get("symbol", "").upper() != symbol:
        raise ValueError("Provider returned another symbol")
    exchange_tz = meta.get("exchangeTimezoneName")
    if exchange_tz != "America/New_York":
        raise ValueError("Unexpected exchange timezone")
    timestamps = result.get("timestamp") or []
    quote = (result.get("indicators", {}).get("quote") or [{}])[0]
    adjusted = (result.get("indicators", {}).get("adjclose") or [{}])[0].get("adjclose")
    if not timestamps or any(len(quote.get(key, [])) != len(timestamps)
                             for key in ("open", "high", "low", "close", "volume")):
        raise ValueError("Incomplete OHLCV array")
    frame = pd.DataFrame({
        "date": [datetime.fromtimestamp(int(ts), timezone.utc).astimezone(ZoneInfo(exchange_tz)).date()
                 for ts in timestamps],
        **{key: quote[key] for key in ("open", "high", "low", "close", "volume")},
        "adjusted_close": adjusted if adjusted and len(adjusted) == len(timestamps)
                          else [None] * len(timestamps),
    })
    frame = frame.sort_values("date").reset_index(drop=True)
    report = validate_ohlcv(frame, expected_first_date=frame.iloc[0]["date"])
    return frame, {"exchange_timezone": exchange_tz, "currency": meta.get("currency"),
                   "splits_count": len(result.get("events", {}).get("splits") or {}),
                   "dividend_events_count": len(result.get("events", {}).get("dividends") or {}),
                   "validation": report.to_dict()}


def completed_daily_bars(frame: pd.DataFrame, exchange_today: date) -> pd.DataFrame:
    """Exclude a provider's potentially incomplete current exchange-day bar."""
    completed = frame.loc[frame.date < exchange_today].reset_index(drop=True)
    if completed.empty:
        raise ValueError("No completed US daily bars")
    return completed


def audit_split_continuity(frame: pd.DataFrame, document: dict) -> list[dict]:
    """Reject a raw split-sized quote discontinuity at declared split events."""
    result = document["chart"]["result"][0]
    events = (result.get("events") or {}).get("splits") or {}
    checks = []
    for event in events.values():
        event_date = datetime.fromtimestamp(int(event["date"]), timezone.utc).astimezone(
            ZoneInfo("America/New_York")).date()
        matching = frame.index[frame.date == event_date]
        if len(matching) != 1 or int(matching[0]) == 0:
            raise ValueError("Split event has no comparable quote session")
        index = int(matching[0])
        close_ratio = float(frame.iloc[index]["close"] / frame.iloc[index - 1]["close"])
        if not 0.5 <= close_ratio <= 1.5:
            raise ValueError("Split-sized quote discontinuity")
        checks.append({"date": event_date.isoformat(), "ratio": event["splitRatio"],
                       "close_ratio": round(close_ratio, 6)})
    return checks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", nargs="+", default=["NVDA", "MSFT", "AAPL"])
    parser.add_argument("--range", choices=("2y", "5y", "10y"), default="2y")
    args = parser.parse_args()
    allowed = {item["symbol"] for item in load_universe(ROOT / "config/universe_seed_kr_us.json")
               if item["market"] == "US"}
    if not set(args.symbols) <= allowed:
        parser.error("Use only configured US seed symbols")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for symbol in args.symbols:
        try:
            response = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
                                    params={"range": args.range, "interval": "1d", "events": "div,splits"},
                                    headers={"User-Agent": "Mozilla/5.0 (ZERO MARKET LAB research)"},
                                    timeout=30)
            response.raise_for_status()
            document = response.json()
            frame, metadata = normalize(document, symbol)
            # A provider can expose today's still-changing bar during the US session.
            # Keep only dates strictly before the current New York calendar day.
            exchange_today = datetime.now(ZoneInfo("America/New_York")).date()
            frame = completed_daily_bars(frame, exchange_today)
            metadata["validation"] = validate_ohlcv(
                frame, expected_first_date=frame.iloc[0]["date"]).to_dict()
            metadata["excluded_current_exchange_date"] = exchange_today.isoformat()
            metadata["split_continuity_checks"] = audit_split_continuity(frame, document)
            raw = ROOT / "data/raw" / f"us_{symbol}" / stamp
            processed = ROOT / "data/processed" / f"us_{symbol}" / stamp
            raw.mkdir(parents=True, exist_ok=True)
            processed.mkdir(parents=True, exist_ok=True)
            (raw / "chart.json").write_bytes(response.content)
            frame.to_csv(processed / "ohlcv.csv", index=False, date_format="%Y-%m-%d")
            manifest = {"symbol": symbol, "provider": "Yahoo Finance chart API (secondary provider)",
                        "source_url": response.url, "retrieved_at": datetime.now(timezone.utc).isoformat(),
                        "market": "US", "currency": "USD", "timezone": "America/New_York",
                        "adjustment": "PROVIDER_QUOTE_SPLIT_EVENT_CONTINUITY_CHECKED" if metadata["split_continuity_checks"]
                                      else "PROVIDER_QUOTE_NO_SPLIT_EVENT_IN_RANGE",
                        "adjustment_policy": "Provider quote OHLC used for execution; declared split events checked for quote continuity. Adjusted close is supplemental only; dividends excluded.",
                        "adjusted_close": "SUPPLEMENTAL_ONLY",
                        "dividends": "EXCLUDED_FROM_STRATEGY", "response_sha256": sha256(response.content).hexdigest(),
                        "row_count": len(frame), "actual_range": [frame.iloc[0].date.isoformat(),
                                                                   frame.iloc[-1].date.isoformat()],
                        "redistribution_status": "Unverified; Git-ignored local research cache",
                        **metadata}
            (processed / "metadata.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                                                     encoding="utf-8")
            print(json.dumps({"symbol": symbol, "status": "OK", "rows": len(frame),
                              "actual_range": manifest["actual_range"],
                              "splits": manifest["splits_count"]}, ensure_ascii=False))
        except (requests.RequestException, ValueError, KeyError, TypeError) as error:
            print(json.dumps({"symbol": symbol, "status": "DATA_UNAVAILABLE",
                              "reason": type(error).__name__}, ensure_ascii=False))


if __name__ == "__main__":
    main()
