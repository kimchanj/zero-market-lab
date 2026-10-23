"""Render two local, self-contained STEP 9 research charts from a completed run."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--output", type=Path, default=Path("artifacts/step9-transit-market"))
    args = parser.parse_args()
    windows = pd.read_parquet(args.run_dir / "transit_market_windows.parquet")
    summary = pd.read_csv(args.run_dir / "gate_summary_64.csv")
    if len(summary) != 192 or set(summary["gate"]) != set(range(1, 65)):
        raise ValueError("Expected all 64 Gate summaries for all three study assets")
    args.output.mkdir(parents=True, exist_ok=True)

    colors = {"005930": "#3298dc", "000660": "#f5a623", "SP500": "#8e66d2"}
    gate32 = windows.loc[(windows["gate"] == 32) &
                         (windows["analysis_status"] == "COMPLETE")]
    figure = go.Figure()
    for asset in colors:
        rows = gate32.loc[gate32["asset"] == asset].sort_values("year")
        figure.add_bar(x=rows["year"].astype(str), y=rows["return_pct"],
                       name=asset, marker_color=colors[asset],
                       customdata=rows[["trading_days", "random_return_percentile",
                                        "pre_return_pct", "post_return_pct"]].to_numpy(),
                       hovertemplate=("%{x} · %{fullData.name}<br>Gate 32 return %{y:.2f}%"
                                      "<br>Observed bars %{customdata[0]}"
                                      "<br>Same-season random percentile %{customdata[1]:.1f}"
                                      "<br>Pre %{customdata[2]:.2f}% · Post %{customdata[3]:.2f}%"
                                      "<extra></extra>"))
    figure.update_layout(title=("Gate 32 — observed close-to-close returns by year"
                                "<br><sup>2026 unavailable in common local span · descriptive, not a trading signal</sup>"),
                         barmode="group", xaxis_title="Gate entry year",
                         yaxis_title="Observed return (%)", template="plotly_white",
                         margin={"t": 105})
    figure.write_html(args.output / "gate32_yearly_returns.html", include_plotlyjs=True)

    matrix = summary.pivot(index="asset", columns="gate", values="median_return").loc[list(colors)]
    count = summary.pivot(index="asset", columns="gate", values="count_windows").loc[list(colors)]
    status = summary.pivot(index="asset", columns="gate", values="research_status").loc[list(colors)]
    heat = go.Figure(go.Heatmap(x=matrix.columns, y=matrix.index, z=matrix.to_numpy(),
                                zmid=0, colorscale="RdBu", reversescale=True,
                                customdata=pd.concat({"count": count.stack(),
                                                      "status": status.stack()}, axis=1)
                                .reindex(pd.MultiIndex.from_product([matrix.index, matrix.columns]))
                                .to_numpy().reshape(3, 64, 2),
                                hovertemplate=("%{y} · Gate %{x}<br>Observed median return %{z:.2f}%"
                                               "<br>Complete years %{customdata[0]}"
                                               "<br>Exploratory status %{customdata[1]}<extra></extra>")))
    heat.update_layout(title=("All 64 Gates — observed median return, 2020–2026"
                              "<br><sup>Exploratory: 192 simultaneous comparisons; colors do not imply significance</sup>"),
                       xaxis_title="Gate", yaxis_title="Asset", template="plotly_white",
                       margin={"t": 105})
    heat.write_html(args.output / "all_64_gate_median_returns.html", include_plotlyjs=True)
    print(args.output.resolve())


if __name__ == "__main__":
    main()
