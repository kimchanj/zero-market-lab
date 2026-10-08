"""Run local Samsung strategy-family comparison on the latest ignored CSV."""

from __future__ import annotations

import argparse
from datetime import date, datetime
from decimal import Decimal
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from zero_market_lab.simulator.models import Instrument  # noqa: E402
from zero_market_lab.simulator.strategy_family import run_family  # noqa: E402


def latest_csv() -> Path:
    paths = sorted((ROOT / "data/processed/samsung_005930").glob("*/samsung_005930_ohlcv.csv"))
    if not paths:
        raise FileNotFoundError("Samsung local OHLCV missing; run scripts/fetch_samsung_005930.py")
    return paths[-1]


def build_report(as_of: date | None = None, source: Path | None = None) -> dict:
    as_of = as_of or datetime.now(ZoneInfo("Asia/Seoul")).date()
    start = (pd.Timestamp(as_of) - pd.DateOffset(months=6)).date()
    path = source or latest_csv()
    frame = pd.read_csv(path)
    instrument = Instrument(
        instrument_id="KRX:005930", symbol="005930", display_name="삼성전자",
        asset_class="KOREAN_EQUITY", market="KRX", currency="KRW",
        timezone="Asia/Seoul", lot_size=Decimal(1), tick_size=Decimal(100),
        fractional_allowed=False, currency_precision=0, data_source="Daum Finance secondary provider",
        adjusted_status="UNADJUSTED", distribution_handling="EXCLUDED",
    )
    report = run_family(frame, instrument, start, as_of)
    report["source"] = "Daum Finance secondary provider · unadjusted OHLCV · local cache"
    report["source_range"] = [frame.iloc[0]["date"], frame.iloc[-1]["date"]]
    report["scope"] = "Historical six-month sample; not a strategy recommendation"
    report["regimes"] = _regimes(report)
    return report


def _regimes(report: dict) -> list[dict]:
    first = next(iter(report["results"].values()))["ledger"]
    frame = pd.DataFrame(first)
    frame["month"] = frame["date"].str.slice(0, 7)
    regimes = []
    previous_return = 0.0
    for month, group in frame.groupby("month", sort=True):
        change = group.iloc[-1]["close"] / group.iloc[0]["close"] - 1
        volatility = group["close"].pct_change().std()
        if change <= -0.10: label = "급락"
        elif change >= 0.10: label = "급반등" if previous_return < -0.05 else "상승추세"
        elif volatility >= 0.05: label = "변동성 확대"
        elif volatility <= 0.02: label = "변동성 축소"
        else: label = "횡보"
        relative = {}
        for key, result in report["results"].items():
            rows = [row for row in result["ledger"] if row["date"].startswith(month)]
            if rows:
                relative[key] = rows[-1]["portfolio_value"] / rows[0]["portfolio_value"] - 1
        best = max(relative, key=relative.get) if relative else None
        worst = min(relative, key=relative.get) if relative else None
        regimes.append({"month": month, "label": label, "price_return": change,
                        "daily_volatility": None if pd.isna(volatility) else float(volatility),
                        "sample_best": best, "sample_worst": worst})
        previous_return = change
    return regimes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", type=date.fromisoformat)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/samsung_strategy_family/report.json")
    args = parser.parse_args()
    report = build_report(args.as_of)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "actual_period": report["actual_period"],
                      "warmup_observations": report["warmup_observations"],
                      "strategies": {key: value["metrics"]["net_return"] for key,value in report["results"].items()}},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
