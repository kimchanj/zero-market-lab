"""STEP 4 descriptive as-of features over frozen v1 events; no Phase rules or orders."""

from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))
from zero_market_lab.asset_discovery.catalog import LocalOHLCVCatalog  # noqa: E402
from scripts.analyze_phase_failures import SYMBOLS, verify_baseline  # noqa: E402

VERSION = "TRANSITION_DYNAMICS_STEP4"
SPRING_NUMERIC = ("ma50_slope", "ma200_slope", "ma50_slope_change_5d",
                  "ma200_slope_change_10d", "positive_ma50_slope_days_10d",
                  "close_above_ma50_days_10d", "price_minus_ma50_pct",
                  "price_minus_ma200_pct", "price_minus_ma200_change_10d",
                  "recovery_from_recent_low", "recovery_persistence_days",
                  "drawdown_from_52w_high")
AUTUMN_NUMERIC = ("ma50_slope", "ma200_slope", "ma50_slope_change_5d",
                  "ma200_slope_change_10d", "negative_ma50_slope_days_10d",
                  "days_below_ma50_10d", "drawdown_from_52w_high",
                  "drawdown_change_5d", "drawdown_change_10d",
                  "days_since_recent_high", "failed_recovery_count_10d",
                  "price_minus_ma50_pct", "price_minus_ma200_pct")
FEATURES = tuple(dict.fromkeys(SPRING_NUMERIC + AUTUMN_NUMERIC))
BOOLEAN_FEATURES = ("ma50_slope_positive", "ma200_slope_improving",
                    "close_above_ma50", "drawdown_worsening_10d")
OUTCOMES = ("group", "original_outcome", "days_to_outcome", "return_20d",
            "return_60d", "return_120d", "max_forward_drawdown_120d")
EXPECTED_HASHES = {
    "005930": "d65515e88e173929c2b2777ad2a1c0ecc062bf3cc877092e6d7b0b19bda6c450",
    "000660": "21c8acaf434b23f029cb8a2a00525bd5b84335bf452031eb99e35c9cae8c16d5",
    "035420": "5586c460a62445dd5fc2242144ba47a154a1c304c943be847d8757e666abfce0",
    "NVDA": "10c9beeb77f2264312014cee7805bd6dc0fc464a628a49e11dfadd65c376683e",
    "MSFT": "aa4b64cf0dead45ed986853b3ebbe33b38214a0c26438c69639572d9261e58ab",
    "AAPL": "16b79ab42ad7012dc4fe9a1c6b556d0a7fd628bc0b78bbdfb21e4e4e3dcd7dd5",
}
EXPECTED_EVENT_HASHES = {
    "005930": "fbb41277a5739416daf8fb5b11d475b46d953db3f003b7af29a6c4ab2c09598d",
    "000660": "c4dc0a4c79b199f69d8892b7271fb64269babf560bb424f19ff4114469df7946",
    "035420": "0fc8066c7dc356b87e43ec5e32df6dfaf90451e8bd269f93d1e85dc924ebb840",
    "NVDA": "7308a3b4c76a08458102702acc49b3ff47dad5bbdccb848553668e96cd9ed926",
    "MSFT": "02674abb345b41b3eee93e234d2b189720021ac59b90a097da8778793c185933",
    "AAPL": "f6e7e457e521ca92f7c6f670023d9899268edce4b54cc6f93925c72ddc1d2277",
}
EXPECTED_CONTEXT_HASHES = {
    "005930": "3e32d9b8a51615bcdd699772b8869c1ceeec6bf7255d1a1979d284cd77bb154d",
    "000660": "e1c45493d3c36b5aa0f740f2b273147c03ca64fe6414ba68a76d6aa63a25e372",
    "035420": "7d60124281195a24c62e82fb6700e793aa55b99fb7517d658d2ea4118ff4e942",
    "NVDA": "5f3a8cd65a0192beb0dd1dbba796eae7bbb498659dd3b17bd430879824d598ca",
    "MSFT": "7d8fd17ee8ea5bf8694f85ca82821e9c993d4da9a87380030b24eb632bcfdf0d",
    "AAPL": "c6aa556187dc8daa61c441a251859bdd58c027d51a4206c1dd3ac7b0b06ec94d",
}


