"""Build an explicitly synthetic, redistributable demo without reading market files."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime
from decimal import Decimal
import json
from math import cos, exp, sin
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zero_market_lab.simulator.models import CostConfig, Instrument  # noqa: E402
from zero_market_lab.simulator.service import run_simulation  # noqa: E402
from zero_market_lab.tiger_v2.payload import build_chart_payload  # noqa: E402

OUTPUT = ROOT / "experiments" / "public_demo"
START = date(2020, 8, 7)
DEMO_NAME = "가상 ETF 데모 · 합성 데이터"
DEMO_SYMBOL = "SYNTH-ETF"


def synthetic_rows(end: date) -> list[dict]:
    """Deterministic weekday-only OHLCV; no real security's prices are sampled."""
    if end < START:
        raise ValueError("Demo end precedes its first synthetic observation")
    rows = []
    previous_close = 12500
    for index, timestamp in enumerate(pd.bdate_range(START, end)):
        trend = 12500 + index * 5
        cycle = 520 * sin(index / 27) + 210 * sin(index / 7)
        shock = -1800 * exp(-((index - 380) / 35) ** 2)
        close = max(1000, round((trend + cycle + shock) / 5) * 5)
        open_price = max(1000, round((previous_close + 60 * sin(index * 1.37)) / 5) * 5)
        high = max(open_price, close) + 5 * (30 + index % 11)
        low_margin = 5 * (10 + index % 6) if index % 5 == 0 else 5 * (45 + index % 16)
        low = min(open_price, close) - low_margin
        rows.append({
            "date": timestamp.date().isoformat(), "open": open_price,
            "high": high, "low": low, "close": close,
            "volume": 100000 + (index * 7919) % 150000 + round(20000 * abs(cos(index / 19))),
        })
        previous_close = close
    return rows


def build(end: date | None = None, output: Path = OUTPUT) -> dict:
    end = end or datetime.now(ZoneInfo("Asia/Seoul")).date()
    rows = synthetic_rows(end)
    instrument = Instrument(
        instrument_id="DEMO:SYNTH-ETF", symbol=DEMO_SYMBOL, display_name=DEMO_NAME,
        asset_class="ETF_DEMO", market="SYNTHETIC", currency="KRW", timezone="Asia/Seoul",
        lot_size=Decimal("1"), tick_size=Decimal("5"), fractional_allowed=False,
        quantity_precision=0, currency_precision=0, trading_calendar="WEEKDAYS_ONLY",
        data_source="ZERO MARKET LAB deterministic generator", provider="ZML_SYNTHETIC",
        market_hours="09:00-15:30", distribution_handling="NOT_APPLICABLE",
    )
    costs = CostConfig(buy_fee_rate=Decimal("0.00015"), sell_fee_rate=Decimal("0.00015"),
                       sell_tax_rate=Decimal("0"), label="SYNTHETIC_RESEARCH_ASSUMPTION")
    provenance = {
        "source": "ZERO MARKET LAB deterministic synthetic generator",
        "data_mode": "PUBLIC_DEMO", "synthetic": True,
        "calendar": "weekdays only; no exchange holidays",
        "generated_through": rows[-1]["date"],
    }
    meta = asdict(instrument)
    meta["lot_size"], meta["tick_size"] = str(instrument.lot_size), str(instrument.tick_size)
    cost_meta = {key: str(value) if isinstance(value, Decimal) else value
                 for key, value in asdict(costs).items()}
    bundle = {
        "simulation": {
            "instrument": meta, "costs": cost_meta, "provenance": provenance,
            "fee_disclaimer": "가상 ETF·합성 시세 · 매수/매도 수수료 각 0.015%, 세금 0% 가정",
        },
        "market": rows,
    }
    simulation = run_simulation(bundle, {
        "start": f"{end.year}-01-01", "end": end.isoformat(),
        "initial_capital": "500000", "entry_percent": "1",
        "take_profit_percent": "5", "minimum_net_percent": "1",
    })
    chart = build_chart_payload(
        pd.DataFrame(rows), pd.DataFrame(columns=["date", "distribution_per_share"]), provenance,
        instrument=DEMO_NAME, symbol=DEMO_SYMBOL, currency="KRW",
    )
    output.mkdir(parents=True, exist_ok=True)
    (output / "research_input.json").write_text(
        json.dumps({**bundle, "simulation": simulation}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    for filename, global_name, payload in (
        ("tiger_data.js", "TIGER_V2_DATA", chart),
        ("simulation_data.js", "TIGER_SIMULATION_DATA", simulation),
    ):
        (output / filename).write_text(
            f"window.{global_name}=" + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n",
            encoding="utf-8",
        )
    return {"mode": "PUBLIC_DEMO", "synthetic": True, "bars": len(rows),
            "period": chart["period"], "output": str(output)}


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False))
