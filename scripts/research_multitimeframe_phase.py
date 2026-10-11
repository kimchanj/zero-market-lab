"""STEP 3 research-only parent/child price context, separate from PRICE_PHASE_V1."""

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
sys.path.insert(0, str(ROOT))
from zero_market_lab.asset_discovery.catalog import LocalOHLCVCatalog  # noqa: E402
from scripts.analyze_phase_failures import SYMBOLS, verify_baseline  # noqa: E402

CANDIDATES = {
    "A": {"parent_ma": 200, "parent_slope": 20, "parent_confirmation": 10,
          "child_ma": 50, "child_slope": 5, "child_confirmation": 3},
    "B": {"parent_ma": 200, "parent_slope": 40, "parent_confirmation": 10,
          "child_ma": 20, "child_slope": 3, "child_confirmation": 3},
}
RESEARCH_VERSION = "PARENT_CHILD_RESEARCH_STEP3"
PHASES = ("UNKNOWN", "WINTER", "SPRING", "SUMMER", "AUTUMN")


def config_hash(config: dict) -> str:
    return sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()


def raw_context(close: float, average: float, previous_average: float) -> str:
    """A descriptive quadrant, not a PRICE_PHASE_V1 transition or order."""
    if not np.isfinite(average) or not np.isfinite(previous_average):
        return "UNKNOWN"
    slope = average - previous_average
    above = close > average
    if above and slope > 0:
        return "SUMMER"
    if not above and slope < 0:
        return "WINTER"
    if above:
        return "SPRING"
    return "AUTUMN"


def confirmed_context(prices: pd.DataFrame, *, ma_window: int, slope_lag: int,
                      confirmation: int, prefix: str) -> pd.DataFrame:
    if ma_window <= slope_lag or confirmation < 1:
        raise ValueError("Invalid research timescale")
    close = pd.to_numeric(prices["close"], errors="raise").astype(float)
    average = close.rolling(ma_window, min_periods=ma_window).mean()
    previous = average.shift(slope_lag)
    raw = [raw_context(c, m, p) for c, m, p in zip(close, average, previous)]
    state, pending, pending_age, age = "UNKNOWN", None, 0, 0
    labels, ages, transitions = [], [], []
    for candidate in raw:
        transition = None
        if candidate != "UNKNOWN" and candidate != state:
            pending_age = pending_age + 1 if pending == candidate else 1
            pending = candidate
        else:
            pending, pending_age = None, 0
        age += 1
        if pending_age >= confirmation:
            old, state, age = state, pending, 1
            transition = f"{old}->{state}"
            pending, pending_age = None, 0
        labels.append(state)
        ages.append(age)
        transitions.append(transition)
    return pd.DataFrame({f"{prefix}_phase": labels, f"{prefix}_days": ages,
                         f"{prefix}_transition": transitions,
                         f"{prefix}_raw": raw, f"{prefix}_ma": average,
                         f"{prefix}_ma_slope_fraction": average / previous - 1})


def combined_context(frame: pd.DataFrame, *, symbol: str, candidate_id: str) -> pd.DataFrame:
    """Only current/past close, average and prior confirmed state enter labels."""
    config = CANDIDATES[candidate_id]
    source = frame.copy().reset_index(drop=True)
    source["date"] = pd.to_datetime(source["date"], errors="raise")
    if source["date"].isna().any() or source["date"].duplicated().any() or not source["date"].is_monotonic_increasing:
        raise ValueError("Dates must be unique and ascending")
    source["close"] = pd.to_numeric(source["close"], errors="raise")
    if not np.isfinite(source["close"]).all() or (source["close"] <= 0).any():
        raise ValueError("Invalid close")
    parent = confirmed_context(source, ma_window=config["parent_ma"],
                               slope_lag=config["parent_slope"],
                               confirmation=config["parent_confirmation"], prefix="parent")
    child = confirmed_context(source, ma_window=config["child_ma"],
                              slope_lag=config["child_slope"],
                              confirmation=config["child_confirmation"], prefix="child")
    result = pd.concat([pd.DataFrame({"symbol": symbol,
                                      "date": source["date"].dt.strftime("%Y-%m-%d"),
                                      "close": source["close"],
                                      "available_at": source["date"].dt.strftime("%Y-%m-%d") + " close",
                                      "candidate_id": candidate_id,
                                      "research_version": RESEARCH_VERSION,
                                      "rule_config_hash": config_hash(config)}), parent, child], axis=1)
    result["combined_state"] = result["parent_phase"] + "+" + result["child_phase"]
    return result


