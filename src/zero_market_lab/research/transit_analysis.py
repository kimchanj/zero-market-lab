"""Preregistered STEP 9 descriptive Gate × market analysis.

No trading decisions or solar/Phase rule changes occur in this module. All
financial values are local observations; Gate labels are symbolic context.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path

import numpy as np
import pandas as pd

from zero_market_lab.market_phase.engine import PhaseEngine, RULE_CONFIG_HASH
from zero_market_lab.research.comparison import ComparisonResearch
from zero_market_lab.research.context_data import FRED_SERIES, as_of_observation, latest_snapshot
from zero_market_lab.transit.calendar import at_market_close, year_calendar
from zero_market_lab.transit.quarters import load_quarters


ASSETS = ("005930", "000660", "SP500")
CONTEXT = ("VIX", "US10Y", "USDKRW", "BROAD_USD")
MAX_AGE = {"VIX": 10, "US10Y": 21, "USDKRW": 35, "BROAD_USD": 35}
METRIC_COLUMNS = ("return_pct", "max_drawdown_pct", "max_runup_pct",
                  "daily_volatility_pct", "positive_day_ratio", "negative_day_ratio")
UTC = timezone.utc


@dataclass(frozen=True)
class StudyConfig:
    start: str
    end: str
    seed: int = 42
    random_repetitions: int = 1000
    bootstrap_repetitions: int = 2000
    season_radius_days: int = 45

    def __post_init__(self) -> None:
        if date.fromisoformat(self.start) > date.fromisoformat(self.end):
            raise ValueError("Study start must precede end")
        if self.random_repetitions < 1000 or self.bootstrap_repetitions < 1000:
            raise ValueError("Control repetitions must be at least 1000")


def stable_seed(master: int, *parts: object) -> int:
    payload = json.dumps([master, *parts], ensure_ascii=False, sort_keys=True)
    return (master + int.from_bytes(sha256(payload.encode()).digest()[:8], "big")) % (2**63)


def gate_intervals(start: str, end: str) -> list[dict]:
    """Merge calendar-year clips back into original half-open solar windows."""
    first_year, last_year = date.fromisoformat(start).year, date.fromisoformat(end).year
    segments = [dict(gate) for year in range(first_year - 1, last_year + 2)
                for gate in year_calendar(year)["gates"]]
    merged: list[dict] = []
    for segment in segments:
        if (merged and merged[-1]["gate"] == segment["gate"] and
                merged[-1]["end_utc"] == segment["start_utc"]):
            merged[-1]["end_utc"] = segment["end_utc"]
        else:
            merged.append({"gate": segment["gate"], "start_utc": segment["start_utc"],
                           "end_utc": segment["end_utc"]})
    lower = datetime.fromisoformat(start).replace(tzinfo=UTC)
    upper = datetime.fromisoformat(end).replace(tzinfo=UTC) + timedelta(days=1)
    return [{**window, "year": datetime.fromisoformat(window["start_utc"]).year,
             "complete": datetime.fromisoformat(window["start_utc"]) >= lower and
                         datetime.fromisoformat(window["end_utc"]) <= upper}
            for window in merged if datetime.fromisoformat(window["end_utc"]) > lower and
            datetime.fromisoformat(window["start_utc"]) < upper]


def validate_asset(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"date", "close"}
    if frame.empty or not required.issubset(frame):
        raise ValueError("Asset requires observed date and close")
    data = frame.copy().reset_index(drop=True)
    data["date"] = data["date"].astype(str).str[:10]
    data["close"] = pd.to_numeric(data["close"], errors="raise")
    if (data["date"].duplicated().any() or not data["date"].is_monotonic_increasing or
            data["close"].isna().any() or (data["close"] <= 0).any()):
        raise ValueError("Asset observations must have ordered unique dates and positive closes")
    return data


def price_metrics(close: np.ndarray, volume: np.ndarray | None = None) -> dict:
    if not len(close):
        return {key: None for key in (*METRIC_COLUMNS, "volume_change_pct")}
    close = np.asarray(close, dtype=float)
    if not np.isfinite(close).all() or (close <= 0).any():
        raise ValueError("Window close values must be finite and positive")
    daily = (close[1:] / close[:-1] - 1) * 100
    peaks = np.maximum.accumulate(close)
    troughs = np.minimum.accumulate(close)
    volume_change = None
    if volume is not None and len(volume) == len(close):
        volume = np.asarray(volume, dtype=float)
        if np.isfinite(volume[[0, -1]]).all() and volume[0] > 0:
            volume_change = float((volume[-1] / volume[0] - 1) * 100)
    return {"return_pct": float((close[-1] / close[0] - 1) * 100),
            "max_drawdown_pct": float(np.min((close / peaks - 1) * 100)),
            "max_runup_pct": float(np.max((close / troughs - 1) * 100)),
            "daily_volatility_pct": float(np.std(daily, ddof=0)) if len(daily) else None,
            "positive_day_ratio": float(np.mean(daily > 0)) if len(daily) else None,
            "negative_day_ratio": float(np.mean(daily < 0)) if len(daily) else None,
            "volume_change_pct": volume_change}


def context_on_dates(root: Path, dates: list[str], currency: str,
                     snapshots: dict[str, tuple[pd.DataFrame, dict] | None]) -> dict[str, dict]:
    """Use existing lag and staleness policy, retaining each observation date."""
    joined = {}
    for day in dates:
        joined[day] = {}
        for key in CONTEXT:
            snapshot = snapshots[key]
            if snapshot is None:
                joined[day][key] = {"value": None, "observation_date": None,
                                    "status": "NOT_CONNECTED", "percentile": None}
                continue
            frame, _ = snapshot
            rule = FRED_SERIES[key]
            lag = rule.krx_lag_days if currency == "KRW" else rule.us_lag_days
            observed = as_of_observation(frame, day, lag)
            if observed is None:
                joined[day][key] = {"value": None, "observation_date": None,
                                    "status": "NO_AVAILABLE_OBSERVATION", "percentile": None}
                continue
            age = (date.fromisoformat(day) - date.fromisoformat(observed["observation_date"])).days
            if age > MAX_AGE[key]:
                joined[day][key] = {"value": None,
                                    "observation_date": observed["observation_date"],
                                    "status": "STALE_OBSERVATION", "percentile": None}
                continue
            position = int(frame["date"].searchsorted(observed["observation_date"], side="right"))
            history = frame.iloc[max(0, position - 252):position]["value"].to_numpy(dtype=float)
            joined[day][key] = {"value": observed["value"],
                                "observation_date": observed["observation_date"],
                                "status": observed["status"],
                                "percentile": float(100 * np.mean(history <= observed["value"]))}
    return joined


def _context_metrics(days: list[str], context: dict[str, dict]) -> dict:
    result: dict = {}
    for key, prefix in (("VIX", "vix"), ("US10Y", "us10y"),
                        ("USDKRW", "usdkrw"), ("BROAD_USD", "broad_dollar")):
        observed = [context[day][key] for day in days if context[day][key]["value"] is not None]
        values = [item["value"] for item in observed]
        result.update({f"{prefix}_start": values[0] if values else None,
                       f"{prefix}_end": values[-1] if values else None,
                       f"{prefix}_mean": float(np.mean(values)) if values else None,
                       f"{prefix}_observed_days": len(values),
                       f"{prefix}_start_observation_date": observed[0]["observation_date"] if values else None,
                       f"{prefix}_end_observation_date": observed[-1]["observation_date"] if values else None})
        if key == "VIX":
            result["vix_change"] = values[-1] - values[0] if values else None
            result["vix_max"] = max(values) if values else None
            result["vix_percentile_mean"] = (float(np.mean([item["percentile"] for item in observed]))
                                             if values else None)
        elif key == "US10Y":
            result["us10y_change_pp"] = values[-1] - values[0] if values else None
        else:
            result[f"{prefix}_change_pct"] = ((values[-1] / values[0] - 1) * 100
                                                if values and values[0] else None)
    return result


def random_control(frame: pd.DataFrame, positions: list[int], *, year: int,
                   midpoint: date, config: StudyConfig, key: str) -> dict:
    n = len(positions)
    if n < 3:
        return {f"random_{metric}_percentile": None for metric in
                ("return", "mdd", "volatility")} | {"random_candidate_count": 0,
                                                       "random_return_median": None}
    dates = frame["date"].tolist()
    actual = set(positions)
    candidates = []
    for first in range(len(frame) - n + 1):
        indices = range(first, first + n)
        candidate_midpoint = date.fromisoformat(dates[first + n // 2])
        if (candidate_midpoint.year != year or
                abs((candidate_midpoint - midpoint).days) > config.season_radius_days or
                any(index in actual for index in indices)):
            continue
        candidates.append(first)
    if not candidates:
        return {f"random_{metric}_percentile": None for metric in
                ("return", "mdd", "volatility")} | {"random_candidate_count": 0,
                                                       "random_return_median": None}
    closes = frame["close"].to_numpy(dtype=float)
    candidate_metrics = [price_metrics(closes[first:first + n]) for first in candidates]
    rng = np.random.default_rng(stable_seed(config.seed, "random", key))
    sampled = rng.integers(0, len(candidates), size=config.random_repetitions)
    actual_metrics = price_metrics(closes[positions])
    keys = (("return", "return_pct"), ("mdd", "max_drawdown_pct"),
            ("volatility", "daily_volatility_pct"))
    sampled_returns = np.array([item["return_pct"] for item in candidate_metrics], dtype=float)[sampled]
    output = {"random_candidate_count": len(candidates),
              "random_return_median": float(np.median(sampled_returns))}
    for label, metric in keys:
        distribution = np.array([item[metric] for item in candidate_metrics], dtype=float)[sampled]
        output[f"random_{label}_percentile"] = float(100 * np.mean(distribution <= actual_metrics[metric]))
    return output


def _adjacent_return(frame: pd.DataFrame, positions: list[int], before: bool) -> float | None:
    n = len(positions)
    if n < 3:
        return None
    first = positions[0] - n if before else positions[-1] + 1
    if first < 0 or first + n > len(frame):
        return None
    return price_metrics(frame["close"].to_numpy(dtype=float)[first:first + n])["return_pct"]


def asset_windows(symbol: str, frame: pd.DataFrame, *, root: Path,
                  config: StudyConfig, intervals: list[dict],
                  snapshots: dict[str, tuple[pd.DataFrame, dict] | None]) -> list[dict]:
    data = validate_asset(frame)
    data = data.loc[(data["date"] >= config.start) & (data["date"] <= config.end)].reset_index(drop=True)
    if data.empty:
        raise ValueError(f"No {symbol} bars in study period")
    currency = "USD" if symbol == "SP500" else "KRW"
    starts = [datetime.fromisoformat(item["start_utc"]) for item in intervals]
    groups: dict[int, list[int]] = {index: [] for index in range(len(intervals))}
    gate_lines: dict[int, list[int]] = {index: [] for index in range(len(intervals))}
    for index, day in enumerate(data["date"]):
        mapping = at_market_close(day, currency)
        instant = datetime.fromisoformat(mapping["market_close_utc"])
        position = bisect_right(starts, instant) - 1
        if position >= 0 and instant < datetime.fromisoformat(intervals[position]["end_utc"]):
            if intervals[position]["gate"] != mapping["gate"]:
                raise ValueError("Calendar/window Gate mismatch")
            groups[position].append(index)
            gate_lines[position].append(mapping["line"])
    phase_map = {}
    if {"open", "high", "low"} <= set(frame):
        phase_result = PhaseEngine().run(validate_asset(frame).loc[lambda x: x["date"] <= config.end],
                                         symbol=symbol, data_source="LOCAL_RESEARCH")
        phase_map = {item["date"]: item["current_phase"] for item in phase_result["rows"]}
    context = context_on_dates(root, data["date"].tolist(), currency, snapshots)
    _, quarter_by_gate = load_quarters(root)
    closes = data["close"].to_numpy(dtype=float)
    volumes = data["volume"].to_numpy(dtype=float) if "volume" in data else None
    rows = []
    for index, interval in enumerate(intervals):
        positions = groups[index]
        days = [data.iloc[position]["date"] for position in positions]
        quarter = quarter_by_gate[interval["gate"]]
        metrics = price_metrics(closes[positions], volumes[positions] if volumes is not None and positions else None)
        phases = [phase_map.get(day) for day in days]
        counts = {phase: phases.count(phase) for phase in sorted(set(phases) - {None})}
        complete = interval["complete"] and len(positions) >= 3
        midpoint = (datetime.fromisoformat(interval["start_utc"]) +
                    (datetime.fromisoformat(interval["end_utc"]) -
                     datetime.fromisoformat(interval["start_utc"])) / 2).date()
        control = (random_control(data, positions, year=interval["year"], midpoint=midpoint,
                                  config=config, key=f"{symbol}:{interval['start_utc']}")
                   if complete else {"random_return_percentile": None,
                                     "random_mdd_percentile": None,
                                     "random_volatility_percentile": None,
                                     "random_candidate_count": 0, "random_return_median": None})
        rows.append({"asset": symbol, "year": interval["year"], "gate": interval["gate"],
                     "quarter_id": quarter["id"], "quarter_name": quarter["name"],
                     "quarter_name_ko": quarter["name_ko"],
                     "start_datetime": interval["start_utc"], "end_datetime": interval["end_utc"],
                     "complete_solar_window": interval["complete"],
                     "analysis_status": "COMPLETE" if complete else "INSUFFICIENT SAMPLE",
                     "first_market_date": days[0] if days else None,
                     "last_market_date": days[-1] if days else None,
                     "trading_days": len(days),
                     "start_close": float(closes[positions[0]]) if positions else None,
                     "end_close": float(closes[positions[-1]]) if positions else None,
                     "gate_lines_observed": json.dumps(gate_lines[index]),
                     **metrics, **_context_metrics(days, context),
                     "phase_at_start": phases[0] if phases else None,
                     "phase_at_end": phases[-1] if phases else None,
                     "phase_distribution": json.dumps({key: count / len(phases) for key, count in counts.items()},
                                                      sort_keys=True),
                     "pre_return_pct": _adjacent_return(data, positions, True) if complete else None,
                     "post_return_pct": _adjacent_return(data, positions, False) if complete else None,
                     **control})
    return rows


def bootstrap_interval(values: list[float], *, config: StudyConfig, key: str,
                       statistic: str) -> tuple[float | None, float | None]:
    if len(values) < 2:
        return None, None
    rng = np.random.default_rng(stable_seed(config.seed, "bootstrap", key, statistic))
    sample = np.asarray(values, dtype=float)[rng.integers(0, len(values),
                                                         size=(config.bootstrap_repetitions, len(values)))]
    computed = np.mean(sample, axis=1) if statistic == "mean" else np.median(sample, axis=1)
    return tuple(float(x) for x in np.quantile(computed, [0.025, 0.975]))


def summarize(windows: pd.DataFrame, *, config: StudyConfig) -> pd.DataFrame:
    complete = windows.loc[windows["analysis_status"] == "COMPLETE"]
    rows = []
    for symbol in sorted(windows["asset"].unique()):
        for gate in range(1, 65):
            group = complete.loc[(complete["asset"] == symbol) & (complete["gate"] == gate)]
            returns = group["return_pct"].dropna().astype(float).tolist()
            percentiles = group["random_return_percentile"].dropna().astype(float).tolist()
            effects = (group["return_pct"] - group["random_return_median"]).dropna().astype(float)
            annual_sign = (max(sum(value > 0 for value in returns), sum(value < 0 for value in returns)) /
                           len(returns) if returns else None)
            mean_ci = bootstrap_interval(returns, config=config, key=f"{symbol}:{gate}", statistic="mean")
            median_ci = bootstrap_interval(returns, config=config, key=f"{symbol}:{gate}", statistic="median")
            def stat(column: str, kind: str = "mean") -> float | None:
                sample = group[column].dropna().astype(float)
                return float(getattr(sample, kind)()) if len(sample) else None
            midpoint = float(np.median(percentiles)) if percentiles else None
            effect = float(effects.median()) if len(effects) else None
            flags = [annual_sign is not None and annual_sign >= .70,
                     effect is not None and abs(effect) >= 1,
                     midpoint is not None and (midpoint < 10 or midpoint > 90),
                     mean_ci[0] is not None and (mean_ci[0] > 0 or mean_ci[1] < 0)]
            insufficient = len(returns) < 5 or len(percentiles) < len(returns) / 2
            status = ("INSUFFICIENT SAMPLE" if insufficient else
                      "WEAK" if sum(flags) >= 2 else "NO EVIDENCE")
            same_phase = complete.loc[(complete["asset"] == symbol) &
                                      (complete["gate"] != gate) &
                                      (complete["phase_at_start"].isin(group["phase_at_start"].dropna()))]
            phase_median = (float(group["return_pct"].median() - same_phase["return_pct"].median())
                            if len(group) and len(same_phase) else None)
            quarter_rows = windows.loc[windows["gate"] == gate, "quarter_id"]
            rows.append({"asset": symbol, "gate": gate, "quarter_id":
                         quarter_rows.iloc[0] if len(quarter_rows) else None,
                         "count_windows": len(returns), "years": json.dumps(group["year"].tolist()),
                         "research_status": status, "exploratory_flags": sum(flags),
                         "annual_sign_consistency": annual_sign,
                         "mean_return": stat("return_pct"), "median_return": stat("return_pct", "median"),
                         "std_return": stat("return_pct", "std"),
                         "min_return": stat("return_pct", "min"), "max_return": stat("return_pct", "max"),
                         "positive_return_ratio": float(np.mean(np.array(returns) > 0)) if returns else None,
                         "mean_mdd": stat("max_drawdown_pct"),
                         "median_mdd": stat("max_drawdown_pct", "median"),
                         "mean_volatility": stat("daily_volatility_pct"),
                         "mean_vix": stat("vix_mean"), "mean_vix_change": stat("vix_change"),
                         "mean_us10y_change": stat("us10y_change_pp"),
                         "mean_usdkrw_change": stat("usdkrw_change_pct"),
                         "mean_broad_dollar_change": stat("broad_dollar_change_pct"),
                         "median_random_return_percentile": midpoint,
                         "median_random_effect_pp": effect,
                         "mean_return_ci_low": mean_ci[0], "mean_return_ci_high": mean_ci[1],
                         "median_return_ci_low": median_ci[0], "median_return_ci_high": median_ci[1],
                         "phase_control_count": len(same_phase),
                         "phase_control_median_effect_pp": phase_median})
    result = pd.DataFrame(rows)
    # MODERATE needs cross-asset replication and Phase control; STRONG needs
    # ten independent annual windows and cannot occur in this study period.
    for index, row in result.iterrows():
        if row["research_status"] != "WEAK" or row["count_windows"] < 6 or row["exploratory_flags"] < 4:
            continue
        percentile = row["median_random_return_percentile"]
        effect = row["median_random_effect_pp"]
        phase_effect = row["phase_control_median_effect_pp"]
        peers = result.loc[(result["gate"] == row["gate"]) & (result["asset"] != row["asset"])]
        replicated = any(pd.notna(peer) and np.sign(peer) == np.sign(effect)
                         for peer in peers["median_random_effect_pp"])
        if (percentile < 5 or percentile > 95) and replicated and pd.notna(phase_effect) and np.sign(phase_effect) == np.sign(effect):
            result.at[index, "research_status"] = "MODERATE"
    return result


def quarter_summary(windows: pd.DataFrame) -> pd.DataFrame:
    valid = windows.loc[windows["analysis_status"] == "COMPLETE"]
    return valid.groupby(["asset", "quarter_id", "quarter_name_ko"], dropna=False).agg(
        count_windows=("return_pct", "count"), median_return=("return_pct", "median"),
        median_mdd=("max_drawdown_pct", "median"),
        median_volatility=("daily_volatility_pct", "median")).reset_index()


def run_study(root: Path, config: StudyConfig, assets: tuple[str, ...] = ASSETS) -> dict:
    if any(symbol not in ASSETS for symbol in assets):
        raise ValueError("Unsupported research asset")
    research = ComparisonResearch(root)
    frames = {symbol: research._local(symbol) for symbol in assets}
    snapshots = {key: latest_snapshot(root, key) for key in CONTEXT}
    intervals = gate_intervals(config.start, config.end)
    windows = pd.DataFrame([row for symbol, (frame, _) in frames.items()
                            for row in asset_windows(symbol, frame, root=root, config=config,
                                                     intervals=intervals, snapshots=snapshots)])
    summary = summarize(windows, config=config)
    quarters = quarter_summary(windows)
    sources = {symbol: {"available_from": str(frame.iloc[0]["date"]),
                        "available_to": str(frame.iloc[-1]["date"]),
                        "rows": len(frame), "provider": source.get("provider"),
                        "frame_sha256": sha256(frame.to_csv(index=False).encode()).hexdigest()}
               for symbol, (frame, source) in frames.items()}
    context_sources = {key: ({"available_from": snapshot[1]["available_from"],
                              "available_to": snapshot[1]["available_to"],
                              "raw_sha256": snapshot[1]["raw_sha256"],
                              "series_id": snapshot[1]["series_id"]} if snapshot else None)
                       for key, snapshot in snapshots.items()}
    manifest = {"study": "TRANSIT_MARKET_V1", "config": asdict(config), "assets": list(assets),
                "analysis_code_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
                "asset_sources": sources, "context_sources": context_sources,
                "price_phase_rule_hash": RULE_CONFIG_HASH,
                "transit_source": year_calendar(date.fromisoformat(config.start).year)["provenance"],
                "window_rows": len(windows), "summary_rows": len(summary)}
    return {"windows": windows, "summary": summary, "quarters": quarters,
            "manifest": manifest}
