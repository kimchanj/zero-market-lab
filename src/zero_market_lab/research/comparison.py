"""Read-only, same-date comparison of locally observed research series.

An unavailable indicator remains unavailable. No market or strategy decision uses
these context values.
"""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path

import pandas as pd

from zero_market_lab.asset_discovery.catalog import LocalOHLCVCatalog, load_universe
from zero_market_lab.market_phase.engine import PhaseEngine
from zero_market_lab.research.context_data import FRED_SERIES, as_of_observation, latest_snapshot
from zero_market_lab.transit.calendar import at_market_close
from zero_market_lab.transit.quarters import load_quarters

ASSET_TYPES = {"ASSET", "INDEX"}
CONTEXT_TYPES = {"PHASE", "TRANSIT"}
NUMERIC_CONTEXT_TYPES = {"VOLATILITY", "RATE", "FX", "MACRO"}
UNCONNECTED = (
    ("KOSPI", "KOSPI", "INDEX", "index points", "index source not connected"),
    ("KOSDAQ", "KOSDAQ", "INDEX", "index points", "index source not connected"),
    ("NASDAQ", "NASDAQ", "INDEX", "index points", "index source not connected"),
    ("VIX", "VIX", "VOLATILITY", "index points", "CBOE source not connected"),
    ("FEAR_GREED", "Fear & Greed", "SENTIMENT", "0–100", "CNN source not connected"),
    ("US10Y", "미국 10년물 국채수익률", "RATE", "%", "rate source not connected"),
    ("DXY", "DXY", "FX", "index points", "dollar index source not connected"),
    ("BROAD_USD", "미 달러 광의지수", "FX", "Jan 2006=100", "FRED DTWEXBGS; DXY와 다른 지수"),
    ("USDKRW", "원/달러 환율 · 1 USD=KRW", "FX", "KRW per USD", "FX source not connected"),
    ("GOLD", "Gold", "COMMODITY", "USD", "gold source not connected"),
    ("WTI", "WTI Crude Oil", "COMMODITY", "USD", "oil source not connected"),
    ("FED_FUNDS", "Fed Funds", "RATE", "%", "rate source not connected"),
    ("US2Y", "US 2Y", "RATE", "%", "rate source not connected"),
    ("US10Y_2Y", "US 10Y–2Y", "RATE", "%p", "spread source not connected"),
    ("REAL_YIELD", "US Real Yield", "RATE", "%", "real yield source not connected"),
    ("HY_SPREAD", "High Yield Spread", "RATE", "%p", "spread source not connected"),
    ("FIN_STRESS", "Financial Stress", "MACRO", "index", "stress source not connected"),
    ("PUT_CALL", "Put/Call", "SENTIMENT", "ratio", "options source not connected"),
    ("INDIVIDUAL_FLOW", "KRX Individual Net Flow", "FLOW", "KRW", "flow source not connected"),
    ("INSTITUTION_FLOW", "KRX Institution Net Flow", "FLOW", "KRW", "flow source not connected"),
    ("FOREIGN_FLOW", "KRX Foreign Net Flow", "FLOW", "KRW", "flow source not connected"),
    ("PROGRAM_FLOW", "KRX Program Net Flow", "FLOW", "KRW", "flow source not connected"),
    ("BREADTH", "KRX Market Breadth", "BREADTH", "%", "breadth source not connected"),
)


def gate_metadata(root: Path) -> list[dict]:
    rows = json.loads((root / "data/reference/human_design_gates.json").read_text(encoding="utf-8"))["gates"]
    if len(rows) != 64 or {row["gate"] for row in rows} != set(range(1, 65)):
        raise ValueError("Gate metadata must cover unique Gates 1–64")
    required = ("center", "center_ko", "gate_name", "gate_name_ko", "short_keynote",
                "short_keynote_ko", "short_description", "short_description_ko",
                "quarter_id", "source", "version")
    if any(not all(row.get(key) for key in required) for row in rows):
        raise ValueError("Gate metadata has missing required labels")
    return rows