def feature_frame(raw: pd.DataFrame) -> pd.DataFrame:
    """Every value at t depends only on the OHLC prefix through t."""
    f = raw[["date", "close", "high", "low"]].copy().reset_index(drop=True)
    f["date"] = pd.to_datetime(f["date"])
    if f["date"].isna().any() or f["date"].duplicated().any() or not f["date"].is_monotonic_increasing:
        raise ValueError("Dates must be unique and ascending")
    for key in ("close", "high", "low"):
        f[key] = pd.to_numeric(f[key], errors="raise")
    if (not np.isfinite(f[["close", "high", "low"]]).all().all()
            or (f[["close", "high", "low"]] <= 0).any().any()
            or (f["low"] > f["close"]).any() or (f["high"] < f["close"]).any()):
        raise ValueError("Invalid OHLC")
    c = f["close"]
    f["ma50"] = c.rolling(50, min_periods=50).mean()
    f["ma200"] = c.rolling(200, min_periods=200).mean()
    f["ma50_slope"] = f["ma50"] / f["ma50"].shift(5) - 1
    f["ma200_slope"] = f["ma200"] / f["ma200"].shift(10) - 1
    f["ma50_slope_change_5d"] = f["ma50_slope"] - f["ma50_slope"].shift(5)
    f["ma200_slope_change_10d"] = f["ma200_slope"] - f["ma200_slope"].shift(10)
    positive = f["ma50_slope"].gt(0).where(f["ma50_slope"].notna())
    negative = f["ma50_slope"].lt(0).where(f["ma50_slope"].notna())
    above = c.gt(f["ma50"]).where(f["ma50"].notna())
    below = c.lt(f["ma50"]).where(f["ma50"].notna())
    for name, series in (("positive_ma50_slope_days_10d", positive),
                         ("negative_ma50_slope_days_10d", negative),
                         ("close_above_ma50_days_10d", above),
                         ("days_below_ma50_10d", below)):
        f[name] = series.astype(float).rolling(10, min_periods=10).sum()
    f["price_minus_ma50_pct"] = c / f["ma50"] - 1
    f["price_minus_ma200_pct"] = c / f["ma200"] - 1
    f["price_minus_ma200_change_10d"] = (f["price_minus_ma200_pct"]
                                            - f["price_minus_ma200_pct"].shift(10))
    f["recovery_from_recent_low"] = c / f["low"].rolling(20, min_periods=20).min() - 1
    high52 = f["high"].rolling(252, min_periods=252).max()
    f["drawdown_from_52w_high"] = c / high52 - 1
    f["drawdown_change_5d"] = f["drawdown_from_52w_high"] - f["drawdown_from_52w_high"].shift(5)
    f["drawdown_change_10d"] = f["drawdown_from_52w_high"] - f["drawdown_from_52w_high"].shift(10)
    for name, series in (("ma50_slope_positive", f["ma50_slope"]),
                         ("ma200_slope_improving", f["ma200_slope_change_10d"]),
                         ("close_above_ma50", f["price_minus_ma50_pct"])):
        f[name] = series.gt(0).where(series.notna())
    f["drawdown_worsening_10d"] = (f["drawdown_change_10d"].lt(0)
                                    .where(f["drawdown_change_10d"].notna()))
    # Consecutive Close>MA50 days through t. Missing pre-MA days remain null.
    run = 0
    persistence = []
    for present in above:
        if pd.isna(present):
            persistence.append(np.nan)
            run = 0
        else:
            run = run + 1 if present else 0
            persistence.append(run)
    f["recovery_persistence_days"] = persistence
    failed = (above.shift(1).eq(True) & above.eq(False)).where(above.notna() & above.shift(1).notna())
    f["failed_recovery_count_10d"] = failed.astype(float).rolling(10, min_periods=10).sum()
    highs = f["high"].to_numpy()
    f["days_since_recent_high"] = [
        i - (i - 251 + int(np.flatnonzero(highs[i-251:i+1] == high52.iat[i])[-1]))
        if i >= 251 else np.nan for i in range(len(f))]
    f["date"] = f["date"].dt.strftime("%Y-%m-%d")
    return f