def episodes(combined: pd.DataFrame, layer: str) -> pd.DataFrame:
    states = combined[f"{layer}_phase"].tolist()
    parts = []
    start = 0
    for end in range(1, len(states) + 1):
        if end == len(states) or states[end] != states[start]:
            if states[start] != "UNKNOWN":
                parts.append({"symbol": combined.iloc[0]["symbol"], "layer": layer,
                              "phase": states[start], "start_date": combined.iloc[start]["date"],
                              "end_date": combined.iloc[end-1]["date"], "trading_days": end-start,
                              "right_censored": end == len(states)})
            start = end
    return pd.DataFrame(parts)


def churn_count(combined: pd.DataFrame, layer: str, *, horizon: int = 60) -> dict:
    transitions = [(i, row[f"{layer}_transition"]) for i, row in combined.iterrows()
                   if isinstance(row[f"{layer}_transition"], str)]
    summer, winter = 0, 0
    for (_, first), (j, middle), (k, last) in zip(transitions, transitions[1:], transitions[2:]):
        if k-j > horizon:
            continue
        if first.endswith("->SUMMER") and middle == "SUMMER->AUTUMN" and last == "AUTUMN->SUMMER":
            summer += 1
        if first.endswith("->WINTER") and middle.startswith("WINTER->") and last.endswith("->WINTER"):
            winter += 1
    return {"summer_autumn_summer_60d": summer, "winter_recovery_winter_60d": winter}


def event_context(events: list[dict], combined: pd.DataFrame, *, kind: str) -> pd.DataFrame:
    lookup = combined.set_index("date")
    rows = []
    for event in events:
        point = lookup.loc[event["date"]]
        rows.append({"symbol": event["symbol"], "date": event["date"], "event_kind": kind,
                     "parent_phase": point["parent_phase"], "child_phase": point["child_phase"],
                     "combined_state": point["combined_state"],
                     "parent_days": int(point["parent_days"]), "child_days": int(point["child_days"]),
                     "parent_ma": point["parent_ma"], "child_ma": point["child_ma"],
                     "parent_ma_slope_fraction": point["parent_ma_slope_fraction"],
                     "child_ma_slope_fraction": point["child_ma_slope_fraction"],
                     "outcome": event["outcome"], "days_to_outcome": event["days_to_outcome"],
                     "return_20d": event["return_20d"], "return_60d": event["return_60d"],
                     "return_120d": event["return_120d"],
                     "max_forward_drawdown_120d": event["max_forward_drawdown_120d"]})
    return pd.DataFrame(rows)


def matrix(combined: pd.DataFrame) -> pd.DataFrame:
    """Daily overlapping descriptive outcomes, never phase inputs or independent trials."""
    valid = combined.loc[(combined["parent_phase"] != "UNKNOWN") &
                         (combined["child_phase"] != "UNKNOWN")].copy()
    close = combined["close"]
    for horizon in (20, 60, 120):
        future = combined.groupby("symbol", sort=False)["close"].shift(-horizon)
        valid[f"forward_{horizon}d_return"] = (future / close - 1).loc[valid.index]
    drawdown = pd.Series(np.nan, index=combined.index)
    for _, segment in combined.groupby("symbol", sort=False):
        prices = segment["close"].to_numpy()
        for i in range(len(prices) - 120):
            window = prices[i:i+121]
            drawdown.at[segment.index[i]] = np.min(window / np.maximum.accumulate(window) - 1)
    valid["forward_drawdown_120d"] = drawdown.loc[valid.index]
    valid["episode_start"] = valid["combined_state"].ne(
        valid.groupby("symbol", sort=False)["combined_state"].shift(1))
    return valid.groupby(["parent_phase", "child_phase"], as_index=False).agg(
        trading_days=("date", "size"), combined_episodes=("episode_start", "sum"),
        median_forward_20d=("forward_20d_return", "median"),
        median_forward_60d=("forward_60d_return", "median"),
        median_forward_120d=("forward_120d_return", "median"),
        observed_forward_120d=("forward_120d_return", "count"),
        median_forward_drawdown_120d=("forward_drawdown_120d", "median"))


