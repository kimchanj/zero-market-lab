"""Run a local historical discovery batch and export JSON/CSV matrix."""

from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from zero_market_lab.asset_discovery.catalog import LocalOHLCVCatalog, load_universe  # noqa: E402
from zero_market_lab.asset_discovery.engine import LOOKBACKS, ResearchRunConfig, run_discovery  # noqa: E402
from zero_market_lab.simulator.strategy_family import FixedTakeProfitConfig  # noqa: E402
from zero_market_lab.simulator.strategy_family import STRATEGIES  # noqa: E402
from zero_market_lab.simulator.strategy_family import (  # noqa: E402
    FamilyConfig, FixedStopConfig, _indicators, _run_one,
)
from zero_market_lab.simulator.models import Instrument  # noqa: E402
from zero_market_lab.tiger_v2.data import validate_ohlcv  # noqa: E402
from zero_market_lab.asset_discovery.yearly import run_yearly_research  # noqa: E402
from zero_market_lab.asset_discovery.rolling import run_s1_robustness  # noqa: E402


def build_report(*, as_of: date | None = None, lookback: str = "1Y", capital: Decimal = Decimal(500000),
                 us_capital: Decimal = Decimal(500), config: ResearchRunConfig | None = None) -> dict:
    as_of = as_of or datetime.now(ZoneInfo("Asia/Seoul")).date()
    universe = load_universe(ROOT / "config/universe_seed_kr_us.json")
    catalog = LocalOHLCVCatalog(ROOT)
    report = run_discovery(universe, catalog.load,
                           config or ResearchRunConfig(as_of, lookback, capital, us_capital))
    report["load_counts"] = catalog.read_count
    return report


def build_period_comparison(config: ResearchRunConfig, symbol: str, strategy_id: str) -> dict:
    """Compare independent calendar windows using one locally cached OHLCV frame."""
    if strategy_id not in STRATEGIES:
        raise ValueError("Unknown strategy")
    entries = [entry for entry in load_universe(ROOT / "config/universe_seed_kr_us.json")
               if entry["symbol"] == symbol]
    if len(entries) != 1:
        raise ValueError("Unknown asset")
    catalog = LocalOHLCVCatalog(ROOT)
    rows = []
    for period in LOOKBACKS:
        run = run_discovery(entries, catalog.load, replace(config, lookback=period))
        asset = run["assets"][0]
        cell = next((item for item in run["cells"] if item["strategy_id"] == strategy_id), None)
        control = next((item for item in run["cells"] if item["strategy_id"] == "S0_BUY_AND_HOLD"), None)
        rows.append({"period": period, "requested_period": run["requested_period"],
                     "actual_period": asset.get("actual_period"),
                     "status": cell["status"] if cell else asset["status"],
                     "reason": cell["reason"] if cell else asset.get("reason"),
                     "metrics": cell["metrics"] if cell else None,
                     "s0_metrics": control["metrics"] if control else None,
                     "difference_vs_s0": (cell["metrics"]["final_portfolio"] -
                                           control["metrics"]["final_portfolio"]
                                           if cell and cell["metrics"] and control and control["metrics"] else None),
                     "run_id": run["run_id"]})
    return {"symbol": symbol, "strategy_id": strategy_id,
            "strategy_config": {"entry_offset_pct": str(config.s1.entry_offset_pct),
                                "take_profit_pct": str(config.s1.take_profit_pct)},
            "periods": rows, "load_count": catalog.read_count.get(symbol, 0)}


def build_yearly_report(config: ResearchRunConfig) -> dict:
    catalog = LocalOHLCVCatalog(ROOT)
    report = run_yearly_research(load_universe(ROOT / "config/universe_seed_kr_us.json"),
                                 catalog.load, config)
    report["load_counts"] = catalog.read_count
    return report


def build_robustness_report(config: ResearchRunConfig, symbol: str | None = None) -> dict:
    universe = load_universe(ROOT / "config/universe_seed_kr_us.json")
    if symbol is not None:
        universe = [entry for entry in universe if entry["symbol"] == symbol]
        if len(universe) != 1:
            raise ValueError("Unknown asset")
    catalog = LocalOHLCVCatalog(ROOT)
    report = run_s1_robustness(universe, catalog.load, config)
    report["load_counts"] = catalog.read_count
    return report


def build_journal_report(config: ResearchRunConfig, symbol: str, strategy_id: str) -> dict:
    """One selected historical daily ledger under exactly the submitted config."""
    if strategy_id not in STRATEGIES:
        raise ValueError("Unknown strategy")
    entries = [entry for entry in load_universe(ROOT / "config/universe_seed_kr_us.json")
               if entry["symbol"] == symbol]
    if len(entries) != 1:
        raise ValueError("Unknown asset")
    catalog = LocalOHLCVCatalog(ROOT)
    run = run_discovery(entries, catalog.load, config, include_ledger_for=strategy_id)
    cell = next((item for item in run["cells"] if item["strategy_id"] == strategy_id), None)
    return {"symbol": symbol, "strategy_id": strategy_id,
            "status": cell["status"] if cell else run["assets"][0]["status"],
            "ledger": cell.get("ledger", []) if cell else [],
            "trades": cell.get("trades", []) if cell else [],
            "open_position": cell.get("open_position") if cell else None,
            "run_id": run["run_id"], "load_count": catalog.read_count.get(symbol, 0)}


