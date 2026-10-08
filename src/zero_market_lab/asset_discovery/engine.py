"""Batch historical research over a configured universe.

No orders are placed. Each asset is loaded once; one bad asset or strategy cell
cannot erase the remaining research run.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from hashlib import sha256
import inspect
import json
from typing import Callable

import pandas as pd

from zero_market_lab.simulator.models import CostConfig, Instrument
from zero_market_lab.simulator import strategy_family
from zero_market_lab.simulator.strategy_family import FamilyConfig, STRATEGIES, run_family
from .behavior import analyze_behavior


ENGINE_VERSION = "asset-discovery-v1"
LOOKBACKS = {"6M": {"months": 6}, "1Y": {"years": 1},
             "3Y": {"years": 3}, "5Y": {"years": 5}}


@dataclass(frozen=True)
class ResearchRunConfig:
    evaluation_date: date
    lookback: str = "1Y"
    initial_capital: Decimal = Decimal(500000)
    us_initial_capital: Decimal = Decimal(500)
    universe_id: str = "kr_us_seed"
    min_evaluation_rows: int = 60
    max_data_lag_days: int = 10


def filter_cells(run: dict, *, strategy_id: str, minimum_trades: int = 0,
                 market: str | None = None,
                 maximum_drawdown: float | None = None,
                 minimum_profit_factor: float | None = None,
                 minimum_liquidity: float = 0,
                 sort_by: str = "net_return", descending: bool = True) -> list[dict]:
    """Filter/sort a strategy slice; undefined profit factor fails a PF filter."""
    fields = {"net_return", "mdd", "profit_factor", "completed_trades", "win_rate",
              "average_holding_days", "market_exposure_ratio", "atr_pct"}
    if strategy_id not in STRATEGIES or sort_by not in fields or market not in {None, "KRX", "US"}:
        raise ValueError("Unknown strategy or sort field")
    if minimum_trades < 0 or minimum_liquidity < 0:
        raise ValueError("Filters must be nonnegative")
    selected = []
    for cell in run["cells"]:
        if (cell["strategy_id"] != strategy_id or cell["status"] != "OK" or
            (market is not None and cell["market"] != market)):
            continue
        metrics = cell["metrics"]
        if metrics["completed_trades"] < minimum_trades:
            continue
        if maximum_drawdown is not None and metrics["mdd"] < maximum_drawdown:
            continue
        if minimum_profit_factor is not None and (metrics["profit_factor"] is None or
                                                  metrics["profit_factor"] < minimum_profit_factor):
            continue
        if cell["profile"]["average_trading_value"] < minimum_liquidity:
            continue
        selected.append(cell)
    def key(cell: dict):
        value = cell["profile"]["atr_pct"] if sort_by == "atr_pct" else cell["metrics"][sort_by]
        return (cell["market"], value is None, -(value or 0) if descending else (value or 0), cell["symbol"])
    return sorted(selected, key=key)


def run_discovery(universe: list[dict], load_frame: Callable[[str], tuple[pd.DataFrame, dict]],
                  config: ResearchRunConfig) -> dict:
    if config.lookback not in LOOKBACKS or config.initial_capital <= 0 or config.us_initial_capital <= 0:
        raise ValueError("Invalid lookback or capital")
    start = (pd.Timestamp(config.evaluation_date) - pd.DateOffset(**LOOKBACKS[config.lookback])).date()
    created = datetime.now(timezone.utc).isoformat()
    research_costs = CostConfig(buy_fee_rate=Decimal("0.00015"),
                                sell_fee_rate=Decimal("0.00015"), sell_tax_rate=Decimal(0),
                                label="MARKET_RESEARCH_ASSUMPTION")
    run = {"run_id": None, "created_at": created, "engine_version": ENGINE_VERSION,
           "evaluation_date": config.evaluation_date.isoformat(), "lookback": config.lookback,
           "requested_period": [start.isoformat(), config.evaluation_date.isoformat()],
           "initial_capital": float(config.initial_capital),
           "initial_capital_by_market": {"KRX": float(config.initial_capital), "US": float(config.us_initial_capital)},
           "universe": config.universe_id,
           "strategy_versions": {name: "v1" for name in STRATEGIES},
           "strategy_config_hash": sha256(inspect.getsource(strategy_family).encode()).hexdigest(),
           "fee_model": asdict(research_costs), "fee_model_version": "research-v1",
           "assets": [], "cells": [], "warnings": [
               "과거 가격데이터 기반 연구결과이며 미래 수익을 보장하지 않습니다.",
               "현재 Universe는 수동 선정이므로 생존자 편향이 있을 수 있습니다."]}
    run["fee_model"] = {key: str(value) for key, value in run["fee_model"].items()}
    for entry in universe:
        symbol = entry["symbol"]
        asset = {"symbol": symbol, "name": entry["name"], "market": entry["market"],
                 "currency": entry.get("currency", "KRW" if entry["market"] == "KRX" else "USD"),
                 "status": "SKIPPED", "reason": None}
        run["assets"].append(asset)
        try:
            frame, provenance = load_frame(symbol)
            frame = frame.copy()
            frame["date"] = pd.to_datetime(frame["date"]).dt.date
            frame = frame.loc[frame.date <= config.evaluation_date].sort_values("date").reset_index(drop=True)
            if frame.empty:
                raise ValueError("INSUFFICIENT_DATA")
            first_eval = int((frame.date < start).sum())
            eval_count = int(((frame.date >= start) & (frame.date <= config.evaluation_date)).sum())
            if first_eval < 100 or eval_count < config.min_evaluation_rows:
                raise ValueError("INSUFFICIENT_DATA")
            if (config.evaluation_date - frame.date.iloc[-1]).days > config.max_data_lag_days:
                raise ValueError("STALE_DATA")
            profile = analyze_behavior(frame, as_of=config.evaluation_date, start=start,
                                       symbol=symbol, name=entry["name"], market=entry["market"])
            is_korea = entry["market"] == "KRX"
            family_config = FamilyConfig(
                initial_capital=config.initial_capital if is_korea else config.us_initial_capital,
                costs=research_costs,
                stock_price_bands=is_korea)
            instrument = Instrument(entry["market"]+":"+symbol, symbol, entry["name"],
                                    "KOREAN_EQUITY" if is_korea else "US_EQUITY",
                                    entry["market"], asset["currency"],
                                    entry.get("timezone", "Asia/Seoul" if is_korea else "America/New_York"),
                                    lot_size=Decimal(1), tick_size=Decimal(1) if is_korea else Decimal("0.01"),
                                    currency_precision=0 if is_korea else 2,
                                    data_source=provenance.get("provider"),
                                    adjusted_status=provenance.get("adjustment", "UNKNOWN"))
            result = run_family(frame, instrument, start, config.evaluation_date,
                                family_config, isolate_errors=True)
            data_hash = sha256(frame.to_csv(index=False).encode()).hexdigest()
            asset.update(status="OK", reason=None, profile=profile,
                         actual_period=result["actual_period"], data_quality={
                             "provider": provenance.get("provider", "UNKNOWN"),
                             "adjustment": provenance.get("adjustment", "UNKNOWN"),
                             "source_url": provenance.get("source_url"),
                             "retrieved_at": provenance.get("retrieved_at"),
                             "data_start": frame.date.iloc[0].isoformat(),
                             "data_end": frame.date.iloc[-1].isoformat(), "row_count": len(frame),
                             "missing_days": None, "missing_days_note": "Exchange calendar reconciliation pending",
                             "sha256": data_hash})
            for strategy_id, item in result["results"].items():
                run["cells"].append({"symbol": symbol, "name": entry["name"],
                                     "market": entry["market"], "currency": asset["currency"],
                                     "strategy_id": strategy_id,
                                     "status": item.get("status", "OK"),
                                     "reason": item.get("reason"),
                                     "metrics": item.get("metrics"), "profile": profile})
        except (FileNotFoundError, ValueError, KeyError, TypeError) as error:
            asset["status"] = "DATA_UNAVAILABLE" if isinstance(error, FileNotFoundError) else "SKIPPED"
            asset["expected_import_file"] = (f"data/processed/{'korea_' if entry['market']=='KRX' else 'us_'}{symbol}/<snapshot>/ohlcv.csv"
                                             if isinstance(error, FileNotFoundError) else None)
            asset["reason"] = ("DATA_NOT_AVAILABLE" if isinstance(error, FileNotFoundError)
                               else str(error) if str(error) in {"INSUFFICIENT_DATA", "STALE_DATA"}
                               else type(error).__name__)
        except Exception as error:
            asset.update(status="ERROR", reason=type(error).__name__)
    fingerprint = json.dumps({"config": {"date": config.evaluation_date.isoformat(),
                                           "lookback": config.lookback, "capital": str(config.initial_capital),
                                           "us_capital": str(config.us_initial_capital),
                                           "universe": config.universe_id,
                                           "strategy_hash": run["strategy_config_hash"],
                                           "fee_model": run["fee_model"]},
                              "universe_entries": universe,
                              "data": [(item["symbol"], item.get("data_quality", {}).get("sha256"))
                                       for item in run["assets"]]}, sort_keys=True)
    run["input_hash"] = sha256(fingerprint.encode()).hexdigest()
    run["run_id"] = created.replace(":", "").replace("-", "") + "-" + run["input_hash"][:12]
    return run
