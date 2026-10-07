"""Build the isolated Lightweight Charts spike from existing Case #01 results."""

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from zero_market_lab.ui.service import (  # noqa: E402
    Case01ComparisonConfig,
    dataset_bounds,
    load_latest_market,
    run_comparison,
)


HERE = Path(__file__).resolve().parent
DATA_FILE = HERE / "prototype_data.js"
REPORT_FILE = HERE / "prototype_report.json"
EVENT_TYPES = {"BUY", "TAKE_PROFIT", "SELL", "REENTRY"}


def _series(frame, column: str) -> list[dict]:
    return [
        {"time": row.date.strftime("%Y-%m-%d"), "value": float(getattr(row, column))}
        for row in frame.itertuples(index=False)
    ]


def build_payload() -> dict:
    market = load_latest_market(ROOT)
    start, end = dataset_bounds(market)
    config = Case01ComparisonConfig(
        start_date=start.date().isoformat(),
        end_date=end.date().isoformat(),
    )
    started = perf_counter()
    output = run_comparison(market, config)
    backend_ms = (perf_counter() - started) * 1_000

    c_events = output.results["C"].events
    c_events = c_events[c_events.event_type.isin(EVENT_TYPES)]
    events = [
        {
            "time": row.date.strftime("%Y-%m-%d"),
            "type": row.event_type,
            "price": float(row.price),
            "quantity": float(row.quantity),
        }
        for row in c_events.itertuples(index=False)
    ]
    control = output.results["A"].daily_states
    payload = {
        "libraryVersion": "5.2.1",
        "instrument": "S&P500 Price Index",
        "period": [config.start_date, config.end_date],
        "market": _series(output.market.rename(columns={"close": "value"}), "value"),
        "portfolios": {
            code: _series(result.daily_states, "portfolio_value")
            for code, result in output.results.items()
        },
        "contribution": _series(control, "total_contribution"),
        "strategyCEvents": events,
        "metrics": output.metrics,
        "benchmarkInvariant": output.insights["a_b_overlap"],
        "backendExecutionMs": backend_ms,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "dataSemantics": {
            "price": "Daily close; dividends excluded",
            "volume": None,
            "ohlc": None,
        },
    }
    return payload


def write_prototype(payload: dict) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    DATA_FILE.write_text(f"window.PROTOTYPE_DATA={serialized};\n", encoding="utf-8")
    report = {
        "library_version": payload["libraryVersion"],
        "market_rows": len(payload["market"]),
        "portfolio_rows": {
            code: len(rows) for code, rows in payload["portfolios"].items()
        },
        "strategy_c_event_count": len(payload["strategyCEvents"]),
        "strategy_c_event_types": sorted(
            {event["type"] for event in payload["strategyCEvents"]}
        ),
        "backend_execution_ms": payload["backendExecutionMs"],
        "fake_volume": False,
        "fake_ohlc": False,
    }
    REPORT_FILE.write_text(json.dumps(report, indent=2), encoding="utf-8")


def main() -> int:
    payload = build_payload()
    write_prototype(payload)
    print(REPORT_FILE.read_text(encoding="utf-8"))
    print(f"PROTOTYPE: {HERE / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