def event_snapshot(day: pd.Series, features: pd.DataFrame, context: pd.DataFrame) -> dict:
    """Snapshot is outcome-free; caller joins frozen outcomes afterward."""
    date = day["date"]
    at = features.loc[features["date"] == date]
    cx = context.loc[context["date"] == date]
    if len(at) != 1 or len(cx) != 1:
        raise ValueError(f"Missing/duplicate feature or context date: {date}")
    x, p = at.iloc[0], cx.iloc[0]
    return {"symbol": day["symbol"], "date": date, "available_at": day["available_at"],
            "close": float(x["close"]), "ma50": x["ma50"], "ma200": x["ma200"],
            "phase": day["current_phase"], "previous_phase": day["previous_phase"],
            "parent_phase": p["parent_phase"], "child_phase": p["child_phase"],
            **{key: x[key] for key in FEATURES + BOOLEAN_FEATURES}}


def numeric_comparison(events: pd.DataFrame, a: str, b: str, columns: tuple[str, ...]) -> pd.DataFrame:
    rows = []
    for name in columns:
        groups = [pd.to_numeric(events.loc[events["group"] == group, name], errors="coerce").dropna()
                  for group in (a, b)]
        x, y = groups
        pooled = np.sqrt(((len(x)-1)*x.var(ddof=1) + (len(y)-1)*y.var(ddof=1)) /
                         (len(x)+len(y)-2)) if len(x) > 1 and len(y) > 1 else np.nan
        row = {"feature": name, "group_a": a, "group_b": b}
        for label, series in (("a", x), ("b", y)):
            row.update({f"{label}_count": len(series), f"{label}_mean": series.mean(),
                        f"{label}_median": series.median(), f"{label}_std": series.std(),
                        f"{label}_p25": series.quantile(.25), f"{label}_p75": series.quantile(.75)})
        row["median_difference"] = x.median() - y.median()
        row["cohens_d"] = (x.mean()-y.mean())/pooled if pd.notna(pooled) and pooled > 0 else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def categorical_comparison(events: pd.DataFrame, a: str, b: str) -> pd.DataFrame:
    rows = []
    for field in BOOLEAN_FEATURES + ("parent_phase", "child_phase"):
        categories = (True,) if field in BOOLEAN_FEATURES else tuple(sorted(events[field].dropna().unique()))
        first = events.loc[events["group"] == a, field].dropna()
        second = events.loc[events["group"] == b, field].dropna()
        for category in categories:
            x = int((first == category).sum())
            y = int((second == category).sum())
            rows.append({"feature": field, "category": str(category), "group_a": a, "group_b": b,
                         "a_count": len(first), "b_count": len(second), "a_true_or_category_count": x,
                         "b_true_or_category_count": y,
                         "a_ratio": x / len(first) if len(first) else np.nan,
                         "b_ratio": y / len(second) if len(second) else np.nan,
                         "ratio_difference": x / len(first) - y / len(second)
                         if len(first) and len(second) else np.nan})
    return pd.DataFrame(rows)


