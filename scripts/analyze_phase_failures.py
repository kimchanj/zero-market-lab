"""Describe frozen PRICE_PHASE_V1 events; never recompute or alter phase labels."""

from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import statistics
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from zero_market_lab.asset_discovery.catalog import LocalOHLCVCatalog  # noqa: E402
from zero_market_lab.market_phase.engine import RULE_CONFIG_HASH, VERSION  # noqa: E402

SYMBOLS = ("005930", "000660", "035420", "NVDA", "MSFT", "AAPL")
BASELINE = {"candidate": 75, "confirmed": 16, "summer": 15, "false_spring": 59,
            "autumn": 87, "winter": 12, "summer_resume": 67, "unresolved": 7,
            "censored": 1}
SPRING_GROUP = {"CONFIRMED": "SPRING_SUCCESS", "FALSE_SPRING": "FALSE_SPRING",
                "CENSORED": "RIGHT_CENSORED", "UNRESOLVED": "UNRESOLVED"}
AUTUMN_GROUP = {"WINTER": "AUTUMN_TO_WINTER", "FALSE_AUTUMN": "AUTUMN_TO_SUMMER",
                "CENSORED": "RIGHT_CENSORED", "UNRESOLVED": "UNRESOLVED"}
SPRING_NUMERIC = ("ma50_minus_ma200_pct", "price_minus_ma50_pct", "price_minus_ma200_pct",
                  "ma50_slope_pct", "ma200_slope_pct", "ma50_slope_change_pct",
                  "ma200_slope_change_pct", "recovery_from_recent_low", "drawdown_from_52w_high",
                  "volatility_20d", "distance_from_recent_low_pct",
                  "distance_from_recent_high_pct", "days_in_previous_phase")
AUTUMN_NUMERIC = SPRING_NUMERIC + ("days_since_52w_high", "days_in_summer_before_autumn")
BOOLEAN = ("recent_higher_low", "recent_higher_high", "breakout_20d",
           "ma200_slope_flat_or_improving", "ma200_slope_positive", "breakdown_below_ma50",
           "ma200_filter_pass", "ma50_above_ma200")


def verify_baseline(source: Path) -> tuple[dict, dict[str, pd.DataFrame], dict[str, dict], dict[str, str]]:
    summary = json.loads((source / "summary.json").read_text(encoding="utf-8"))
    assets = summary["assets"]
    if summary["errors"] or {a["symbol"] for a in assets} != set(SYMBOLS):
        raise ValueError("Baseline asset set or errors differ; analysis halted")
    counts = {"candidate": sum(a["spring_candidate_count"] for a in assets),
              "confirmed": sum(a["confirmed_spring_count"] for a in assets),
              "summer": sum(a["candidate_to_summer_within_120d_count"] for a in assets),
              "false_spring": sum(a["false_spring_count"] for a in assets),
              "autumn": sum(a["autumn_count"] for a in assets),
              "winter": sum(a["autumn_to_winter"] for a in assets),
              "summer_resume": sum(a["autumn_to_summer_resume"] for a in assets),
              "unresolved": sum(a["autumn_unresolved"] for a in assets),
              "censored": sum(a["autumn_censored"] for a in assets)}
    if counts != BASELINE or any(a["rule_config_hash"] != RULE_CONFIG_HASH for a in assets):
        raise ValueError(f"Frozen baseline mismatch: {counts} / expected {BASELINE}")
    daily, events, hashes = {}, {}, {}
    for symbol in SYMBOLS:
        path = source / f"{symbol}_daily.csv"
        hashes[symbol] = sha256(path.read_bytes()).hexdigest()
        daily[symbol] = pd.read_csv(path, encoding="utf-8-sig")
        events[symbol] = json.loads((source / f"{symbol}_events.json").read_text(encoding="utf-8"))
        if (set(daily[symbol]["engine_version"]) != {VERSION} or
                set(daily[symbol]["rule_config_hash"]) != {RULE_CONFIG_HASH}):
            raise ValueError(f"Frozen daily labels mismatch: {symbol}")
        if len(events[symbol]["spring_events"]) != next(a["spring_candidate_count"] for a in assets if a["symbol"] == symbol):
            raise ValueError(f"Frozen event count mismatch: {symbol}")
    return summary, daily, events, hashes


def _float(value) -> float | None:
    return float(value) if pd.notna(value) else None


def _ratio(a, b) -> float | None:
    return _float(a / b - 1) if pd.notna(a) and pd.notna(b) and b else None