def build_survival_comparison(config: ResearchRunConfig, symbol: str) -> dict:
    """Fixed, disclosed strategy matrix on one frame; never optimizes parameters."""
    entries = [item for item in load_universe(ROOT / "config/universe_seed_kr_us.json")
               if item["symbol"] == symbol]
    if len(entries) != 1 or config.lookback not in LOOKBACKS:
        raise ValueError("Unknown asset or period")
    entry = entries[0]
    catalog = LocalOHLCVCatalog(ROOT)
    frame, provenance = catalog.load(symbol)
    validate_ohlcv(frame, expected_first_date=pd.Timestamp(frame.iloc[0]["date"]).date())
    frame = frame.loc[pd.to_datetime(frame["date"]).dt.date <= config.evaluation_date].copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    frame = frame.reset_index(drop=True)
    start = (pd.Timestamp(config.evaluation_date)-pd.DateOffset(**LOOKBACKS[config.lookback])).date()
    first = int((frame.date < start).sum())
    last = len(frame)-1
    if first < 100 or last-first+1 < config.min_evaluation_rows:
        raise ValueError("INSUFFICIENT_DATA")
    is_kr = entry["market"] == "KRX"
    instrument = Instrument(entry["market"]+":"+symbol, symbol, entry["name"],
                            "KOREAN_EQUITY" if is_kr else "US_EQUITY",
                            entry["market"], entry.get("currency", "KRW" if is_kr else "USD"),
                            entry.get("timezone", "Asia/Seoul" if is_kr else "America/New_York"),
                            lot_size=Decimal(1), tick_size=Decimal(1) if is_kr else Decimal("0.01"),
                            currency_precision=0 if is_kr else 2)
    family = FamilyConfig(config.initial_capital if is_kr else config.us_initial_capital,
                          config.krx_costs if is_kr else config.us_costs, is_kr,
                          config.s1, config.s2,
                          config.krx_slippage_rate if is_kr else config.us_slippage_rate)
    data = _indicators(frame)
    variants = [("S0_BUY_AND_HOLD", None, None),
                ("S7_BREAKOUT_TREND_FOLLOWING", None, None)]
    for tp in (Decimal(3), Decimal(5)):
        for strategy in ("S1_FIXED_TAKE_PROFIT", "S1_TREND_FILTERED_TAKE_PROFIT"):
            variants.append((strategy, tp, None))
    for tp in (Decimal(3), Decimal(5)):
        for sl in (Decimal(5), Decimal(7), Decimal(10)):
            for strategy in ("S2_FIXED_TP_SL", "S2_TREND_FILTERED_TP_SL"):
                variants.append((strategy, tp, sl))
    rows = []
    for strategy, tp, sl in variants:
        if strategy in {"S1_TREND_FILTERED_TAKE_PROFIT", "S2_TREND_FILTERED_TP_SL"} and first < 205:
            rows.append({"strategy_id": strategy, "tp_pct": float(tp),
                         "sl_pct": float(sl) if sl is not None else None,
                         "status": "INSUFFICIENT_DATA", "metrics": None})
            continue
        configured = family
        if tp is not None and sl is None:
            configured = replace(family, s1=FixedTakeProfitConfig(config.s1.entry_offset_pct, tp))
        elif tp is not None:
            configured = replace(family, s2=FixedStopConfig(tp, sl))
        result = _run_one(data, instrument, first, last, configured, strategy)
        rows.append({"strategy_id": strategy, "tp_pct": float(tp) if tp is not None else None,
                     "sl_pct": float(sl) if sl is not None else None,
                     "status": "OK", "metrics": result["metrics"],
                     "open_position": result["open_position"],
                     "blocked_entries": result["blocked_entries"]})
    s0 = rows[0]["metrics"]["final_portfolio"]
    for row in rows:
        row["difference_vs_s0"] = (row["metrics"]["final_portfolio"]-s0
                                    if row.get("metrics") else None)
    return {"symbol": symbol, "name": entry["name"], "currency": instrument.currency,
            "actual_period": [frame.date.iloc[first].isoformat(), frame.date.iloc[last].isoformat()],
            "data_source": provenance.get("provider"), "rows": rows,
            "load_count": catalog.read_count.get(symbol, 0),
            "warnings": ["고정된 가설군 비교이며 최적 파라미터 선정이 아닙니다.",
                         "청산거래 기대값은 종료 시 미청산 손익을 포함하지 않습니다."]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", type=date.fromisoformat)
    parser.add_argument("--lookback", choices=("6M", "1Y", "2Y", "3Y", "4Y", "5Y"), default="1Y")
    parser.add_argument("--krw-capital", type=Decimal, default=Decimal(500000))
    parser.add_argument("--usd-capital", type=Decimal, default=Decimal(500))
    parser.add_argument("--s1-entry", type=Decimal, default=Decimal("-1"))
    parser.add_argument("--s1-tp", type=Decimal, default=Decimal("5"))
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/asset_discovery")
    args = parser.parse_args()
    report = build_report(config=ResearchRunConfig(
        args.as_of or datetime.now(ZoneInfo("Asia/Seoul")).date(), args.lookback,
        args.krw_capital, args.usd_capital,
        s1=FixedTakeProfitConfig(args.s1_entry, args.s1_tp)))
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "research_run.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = [{"symbol": cell["symbol"], "name": cell["name"], "market": cell["market"],
             "currency": cell["currency"], "strategy_id": cell["strategy_id"],
             "status": cell["status"], "reason": cell["reason"],
             **(cell["metrics"] or {}), "atr_pct": cell["profile"]["atr_pct"]}
            for cell in report["cells"]]
    pd.DataFrame(rows).to_csv(args.output / "matrix.csv", index=False)
    print(json.dumps({"run_id": report["run_id"], "assets_ok": sum(a["status"] == "OK" for a in report["assets"]),
                      "assets_skipped": sum(a["status"] != "OK" for a in report["assets"]),
                      "cells": len(report["cells"]), "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
