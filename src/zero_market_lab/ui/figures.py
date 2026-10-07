"""Plotly adapters for the Case #01 interactive research UI."""

import plotly.graph_objects as go

from .service import ComparisonOutput


TICK_FORMAT_STOPS = [
    {"dtickrange": [None, 86_400_000], "value": "%b %d"},
    {"dtickrange": [86_400_000, 2_678_400_000], "value": "%b %d"},
    {"dtickrange": [2_678_400_000, 31_536_000_000], "value": "%b\n%Y"},
    {"dtickrange": [31_536_000_000, None], "value": "%Y"},
]


def _research_layout(
    fig: go.Figure,
    title: str,
    y_title: str,
    uirevision: str,
) -> None:
    fig.update_layout(
        title=title,
        title_font={"size": 15},
        template="plotly_white",
        margin={"l": 58, "r": 18, "t": 48, "b": 38},
        hovermode="x unified",
        dragmode="pan",
        legend={"orientation": "h", "y": 1.02, "x": 0, "font": {"size": 11}},
        xaxis={
            "title": "Date",
            "type": "date",
            "tickformatstops": TICK_FORMAT_STOPS,
            "showspikes": True,
            "spikemode": "across",
            "spikesnap": "cursor",
            "spikethickness": 1,
            "tickfont": {"size": 10},
        },
        yaxis={
            "title": {"text": y_title, "font": {"size": 11}},
            "tickfont": {"size": 10},
            "fixedrange": False,
        },
        uirevision=uirevision,
    )


def market_figure(output: ComparisonOutput) -> go.Figure:
    fig = go.Figure(
        go.Scatter(
            x=output.market.date,
            y=output.market.close,
            mode="lines",
            name="S&P 500 Daily Close",
            line={"color": "#334155", "width": 2},
            hovertemplate="%{y:,.2f} index points<extra></extra>",
        )
    )
    _research_layout(
        fig,
        "Market — S&P 500 Price Index<br>"
        "<sup>FRED / S&P Dow Jones Indices · Daily Close · Dividend Excluded</sup>",
        "Index points",
        f"{output.config.start_date}:{output.config.end_date}",
    )
    fig.update_layout(height=220, showlegend=False)
    return fig


def portfolio_figure(output: ComparisonOutput) -> go.Figure:
    labels = {
        "A": "A — Buy & Hold",
        "B": f"B — +{output.config.take_profit_percent:g}% / Immediate",
        "C": (
            f"C — +{output.config.take_profit_percent:g}% / "
            f"{output.config.reentry_months}M Delay"
        ),
    }
    styles = {
        "A": {"color": "#315efb", "width": 5, "dash": "solid"},
        "B": {"color": "#ef553b", "width": 2, "dash": "dash"},
        "C": {"color": "#00a67e", "width": 2, "dash": "dot"},
    }
    fig = go.Figure()
    for code, result in output.results.items():
        states = result.daily_states
        gain = states.portfolio_value - states.total_contribution
        fig.add_trace(
            go.Scatter(
                x=states.date,
                y=states.portfolio_value,
                customdata=gain,
                mode="lines",
                name=labels[code],
                line=styles[code],
                hovertemplate="Value %{y:,.0f}<br>Gain %{customdata:,.0f}<extra></extra>",
            )
        )
    baseline = output.results["A"].daily_states
    fig.add_trace(
        go.Scatter(
            x=baseline.date,
            y=baseline.total_contribution,
            mode="lines",
            name="Total Contribution",
            line={"color": "#94a3b8", "width": 2, "dash": "longdash"},
            hovertemplate="%{y:,.0f}<extra></extra>",
        )
    )
    _research_layout(
        fig,
        "Portfolio — Strategy Comparison",
        "Simulation currency units",
        (
            f"{output.config.start_date}:{output.config.end_date}:"
            f"{output.config.monthly_contribution}:"
            f"{output.config.take_profit_percent}:{output.config.reentry_months}"
        ),
    )
    fig.update_layout(height=290, margin={"l": 58, "r": 18, "t": 54, "b": 38})
    return fig