def asof_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Descriptive features only; rolling windows use t and earlier observations."""
    f = frame.copy().sort_values("date").reset_index(drop=True)
    f["date"] = pd.to_datetime(f["date"])
    for col in ("open", "high", "low", "close"):
        f[col] = pd.to_numeric(f[col])
    c, h, l = f["close"], f["high"], f["low"]
    f["ma50"] = c.rolling(50, min_periods=50).mean()
    f["ma200"] = c.rolling(200, min_periods=200).mean()
    f["ma50_slope_pct"] = f["ma50"] / f["ma50"].shift(5) - 1
    f["ma200_slope_pct"] = f["ma200"] / f["ma200"].shift(10) - 1
    f["ma50_slope_change_pct"] = f["ma50_slope_pct"] - f["ma50_slope_pct"].shift(5)
    f["ma200_slope_change_pct"] = f["ma200_slope_pct"] - f["ma200_slope_pct"].shift(10)
    f["volatility_20d"] = c.pct_change(fill_method=None).rolling(20, min_periods=20).std()
    f["recent_low20"] = l.rolling(20, min_periods=20).min()
    f["recent_high20"] = h.rolling(20, min_periods=20).max()
    f["high52w"] = h.rolling(252, min_periods=252).max()
    f["days_since_52w_high"] = [
        (251 - int(np.argmax(h.iloc[i-251:i+1].to_numpy()))) if i >= 251 else np.nan
        for i in range(len(f))]
    return f.set_index(f["date"].dt.strftime("%Y-%m-%d"), drop=False)


def snapshot(symbol: str, date: str, daily: pd.DataFrame, features: pd.DataFrame,
             previous_duration: int, *, kind: str) -> dict:
    day = daily.loc[daily["date"] == date].iloc[0]
    f = features.loc[date]
    evidence = json.loads(day["evidence"])
    ma50, ma200, close = f["ma50"], f["ma200"], f["close"]
    return {"symbol": symbol, "date": date, "close": float(close),
            "ma50": _float(ma50), "ma200": _float(ma200),
            "ma50_minus_ma200_pct": _ratio(ma50, ma200),
            "price_minus_ma50_pct": _ratio(close, ma50),
            "price_minus_ma200_pct": _ratio(close, ma200),
            "ma50_slope_pct": _float(f["ma50_slope_pct"]),
            "ma200_slope_pct": _float(f["ma200_slope_pct"]),
            "ma50_slope_change_pct": _float(f["ma50_slope_change_pct"]),
            "ma200_slope_change_pct": _float(f["ma200_slope_change_pct"]),
            "volatility_20d": _float(f["volatility_20d"]),
            "distance_from_recent_low_pct": _ratio(close, f["recent_low20"]),
            "distance_from_recent_high_pct": _ratio(close, f["recent_high20"]),
            "days_since_52w_high": _float(f["days_since_52w_high"]),
            "days_in_previous_phase": previous_duration,
            "days_in_summer_before_autumn": previous_duration if kind == "autumn" else None,
            "breakdown_below_ma50": bool(close < ma50),
            "ma200_filter_pass": (bool(day["ma200_entry_filter_allowed_next_day"])
                                  if pd.notna(day["ma200_entry_filter_allowed_next_day"]) else None),
            **evidence}


def build_events(daily: dict[str, pd.DataFrame], events: dict[str, dict],
                 catalog: LocalOHLCVCatalog) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
    spring, autumn, features = [], [], {}
    for symbol in SYMBOLS:
        raw, _ = catalog.load(symbol)
        f = asof_features(raw)
        f = f.loc[:daily[symbol]["date"].iloc[-1]]
        features[symbol] = f
        if not np.allclose(f.loc[daily[symbol]["date"], "close"].to_numpy(), daily[symbol]["close"].to_numpy()):
            raise ValueError(f"Local OHLC does not match frozen daily labels: {symbol}")
        transitions = {item["transition_date"]: item for item in events[symbol]["transitions"]}
        for kind, target, group_map, output in (("spring", "SPRING_CANDIDATE", SPRING_GROUP, spring),
                                                ("autumn", "AUTUMN", AUTUMN_GROUP, autumn)):
            for event in events[symbol][f"{kind}_events"]:
                day = event["date"]
                transition = transitions[day]
                if transition["to_phase"] != target:
                    raise ValueError(f"Event/transition mismatch: {symbol} {day}")
                point = snapshot(symbol, day, daily[symbol], f, transition["previous_duration"], kind=kind)
                output.append({**point, "group": group_map[event["outcome"]],
                               "original_outcome": event["outcome"],
                               "days_to_outcome": event["days_to_outcome"],
                               "days_to_summer_120d": event.get("days_to_summer_120d"),
                               "return_20d": event["return_20d"],
                               "return_60d": event["return_60d"],
                               "return_120d": event["return_120d"],
                               "max_forward_drawdown_120d": event["max_forward_drawdown_120d"]})
    return pd.DataFrame(spring), pd.DataFrame(autumn), features


def cluster_events(events: pd.DataFrame, daily: dict[str, pd.DataFrame], *, gap: int = 30) -> pd.DataFrame:
    """Supplemental per-symbol episodes; never replaces raw event outcomes."""
    clusters = []
    for symbol in SYMBOLS:
        positions = {date: i for i, date in enumerate(daily[symbol]["date"])}
        ordered = events.loc[events["symbol"] == symbol].sort_values("date")
        start = last = None
        members = []
        for row in ordered.itertuples(index=False):
            at = positions[row.date]
            if last is not None and at - last > gap:
                clusters.append({"symbol": symbol, "cluster_start": start, "cluster_end": members[-1]["date"],
                                 "event_count": len(members), "groups": dict(Counter(x["group"] for x in members))})
                members = []
            if not members:
                start = row.date
            members.append({"date": row.date, "group": row.group})
            last = at
        if members:
            clusters.append({"symbol": symbol, "cluster_start": start, "cluster_end": members[-1]["date"],
                             "event_count": len(members), "groups": dict(Counter(x["group"] for x in members))})
    return pd.DataFrame(clusters)


def diff_table(events: pd.DataFrame, first: str, second: str,
               numeric: tuple[str, ...]) -> pd.DataFrame:
    """Descriptive effect sizes; zero-variance pooled SD is undefined, not zero."""
    rows = []
    for field in numeric + BOOLEAN:
        a, b = events.loc[events["group"] == first, field], events.loc[events["group"] == second, field]
        if field in BOOLEAN:
            a, b = a.dropna().astype(bool), b.dropna().astype(bool)
            rows.append({"feature": field, "type": "boolean", "group_a": first, "group_b": second,
                         "a_count": len(a), "b_count": len(b), "a_true_rate": a.mean() if len(a) else None,
                         "b_true_rate": b.mean() if len(b) else None,
                         "true_rate_difference": a.mean() - b.mean() if len(a) and len(b) else None})
        else:
            a, b = pd.to_numeric(a, errors="coerce").dropna(), pd.to_numeric(b, errors="coerce").dropna()
            pooled = np.sqrt(((len(a)-1)*a.var(ddof=1) + (len(b)-1)*b.var(ddof=1)) /
                             (len(a)+len(b)-2)) if len(a) > 1 and len(b) > 1 else np.nan
            rows.append({"feature": field, "type": "numeric", "group_a": first, "group_b": second,
                         **{f"{label}_{stat}": value for label, series in (("a", a), ("b", b))
                            for stat, value in (("count", len(series)), ("mean", series.mean()),
                                                ("median", series.median()), ("std", series.std()),
                                                ("min", series.min()), ("max", series.max()),
                                                ("p25", series.quantile(.25)), ("p75", series.quantile(.75)))},
                         "median_difference": a.median() - b.median(),
                         "cohens_d": (a.mean()-b.mean())/pooled if pd.notna(pooled) and pooled > 0 else None})
    return pd.DataFrame(rows)


def timeline(symbol: str, daily: pd.DataFrame, features: pd.DataFrame,
             start: str, end: str) -> pd.DataFrame:
    subset = daily.loc[daily["date"].between(start, end)]
    cols = ("date", "close", "current_phase", "transition", "ma50", "ma200",
            "ma50_slope_pct", "ma200_slope_pct", "drawdown_from_52w_high",
            "breakout_20d", "recent_higher_high", "price_above_ma50")
    points = [snapshot(symbol, day, daily, features, 0, kind="case") for day in subset["date"]]
    return pd.DataFrame([{**dict(zip(("date", "close", "current_phase", "transition"),
                                     (row.date, row.close, row.current_phase, row.transition))),
                          **{key: point[key] for key in cols[4:]}}
                         for row, point in zip(subset.itertuples(index=False), points)])


def success_timelines(spring: pd.DataFrame, daily: dict[str, pd.DataFrame],
                      features: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Illustrations selected after outcomes; not a validation sample."""
    examples = (("005930", "2025-06-24"), ("000660", "2023-05-22"),
                ("035420", "2023-05-16"))
    parts = []
    for symbol, date in examples:
        matched = spring.loc[(spring["symbol"] == symbol) & (spring["date"] == date)]
        if len(matched) != 1 or matched.iloc[0]["group"] != "SPRING_SUCCESS":
            raise ValueError(f"Illustrative success event changed: {symbol} {date}")
        asset_days = daily[symbol]["date"].tolist()
        at = asset_days.index(date)
        part = timeline(symbol, daily[symbol], features[symbol],
                        asset_days[max(0, at-10)], asset_days[min(len(asset_days)-1, at+80)])
        part.insert(0, "symbol", symbol)
        part.insert(1, "candidate_date", date)
        parts.append(part)
    return pd.concat(parts, ignore_index=True)