def interpret_indicator(indicator_id: str, current: float | None,
                        history: list[float] | None = None) -> dict:
    """Reference interpretations only; never infer a value from another series."""
    if current is None:
        return {"value": None, "status": "NOT_CONNECTED", "reference": None,
                "change": None, "meaning": "관측 데이터가 연결되지 않았습니다."}
    if indicator_id == "FEAR_GREED":
        if not 0 <= current <= 100:
            raise ValueError("Fear & Greed value outside 0–100")
        label = ("Extreme Fear" if current < 25 else "Fear" if current < 45 else
                 "Neutral" if current <= 55 else "Greed" if current <= 75 else "Extreme Greed")
        return {"value": current, "status": label, "reference": "0–100; 50 neutral",
                "scale_type": "FIXED_SCALE", "meaning": "미국 시장 심리 지표의 관측값입니다."}
    if indicator_id == "VIX":
        label = "Elevated" if current >= 30 else "Moderate" if current >= 20 else "Lower"
        return {"value": current, "status": label,
                "reference": "20/30 are research reference thresholds, not laws",
                "scale_type": "REFERENCE_THRESHOLD", "meaning": "미국 주식시장 기대 변동성의 관측값입니다."}
    if indicator_id in {"US10Y", "DXY", "BROAD_USD", "USDKRW", "FOREIGN_FLOW"}:
        sample = sorted(history or [])
        percentile = 100 * sum(value <= current for value in sample) / len(sample) if sample else None
        return {"value": current, "status": "Historical context" if sample else "Reference unavailable",
                "percentile": percentile, "reference": f"{len(sample)} observed values",
                "scale_type": "HISTORICAL_PERCENTILE", "meaning": "과거 관측 분포와 비교하며 인과관계를 뜻하지 않습니다."}
    return {"value": current, "status": "Observed", "reference": None,
            "scale_type": "OBSERVED", "meaning": "관측값입니다."}


