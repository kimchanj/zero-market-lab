"""Prospective research runner; default mode cannot mutate runtime or Registry."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

from zero_market_lab.research.forward_validation import (  # noqa: E402
    ASSETS, PREEXISTING_MAX_DATE, plan_contents, verify_forward,
)
from zero_market_lab.research.forward_evidence import (  # noqa: E402
    active_bars, append_correction, connect, evaluate_window, ingest,
    registry_projection, runtime_summary,
)
from zero_market_lab.research.context_data import latest_snapshot  # noqa: E402
from zero_market_lab.research.transit_analysis import (  # noqa: E402
    CONTEXT, context_on_dates, gate_intervals,
)
from zero_market_lab.research.comparison import ComparisonResearch  # noqa: E402
from zero_market_lab.market_phase.engine import PhaseEngine  # noqa: E402
from zero_market_lab.transit.quarters import load_quarters  # noqa: E402

DB = ROOT / "data/processed/research/forward_runtime/forward.sqlite3"
REGISTRY = ROOT / "data/reference/research_registry.json"


def fetch_new_rows(symbol: str, *, now: datetime) -> list[dict]:
    """Use existing provider parsers, excluding unfinished and baseline sessions."""
    import pandas as pd
    import requests

    lower = PREEXISTING_MAX_DATE[symbol]
    if symbol in {"005930", "000660"}:
        from zero_market_lab.tiger_v2.data import parse_daum_chart
        response = requests.get(f"https://finance.daum.net/api/charts/A{symbol}/days",
                                params={"limit": 500, "adjusted": "false"},
                                headers={"User-Agent": "Mozilla/5.0 (ZERO MARKET LAB research)",
                                         "Referer": f"https://finance.daum.net/quotes/A{symbol}"},
                                timeout=30)
        response.raise_for_status()
        frame, meta = parse_daum_chart(response.json())
        if not str(meta["symbol_code"]).startswith("KR7" + symbol):
            raise ValueError("Daum symbol mismatch")
        raw = response.content
        provider, series, zone = "Daum Finance secondary provider", "daily-unadjusted-ohlcv", "Asia/Seoul"
    elif symbol == "SP500":
        from zero_market_lab.market_data.loader import download, normalize
        raw, _, _ = download(lower, now.date().isoformat())
        frame, _, _ = normalize(raw)
        provider, series, zone = "FRED / S&P Dow Jones Indices", "SP500-price-index", "America/New_York"
    else:
        from scripts.fetch_us_seed import normalize, audit_split_continuity
        response = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
                                params={"range": "2y", "interval": "1d", "events": "div,splits"},
                                headers={"User-Agent": "Mozilla/5.0 (ZERO MARKET LAB research)"},
                                timeout=30)
        response.raise_for_status()
        document = response.json()
        frame, _ = normalize(document, symbol)
        audit_split_continuity(frame, document)
        raw = response.content
        provider, series, zone = "Yahoo Finance chart API (secondary provider)", "daily-ohlcv", "America/New_York"
    today = now.astimezone(ZoneInfo(zone)).date()
    source_hash = sha256(raw).hexdigest()
    raw_path = ROOT / "data/raw/forward" / symbol / f"{source_hash}.bin"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    if raw_path.exists():
        if sha256(raw_path.read_bytes()).hexdigest() != source_hash:
            raise ValueError("Stored provider response checksum changed")
    else:
        with raw_path.open("xb") as stream:
            stream.write(raw)
    rows = []
    for item in frame.to_dict("records"):
        day = pd.Timestamp(item["date"]).date()
        if day <= date.fromisoformat(lower) or day >= today:
            continue
        row = {"symbol": symbol, "provider": provider, "series": series,
               "observation_date": day.isoformat(), "collected_at": now.isoformat(),
               "source_hash": source_hash,
               "raw_path": raw_path.relative_to(ROOT).as_posix(),
               "close": float(item["close"])}
        if symbol != "SP500":
            row.update({field: float(item[field]) for field in ("open", "high", "low", "volume")})
        rows.append(row)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--ingest", action="store_true")
    group.add_argument("--finalize", action="store_true")
    group.add_argument("--correct-source", action="store_true",
                       help="Explicit source revision acceptance; old evidence remains")
    parser.add_argument("--symbol", choices=ASSETS)
    parser.add_argument("--date")
    parser.add_argument("--reason")
    args = parser.parse_args()
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    verify_forward(registry, plan_bytes=plan_contents(ROOT))
    if not args.ingest and not args.finalize and not args.correct_source:
        print(json.dumps({"protocol": registry["forward_protocol"]["protocol_id"],
                          "mode": "DRY_RUN", "registry_changed": False,
                          "runtime_exists": DB.exists(), "forward_windows_in_registry": 0,
                          "assets": list(ASSETS)}, ensure_ascii=False))
        return
    now = datetime.now(timezone.utc)
    with connect(DB) as db:
        if args.correct_source:
            if not args.symbol or not args.date or not args.reason:
                parser.error("--correct-source requires --symbol, --date and --reason")
            accepted = append_correction(db, args.symbol, args.date, args.reason, now=now)
            print(json.dumps({"mode": "CORRECT_SOURCE", "symbol": args.symbol,
                              "date": args.date, "accepted_hash": accepted}, ensure_ascii=False))
            return
        if args.ingest:
            outcome: dict = {}
            for symbol in ASSETS:
                counts: dict[str, int] = {}
                try:
                    for row in fetch_new_rows(symbol, now=now):
                        status = ingest(db, row, now=now)
                        counts[status] = counts.get(status, 0) + 1
                    outcome[symbol] = counts
                except Exception as error:
                    outcome[symbol] = f"DATA_UNAVAILABLE: {type(error).__name__}: {error}"
            print(json.dumps({"mode": "INGEST", "assets": outcome,
                              "runtime": runtime_summary(db)}, ensure_ascii=False))
            if any(isinstance(value, str) for value in outcome.values()):
                raise SystemExit(1)
            return
        snapshots = {layer: latest_snapshot(ROOT, layer) for layer in CONTEXT}
        outcomes: dict = {}
        by_gate = {entry["gate"]: entry["research_id"] for entry in registry["entries"]}
        _, quarters = load_quarters(ROOT)
        for symbol in ASSETS:
            try:
                bars = active_bars(db, symbol)
            except ValueError as error:
                outcomes[f"{symbol}:BLOCKED"] = str(error)
                continue
            if not bars:
                continue
            currency = "KRW" if symbol in {"005930", "000660"} else "USD"
            dates = [item["observation_date"] for item in bars]
            context = context_on_dates(ROOT, dates, currency, snapshots)
            corrected_days = {event["observation_date"] for row in db.execute(
                "SELECT payload FROM events WHERE kind='CORRECTION_APPENDED'")
                if (event := json.loads(row["payload"])).get("symbol") == symbol and
                "accepted_hash" in event}
            phases: dict[str, str] = {}
            if symbol != "SP500":
                import pandas as pd
                baseline, _ = ComparisonResearch(ROOT)._local(symbol)
                baseline = baseline.loc[baseline["date"] <= PREEXISTING_MAX_DATE[symbol],
                                        ["date", "open", "high", "low", "close", "volume"]]
                incoming = pd.DataFrame(bars)[["observation_date", "open", "high", "low", "close", "volume"]]
                incoming = incoming.rename(columns={"observation_date": "date"})
                price = pd.concat([baseline, incoming], ignore_index=True)
                phase_result = PhaseEngine().run(price, symbol=symbol,
                                                 data_source="FORWARD_LOCAL_AS_OF",
                                                 as_of=dates[-1])
                phases = {row["date"]: row["current_phase"] for row in phase_result["rows"]}
            for interval in gate_intervals(dates[0], now.date().isoformat()):
                research_id = by_gate.get(interval["gate"])
                if research_id:
                    status = evaluate_window(db, research_id=research_id, asset=symbol,
                                             interval=interval, bars=bars, now=now,
                                             context=context, phase_map=phases,
                                             quarter=quarters[interval["gate"]],
                                             allow_correction=any(day <= dates[-1]
                                                                  for day in corrected_days))
                    outcomes[status] = outcomes.get(status, 0) + 1
        summary_path = DB.parent / "registry_summary.json"
        summary_path.write_text(json.dumps(registry_projection(db, registry),
                                           ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"mode": "FINALIZE", "outcomes": outcomes,
                          "runtime": runtime_summary(db),
                          "registry_summary": str(summary_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