def lead_lag(combined: pd.DataFrame, *, horizon: int = 120) -> pd.DataFrame:
    """Post-hoc next parent transition after each child transition."""
    parent = [(i, row["parent_transition"]) for i, row in combined.iterrows()
              if isinstance(row["parent_transition"], str)]
    child = [(i, row["child_transition"]) for i, row in combined.iterrows()
             if isinstance(row["child_transition"], str)]
    rows = []
    for i, child_change in child:
        next_parent = next(((j, change) for j, change in parent if i < j <= i+horizon), None)
        child_destination = child_change.split("->")[-1]
        direction = "WEAK" if child_destination in {"AUTUMN", "WINTER"} else "STRONG"
        same_direction = next(((j, change) for j, change in parent
                               if i < j <= i+horizon and
                               ((change.split("->")[-1] in {"AUTUMN", "WINTER"}) ==
                                (direction == "WEAK"))), None)
        rows.append({"symbol": combined.iloc[i]["symbol"], "child_date": combined.iloc[i]["date"],
                     "child_transition": child_change,
                     "child_direction": direction,
                     "parent_at_child": combined.iloc[i]["parent_phase"],
                     "next_parent_date": combined.iloc[next_parent[0]]["date"] if next_parent else None,
                     "next_parent_transition": next_parent[1] if next_parent else None,
                     "lag_trading_days": next_parent[0]-i if next_parent else None,
                     "same_direction_parent_date": combined.iloc[same_direction[0]]["date"] if same_direction else None,
                     "same_direction_parent_transition": same_direction[1] if same_direction else None,
                     "same_direction_lag_trading_days": same_direction[0]-i if same_direction else None,
                     "same_direction_right_censored_120d": same_direction is None and i+horizon >= len(combined),
                     "right_censored_120d": next_parent is None and i+horizon >= len(combined)})
    return pd.DataFrame(rows)


def case(combined: pd.DataFrame, start: str, end: str, *, name: str) -> pd.DataFrame:
    selected = combined.loc[combined["date"].between(start, end),
                            ["symbol", "date", "close", "parent_phase", "child_phase",
                             "parent_transition", "child_transition", "parent_days", "child_days",
                             "parent_ma", "child_ma", "parent_ma_slope_fraction",
                             "child_ma_slope_fraction"]].copy()
    selected.insert(0, "case", name)
    return selected