class ComparisonResearch:
    def __init__(self, root: Path, loader=None):
        self.root = root
        self.loader = loader or LocalOHLCVCatalog(root).load
        self.assets = {a["symbol"]: a for a in load_universe(root / "config/universe_seed_kr_us.json")}
        self.gates = {row["gate"]: row for row in gate_metadata(root)}
        self.quarters, self.quarter_by_gate = load_quarters(root)

    def _local(self, symbol: str) -> tuple[pd.DataFrame, dict]:
        if symbol == "SP500":
            paths = sorted((self.root / "data/processed").glob("*/sp500_price_daily.parquet"))
            if not paths:
                raise FileNotFoundError(symbol)
            frame = pd.read_parquet(paths[-1])
            source = {"provider": "FRED / S&P Dow Jones Indices", "adjustment": "PRICE_INDEX_DIVIDEND_EXCLUDED",
                      "retrieved_at": None, "timezone": "America/New_York"}
        elif symbol in self.assets:
            frame, source = self.loader(symbol)
        else:
            raise ValueError("Unsupported comparison symbol")
        frame = frame.copy()
        frame["date"] = frame["date"].astype(str).str[:10]
        if frame.empty or frame["date"].duplicated().any() or not frame["date"].is_monotonic_increasing:
            raise ValueError("Comparison data must be nonempty, unique and ascending")
        frame["close"] = pd.to_numeric(frame["close"], errors="raise")
        if frame["close"].isna().any() or (frame["close"] <= 0).any():
            raise ValueError("Comparison close must be positive and non-null")
        return frame, {key: source.get(key) for key in
                       ("provider", "source_url", "retrieved_at", "adjustment", "timezone")}

    def catalog(self) -> dict:
        rows = []
        for symbol, asset in [*self.assets.items(), ("SP500", {"name": "S&P 500 Price Index",
                                                 "currency": "index points", "market": "US"})]:
            try:
                frame, source = self._local(symbol)
                status = "AVAILABLE"
                first, last = frame.iloc[0]["date"], frame.iloc[-1]["date"]
            except FileNotFoundError:
                status, first, last, source = "NOT_CONNECTED", None, None, {}
            rows.append({"layer_id": symbol, "layer_type": "INDEX" if symbol == "SP500" else "ASSET",
                         "indicator_id": symbol, "symbol": symbol, "display_name": asset["name"],
                         "unit": asset["currency"], "source": source.get("provider"),
                         "frequency": "DAILY_OBSERVED", "timezone": asset.get("timezone", "America/New_York"),
                         "render_type": "LINE", "scale_type": "PRICE", "axis_policy": "OWN_UNIT_IN_ACTUAL",
                         "enabled": False, "availability": status, "available_from": first,
                         "available_to": last, "metadata": {"market": asset["market"]}})
        for key, name, kind, unit, note in UNCONNECTED:
            snapshot = latest_snapshot(self.root, key) if key in FRED_SERIES else None
            metadata = snapshot[1] if snapshot else None
            rows.append({"layer_id": key, "layer_type": kind, "indicator_id": key, "symbol": None,
                         "display_name": FRED_SERIES[key].name if metadata else name,
                         "unit": unit, "source": "FRED / " + metadata["original_source"] if metadata else None,
                         "frequency": metadata["frequency"] if metadata else "UNKNOWN",
                         "timezone": metadata["timezone"] if metadata else None,
                         "render_type": "INDICATOR_PANE" if metadata else "LINE",
                         "scale_type": "OBSERVED_CONTEXT" if metadata else "UNCONNECTED",
                         "axis_policy": "SEPARATE", "enabled": False,
                         "availability": "AVAILABLE" if metadata else "NOT_CONNECTED",
                         "available_from": metadata["available_from"] if metadata else None,
                         "available_to": metadata["available_to"] if metadata else None,
                         "metadata": metadata or {"reason": note}})
        rows.extend([
            {"layer_id": "PRICE_PHASE_V1", "layer_type": "PHASE", "indicator_id": "PRICE_PHASE_V1",
             "symbol": None, "display_name": "FECM 가격 Phase", "unit": "category", "source": "PRICE_PHASE_V1",
             "frequency": "DAILY_CLOSE", "timezone": "base exchange", "render_type": "CATEGORICAL_BAND",
             "scale_type": "CATEGORICAL", "axis_policy": "NONE", "enabled": False,
             "availability": "RESEARCH_ONLY", "available_from": None, "available_to": None,
             "metadata": {"meaning": "As-of price phase; not a trade signal"}},
            {"layer_id": "HD_TRANSIT", "layer_type": "TRANSIT", "indicator_id": "SOLAR_GATE_V1",
             "symbol": None, "display_name": "☉ 휴먼디자인 트랜짓", "unit": "Gate.Line", "source": "USNO approximate solar longitude",
             "frequency": "CONTINUOUS_ESTIMATE", "timezone": "UTC boundary; market close mapping",
             "render_type": "CATEGORICAL_BAND", "scale_type": "CATEGORICAL", "axis_policy": "NONE",
             "enabled": False, "availability": "RESEARCH_ONLY", "available_from": "2000-01-01",
             "available_to": "2100-12-31", "metadata": {"meaning": "Symbolic context, not market evidence"}},
        ])
        return {"layers": rows, "quarters": self.quarters,
                "gate_to_quarter": {str(gate): item["id"] for gate, item in self.quarter_by_gate.items()}}

    def series(self, *, base: str, start: str, end: str, layers: list[str],
               display: str = "ACTUAL") -> dict:
        begin, finish = date.fromisoformat(start), date.fromisoformat(end)
        if begin > finish or (finish - begin).days > 3653 or display not in {"ACTUAL", "NORMALIZE_100"}:
            raise ValueError("Invalid comparison period or display")
        catalog = {row["layer_id"]: row for row in self.catalog()["layers"]}
        if base not in catalog or catalog[base]["layer_type"] not in ASSET_TYPES:
            raise ValueError("Base must be a connected asset or index")
        if len(layers) > 10 or len(set(layers)) != len(layers) or any(key not in catalog or key == base for key in layers):
            raise ValueError("Invalid comparison layers")
        if catalog[base]["availability"] == "NOT_CONNECTED":
            raise FileNotFoundError(base)
        ids = [base, *layers]
        series = []
        base_frame = None
        base_previous_close = None
        previous_by_series = {}
        numeric_frames = {}
        base_source = None
        for key in ids:
            descriptor = catalog[key]
            if descriptor["layer_type"] in NUMERIC_CONTEXT_TYPES and key in FRED_SERIES and descriptor["availability"] == "AVAILABLE":
                numeric_frames[key], metadata = latest_snapshot(self.root, key)
                series.append({"layer_id": key, "availability": "AVAILABLE", "points": [],
                               "unit": descriptor["unit"], "source": metadata})
                continue
            if descriptor["layer_type"] not in ASSET_TYPES or descriptor["availability"] == "NOT_CONNECTED":
                series.append({"layer_id": key, "availability": descriptor["availability"], "points": [],
                               "unit": descriptor["unit"], "source": descriptor["source"]})
                continue
            frame, source = self._local(key)
            earlier = frame.loc[frame["date"] < start, "close"]
            previous_by_series[key] = float(earlier.iloc[-1]) if not earlier.empty else None
            if key == base:
                base_previous_close = previous_by_series[key]
            frame = frame.loc[(frame["date"] >= start) & (frame["date"] <= end)]
            if key == base:
                base_frame, base_source = frame, source
            first = float(frame.iloc[0]["close"]) if not frame.empty else None
            points = [{"date": str(row["date"]), "value": float(row["close"]),
                       "display_value": (float(row["close"]) / first * 100
                                         if display == "NORMALIZE_100" and first else float(row["close"]))}
                      for _, row in frame.iterrows()]
            series.append({"layer_id": key, "availability": "AVAILABLE" if points else "PARTIAL_HISTORY",
                           "points": points, "unit": descriptor["unit"], "source": source})
        if base_frame is None or base_frame.empty:
            raise ValueError("No base observations in period")
        phase_by_date = {}
        if "PRICE_PHASE_V1" in layers:
            full, _ = self._local(base)
            if {"open", "high", "low"} <= set(full.columns):
                prefix = full.loc[full["date"] <= end]
                phase_rows = PhaseEngine().run(prefix, symbol=base,
                                               data_source=base_source.get("provider") or "LOCAL")["rows"]
                phase_by_date = {row["date"]: row["current_phase"] for row in phase_rows}
        context = {}
        previous_close = base_previous_close
        for _, row in base_frame.iterrows():
            day = str(row["date"])
            close = float(row["close"])
            change = (close / previous_close - 1) * 100 if previous_close else None
            transit = None
            if "HD_TRANSIT" in layers:
                mapping = at_market_close(day, "KRW" if base in self.assets and self.assets[base]["currency"] == "KRW" else "USD")
                gate = self.gates[mapping["gate"]]
                transit = {"gate": mapping["gate"], "line": mapping["line"],
                           "center": gate["center"], "gate_name": gate["gate_name"],
                           "keynote": gate["short_keynote"], "short_theme": gate["short_theme"],
                           "fear_theme": gate["fear_theme"], "research_summary": gate["research_summary"],
                           "center_ko": gate["center_ko"], "gate_name_ko": gate["gate_name_ko"],
                           "keynote_ko": gate["short_keynote_ko"],
                           "short_description": gate["short_description"],
                           "short_description_ko": gate["short_description_ko"],
                           "theme": gate["theme"], "theme_ko": gate["theme_ko"],
                           "fear_theme_ko": gate["fear_theme_ko"],
                           "quarter": self.quarter_by_gate[mapping["gate"]],
                           "start_utc": mapping["start_utc"], "end_utc": mapping["end_utc"],
                           "source": mapping["source"], "accuracy": "MODEL_ESTIMATE_NOT_EPHEMERIS_VERIFIED"}
            is_krx = base in self.assets and self.assets[base]["market"] == "KRX"
            flow_status = "NOT_CONNECTED" if is_krx else "NOT_APPLICABLE"
            flow_meaning = ("투자주체별 순매수 금액 원천이 연결되지 않았습니다."
                            if is_krx else "해외 종목에 한국식 투자주체 분류를 적용하지 않습니다.")
            investor_flow = {key: {"value": None, "unit": "KRW" if is_krx else None,
                                   "status": flow_status, "source": None,
                                   "observation_date": None, "meaning": flow_meaning}
                             for key in ("individual", "institution", "foreign")}
            def observed(field: str):
                return float(row[field]) if field in row and pd.notna(row[field]) else None
            context[day] = {"date": day, "base": {"symbol": base, "close": close,
                        "open": observed("open"), "high": observed("high"),
                        "low": observed("low"), "volume": observed("volume"),
                        "daily_change_pct": change, "unit": catalog[base]["unit"],
                        "reference": "직전 관측 종가", "status": ("상승" if change > 0 else "하락" if change < 0 else "보합") if change is not None else "첫 관측",
                        "meaning": "해당 거래일 종가 변화이며 원인·추세·미래 방향의 판정이 아닙니다. 배당 및 환율 효과는 별도"},
                        "phase": phase_by_date.get(day), "transit": transit,
                        "investor_flow": investor_flow}
            previous_close = close
        for item in series[1:]:
            if item["layer_id"] in numeric_frames:
                key = item["layer_id"]
                frame = numeric_frames[key]
                definition = FRED_SERIES[key]
                is_krx = base in self.assets and self.assets[base]["market"] == "KRX"
                lag = definition.krx_lag_days if is_krx else definition.us_lag_days
                for day, snapshot in context.items():
                    observed = as_of_observation(frame, day, lag)
                    age = (date.fromisoformat(day) - date.fromisoformat(observed["observation_date"])).days if observed else None
                    max_age = 10 if key == "VIX" else 21 if key == "US10Y" else 35
                    if observed and age <= max_age:
                        position = int(frame["date"].searchsorted(observed["observation_date"], side="right"))
                        history = frame.iloc[:position]
                        prior = history.iloc[-2]["value"] if len(history) > 1 else None
                        value = observed["value"]
                        interpretation = interpret_indicator(key, value,
                            history.tail(252)["value"].tolist())
                        snapshot.setdefault("layers", {})[key] = {
                            **observed, "availability": "AVAILABLE", "unit": item["unit"],
                            "change_1d_pct": (value / prior - 1) * 100 if prior else None,
                            "reference": interpretation.get("reference") or "직전 해당 시리즈 관측값",
                            "state": interpretation["status"], "meaning": interpretation["meaning"],
                            "source": {field: item["source"][field] for field in
                                       ("provider", "series_id", "source_url", "raw_sha256")},
                            "frequency": "DAILY_OBSERVATION"}
                    else:
                        snapshot.setdefault("layers", {})[key] = {
                            "value": None, "observation_date": observed["observation_date"] if observed else None,
                            "availability": "STALE_OBSERVATION" if observed else "NO_AVAILABLE_OBSERVATION",
                            "status": "STALE_OBSERVATION" if observed else "NO_AVAILABLE_OBSERVATION",
                            "unit": item["unit"],
                            "source": {field: item["source"][field] for field in
                                       ("provider", "series_id", "source_url", "raw_sha256")},
                            "frequency": "DAILY_OBSERVATION"}
                continue
            point_by_date = {point["date"]: point for point in item["points"]}
            previous_by_date = {point["date"]: item["points"][index - 1]["value"] if index else previous_by_series.get(item["layer_id"])
                                for index, point in enumerate(item["points"])}
            for day, snapshot in context.items():
                point = point_by_date.get(day)
                previous = previous_by_date.get(day)
                change = (point["value"] / previous - 1) * 100 if point and previous else None
                snapshot.setdefault("layers", {})[item["layer_id"]] = {
                    "value": point["value"] if point else None,
                    "display_value": point["display_value"] if point else None,
                    "change_1d_pct": change,
                    "reference": "직전 해당 시장 관측 종가" if point else None,
                    "status": ("상승" if change > 0 else "하락" if change < 0 else "보합") if change is not None else "기준 없음",
                    "meaning": "관측 가격 변화; 인과관계 또는 환율 조정 수익률이 아님" if point else None,
                    "observation_date": day if point else None,
                    "availability": item["availability"] if point else
                                    ("NO_SAME_DATE_OBSERVATION" if item["points"] else item["availability"]),
                    "unit": item["unit"], "source": item["source"]}
        return {"base": base, "start": start, "end": end, "display": display,
                "series": series, "context_by_date": context,
                "provenance": {"base": base_source, "same_date_rule": "Exact market date only; no forward fill",
                               "normalization": "First observed value within selected period = 100"}}
