"""Dash Visual MVP for interactive Case #01 strategy comparison."""

from pathlib import Path

from dash import ALL, Dash, Input, Output, State, ctx, dcc, html, no_update
import pandas as pd

from .figures import market_figure, portfolio_figure
from .service import (
    Case01ComparisonConfig,
    ComparisonOutput,
    ParameterValidationError,
    dataset_bounds,
    load_latest_market,
    run_comparison,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
GRAPH_CONFIG = {
    "scrollZoom": True,
    "responsive": True,
    "displaylogo": False,
    "modeBarButtonsToRemove": ["lasso2d", "select2d"],
}
QUICK_RANGES = ("1W", "1M", "3M", "6M", "1Y", "3Y", "5Y", "ALL")


def quick_range_dates(
    period: str,
    data_start: pd.Timestamp,
    data_end: pd.Timestamp,
) -> tuple[str, str]:
    """Return a calendar range ending at the dataset's latest observation."""
    offsets = {
        "1W": pd.DateOffset(weeks=1),
        "1M": pd.DateOffset(months=1),
        "3M": pd.DateOffset(months=3),
        "6M": pd.DateOffset(months=6),
        "1Y": pd.DateOffset(years=1),
        "3Y": pd.DateOffset(years=3),
        "5Y": pd.DateOffset(years=5),
    }
    if period == "ALL":
        start = data_start
    elif period in offsets:
        start = max(data_start, data_end - offsets[period])
    else:
        raise ValueError(f"Unsupported quick range: {period}")
    return start.date().isoformat(), data_end.date().isoformat()


def transition_workspace(
    trigger: str | None,
    state: dict | None,
    search: str | None = None,
) -> dict:
    """Pure state transition for header/sidebar/research view controls."""
    current = {
        "header_collapsed": False,
        "sidebar_collapsed": False,
        "research_mode": False,
        **(state or {}),
    }
    if trigger in (None, "url"):
        if search and "research=1" in search:
            current.update(
                header_collapsed=True,
                sidebar_collapsed=True,
                research_mode=True,
            )
        return current
    if trigger == "research-toggle":
        enabled = not current["research_mode"]
        current.update(
            header_collapsed=enabled,
            sidebar_collapsed=enabled,
            research_mode=enabled,
        )
    elif trigger == "sidebar-toggle":
        current["sidebar_collapsed"] = not current["sidebar_collapsed"]
        current["research_mode"] = False
    elif trigger == "header-toggle":
        current["header_collapsed"] = not current["header_collapsed"]
        current["research_mode"] = False
    return current


def _format_number(value: float, decimals: int = 0) -> str:
    return f"{value:,.{decimals}f}"


def _strategy_cards(output: ComparisonOutput):
    labels = {
        "A": ("Buy & Hold", "Monthly contribution → hold"),
        "B": (
            "Immediate Reentry",
            f"+{output.config.take_profit_percent:g}% TP → same-close reentry",
        ),
        "C": (
            "Cash Wait Reentry",
            f"+{output.config.take_profit_percent:g}% TP → "
            f"{output.config.reentry_months}M wait → reentry",
        ),
    }
    cards = []
    for row in output.metrics:
        code = row["strategy"]
        name, rule = labels[code]
        cards.append(
            html.Div(
                [
                    html.Div(
                        [html.Strong(code), html.Span(name)],
                        className="strategy-card-title",
                    ),
                    html.P(rule, className="strategy-rule"),
                    html.Div(
                        [
                            html.Span(f"Final {_format_number(row['final_portfolio_value'])}"),
                            html.Span(
                                f"TP {row['take_profit_count']} · Sell {row['sell_count']} · "
                                f"Re {row['reentry_count']} · Wait {row['cash_waiting_days']}d"
                            ),
                        ],
                        className="strategy-card-stats",
                    ),
                ],
                className=f"strategy-card strategy-{code.lower()}",
            )
        )
    return cards


def metrics_panel(output: ComparisonOutput):
    labels = {"A": "A", "B": "B", "C": "C"}
    fields = [
        ("Final Portfolio", "final_portfolio_value", 0),
        ("Investment Gain", "investment_gain", 0),
        ("Delta vs A", "delta_vs_a", 0),
        ("Delta vs A (%)", "delta_vs_a_percent", 2),
        ("Total Contribution", "total_contribution", 0),
        ("Cash", "final_cash", 0),
        ("Final Quantity", "final_quantity", 3),
    ]
    by_strategy = {row["strategy"]: row for row in output.metrics}
    header = html.Thead(
        html.Tr([html.Th("Metric")] + [html.Th(labels[code]) for code in "ABC"])
    )
    body = html.Tbody(
        [
            html.Tr(
                [html.Th(label)]
                + [
                    html.Td(_format_number(by_strategy[code][key], decimals))
                    for code in "ABC"
                ]
            )
            for label, key, decimals in fields
        ]
    )
    overlap = (
        "A and B overlap by design under same-close, zero-cost assumptions."
        if output.insights["a_b_overlap"]
        else "A and B no longer overlap under the selected configuration."
    )
    return html.Div(
        [
            html.Div(overlap, className="overlap-note"),
            html.Div(_strategy_cards(output), className="strategy-card-grid"),
            html.Table([header, body], className="metrics-table"),
        ]
    )


def _assumptions():
    return html.Details(
        [
            html.Summary("Fixed assumptions"),
            html.P(
                "S&P500 Price Index · Dividend Excluded · FX OFF · Cost 0 · "
                "Slippage 0 · Same Close · Fractional Units Allowed"
            ),
        ],
        className="assumptions-details",
    )


def _quick_range_buttons():
    return html.Div(
        [
            html.Button(
                period,
                id={"type": "quick-range", "period": period},
                n_clicks=0,
                className="quick-button",
            )
            for period in QUICK_RANGES
        ],
        className="quick-ranges",
    )


def _layout(initial: ComparisonOutput, bounds: tuple[pd.Timestamp, pd.Timestamp]):
    data_start, data_end = bounds
    return html.Div(
        [
            dcc.Location(id="url", refresh=False),
            dcc.Store(
                id="workspace-state",
                data={
                    "header_collapsed": False,
                    "sidebar_collapsed": False,
                    "research_mode": False,
                },
            ),
            dcc.Store(id="resize-signal"),
            html.Header(
                [
                    html.Div(
                        [
                            html.Strong("ZERO MARKET LAB · CASE #01"),
                            html.Span("Interactive Strategy Comparison"),
                        ],
                        className="toolbar-brand",
                    ),
                    _quick_range_buttons(),
                    html.Div(
                        [
                            html.Button("☰ Parameters", id="sidebar-toggle", n_clicks=0),
                            html.Button("▲ Header", id="header-toggle", n_clicks=0),
                            html.Button("⛶ Research View", id="research-toggle", n_clicks=0),
                            html.Button("Reset", id="reset-view", n_clicks=0),
                        ],
                        className="toolbar-actions",
                    ),
                ],
                id="compact-header",
                className="compact-header",
            ),
            html.Main(
                [
                    html.Aside(
                        [
                            html.H2("Parameters"),
                            html.Label("Start Date"),
                            dcc.Input(
                                id="start-date",
                                type="date",
                                value=initial.config.start_date,
                                min=data_start.date().isoformat(),
                                max=data_end.date().isoformat(),
                            ),
                            html.Label("End Date"),
                            dcc.Input(
                                id="end-date",
                                type="date",
                                value=initial.config.end_date,
                                min=data_start.date().isoformat(),
                                max=data_end.date().isoformat(),
                            ),
                            html.Label("Monthly Contribution"),
                            dcc.Input(
                                id="monthly-contribution",
                                type="number",
                                value=initial.config.monthly_contribution,
                                min=0,
                                max=1_000_000_000,
                                step=10_000,
                            ),
                            html.Label("Take Profit (%)"),
                            dcc.Input(
                                id="take-profit-percent",
                                type="number",
                                value=initial.config.take_profit_percent,
                                min=0,
                                max=100,
                                step=0.5,
                            ),
                            html.Label("C Reentry (months)"),
                            dcc.Input(
                                id="reentry-months",
                                type="number",
                                value=initial.config.reentry_months,
                                min=1,
                                max=120,
                                step=1,
                            ),
                            html.Button(
                                "Run Backtest",
                                id="run-backtest",
                                n_clicks=0,
                                className="run-button",
                            ),
                            html.Div(id="validation-message", role="alert"),
                            _assumptions(),
                        ],
                        id="parameter-sidebar",
                        className="parameter-panel",
                    ),
                    html.Section(
                        [
                            html.Div(
                                dcc.Graph(
                                    id="market-chart",
                                    figure=market_figure(initial),
                                    config=GRAPH_CONFIG,
                                ),
                                className="chart-card market-card",
                            ),
                            html.Div(
                                dcc.Graph(
                                    id="portfolio-chart",
                                    figure=portfolio_figure(initial),
                                    config=GRAPH_CONFIG,
                                ),
                                className="chart-card portfolio-card",
                            ),
                            html.Div(
                                [
                                    html.H2("Strategy Results", className="metrics-title"),
                                    html.Div(metrics_panel(initial), id="metrics-panel"),
                                ],
                                className="metrics-card",
                            ),
                        ],
                        className="research-panel",
                    ),
                ],
                id="workspace-grid",
                className="workspace-grid",
            ),
        ],
        className="app-shell",
    )


def create_app(market_data: pd.DataFrame | None = None) -> Dash:
    market = (
        load_latest_market(PROJECT_ROOT)
        if market_data is None
        else market_data.loc[:, ["date", "close"]].copy()
    )
    data_start, data_end = dataset_bounds(market)
    initial_config = Case01ComparisonConfig(
        start_date=data_start.date().isoformat(),
        end_date=data_end.date().isoformat(),
    )
    initial = run_comparison(market, initial_config)

    app = Dash(
        __name__,
        title="ZERO MARKET LAB — Case #01",
        assets_folder=str(PROJECT_ROOT / "assets"),
    )
    app.layout = _layout(initial, (data_start, data_end))

    @app.callback(
        Output("start-date", "value"),
        Output("end-date", "value"),
        Output("market-chart", "figure"),
        Output("portfolio-chart", "figure"),
        Output("metrics-panel", "children"),
        Output("validation-message", "children"),
        Input("run-backtest", "n_clicks"),
        Input({"type": "quick-range", "period": ALL}, "n_clicks"),
        State("start-date", "value"),
        State("end-date", "value"),
        State("monthly-contribution", "value"),
        State("take-profit-percent", "value"),
        State("reentry-months", "value"),
        prevent_initial_call=True,
    )
    def execute_backtest(
        _run_clicks,
        _quick_clicks,
        start_date,
        end_date,
        contribution,
        take_profit,
        reentry_months,
    ):
        trigger = ctx.triggered_id
        if isinstance(trigger, dict) and trigger.get("type") == "quick-range":
            start_date, end_date = quick_range_dates(
                trigger["period"], data_start, data_end
            )
        config = Case01ComparisonConfig(
            start_date=start_date,
            end_date=end_date,
            monthly_contribution=contribution,
            take_profit_percent=take_profit,
            reentry_months=reentry_months,
        )
        try:
            output = run_comparison(market, config)
        except ParameterValidationError as exc:
            message = html.Ul([html.Li(item) for item in exc.messages])
            return start_date, end_date, no_update, no_update, no_update, message
        except (TypeError, ValueError):
            return (
                start_date,
                end_date,
                no_update,
                no_update,
                no_update,
                "입력값을 확인한 뒤 다시 실행하세요.",
            )
        return (
            start_date,
            end_date,
            market_figure(output),
            portfolio_figure(output),
            metrics_panel(output),
            "",
        )

    @app.callback(
        Output("workspace-state", "data"),
        Output("compact-header", "className"),
        Output("workspace-grid", "className"),
        Output("sidebar-toggle", "children"),
        Output("header-toggle", "children"),
        Output("research-toggle", "children"),
        Input("sidebar-toggle", "n_clicks"),
        Input("header-toggle", "n_clicks"),
        Input("research-toggle", "n_clicks"),
        Input("url", "search"),
        State("workspace-state", "data"),
    )
    def update_workspace(_sidebar, _header, _research, search, state):
        next_state = transition_workspace(ctx.triggered_id, state, search)
        header_class = "compact-header"
        if next_state["header_collapsed"]:
            header_class += " header-collapsed"
        workspace_class = "workspace-grid"
        if next_state["sidebar_collapsed"]:
            workspace_class += " sidebar-collapsed"
        if next_state["research_mode"]:
            workspace_class += " research-mode"
        sidebar_label = (
            "☰ Show Parameters"
            if next_state["sidebar_collapsed"]
            else "☰ Hide Parameters"
        )
        header_label = (
            "▼ Show Header"
            if next_state["header_collapsed"]
            else "▲ Hide Header"
        )
        research_label = (
            "Exit Research View"
            if next_state["research_mode"]
            else "⛶ Research View"
        )
        return (
            next_state,
            header_class,
            workspace_class,
            sidebar_label,
            header_label,
            research_label,
        )

    app.clientside_callback(
        """
        function(state) {
            window.setTimeout(function() {
                window.dispatchEvent(new Event("resize"));
            }, 120);
            return Date.now();
        }
        """,
        Output("resize-signal", "data"),
        Input("workspace-state", "data"),
    )

    app.clientside_callback(
        """
        function(marketRelayout, portfolioRelayout, resetClicks, marketFigure, portfolioFigure) {
            const noUpdate = window.dash_clientside.no_update;
            const trigger = window.dash_clientside.callback_context.triggered_id;
            if (!marketFigure || !portfolioFigure) {
                return [noUpdate, noUpdate];
            }
            const market = JSON.parse(JSON.stringify(marketFigure));
            const portfolio = JSON.parse(JSON.stringify(portfolioFigure));
            market.layout = market.layout || {};
            portfolio.layout = portfolio.layout || {};
            market.layout.xaxis = market.layout.xaxis || {};
            portfolio.layout.xaxis = portfolio.layout.xaxis || {};

            if (trigger === "reset-view") {
                delete market.layout.xaxis.range;
                delete portfolio.layout.xaxis.range;
                market.layout.xaxis.autorange = true;
                portfolio.layout.xaxis.autorange = true;
                return [market, portfolio];
            }

            const relayout = trigger === "market-chart" ? marketRelayout : portfolioRelayout;
            if (!relayout) {
                return [noUpdate, noUpdate];
            }
            if (relayout["xaxis.autorange"] === true) {
                delete market.layout.xaxis.range;
                delete portfolio.layout.xaxis.range;
                market.layout.xaxis.autorange = true;
                portfolio.layout.xaxis.autorange = true;
                return [market, portfolio];
            }
            const left = relayout["xaxis.range[0]"];
            const right = relayout["xaxis.range[1]"];
            if (left === undefined || right === undefined) {
                return [noUpdate, noUpdate];
            }
            market.layout.xaxis.range = [left, right];
            portfolio.layout.xaxis.range = [left, right];
            market.layout.xaxis.autorange = false;
            portfolio.layout.xaxis.autorange = false;
            return [market, portfolio];
        }
        """,
        Output("market-chart", "figure", allow_duplicate=True),
        Output("portfolio-chart", "figure", allow_duplicate=True),
        Input("market-chart", "relayoutData"),
        Input("portfolio-chart", "relayoutData"),
        Input("reset-view", "n_clicks"),
        State("market-chart", "figure"),
        State("portfolio-chart", "figure"),
        prevent_initial_call=True,
    )
    return app
