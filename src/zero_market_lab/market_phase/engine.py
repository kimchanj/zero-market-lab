"""Frozen PRICE_PHASE_V1 candidate. Labels use no observations after their date."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json

import numpy as np
import pandas as pd


VERSION = "PRICE_PHASE_V1"
RULE_CONFIG = {
    "ma_short": 50, "ma_long": 200, "slope_short": 5, "slope_long": 10,
    "recent_block": 10, "breakout": 20, "high_52w": 252,
    "recovery_fraction": 0.05, "autumn_drawdown_fraction": 0.10,
    "confirmation_days": 3, "outcome_horizon": 60,
}
RULE_CONFIG_HASH = sha256(json.dumps(RULE_CONFIG, sort_keys=True).encode()).hexdigest()
PHASES = ("WINTER", "SPRING_CANDIDATE", "SPRING", "SUMMER", "AUTUMN")


@dataclass(frozen=True)
class PhaseEvidence:
    price_above_ma50: bool | None
    price_above_ma200: bool | None
    ma50_above_ma200: bool | None
    ma50_slope_positive: bool | None
    ma200_slope_positive: bool | None
    ma200_slope_flat_or_improving: bool | None
    recent_higher_low: bool | None
    recent_higher_high: bool | None
    drawdown_from_52w_high: float | None
    recovery_from_recent_low: float | None
    breakout_20d: bool | None


@dataclass(frozen=True)
class PhaseResult:
    symbol: str
    date: str
    available_at: str
    close: float
    ma50: float | None
    ma200: float | None
    current_phase: str
    previous_phase: str | None
    days_in_phase: int
    transition_date: str | None
    transition: str | None
    evidence: PhaseEvidence
    ma200_entry_filter_allowed_next_day: bool | None
    engine_version: str
    rule_config_hash: str
    data_source: str


@dataclass(frozen=True)
class PhaseTransition:
    symbol: str
    transition_date: str
    from_phase: str
    to_phase: str
    close: float
    previous_duration: int
    evidence_snapshot: PhaseEvidence


def _optional_float(value) -> float | None:
    return float(value) if pd.notna(value) else None


def _optional_bool(value) -> bool | None:
    return bool(value) if pd.notna(value) else None


def _validated(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"date", "open", "high", "low", "close"}
    if frame.empty or not required.issubset(frame.columns):
        raise ValueError("Nonempty daily OHLC with date is required")
    data = frame.copy().reset_index(drop=True)
    data["date"] = pd.to_datetime(data["date"], errors="raise")
    if data["date"].isna().any() or data["date"].duplicated().any() or not data["date"].is_monotonic_increasing:
        raise ValueError("Dates must be unique and ascending")
    for column in ("open", "high", "low", "close"):
        data[column] = pd.to_numeric(data[column], errors="raise")
    if (not np.isfinite(data[["open", "high", "low", "close"]].to_numpy()).all() or
        (data[["open", "high", "low", "close"]] <= 0).any().any() or
        not ((data["high"] >= data[["open", "close", "low"]].max(axis=1)) &
             (data["low"] <= data[["open", "close", "high"]].min(axis=1))).all()):
        raise ValueError("Invalid OHLC")
    return data


def _indicators(frame: pd.DataFrame) -> pd.DataFrame:
    data = _validated(frame)
    close, high, low = data["close"], data["high"], data["low"]
    data["ma50"] = close.rolling(50, min_periods=50).mean()
    data["ma200"] = close.rolling(200, min_periods=200).mean()
    data["ma50_delta"] = data["ma50"] - data["ma50"].shift(5)
    data["ma200_delta"] = data["ma200"] - data["ma200"].shift(10)
    data["ma200_delta_prior"] = data["ma200_delta"].shift(10)
    data["higher_low"] = low.rolling(10, min_periods=10).min() > low.shift(10).rolling(10, min_periods=10).min()
    data["higher_high"] = high.rolling(10, min_periods=10).max() > high.shift(10).rolling(10, min_periods=10).max()
    data["recent_low"] = low.rolling(20, min_periods=20).min()
    data["previous_high20"] = high.shift(1).rolling(20, min_periods=20).max()
    data["high52w"] = high.rolling(252, min_periods=252).max()
    data["ma200_5ago"] = data["ma200"].shift(5)
    return data


def _evidence(row: pd.Series) -> PhaseEvidence:
    close, ma50, ma200 = row["close"], row["ma50"], row["ma200"]
    return PhaseEvidence(
        price_above_ma50=_optional_bool(close > ma50) if pd.notna(ma50) else None,
        price_above_ma200=_optional_bool(close > ma200) if pd.notna(ma200) else None,
        ma50_above_ma200=_optional_bool(ma50 > ma200) if pd.notna(ma50) and pd.notna(ma200) else None,
        ma50_slope_positive=_optional_bool(row["ma50_delta"] > 0) if pd.notna(row["ma50_delta"]) else None,
        ma200_slope_positive=_optional_bool(row["ma200_delta"] > 0) if pd.notna(row["ma200_delta"]) else None,
        ma200_slope_flat_or_improving=(bool(row["ma200_delta"] >= row["ma200_delta_prior"])
            if pd.notna(row["ma200_delta"]) and pd.notna(row["ma200_delta_prior"]) else None),
        recent_higher_low=bool(row["higher_low"]) if pd.notna(row["recent_low"]) else None,
        recent_higher_high=bool(row["higher_high"]) if pd.notna(row["recent_low"]) else None,
        drawdown_from_52w_high=_optional_float(close / row["high52w"] - 1) if pd.notna(row["high52w"]) else None,
        recovery_from_recent_low=_optional_float(close / row["recent_low"] - 1) if pd.notna(row["recent_low"]) else None,
        breakout_20d=bool(close > row["previous_high20"]) if pd.notna(row["previous_high20"]) else None,
    )


def _raw(e: PhaseEvidence, *, current: str) -> dict[str, bool]:
    winter = (e.price_above_ma200 is False and e.ma50_above_ma200 is False and
              e.ma200_slope_positive is False)
    summer = (e.price_above_ma200 is True and e.ma50_above_ma200 is True and
              e.ma50_slope_positive is True and e.ma200_slope_positive is True)
    recovery = e.recovery_from_recent_low is not None and e.recovery_from_recent_low >= 0.05
    core = (e.price_above_ma50 is True and e.ma50_slope_positive is True and
            (e.recent_higher_low is True or recovery))
    autumn = (current in {"SUMMER", "AUTUMN"} and not summer and
              (e.price_above_ma50 is False or e.ma50_slope_positive is False or
               (e.drawdown_from_52w_high is not None and e.drawdown_from_52w_high <= -0.10)))
    return {"WINTER": winter, "SUMMER": summer,
            "SPRING_CANDIDATE": core and not summer,
            "SPRING": core and (e.ma50_above_ma200 is True or e.breakout_20d is True),
            "AUTUMN": autumn}


def _targets(current: str) -> tuple[str, ...]:
    return {"UNKNOWN": ("WINTER", "SUMMER", "SPRING_CANDIDATE"),
            "WINTER": ("SPRING_CANDIDATE",),
            "SPRING_CANDIDATE": ("WINTER", "SPRING"),
            "SPRING": ("WINTER", "SUMMER"),
            "SUMMER": ("AUTUMN",),
            "AUTUMN": ("WINTER", "SUMMER")}[current]


def _forward_event(rows: list[PhaseResult], index: int, transitions: list[PhaseTransition],
                   *, kind: str) -> dict:
    start = rows[index]
    horizon = RULE_CONFIG["outcome_horizon"]
    end = min(index + horizon, len(rows) - 1)
    progress = [event for event in transitions
                if start.date < event.transition_date <= rows[end].date]
    if kind == "SPRING_CANDIDATE":
        success, failure = {"SPRING", "SUMMER"}, "WINTER"
    else:
        success, failure = {"WINTER"}, "SUMMER"
    outcome = "CENSORED" if end - index < horizon else "UNRESOLVED"
    days_to_outcome = None
    for event in progress:
        if event.to_phase in success | {failure}:
            outcome = ("FALSE_SPRING" if kind == "SPRING_CANDIDATE" else "FALSE_AUTUMN") if event.to_phase == failure else ("CONFIRMED" if kind == "SPRING_CANDIDATE" else "WINTER")
            days_to_outcome = next(i - index for i, row in enumerate(rows) if row.date == event.transition_date)
            break
    returns = {f"return_{horizon_days}d":
        rows[index+horizon_days].close / start.close - 1 if index+horizon_days < len(rows) else None
        for horizon_days in (20, 60, 120)}
    forward_prices = [row.close for row in rows[index:min(index+121, len(rows))]]
    if len(forward_prices) == 121:
        running_peak = forward_prices[0]
        max_forward_drawdown = 0.0
        for price in forward_prices[1:]:
            running_peak = max(running_peak, price)
            max_forward_drawdown = min(max_forward_drawdown, price / running_peak - 1)
    else:
        max_forward_drawdown = None
    first_winter = next((event.transition_date for event in transitions
                         if start.date < event.transition_date <= rows[min(index+120, len(rows)-1)].date
                         and event.to_phase == "WINTER"), None)
    days_to_summer = next((j-index for j in range(index+1, min(index+121, len(rows)))
                           if rows[j].transition == "SPRING->SUMMER" and
                           (first_winter is None or rows[j].date < first_winter)), None)
    return {"symbol": start.symbol, "date": start.date, "kind": kind, "outcome": outcome,
            "days_to_outcome": days_to_outcome, "max_forward_drawdown_120d": max_forward_drawdown,
            "days_to_summer_120d": days_to_summer,
            **returns}


class PhaseEngine:
    """Independent phase detector. No strategy/portfolio/order imports."""

    def run(self, frame: pd.DataFrame, *, symbol: str, data_source: str,
            as_of: str | None = None) -> dict:
        data = _indicators(frame)
        if as_of is not None:
            data = data.loc[data["date"] <= pd.Timestamp(as_of)].reset_index(drop=True)
        if data.empty:
            raise ValueError("No observations by as_of")
        rows: list[PhaseResult] = []
        transitions: list[PhaseTransition] = []
        phase, prior_distinct, transition_date, age = "UNKNOWN", None, None, 0
        pending, pending_days = None, 0
        for _, row in data.iterrows():
            day = row["date"].date().isoformat()
            e = _evidence(row)
            raw = _raw(e, current=phase)
            eligible = (next((target for target in _targets(phase) if raw[target]), None)
                        if pd.notna(row["ma200_delta"]) else None)
            if eligible is not None:
                pending_days = pending_days + 1 if eligible == pending else 1
                pending = eligible
            else:
                pending, pending_days = None, 0
            previous_duration = age
            age += 1
            transition = None
            if pending_days >= RULE_CONFIG["confirmation_days"]:
                old = phase
                phase, prior_distinct, transition_date, age = pending, old, day, 1
                transition = f"{old}->{phase}"
                transitions.append(PhaseTransition(symbol, day, old, phase, float(row["close"]),
                                                   previous_duration, e))
                pending, pending_days = None, 0
            baseline = (bool(row["close"] > row["ma200"] and row["ma200"] > row["ma200_5ago"])
                        if pd.notna(row["ma200_5ago"]) else None)
            rows.append(PhaseResult(symbol, day, day + " close", float(row["close"]),
                                    _optional_float(row["ma50"]), _optional_float(row["ma200"]),
                                    phase, prior_distinct, age, transition_date, transition, e,
                                    baseline, VERSION, RULE_CONFIG_HASH, data_source))
        durations = []
        begin = 0
        for i in range(1, len(rows) + 1):
            if i == len(rows) or rows[i].current_phase != rows[begin].current_phase:
                segment = rows[begin:i]
                durations.append({"phase": segment[0].current_phase, "start_date": segment[0].date,
                                  "end_date": segment[-1].date, "trading_days": len(segment),
                                  "start_price": segment[0].close, "end_price": segment[-1].close,
                                  "phase_return": segment[-1].close / segment[0].close - 1,
                                  "right_censored": i == len(rows)})
                begin = i
        dates = {row.date: i for i, row in enumerate(rows)}
        spring = [_forward_event(rows, dates[event.transition_date], transitions, kind="SPRING_CANDIDATE")
                  for event in transitions if event.to_phase == "SPRING_CANDIDATE"]
        autumn = [_forward_event(rows, dates[event.transition_date], transitions, kind="AUTUMN")
                  for event in transitions if event.to_phase == "AUTUMN"]
        return {"symbol": symbol, "engine_version": VERSION, "rule_config_hash": RULE_CONFIG_HASH,
                "rule_config": RULE_CONFIG.copy(), "data_source": data_source,
                "rows": [asdict(row) for row in rows],
                "transitions": [asdict(event) for event in transitions],
                "durations": durations, "spring_events": spring, "autumn_events": autumn}
