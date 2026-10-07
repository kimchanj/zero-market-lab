"""Build the TIGER 360750 V2 chart payload from the latest validated dataset."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from zero_market_lab.tiger_v2.data import validate_ohlcv  # noqa: E402
from zero_market_lab.tiger_v2.payload import build_chart_payload  # noqa: E402


HERE = Path(__file__).resolve().parent
DATA_FILE = HERE / "tiger_data.js"
REPORT_FILE = HERE / "chart_report.json"


def _latest_provenance() -> tuple[dict, Path]:
    candidates = sorted(
        path
        for path in (ROOT / "data" / "provenance").glob("tiger_360750_*.json")
        if "crosscheck" not in path.name
    )
    if not candidates:
        raise FileNotFoundError("Run scripts/fetch_tiger_360750.py first")
    path = candidates[-1]
    return json.loads(path.read_text(encoding="utf-8")), path


def build() -> dict:
    provenance, provenance_path = _latest_provenance()
    frame = pd.read_csv(ROOT / provenance["processed_file"], parse_dates=["date"])
    report = validate_ohlcv(frame)
    distributions = pd.DataFrame(columns=["date", "distribution_per_share"])
    public_provenance = {
        key: provenance[key]
        for key in (
            "instrument",
            "symbol",
            "market",
            "currency",
            "source",
            "retrieval_time",
            "frequency",
            "adjusted_status",
            "distribution_handling",
            "actual_range",
            "row_count",
        )
    }
    payload = build_chart_payload(frame, distributions, public_provenance)
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    DATA_FILE.write_text(f"window.TIGER_V2_DATA={serialized};\n", encoding="utf-8")
    chart_report = {
        "instrument": payload["instrument"],
        "symbol": payload["symbol"],
        "rows": len(payload["candles"]),
        "volume_rows": len(payload["volume"]),
        "period": payload["period"],
        "first_bar": payload["candles"][0],
        "last_bar": payload["candles"][-1],
        "validation": report.to_dict(),
        "provenance_file": str(provenance_path.relative_to(ROOT)),
        "fake_ohlc": False,
        "fake_volume": False,
        "strategy_overlay": False,
    }
    REPORT_FILE.write_text(json.dumps(chart_report, ensure_ascii=False, indent=2), encoding="utf-8")
    return chart_report


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