def _json_safe(value):
    if isinstance(value, dict):
        return {key: _json_safe(v) for key, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return float(value) if np.isfinite(value) else None
    return value


def run(source: Path, step3: Path, output: Path) -> dict:
    baseline, daily, events, hashes = verify_baseline(source)
    if hashes != EXPECTED_HASHES:
        raise ValueError("Frozen v1 daily SHA-256 mismatch")
    event_hashes = {symbol: sha256((source / f"{symbol}_events.json").read_bytes()).hexdigest()
                    for symbol in SYMBOLS}
    context_hashes = {symbol: sha256((step3 / "A" / f"{symbol}_combined.csv").read_bytes()).hexdigest()
                      for symbol in SYMBOLS}
    if event_hashes != EXPECTED_EVENT_HASHES or context_hashes != EXPECTED_CONTEXT_HASHES:
        raise ValueError("Frozen v1 event or STEP 3 context SHA-256 mismatch")
    spring, autumn = [], []
    all_features = {}
    catalog = LocalOHLCVCatalog(ROOT)
    for symbol in SYMBOLS:
        raw, _ = catalog.load(symbol)
        f = feature_frame(raw)
        frozen = daily[symbol]
        f = f.loc[f["date"] <= frozen["date"].iat[-1]].reset_index(drop=True)
        if (f["date"].tolist() != frozen["date"].tolist()
                or not np.allclose(f["close"], frozen["close"], rtol=0, atol=1e-6)):
            raise ValueError(f"Local OHLC differs from frozen v1: {symbol}")
        cx = pd.read_csv(step3 / "A" / f"{symbol}_combined.csv", dtype={"symbol": str}, encoding="utf-8-sig")
        if (cx["date"].tolist() != frozen["date"].tolist()
                or not np.allclose(cx["close"], frozen["close"], rtol=0, atol=1e-6)
                or set(cx["candidate_id"]) != {"A"}
                or set(cx["research_version"]) != {"PARENT_CHILD_RESEARCH_STEP3"}):
            raise ValueError(f"STEP 3 context differs from frozen v1: {symbol}")
        all_features[symbol] = (f, cx)
        by_date = frozen.set_index("date", drop=False)
        for kind, target, group_map, bucket in (
            ("spring", "SPRING_CANDIDATE",
             {"CONFIRMED": "SPRING_SUCCESS", "FALSE_SPRING": "FALSE_SPRING",
              "UNRESOLVED": "UNRESOLVED", "CENSORED": "RIGHT_CENSORED"}, spring),
            ("autumn", "AUTUMN",
             {"WINTER": "AUTUMN_TO_WINTER", "FALSE_AUTUMN": "AUTUMN_TO_SUMMER",
              "UNRESOLVED": "UNRESOLVED", "CENSORED": "RIGHT_CENSORED"}, autumn)):
            for event in events[symbol][f"{kind}_events"]:
                day = by_date.loc[event["date"]]
                if day["current_phase"] != target or not isinstance(day["transition"], str):
                    raise ValueError(f"Frozen event transition mismatch: {symbol} {event['date']}")
                snap = event_snapshot(day, f, cx)
                snap["symbol"] = symbol  # pandas may infer numeric Korean codes in frozen CSV
                bucket.append({**snap, "group": group_map[event["outcome"]],
                               "original_outcome": event["outcome"],
                               **{name: event.get(name) for name in OUTCOMES[2:]}})
    sp = pd.DataFrame(spring).sort_values(["symbol", "date"]).reset_index(drop=True)
    au = pd.DataFrame(autumn).sort_values(["symbol", "date"]).reset_index(drop=True)
    if Counter(sp["group"]) != {"SPRING_SUCCESS": 16, "FALSE_SPRING": 59}:
        raise ValueError("Frozen Spring events changed")
    if Counter(au["group"]) != {"AUTUMN_TO_WINTER": 12, "AUTUMN_TO_SUMMER": 67,
                                "UNRESOLVED": 7, "RIGHT_CENSORED": 1}:
        raise ValueError("Frozen Autumn events changed")
    sp_diff = numeric_comparison(sp, "SPRING_SUCCESS", "FALSE_SPRING", SPRING_NUMERIC)
    au_diff = numeric_comparison(au, "AUTUMN_TO_WINTER", "AUTUMN_TO_SUMMER", AUTUMN_NUMERIC)
    sp_cat = categorical_comparison(sp, "SPRING_SUCCESS", "FALSE_SPRING")
    au_cat = categorical_comparison(au, "AUTUMN_TO_WINTER", "AUTUMN_TO_SUMMER")
    output.mkdir(parents=True, exist_ok=True)
    files = {"spring_transition_events.csv": sp, "autumn_transition_events.csv": au,
             "spring_transition_diff.csv": sp_diff, "autumn_transition_diff.csv": au_diff,
             "spring_transition_categorical.csv": sp_cat,
             "autumn_transition_categorical.csv": au_cat}
    # Date ranges and examples are frozen in the STEP 4 pre-registration document.
    for filename, symbol, start, end in (
        ("case_samsung_transition.csv", "005930", "2026-06-01", "2026-08-15"),
        ("case_sk_hynix_transition.csv", "000660", "2025-08-18", "2025-09-30")):
        f, cx = all_features[symbol]
        view = f.loc[f["date"].between(start, end)].copy()
        view.insert(0, "symbol", symbol)
        labels = daily[symbol][["date", "current_phase", "transition"]]
        view = view.merge(labels, on="date", validate="one_to_one")
        view = view.merge(cx[["date", "parent_phase", "child_phase"]], on="date", validate="one_to_one")
        files[filename] = view
    examples = (("035420", "2026-06-05", "FALSE_SPRING"),
                ("035420", "2026-08-06", "FALSE_SPRING"),
                ("035420", "2026-09-09", "FALSE_SPRING"),
                ("005930", "2025-06-24", "SPRING_SUCCESS"),
                ("000660", "2023-05-22", "SPRING_SUCCESS"),
                ("035420", "2023-05-16", "SPRING_SUCCESS"))
    case_parts = {"FALSE_SPRING": [], "SPRING_SUCCESS": []}
    for symbol, date, group in examples:
        match = sp.loc[(sp["symbol"] == symbol) & (sp["date"] == date)]
        if len(match) != 1 or match.iloc[0]["group"] != group:
            raise ValueError(f"Frozen example changed: {symbol} {date}")
        f, cx = all_features[symbol]
        i = f.index[f["date"] == date][0]
        view = f.iloc[max(0, i-10):min(len(f), i+11)].copy()
        view.insert(0, "symbol", symbol)
        view.insert(1, "candidate_date", date)
        view.insert(2, "event_group", group)
        view = view.merge(daily[symbol][["date", "current_phase"]], on="date", validate="one_to_one")
        view = view.merge(cx[["date", "parent_phase", "child_phase"]], on="date", validate="one_to_one")
        case_parts[group].append(view)
    files["case_naver_transition.csv"] = pd.concat(case_parts["FALSE_SPRING"], ignore_index=True)
    files["successful_spring_transition_cases.csv"] = pd.concat(case_parts["SPRING_SUCCESS"], ignore_index=True)
    for filename, frame in files.items():
        frame.to_csv(output / filename, index=False, encoding="utf-8-sig", float_format="%.12g")
    summary = {"version": VERSION, "development_symbols": list(SYMBOLS),
               "frozen_v1_daily_sha256": hashes, "frozen_v1_event_sha256": event_hashes,
               "frozen_step3_A_context_sha256": context_hashes,
               "frozen_v1_counts": baseline["assets"],
               "spring_groups": dict(Counter(sp["group"])),
               "autumn_groups": dict(Counter(au["group"])),
               "primary_h4_median_difference": sp_diff.set_index("feature").loc[
                   "ma200_slope_change_10d", "median_difference"],
               "primary_h5_median_difference": au_diff.set_index("feature").loc[
                   "drawdown_change_10d", "median_difference"],
               "output_sha256": {name: sha256((output / name).read_bytes()).hexdigest() for name in files}}
    (output / "transition_summary.json").write_text(
        json.dumps(_json_safe(summary), ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8")
    return _json_safe(summary)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path,
                        default=ROOT / "artifacts/fecm-price-phase-v1-20261010-validated")
    parser.add_argument("--step3", type=Path, default=ROOT / "artifacts/fecm-multitimeframe-step3")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/fecm-transition-dynamics-step4")
    args = parser.parse_args()
    result = run(args.source, args.step3, args.output)
    print(json.dumps({key: result[key] for key in ("spring_groups", "autumn_groups",
                                                "primary_h4_median_difference",
                                                "primary_h5_median_difference")}, indent=2))
