"""Independent annual research windows for S0, S1 and S7.

Each year starts with fresh capital. Regimes are retrospective year-end labels,
never strategy-selection signals for that same year.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
from statistics import mean, median
from typing import Callable

import pandas as pd

from zero_market_lab.simulator.models import Instrument
from zero_market_lab.simulator.strategy_family import FamilyConfig, run_family
from zero_market_lab.tiger_v2.data import validate_ohlcv
from .engine import ResearchRunConfig
from .regime import REGIME_RULE_VERSION, classify_historical_window


CORE_STRATEGIES = ("S0_BUY_AND_HOLD", "S1_FIXED_TAKE_PROFIT", "S7_BREAKOUT_TREND_FOLLOWING")
YEARLY_ENGINE_VERSION = "yearly-independent-v1"
SUMMARY_FIELDS = ("initial_capital", "final_portfolio", "net_return", "gross_return_cost_addback",
                  "mdd", "completed_trades", "win_rate", "profit_factor",
                  "average_holding_days", "market_exposure_ratio", "total_trading_cost",
                  "total_buy_fee", "total_sell_fee", "total_tax", "total_slippage", "open_trades")


def run_yearly_research(universe: list[dict], load_frame: Callable[[str], tuple[pd.DataFrame, dict]],
                        config: ResearchRunConfig) -> dict:
    created = datetime.now(timezone.utc).isoformat()
    output = {"run_id": None, "created_at": created, "engine_version": YEARLY_ENGINE_VERSION,
              "regime_rule_version": REGIME_RULE_VERSION,
              "evaluation_date": config.evaluation_date.isoformat(),
              "strategy_config": {"S1_FIXED_TAKE_PROFIT": {
                  key: str(value) for key, value in asdict(config.s1).items()}},
              "fee_model_by_market": {
                  "KRX": {**{key: str(value) for key, value in asdict(config.krx_costs).items()},
                          "slippage_rate": str(config.krx_slippage_rate)},
                  "US": {**{key: str(value) for key, value in asdict(config.us_costs).items()},
                         "slippage_rate": str(config.us_slippage_rate)}},
              "assets": [], "years": [], "regime_summary": [],
              "warnings": ["연도마다 초기자금을 새로 시작하는 독립 실험입니다.",
                           "Regime은 해당 연도 마지막 관측일까지의 사후 분류이며 연초 투자 신호가 아닙니다."]}
    for entry in universe:
        symbol, market = entry["symbol"], entry["market"]
        asset = {"symbol": symbol, "name": entry["name"], "market": market,
                 "currency": entry.get("currency", "KRW" if market == "KRX" else "USD"),
                 "status": "SKIPPED"}
        output["assets"].append(asset)
        try:
            frame, provenance = load_frame(symbol)
            validate_ohlcv(frame, expected_first_date=pd.Timestamp(frame.iloc[0]["date"]).date())
            frame = frame.loc[pd.to_datetime(frame["date"]).dt.date <= config.evaluation_date].copy()
            frame["date"] = pd.to_datetime(frame["date"]).dt.date
            frame = frame.reset_index(drop=True)
            if len(frame) < 201:
                raise ValueError("INSUFFICIENT_DATA")
            if (config.evaluation_date - frame.date.iloc[-1]).days > config.max_data_lag_days:
                raise ValueError("STALE_DATA")
            data_hash = sha256(frame.to_csv(index=False).encode()).hexdigest()
            is_korea = market == "KRX"
            instrument = Instrument(market+":"+symbol, symbol, entry["name"],
                                    "KOREAN_EQUITY" if is_korea else "US_EQUITY",
                                    market, asset["currency"],
                                    entry.get("timezone", "Asia/Seoul" if is_korea else "America/New_York"),
                                    lot_size=Decimal(1),
                                    tick_size=Decimal(1) if is_korea else Decimal("0.01"),
                                    currency_precision=0 if is_korea else 2,
                                    data_source=provenance.get("provider"),
                                    adjusted_status=provenance.get("adjustment", "UNKNOWN"))
            family_config = FamilyConfig(
                initial_capital=config.initial_capital if is_korea else config.us_initial_capital,
                costs=config.krx_costs if is_korea else config.us_costs,
                stock_price_bands=is_korea, s1=config.s1,
                slippage_rate=config.krx_slippage_rate if is_korea else config.us_slippage_rate)
            asset.update(status="OK", source=provenance.get("provider"),
                         adjustment=provenance.get("adjustment", "UNKNOWN"),
                         data_hash=data_hash,
                         data_period=[frame.date.iloc[0].isoformat(), frame.date.iloc[-1].isoformat()])
            for year in range(2021, config.evaluation_date.year + 1):
                requested_start = date(year, 1, 1)
                requested_end = min(date(year, 12, 31), config.evaluation_date)
                indices = frame.index[(frame.date >= requested_start) & (frame.date <= requested_end)]
                if len(indices) == 0:
                    continue
                first, last = max(int(indices[0]), 100), int(indices[-1])
                if first > last:
                    output["years"].append({"symbol": symbol, "year": year,
                                            "status": "INSUFFICIENT_WARMUP"})
                    continue
                actual_start, actual_end = frame.date.iloc[first], frame.date.iloc[last]
                family = run_family(frame, instrument, actual_start, actual_end,
                                    family_config, isolate_errors=True,
                                    strategies=CORE_STRATEGIES)
                regime = classify_historical_window(frame, requested_start, actual_end)
                strategies = {}
                for strategy_id, item in family["results"].items():
                    metrics = item.get("metrics")
                    strategies[strategy_id] = ({key: metrics.get(key) for key in SUMMARY_FIELDS}
                                               if metrics is not None else None)
                baseline = strategies["S0_BUY_AND_HOLD"]
                no_position = all(metrics is not None and metrics["market_exposure_ratio"] == 0
                                  for metrics in strategies.values())
                excess = {strategy_id: (metrics["net_return"] - baseline["net_return"])
                          if metrics and baseline else None
                          for strategy_id, metrics in strategies.items() if strategy_id != "S0_BUY_AND_HOLD"}
                output["years"].append({
                    "symbol": symbol, "name": entry["name"], "market": market,
                    "currency": asset["currency"], "year": year,
                    "status": "NO_POSITION_CAPITAL" if no_position else "OK",
                    "capital_constraint": no_position,
                    "requested_period": [requested_start.isoformat(), requested_end.isoformat()],
                    "actual_period": [actual_start.isoformat(), actual_end.isoformat()],
                    "partial_start": first > int(indices[0]),
                    "partial_end": requested_end < date(year, 12, 31),
                    "warmup_observations": first,
                    "regime": regime, "strategies": strategies,
                    "excess_return_vs_s0": excess,
                    "data_hash": data_hash, "source": provenance.get("provider"),
                    "adjustment": provenance.get("adjustment", "UNKNOWN"),
                })
        except (FileNotFoundError, ValueError, KeyError, TypeError) as error:
            asset["status"] = "DATA_UNAVAILABLE" if isinstance(error, FileNotFoundError) else "SKIPPED"
            asset["reason"] = str(error) if str(error) in {"INSUFFICIENT_DATA", "STALE_DATA"} else type(error).__name__
        except Exception as error:
            asset.update(status="ERROR", reason=type(error).__name__)
    for label in ("BULL", "SIDEWAYS", "BEAR"):
        for strategy_id in CORE_STRATEGIES:
            members = [(record, record["strategies"][strategy_id]) for record in output["years"]
                       if record["status"] == "OK" and not record["partial_start"]
                       and not record["partial_end"] and record["regime"]["label"] == label
                       and record["strategies"].get(strategy_id)]
            if not members:
                continue
            returns = [metrics["net_return"] for _, metrics in members]
            excesses = [record["excess_return_vs_s0"].get(strategy_id) for record, _ in members
                        if strategy_id != "S0_BUY_AND_HOLD"]
            output["regime_summary"].append({
                "regime": label, "strategy_id": strategy_id, "sample_count": len(members),
                "mean_net_return": mean(returns), "median_net_return": median(returns),
                "positive_period_ratio": sum(value > 0 for value in returns) / len(returns),
                "mean_mdd": mean(metrics["mdd"] for _, metrics in members),
                "mean_completed_trades": mean(metrics["completed_trades"] for _, metrics in members),
                "mean_excess_vs_s0": mean(excesses) if excesses else None,
            })
    fingerprint = json.dumps({"date": output["evaluation_date"], "strategy": output["strategy_config"],
                              "fees": output["fee_model_by_market"],
                              "data": [(asset["symbol"], asset.get("data_hash")) for asset in output["assets"]],
                              "engine": YEARLY_ENGINE_VERSION, "regime": REGIME_RULE_VERSION}, sort_keys=True)
    output["run_id"] = created.replace(":", "").replace("-", "") + "-" + sha256(fingerprint.encode()).hexdigest()[:12]
    return output
