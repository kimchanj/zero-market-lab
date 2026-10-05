"""Run Case #01 A/B/C on one STEP 1 dataset and create verification artifacts."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd
import plotly.graph_objects as go

from zero_market_lab.backtest import run_case01_comparison


def latest_dataset() -> Path:
    candidates = sorted((ROOT / "data" / "processed").glob("*/sp500_price_daily.parquet"))
    if not candidates:
        raise FileNotFoundError("No STEP 1 processed S&P500 dataset found")
    return candidates[-1]


def summarize(result) -> dict:
    states, events = result.daily_states, result.events
    final = states.iloc[-1]
    event_count = lambda event: int((events.event_type == event).sum())
    return {
        "strategy_name": result.metadata["strategy_name"],
        "final_portfolio_value": float(final.portfolio_value),
        "total_contribution": float(final.total_contribution),
        "investment_gain": float(final.portfolio_value - final.total_contribution),
        "final_cash": float(final.cash),
        "final_quantity": float(final.quantity),
        "final_average_purchase_price": (
            None
            if pd.isna(final.average_purchase_price)
            else float(final.average_purchase_price)
        ),
        "buy_count": event_count("BUY") + event_count("REENTRY"),
        "sell_count": event_count("SELL"),
        "take_profit_count": event_count("TAKE_PROFIT"),
        "reentry_count": event_count("REENTRY"),
        "cash_waiting_days": result.metadata["cash_waiting_days"],
        "final_strategy_state": result.metadata["final_strategy_state"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=None)
    parser.add_argument("--monthly-contribution", type=float, default=500_000.0)
    args = parser.parse_args()
    data_path = args.data or latest_dataset()
    market = pd.read_parquet(data_path)
    results = run_case01_comparison(market, args.monthly_contribution)

    for column in ("portfolio_value", "quantity", "cash"):
        pd.testing.assert_series_equal(
            results["A"].daily_states[column].reset_index(drop=True),
            results["B"].daily_states[column].reset_index(drop=True),
            check_names=False,
            rtol=1e-12,
            atol=1e-9,
            obj=f"Strategy A/B {column}",
        )

    summary = {
        "case": "Case #01 A/B/C Comparison",
        "data_path": str(data_path.resolve()),
        "period": [
            market.date.min().date().isoformat(),
            market.date.max().date().isoformat(),
        ],
        "market_rows": len(market),
        "monthly_contribution": args.monthly_contribution,
        "assumptions": {
            "instrument": "S&P500 Price Index Benchmark",
            "currency_effect": "OFF",
            "transaction_cost": 0,
            "slippage": 0,
            "fractional_units": True,
            "execution": "SAME_CLOSE",
            "dividend": "EXCLUDED",
            "cash_waiting_days": (
                "calendar days; open wait counted through final observation"
            ),
        },
        "strategies": {code: summarize(result) for code, result in results.items()},
        "verification": {
            "strategy_a_b_daily_value_quantity_cash_equal": True,
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = ROOT / "artifacts" / "step_04" / run_id
    output.mkdir(parents=True, exist_ok=False)
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    fig = go.Figure()
    line_styles = {
        "A": {"width": 5, "dash": "solid"},
        "B": {"width": 2, "dash": "dash"},
        "C": {"width": 2, "dash": "dot"},
    }
    for code, result in results.items():
        result.daily_states.to_parquet(
            output / f"strategy_{code}_states.parquet", index=False
        )
        result.events.to_parquet(
            output / f"strategy_{code}_events.parquet", index=False
        )
        fig.add_trace(
            go.Scatter(
                x=result.daily_states.date,
                y=result.daily_states.portfolio_value,
                mode="lines",
                name=f"Strategy {code}",
                line=line_styles[code],
            )
        )
    fig.update_layout(
        title="Case #01 — Strategy A / B / C Portfolio Value<br>"
        "<sup>S&P500 Price Index | Same Close | FX OFF | Cost 0 | "
        "Dividend Excluded</sup>",
        xaxis_title="Date",
        yaxis_title="Simulation currency units",
        template="plotly_white",
        hovermode="x unified",
        height=650,
    )
    html = output / "strategy_comparison.html"
    image = output / "strategy_comparison.png"
    fig.write_html(html, include_plotlyjs=True)
    fig.write_image(image, width=1600, height=900, scale=1)
    print(json.dumps(summary, indent=2))
    print(f"OUTPUT: {output}\nCHART: {html}\nIMAGE: {image}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
