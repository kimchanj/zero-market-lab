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
from zero_market_lab.simulator.execution import ConfigurableFeeModel, affordable_quantity, required_buy_cash
from zero_market_lab.simulator import strategy_family, entry_filter
from zero_market_lab.simulator.strategy_family import FamilyConfig, FixedTakeProfitConfig, FixedStopConfig, STRATEGIES, run_family
from .behavior import analyze_behavior
from .instrument_policy import ISA_SOURCE, ISA_FOREIGN_SOURCE, current_cost_reference


ENGINE_VERSION = "asset-discovery-v2-entry-filter"
LOOKBACKS = {"6M": {"months": 6}, "1Y": {"years": 1},
             "2Y": {"years": 2}, "3Y": {"years": 3},
             "4Y": {"years": 4}, "5Y": {"years": 5}}


@dataclass(frozen=True)
class ResearchRunConfig:
    evaluation_date: date
    lookback: str = "1Y"
    initial_capital: Decimal = Decimal(500000)
    us_initial_capital: Decimal = Decimal(500)
    universe_id: str = "kr_us_seed"
    min_evaluation_rows: int = 60
    max_data_lag_days: int = 10
    s1: FixedTakeProfitConfig = FixedTakeProfitConfig()
    s2: FixedStopConfig = FixedStopConfig()
    krx_costs: CostConfig = CostConfig(buy_fee_rate=Decimal("0.00015"),
                                       sell_fee_rate=Decimal("0.00015"), sell_tax_rate=Decimal(0))
    us_costs: CostConfig = CostConfig(buy_fee_rate=Decimal("0.00015"),
                                      sell_fee_rate=Decimal("0.00015"), sell_tax_rate=Decimal(0))
    krx_slippage_rate: Decimal = Decimal(0)
    us_slippage_rate: Decimal = Decimal(0)


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
                  config: ResearchRunConfig, *, include_ledger_for: str | None = None) -> dict:
    if config.lookback not in LOOKBACKS or config.initial_capital <= 0 or config.us_initial_capital <= 0:
        raise ValueError("Invalid lookback or capital")
    start = (pd.Timestamp(config.evaluation_date) - pd.DateOffset(**LOOKBACKS[config.lookback])).date()
    created = datetime.now(timezone.utc).isoformat()
    fee_models = {
        "KRX": {**{key: str(value) for key, value in asdict(config.krx_costs).items()},
                "slippage_rate": str(config.krx_slippage_rate)},
        "US": {**{key: str(value) for key, value in asdict(config.us_costs).items()},
               "slippage_rate": str(config.us_slippage_rate)},
    }
    if any(not rate.is_finite() or not 0 <= rate <= Decimal("0.05") for rate in (
        config.krx_costs.buy_fee_rate, config.krx_costs.sell_fee_rate,
        config.krx_costs.sell_tax_rate, config.us_costs.buy_fee_rate,
        config.us_costs.sell_fee_rate, config.us_costs.sell_tax_rate,
        config.krx_slippage_rate, config.us_slippage_rate)):
        raise ValueError("Invalid research cost rate")
    s1_config = {key: str(value) for key, value in asdict(config.s1).items()}
    s2_config = {key: str(value) for key, value in asdict(config.s2).items()}
    source_hash = sha256((inspect.getsource(strategy_family) +
                          inspect.getsource(entry_filter)).encode()).hexdigest()
    strategy_hash = sha256(json.dumps({"source": source_hash, "s1": s1_config, "s2": s2_config},
                                      sort_keys=True).encode()).hexdigest()
    run = {"run_id": None, "created_at": created, "engine_version": ENGINE_VERSION,
           "evaluation_date": config.evaluation_date.isoformat(), "lookback": config.lookback,
           "requested_period": [start.isoformat(), config.evaluation_date.isoformat()],
           "initial_capital": float(config.initial_capital),
           "initial_capital_by_market": {"KRX": float(config.initial_capital), "US": float(config.us_initial_capital)},
           "universe": config.universe_id,
           "strategy_versions": {name: "v1" for name in STRATEGIES},
           "strategy_config_hash": strategy_hash,
           "strategy_config": {"S1_FIXED_TAKE_PROFIT": s1_config,
                               "S1_TREND_FILTERED_TAKE_PROFIT": s1_config,
                               "S2_FIXED_TP_SL": s2_config,
                               "S2_TREND_FILTERED_TP_SL": s2_config},
           "fee_model": fee_models["KRX"], "fee_model_by_market": fee_models,
           "fee_model_version": "research-v2",
           "assets": [], "cells": [], "warnings": [
               "과거 가격데이터 기반 연구결과이며 미래 수익을 보장하지 않습니다.",
               "현재 Universe는 수동 선정이므로 생존자 편향이 있을 수 있습니다."]}
    for entry in universe:
        symbol = entry["symbol"]
        asset = {"symbol": symbol, "name": entry["name"], "market": entry["market"],
                 "currency": entry.get("currency", "KRW" if entry["market"] == "KRX" else "USD"),
                 "instrument_type": entry.get("instrument_type", "KRX_STOCK" if entry["market"] == "KRX" else "US_STOCK"),
                 "group": entry.get("group", "SEED"),
                 "isa_eligible": entry.get("isa_eligible", entry["market"] == "KRX"),
                 "isa_reason": entry.get("isa_reason", "국내 상장주식" if entry["market"] == "KRX"
                                         else "해외 상장주식은 중개형 ISA 직접매수 불가"),
                 "isa_source": ISA_SOURCE if entry["market"] == "KRX" else ISA_FOREIGN_SOURCE,
                 "exchange_segment": entry.get("exchange_segment"),
                 "status": "SKIPPED", "reason": None}
        reference = current_cost_reference(asset["instrument_type"], asset["exchange_segment"])
        asset["cost_profile_reference"] = reference.as_dict() if reference else None
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
                costs=config.krx_costs if is_korea else config.us_costs,
                stock_price_bands=is_korea, s1=config.s1, s2=config.s2,
                slippage_rate=config.krx_slippage_rate if is_korea else config.us_slippage_rate)
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
            current_price = Decimal(str(frame.iloc[-1]["close"]))
            fee = ConfigurableFeeModel(family_config.costs, instrument.currency_precision)
            current_qty = affordable_quantity(family_config.initial_capital, current_price,
                                               instrument.lot_size, fee, family_config.slippage_rate)
            asset["affordability"] = {
                "current_price": float(current_price),
                "price_date": frame.iloc[-1]["date"].isoformat(),
                "available_cash": float(family_config.initial_capital),
                "max_affordable_qty": int(current_qty),
                "required_cash_for_one_share": float(required_buy_cash(
                    instrument.lot_size, current_price, fee, family_config.slippage_rate)),
                "affordability_status": "AFFORDABLE" if current_qty else "NOT_AFFORDABLE"}
            data_hash = sha256(frame.to_csv(index=False).encode()).hexdigest()
            period_support = {}
            for period, offset in LOOKBACKS.items():
                period_start = (pd.Timestamp(config.evaluation_date) - pd.DateOffset(**offset)).date()
                period_support[period] = (int((frame.date < period_start).sum()) >= 100 and
                                          int((frame.date >= period_start).sum()) >= config.min_evaluation_rows)
            asset.update(status="OK", reason=None, profile=profile,
                         actual_period=result["actual_period"],
                         warmup_observations=result["warmup_observations"], data_quality={
                             "provider": provenance.get("provider", "UNKNOWN"),
                             "adjustment": provenance.get("adjustment", "UNKNOWN"),
                             "source_url": provenance.get("source_url"),
                             "retrieved_at": provenance.get("retrieved_at"),
                             "data_start": frame.date.iloc[0].isoformat(),
                             "data_end": frame.date.iloc[-1].isoformat(), "row_count": len(frame),
                             "available_years": round((frame.date.iloc[-1] - frame.date.iloc[0]).days / 365.2425, 2),
                             "period_support": period_support,
                             "missing_days": None, "missing_days_note": "Exchange calendar reconciliation pending",
                             "sha256": data_hash})
            for strategy_id, item in result["results"].items():
                metrics = item.get("metrics")
                no_buy_due_to_capital = bool(metrics and not metrics["completed_trades"] and
                    not metrics["open_trades"] and item.get("affordability_events"))
                run["cells"].append({"symbol": symbol, "name": entry["name"],
                                     "market": entry["market"], "currency": asset["currency"],
                                     "strategy_id": strategy_id,
                                     "strategy_config": (s1_config if strategy_id in {
                                         "S1_FIXED_TAKE_PROFIT", "S1_TREND_FILTERED_TAKE_PROFIT"}
                                         else s2_config if strategy_id in {
                                         "S2_FIXED_TP_SL", "S2_TREND_FILTERED_TP_SL"} else {}),
                                     "status": "NOT_AFFORDABLE" if no_buy_due_to_capital else item.get("status", "OK"),
                                     "reason": "NO_SHARE_AFFORDABLE_AT_ENTRY" if no_buy_due_to_capital else item.get("reason"),
                                     "metrics": metrics, "profile": profile,
                                     "trades": item.get("trades", []),
                                     **({"ledger": item.get("ledger", [])}
                                        if strategy_id == include_ledger_for else {}),
                                     "open_position": item.get("open_position"),
                                     "affordability_events": item.get("affordability_events", []),
                                     "blocked_entries": item.get("blocked_entries", []),
                                     "last_entry_filter_allowed": item.get("last_entry_filter_allowed"),
                                     "affordability": asset["affordability"]})
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
                                           "fee_model": run["fee_model_by_market"]},
                              "universe_entries": universe,
                              "data": [(item["symbol"], item.get("data_quality", {}).get("sha256"))
                                       for item in run["assets"]]}, sort_keys=True)
    run["input_hash"] = sha256(fingerprint.encode()).hexdigest()
    run["run_id"] = created.replace(":", "").replace("-", "") + "-" + run["input_hash"][:12]
    return run
