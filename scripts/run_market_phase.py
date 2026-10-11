"""Run frozen price-only phase labels on the local seed universe; no orders/UI."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date
import json
from pathlib import Path
import statistics
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zero_market_lab.asset_discovery.catalog import LocalOHLCVCatalog, load_universe  # noqa: E402
from zero_market_lab.market_phase import PhaseEngine  # noqa: E402


def _median(values: list[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    return statistics.median(present) if present else None


def summarize(result: dict) -> dict:
    spring, autumn = result["spring_events"], result["autumn_events"]
    spring_outcomes = Counter(item["outcome"] for item in spring)
    autumn_outcomes = Counter(item["outcome"] for item in autumn)
    transitions = Counter(f'{item["from_phase"]}->{item["to_phase"]}'
                          for item in result["transitions"])
    rows = result["rows"]
    durations_by_phase = defaultdict(list)
    for segment in result["durations"]:
        durations_by_phase[segment["phase"]].append(segment["trading_days"])
    spring_dates = {item["date"] for item in spring}
    autumn_dates = {item["date"] for item in autumn}
    baseline_spring = [row for row in rows if row["date"] in spring_dates]
    baseline_autumn = [row for row in rows if row["date"] in autumn_dates]
    resolved_spring = spring_outcomes["CONFIRMED"] + spring_outcomes["FALSE_SPRING"]
    resolved_autumn = autumn_outcomes["WINTER"] + autumn_outcomes["FALSE_AUTUMN"]
    return {
        "symbol": result["symbol"], "observations": len(rows),
        "first_date": rows[0]["date"], "last_date": rows[-1]["date"],
        "latest_phase": rows[-1]["current_phase"],
        "phase_days": dict(Counter(row["current_phase"] for row in rows)),
        "phase_duration_statistics": {phase: {"episodes": len(lengths),
                                               "median_trading_days": statistics.median(lengths),
                                               "max_trading_days": max(lengths)}
                                      for phase, lengths in durations_by_phase.items()},
        "transition_counts": dict(transitions),
        "spring_candidate_count": len(spring),
        "confirmed_spring_count": spring_outcomes["CONFIRMED"],
        "summer_transition_count": sum(item["to_phase"] == "SUMMER" for item in result["transitions"]),
        "candidate_to_summer_within_120d_count": sum(item["days_to_summer_120d"] is not None
                                                     for item in spring),
        "false_spring_count": spring_outcomes["FALSE_SPRING"],
        "false_spring_rate_resolved": (spring_outcomes["FALSE_SPRING"] / resolved_spring
                                       if resolved_spring else None),
        "spring_unresolved": spring_outcomes["UNRESOLVED"],
        "spring_censored": spring_outcomes["CENSORED"],
        "median_days_to_spring": _median([item["days_to_outcome"] for item in spring
                                          if item["outcome"] == "CONFIRMED"]),
        "median_days_to_summer_120d": _median([item["days_to_summer_120d"] for item in spring]),
        **{f"median_spring_{h}d_return": _median([item[f"return_{h}d"] for item in spring])
           for h in (20, 60, 120)},
        "worst_spring_60d_return": min((item["return_60d"] for item in spring
                                         if item["return_60d"] is not None), default=None),
        "autumn_count": len(autumn),
        "autumn_to_winter": autumn_outcomes["WINTER"],
        "autumn_to_summer_resume": autumn_outcomes["FALSE_AUTUMN"],
        "false_autumn_count": autumn_outcomes["FALSE_AUTUMN"],
        "false_autumn_rate_resolved": (autumn_outcomes["FALSE_AUTUMN"] / resolved_autumn
                                       if resolved_autumn else None),
        "autumn_unresolved": autumn_outcomes["UNRESOLVED"],
        "autumn_censored": autumn_outcomes["CENSORED"],
        **{f"median_autumn_{h}d_return": _median([item[f"return_{h}d"] for item in autumn])
           for h in (20, 60, 120)},
        "spring_candidate_baseline_ma200_false": sum(row["ma200_entry_filter_allowed_next_day"] is False
                                                      for row in baseline_spring),
        "autumn_baseline_ma200_true": sum(row["ma200_entry_filter_allowed_next_day"] is True
                                          for row in baseline_autumn),
    }


def run(*, as_of: date, output: Path) -> dict:
    catalog = LocalOHLCVCatalog(ROOT)
    universe = load_universe(ROOT / "config/universe_seed_kr_us.json")
    output.mkdir(parents=True, exist_ok=True)
    summary = {"as_of": as_of.isoformat(), "rule_version": "PRICE_PHASE_V1",
               "selection_warning": "Six manually selected surviving assets; overlapping events are not independent.",
               "assets": [], "errors": []}
    for asset in universe:
        symbol = asset["symbol"]
        try:
            frame, provenance = catalog.load(symbol)
            frame = frame.loc[pd.to_datetime(frame["date"]) <= pd.Timestamp(as_of)].copy()
            source = str(provenance.get("provider", "LOCAL_UNVERIFIED"))
            result = PhaseEngine().run(frame, symbol=symbol, data_source=source)
            rows = pd.DataFrame(result["rows"])
            rows["evidence"] = rows["evidence"].map(lambda item: json.dumps(item, sort_keys=True))
            rows.to_csv(output / f"{symbol}_daily.csv", index=False, encoding="utf-8-sig")
            with (output / f"{symbol}_events.json").open("w", encoding="utf-8") as stream:
                json.dump({key: result[key] for key in ("transitions", "durations", "spring_events",
                                                           "autumn_events")}, stream, ensure_ascii=False, indent=2)
            asset_summary = summarize(result)
            asset_summary.update({"name": asset["name"], "market": asset["market"],
                                  "data_source": source, "adjustment": provenance.get("adjustment"),
                                  "rule_config_hash": result["rule_config_hash"]})
            summary["assets"].append(asset_summary)
        except (ValueError, FileNotFoundError, KeyError) as error:
            summary["errors"].append({"symbol": symbol, "type": type(error).__name__,
                                      "reason": str(error)})
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", type=date.fromisoformat, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "fecm-price-phase-v1")
    args = parser.parse_args()
    report = run(as_of=args.as_of, output=args.output)
    for item in report["assets"]:
        print(f'{item["symbol"]} {item["latest_phase"]} candidate={item["spring_candidate_count"]} '
              f'false_spring={item["false_spring_count"]} autumn={item["autumn_count"]}')
    for error in report["errors"]:
        print(f'ERROR {error["symbol"]}: {error["reason"]}', file=sys.stderr)
    print(args.output)
    if report["errors"]:
        raise SystemExit(1)