def run(source: Path, output: Path) -> dict:
    baseline, daily, events, hashes = verify_baseline(source)  # fail closed before writing
    spring, autumn, features = build_events(daily, events, LocalOHLCVCatalog(ROOT))
    if Counter(spring["group"]) != {"SPRING_SUCCESS": 16, "FALSE_SPRING": 59}:
        raise ValueError("Spring classification mismatch")
    if Counter(autumn["group"]) != {"AUTUMN_TO_WINTER": 12, "AUTUMN_TO_SUMMER": 67,
                                    "UNRESOLVED": 7, "RIGHT_CENSORED": 1}:
        raise ValueError("Autumn classification mismatch")
    spring_clusters = cluster_events(spring, daily)
    autumn_clusters = cluster_events(autumn, daily)
    duration, churn, cross = [], [], []
    for asset in baseline["assets"]:
        symbol = asset["symbol"]
        span = (pd.Timestamp(asset["last_date"]) - pd.Timestamp(asset["first_date"])).days / 365.2425
        e = events[symbol]
        duration.extend({"symbol": symbol, **part} for part in e["durations"])
        autumn_sub = autumn.loc[autumn["symbol"] == symbol]
        false_sub = spring.loc[(spring["symbol"] == symbol) & (spring["group"] == "FALSE_SPRING")]
        resume_days = autumn_sub.loc[autumn_sub["group"] == "AUTUMN_TO_SUMMER", "days_to_outcome"].dropna()
        churn.append({"symbol": symbol, "summer_autumn_summer_count": len(resume_days),
                      "median_days_to_summer_resume": resume_days.median(),
                      "false_spring_cycles_per_year": len(false_sub)/span,
                      "spring_raw_events": sum(spring["symbol"] == symbol),
                      "spring_clusters_30d": sum(spring_clusters["symbol"] == symbol),
                      "autumn_raw_events": len(autumn_sub),
                      "autumn_clusters_30d": sum(autumn_clusters["symbol"] == symbol)})
        cross.append({"symbol": symbol, "market": asset["market"], "calendar_year_span": span,
                      "transitions_per_year": len(e["transitions"])/span,
                      "candidate_per_year": asset["spring_candidate_count"]/span,
                      "autumn_per_year": asset["autumn_count"]/span,
                      "spring_success_rate_resolved": asset["confirmed_spring_count"] /
                          (asset["confirmed_spring_count"] + asset["false_spring_count"]),
                      "false_spring_rate_resolved": asset["false_spring_rate_resolved"],
                      "autumn_winter_rate_resolved": asset["autumn_to_winter"] /
                          (asset["autumn_to_winter"] + asset["autumn_to_summer_resume"]),
                      "autumn_summer_rate_resolved": asset["false_autumn_rate_resolved"]})
    output.mkdir(parents=True, exist_ok=True)
    tables = {"spring_events": spring, "autumn_events": autumn,
              "spring_diff_summary": diff_table(spring, "SPRING_SUCCESS", "FALSE_SPRING", SPRING_NUMERIC),
              "autumn_diff_summary": diff_table(autumn, "AUTUMN_TO_WINTER", "AUTUMN_TO_SUMMER", AUTUMN_NUMERIC),
              "spring_clusters_30d": spring_clusters, "autumn_clusters_30d": autumn_clusters,
              "phase_duration_summary": pd.DataFrame(duration),
              "transition_churn_summary": pd.DataFrame(churn),
              "cross_asset_summary": pd.DataFrame(cross),
              "case_samsung": timeline("005930", daily["005930"], features["005930"], "2026-06-01", "2026-08-15"),
              "case_sk_hynix": pd.concat([timeline("000660", daily["000660"], features["000660"],
                                                   "2025-09-01", "2025-09-30"),
                                               timeline("000660", daily["000660"], features["000660"],
                                                        "2026-07-01", "2026-08-31")], ignore_index=True),
              "case_naver": timeline("035420", daily["035420"], features["035420"],
                                     "2026-05-01", "2026-10-08"),
              "case_spring_success": success_timelines(spring, daily, features)}
    for name, table in tables.items():
        table.to_csv(output / f"{name}.csv", index=False, encoding="utf-8-sig")
    report = {"engine_version": VERSION, "rule_config_hash": RULE_CONFIG_HASH,
              "baseline_counts": BASELINE, "source_daily_sha256": hashes,
              "spring_groups": dict(Counter(spring["group"])),
              "autumn_groups": dict(Counter(autumn["group"])),
              "spring_clusters_30d": len(spring_clusters), "autumn_clusters_30d": len(autumn_clusters),
              "output_tables": {name: len(table) for name, table in tables.items()},
              "warning": "Post-event outcomes are descriptive only; episodes overlap and six survivors are selected."}
    (output / "analysis_summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "artifacts/fecm-price-phase-v1-20261010-validated")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/fecm-price-phase-v1-failure-analysis-step2")
    args = parser.parse_args()
    print(json.dumps(run(args.source, args.output), ensure_ascii=False, indent=2))
