"""Run Strategy A on a local STEP 1 processed snapshot and create a verification chart."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd
import plotly.graph_objects as go

from zero_market_lab.backtest import run_monthly_buy_and_hold


def latest_dataset() -> Path:
    candidates = sorted((ROOT / "data" / "processed").glob("*/sp500_price_daily.parquet"))
    if not candidates:
        raise FileNotFoundError("No STEP 1 processed S&P500 dataset found")
    return candidates[-1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=None)
    parser.add_argument("--monthly-contribution", type=float, default=500_000.0)
    args = parser.parse_args()

    data_path = args.data or latest_dataset()
    market = pd.read_parquet(data_path)
    result = run_monthly_buy_and_hold(market, args.monthly_contribution)
    states, events = result.daily_states, result.events
    last = states.iloc[-1]
    summary = {
        "strategy": "Monthly Buy & Hold", "instrument": "S&P500 Price Index Benchmark",
        "currency_effect": "OFF", "transaction_cost": 0, "slippage": 0,
        "fractional_units": True, "data_path": str(data_path.resolve()),
        "start_date": states.date.min().date().isoformat(),
        "end_date": states.date.max().date().isoformat(), "market_rows": len(states),
        "contribution_count": int((events.event_type == "CONTRIBUTION").sum()),
        "buy_count": int((events.event_type == "BUY").sum()),
        "sell_count": int((events.event_type == "SELL").sum()),
        "total_contribution": float(last.total_contribution),
        "final_quantity": float(last.quantity),
        "final_average_purchase_price": float(last.average_purchase_price),
        "final_market_price": float(last.market_price),
        "final_position_value": float(last.position_value), "final_cash": float(last.cash),
        "final_portfolio_value": float(last.portfolio_value),
        "investment_gain": float(last.portfolio_value - last.total_contribution),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "limitations": ["Benchmark simulation; S&P500 index is not directly tradable",
                        "Price Return only; dividends and FX excluded",
                        "Same-close fractional execution; cost and slippage are zero",
                        "Investment gain is not CAGR or evidence of strategy superiority"],
    }

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = ROOT / "artifacts" / "step_02" / run_id
    output.mkdir(parents=True, exist_ok=False)
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    states.to_parquet(output / "daily_states.parquet", index=False)
    events.to_parquet(output / "events.parquet", index=False)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=states.date, y=states.portfolio_value,
                             name="Portfolio Value", mode="lines"))
    fig.add_trace(go.Scatter(x=states.date, y=states.total_contribution,
                             name="Total Contribution", mode="lines"))
    fig.update_layout(
        title="Monthly Buy & Hold — S&P500 Price Index Benchmark<br>"
              "<sup>FX OFF | Fractional Units | Transaction Cost 0 | Dividend Excluded</sup>",
        xaxis_title="Date", yaxis_title="Simulation currency units",
        template="plotly_white", hovermode="x unified", height=650,
    )
    chart = output / "portfolio_vs_contribution.html"
    fig.write_html(chart, include_plotlyjs=True)
    image = output / "portfolio_vs_contribution.png"
    fig.write_image(image, width=1600, height=900, scale=1)
    print(json.dumps(summary, indent=2))
    print(f"OUTPUT: {output}\nCHART: {chart}\nIMAGE: {image}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
