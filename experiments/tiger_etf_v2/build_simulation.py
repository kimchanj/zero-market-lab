"""Run the generic explainable simulator on actual TIGER 360750 daily bars."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from zero_market_lab.simulator import (  # noqa: E402
    CostConfig,
    ExecutionConfig,
    FrameOHLCVProvider,
    Instrument,
    StrategyParameters,
    required_exit_price,
    simulate,
)


HERE = Path(__file__).resolve().parent
DATA_FILE = HERE / "simulation_data.js"
REPORT_FILE = HERE / "simulation_report.json"
ARTIFACT_DIR = ROOT / "artifacts" / "tiger_etf_v2_explainable" / "prototype_20230104_20230404"
# Fixed demonstrative window: contains one closed lifecycle and one open position.
# It was not selected for maximum return; 2024-08~11 produced a higher result.
START = date(2023, 1, 4)
END = date(2023, 4, 4)
INITIAL_CAPITAL = Decimal("500000")


def _latest_market() -> tuple[pd.DataFrame, dict]:
    candidates = sorted(
        path
        for path in (ROOT / "data" / "provenance").glob("tiger_360750_*.json")
        if "crosscheck" not in path.name
    )
    if not candidates:
        raise FileNotFoundError("Run scripts/fetch_tiger_360750.py first")
    provenance = json.loads(candidates[-1].read_text(encoding="utf-8"))
    return pd.read_csv(ROOT / provenance["processed_file"]), provenance


def build() -> dict:
    frame, provenance = _latest_market()
    instrument = Instrument(
        instrument_id="KRX:360750", symbol="360750", display_name="TIGER 미국S&P500",
        asset_class="ETF", market="KRX", currency="KRW", timezone="Asia/Seoul",
        lot_size=Decimal("1"), tick_size=Decimal("5"), fractional_allowed=False,
        quantity_precision=0, currency_precision=0, trading_calendar="KRX",
        data_source=provenance["source_url"], provider=provenance["source"],
        adjusted_status="UNADJUSTED", distribution_handling="EXCLUDED",
        market_hours="09:00-15:30", news_keywords=("S&P500", "US stocks", "USD/KRW"),
        related_indices=("S&P500",), related_macro_topics=("Federal Reserve", "FOMC", "CPI", "US economy"),
    )
    strategy = StrategyParameters(
        strategy_id="OPEN_MINUS_1_TP_5", entry_offset_rate=Decimal("0.01"),
        take_profit_rate=Decimal("0.05"),
    )
    execution = ExecutionConfig(
        gap_fill_policy="LIMIT_PRICE", same_bar_policy="CONSERVATIVE_HOLD",
        reentry_policy="NEXT_BAR",
    )
    costs = CostConfig(
        buy_fee_rate=Decimal("0.00015"), sell_fee_rate=Decimal("0.00015"),
        sell_tax_rate=Decimal("0"),
        label="RESEARCH_ASSUMPTION_0.015_PERCENT_EACH_SIDE_TAX_ZERO",
    )
    bars = FrameOHLCVProvider(frame).load_ohlcv(instrument, START, END)
    result = simulate(
        instrument=instrument, bars=bars, initial_capital=INITIAL_CAPITAL,
        strategy=strategy, execution=execution, costs=costs,
    )
    payload = result.to_dict()
    for row in payload["ledger"]:
        row["target_gap"] = None if row["take_profit_price"] is None else row["take_profit_price"] - row["close"]
        row["target_gap_rate"] = None if row["take_profit_price"] is None else row["take_profit_price"] / row["close"] - 1
    payload["provenance"] = provenance
    payload["scope"] = {
        "requested_period": [START.isoformat(), END.isoformat()],
        "actual_period": [result.summary.start_date.isoformat(), result.summary.end_date.isoformat()],
        "initial_capital": float(INITIAL_CAPITAL),
        "fee_disclaimer": "매수·매도 각 0.015%, 매도세 0%의 연구용 가정이며 증권사 실비 검증값이 아닙니다.",
        "parameter_search": False,
    }
    markers = []
    average_cost = []
    target_line = []
    for row in result.ledger:
        item = row.to_dict()
        if row.position_qty_after > 0 and row.avg_entry_price_after is not None:
            average_cost.append({"time": row.date.isoformat(), "value": float(row.avg_entry_price_after)})
            target_line.append({"time": row.date.isoformat(), "value": float(row.take_profit_price)})
        else:
            average_cost.append({"time": row.date.isoformat()})
            target_line.append({"time": row.date.isoformat()})
        if row.action in {"BUY", "SELL"}:
            markers.append({
                "time": row.date.isoformat(), "action": row.action,
                "tradeId": row.trade_id, "price": float(row.execution_price),
                "quantity": float(row.execution_qty), "fee": float(row.total_cost),
                "cashAfter": float(row.cash_after), "netProfit": float(row.net_profit),
                "netReturn": None if row.net_return is None else float(row.net_return),
                "holdingDays": row.trading_holding_days, "explanation": row.explanation,
                "grossProfit": float(row.gross_profit), "tax": float(row.tax),
            })
    payload["chart"] = {
        "markers": markers, "averageCost": average_cost, "takeProfit": target_line,
    }
    open_trade = next((trade for trade in result.trades if trade.status == "OPEN"), None)
    if open_trade:
        payload["open_position"] = {
            **open_trade.to_dict(),
            "current_close": float(result.ledger[-1].close),
            "current_value": float(result.ledger[-1].position_value),
            "target_price": float(result.ledger[-1].take_profit_price),
            "target_gap": float(result.ledger[-1].take_profit_price - result.ledger[-1].close),
            "target_gap_rate": float(
                result.ledger[-1].take_profit_price / result.ledger[-1].close - Decimal("1")
            ),
        }
    else:
        payload["open_position"] = None
    if result.trades:
        first = result.trades[0]
        payload["required_exit_for_net_1_percent"] = float(required_exit_price(
            entry_price=first.entry_price, quantity=first.entry_qty, buy_fee=first.entry_fee,
            minimum_net_return=Decimal("0.01"), instrument=instrument, costs=costs,
        ))
    DATA_FILE.write_text(
        "window.TIGER_SIMULATION_DATA="
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n",
        encoding="utf-8",
    )
    report = {
        "instrument": instrument.instrument_id,
        "period": payload["scope"]["actual_period"],
        "ledger_rows": len(result.ledger),
        "decision_records": sum(len(row.decisions) for row in result.ledger),
        "trade_count": len(result.trades),
        "marker_count": len(markers),
        "summary": result.summary.to_dict(),
        "open_position": payload["open_position"],
        "required_exit_for_net_1_percent": payload.get("required_exit_for_net_1_percent"),
        "source_of_truth": "zero_market_lab.simulator.simulate",
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([row.to_dict() for row in result.ledger]).drop(columns=["decisions"]).to_csv(
        ARTIFACT_DIR / "daily_ledger.csv", index=False, encoding="utf-8-sig"
    )
    pd.DataFrame([trade.to_dict() for trade in result.trades]).to_csv(
        ARTIFACT_DIR / "trade_summary.csv", index=False, encoding="utf-8-sig"
    )
    (ARTIFACT_DIR / "decision_records.json").write_text(
        json.dumps(
            [decision.to_dict() for row in result.ledger for decision in row.decisions],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    report["artifacts"] = [
        str(ARTIFACT_DIR / "daily_ledger.csv"),
        str(ARTIFACT_DIR / "trade_summary.csv"),
        str(ARTIFACT_DIR / "decision_records.json"),
        str(ARTIFACT_DIR / "period_summary.json"),
    ]
    REPORT_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (HERE / "research_input.json").write_text(json.dumps({
        "simulation": payload,
        "market": frame[["date", "open", "high", "low", "close", "volume"]].to_dict("records"),
    }, ensure_ascii=False), encoding="utf-8")
    (ARTIFACT_DIR / "period_summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