def run(source: Path, output: Path) -> dict:
    baseline, daily, events, hashes = verify_baseline(source)
    catalog = LocalOHLCVCatalog(ROOT)
    frames = {}
    for symbol in SYMBOLS:
        frame, _ = catalog.load(symbol)
        frame = frame.loc[pd.to_datetime(frame["date"]) <= pd.Timestamp(daily[symbol]["date"].iloc[-1])].copy()
        if (frame["date"].astype(str).tolist() != daily[symbol]["date"].tolist() or
                not np.allclose(frame["close"].to_numpy(dtype=float), daily[symbol]["close"].to_numpy())):
            raise ValueError(f"Local prices differ from frozen v1 rows: {symbol}")
        frames[symbol] = frame
    output.mkdir(parents=True, exist_ok=True)
    report = {"research_version": RESEARCH_VERSION, "frozen_v1_daily_sha256": hashes,
              "frozen_v1_count": baseline["assets"], "candidates": {},
              "warning": "Selected six surviving assets; daily forward outcomes overlap; candidate thresholds not optimized."}
    for candidate_id, config in CANDIDATES.items():
        path = output / candidate_id
        path.mkdir(exist_ok=True)
        all_combined, all_spring, all_autumn, all_episodes, all_lead_lag = [], [], [], [], []
        stability = []
        case_parts = []
        for symbol in SYMBOLS:
            combined = combined_context(frames[symbol], symbol=symbol, candidate_id=candidate_id)
            combined.insert(0, "v1_phase", daily[symbol]["current_phase"].to_numpy())
            combined.to_csv(path / f"{symbol}_combined.csv", index=False, encoding="utf-8-sig")
            all_combined.append(combined)
            for layer in ("parent", "child"):
                all_episodes.append(episodes(combined, layer))
            all_spring.append(event_context(events[symbol]["spring_events"], combined, kind="SPRING_CANDIDATE"))
            all_autumn.append(event_context(events[symbol]["autumn_events"], combined, kind="AUTUMN"))
            all_lead_lag.append(lead_lag(combined))
            valid = combined.loc[(combined["parent_phase"] != "UNKNOWN") &
                                 (combined["child_phase"] != "UNKNOWN")]
            for layer in ("parent", "child"):
                segment = episodes(combined, layer)
                transition_count = valid[f"{layer}_transition"].notna().sum()
                stability.append({"symbol": symbol, "layer": layer,
                                  "common_valid_days": len(valid),
                                  "transitions_common_period": int(transition_count),
                                  "episode_count_all": len(segment),
                                  "median_episode_days_all": segment["trading_days"].median(),
                                  "median_episode_days_completed": segment.loc[
                                      ~segment["right_censored"], "trading_days"].median(),
                                  "right_censored_episodes": int(segment["right_censored"].sum()),
                                  **churn_count(combined, layer)})
            for name, start, end in (("samsung_2026", "2026-06-01", "2026-10-08"),
                                     ("sk_2025_false_autumn", "2025-09-01", "2025-09-30"),
                                     ("sk_2026_autumn", "2026-07-01", "2026-10-08"),
                                     ("naver_2026", "2026-05-01", "2026-10-08"),
                                     ("spring_success_samsung", "2025-06-01", "2025-09-01"),
                                     ("spring_success_sk", "2023-05-01", "2023-08-31"),
                                     ("spring_success_naver", "2023-05-01", "2023-09-01")):
                if ((name.startswith("samsung") or name.endswith("samsung")) and symbol == "005930" or
                    name.startswith("sk_") and symbol == "000660" or
                    name.endswith("_sk") and symbol == "000660" or
                    name.startswith("naver") and symbol == "035420" or
                    name.endswith("naver") and symbol == "035420"):
                    case_parts.append(case(combined, start, end, name=name))
        combined_all = pd.concat(all_combined, ignore_index=True)
        spring_all = pd.concat(all_spring, ignore_index=True)
        autumn_all = pd.concat(all_autumn, ignore_index=True)
        if len(spring_all) != 75 or len(autumn_all) != 87:
            raise ValueError("Original event membership changed")
        tables = {"stability": pd.DataFrame(stability), "spring_context": spring_all,
                  "autumn_context": autumn_all, "combined_matrix": matrix(combined_all),
                  "episodes": pd.concat(all_episodes, ignore_index=True),
                  "lead_lag": pd.concat(all_lead_lag, ignore_index=True),
                  "case_timelines": pd.concat(case_parts, ignore_index=True)}
        for name, table in tables.items():
            table.to_csv(path / f"{name}.csv", index=False, encoding="utf-8-sig")
        report["candidates"][candidate_id] = {"config": config, "config_hash": config_hash(config),
                                                "tables": {name: len(table) for name, table in tables.items()},
                                                "spring_parent": pd.crosstab(spring_all["parent_phase"],
                                                                              spring_all["outcome"]).to_dict(),
                                                "autumn_parent": pd.crosstab(autumn_all["parent_phase"],
                                                                              autumn_all["outcome"]).to_dict()}
    (output / "analysis_summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "artifacts/fecm-price-phase-v1-20261010-validated")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/fecm-multitimeframe-step3")
    args = parser.parse_args()
    result = run(args.source, args.output)
    print(json.dumps({"research_version": result["research_version"],
                      "candidates": {key: value["tables"] for key, value in result["candidates"].items()},
                      "output": str(args.output)}, ensure_ascii=False, indent=2))
