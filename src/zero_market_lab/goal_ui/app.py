"""Compact Korean Dash UI for investment experiments."""

from pathlib import Path
import logging
from time import perf_counter

from dash import ALL, Dash, Input, Output, ctx, dcc, html, no_update
import pandas as pd
import plotly.graph_objects as go

from zero_market_lab.ui.service import load_latest_market

from .figures import unified_research_figure
from .service import (
    GoalParameterError,
    GoalSimulationConfig,
    GoalSimulationOutput,
    STRATEGIES,
    run_goal_simulation,
)
from .viewport import (
    apply_visible_viewport,
    quick_view_range,
    x_range_from_relayout,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
LOGGER = logging.getLogger(__name__)
GRAPH_CONFIG = {
    "scrollZoom": True,
    "responsive": True,
    "displaylogo": False,
    "modeBarButtonsToRemove": [
        "lasso2d", "select2d", "zoomIn2d", "zoomOut2d",
        "autoScale2d", "resetScale2d",
    ],
}
QUICK_RANGES = ("1W", "1M", "3M", "6M", "1Y", "3Y", "ALL")
LAYER_OPTIONS = [
    {"label": "S&P500", "value": "market"},
    {"label": "A 장기보유", "value": "A"},
    {"label": "B 즉시 재진입", "value": "B"},
    {"label": "C 대기 후 재진입", "value": "C"},
    {"label": "목표금액", "value": "target"},
    {"label": "C 거래 표시", "value": "events"},
]
DEFAULT_LAYERS = ["market", "A", "B", "C", "target"]


def _money(value: float) -> str:
    return f"{value:,.0f}"


def quick_start_date(period: str, data_start: pd.Timestamp, data_end: pd.Timestamp) -> str:
    offsets = {
        "1W": pd.DateOffset(weeks=1),
        "1M": pd.DateOffset(months=1),
        "3M": pd.DateOffset(months=3),
        "6M": pd.DateOffset(months=6),
        "1Y": pd.DateOffset(years=1),
        "3Y": pd.DateOffset(years=3),
    }
    if period == "ALL":
        value = data_start
    elif period in offsets:
        value = max(data_start, data_end - offsets[period])
    else:
        raise ValueError(f"Unsupported quick range: {period}")
    return value.date().isoformat()


def pension_preset_values() -> tuple[float, float, int, float, int]:
    """Representative simulation inputs; this does not imply a real KRW account result."""
    return 0.0, 500_000.0, 10, 5.0, 1


def build_config(
    start: str,
    initial_amount: float,
    monthly: float,
    years: int,
    take_profit: float,
    reentry: int,
    goal_values: list[str] | None,
    target: float,
) -> GoalSimulationConfig:
    """Map UI state to the service contract without hidden transformations."""
    return GoalSimulationConfig(
        start_date=start,
        initial_investment=initial_amount,
        monthly_contribution=monthly,
        max_years=years,
        take_profit_percent=take_profit,
        reentry_months=reentry,
        goal_enabled="enabled" in (goal_values or []),
        target_return_percent=target,
    )


def apply_layer_visibility(stored_figure: dict, layers: list[str] | None) -> go.Figure:
    """Change trace visibility only; this function never runs a backtest."""
    figure = go.Figure(stored_figure)
    enabled = set(layers or [])
    for trace in figure.data:
        trace.visible = trace.meta in enabled
    return figure


def _overview(output: GoalSimulationOutput):
    a = output.evaluations["A"]
    fields = [
        ("실제 시작일", output.actual_start.date().isoformat()),
        ("총 납입금", _money(a.total_contribution)),
        ("A 최종 평가금액", _money(a.final_portfolio_value)),
        ("A 투자손익", f"{a.investment_gain:+,.0f}"),
    ]
    if output.goal_active:
        goal = output.analyses["A"]
        fields.extend([
            ("목표금액", _money(goal.target_value)),
            ("A 목표 달성일", goal.goal_date.date().isoformat() if goal.goal_date else "—"),
        ])
    return [html.Span([html.Small(label), html.Strong(value)]) for label, value in fields]


def _strategy_summary(output: GoalSimulationOutput):
    rows = []
    take_profit = float(output.config.take_profit_percent)
    reentry = int(float(output.config.reentry_months))
    titles = {
        "A": "A — 장기보유",
        "B": f"B — +{take_profit:g}% 즉시 재진입",
        "C": f"C — +{take_profit:g}% / {reentry}개월 대기",
    }
    for code in "ABC":
        item = output.evaluations[code]
        rows.append(html.Article([
            html.Div([
                html.Strong(titles[code]),
                html.B("기준전략" if code == "A" else f"A 대비 {item.delta_vs_a:+,.0f} ({item.delta_percent_vs_a:+.2%})"),
            ], className="strategy-card-head"),
            html.Div([
                html.Span([html.Small("총 납입금"), html.B(_money(item.total_contribution))]),
                html.Span([html.Small("최종 평가금액"), html.B(_money(item.final_portfolio_value))]),
                html.Span([html.Small("투자손익"), html.B(f"{item.investment_gain:+,.0f}")]),
                html.Span([html.Small("최대 하락폭"), html.B(f"{item.max_drawdown:.1%}")]),
                html.Span([html.Small("익절 / 매도 / 재진입"), html.B(
                    f"{item.take_profit_count} / {item.sell_count} / {item.reentry_count}회"
                )]),
                html.Span([html.Small("현금 대기 / 시장 참여"), html.B(
                    f"{item.cash_waiting_days:,}일 / {item.time_in_market:.1%}"
                )]),
            ], className="strategy-card-metrics"),
            html.P(item.verdict),
        ], className=f"goal-strategy-card strategy-{code.lower()}"))
    return rows


def _quick_buttons():
    return html.Div([
        html.Button(
            period,
            id={"type": "goal-quick-range", "period": period},
            n_clicks=0,
            title="시뮬레이션은 유지하고 차트 표시 범위만 변경",
        )
        for period in QUICK_RANGES
    ], className="goal-quick-ranges")


def _number_input(input_id: str, value: float, width: int, **kwargs):
    # Dash number inputs can transiently publish None while a user replaces a value.
    # Text keeps the exact visible value; the service owns numeric/range validation.
    kwargs.pop("min", None)
    kwargs.pop("max", None)
    kwargs.pop("step", None)
    return dcc.Input(
        id=input_id, type="text", value=str(value), inputMode="decimal",
        style={"width": f"{width}px", "minWidth": f"{width}px"}, **kwargs,
    )


def _layout(initial: GoalSimulationOutput, bounds: tuple[pd.Timestamp, pd.Timestamp]):
    data_start, data_end = bounds
    chart = unified_research_figure(initial)
    return html.Div([
        dcc.Store(id="goal-chart-store", data=chart.to_dict()),
        dcc.Store(id="goal-view-range", data=None),
        dcc.Store(id="goal-run-request", data=None),
        dcc.Store(id="goal-data-bounds", data={
            "start": data_start.date().isoformat(), "end": data_end.date().isoformat(),
        }),
        html.Header([
            html.Strong("ZERO MARKET LAB"),
            html.Span("투자 전략 비교 실험"),
            html.Small("A/B/C 단일 시작일 비교 · STEP 5 Research Prototype"),
        ], className="goal-header"),
        html.Main([
            html.Section([
                html.Div([
                    html.Strong("투자 조건"),
                    html.Label([html.Span("시작일"), dcc.Input(
                        id="goal-start", type="date", value=initial.config.start_date,
                        min=data_start.date().isoformat(), max=data_end.date().isoformat(),
                        style={"width": "128px", "minWidth": "128px"})]),
                    _quick_buttons(),
                    html.Label([html.Span("초기 투자금"), _number_input(
                        "goal-initial", initial.config.initial_investment, 116, min=0, step=100000)]),
                    html.Label([html.Span("매월 투자금"), _number_input(
                        "goal-monthly", initial.config.monthly_contribution, 110, min=0, step=100000)]),
                    html.Label([html.Span("투자 기간"), _number_input(
                        "goal-years", initial.config.max_years, 58, min=1, max=50, step=1), html.Em("년")]),
                ], className="condition-group investment-conditions"),
                html.Div([
                    html.Strong("전략 조건"),
                    html.Label([html.Span("익절 기준"), _number_input(
                        "goal-take-profit", initial.config.take_profit_percent, 62, min=0.1, step=1), html.Em("%")]),
                    html.Label([html.Span("재진입 대기"), _number_input(
                        "goal-reentry", initial.config.reentry_months, 58, min=1, max=120, step=1), html.Em("개월")]),
                ], className="condition-group strategy-conditions"),
                html.Button("월 50만원 적립", id="goal-pension-preset", n_clicks=0,
                            title="초기 0 · 매월 500,000 · 10년 · 익절 5% · 재진입 1개월"),
                html.Button("시뮬레이션 실행", id="goal-run", n_clicks=0),
            ], className="goal-toolbar"),
            html.Details([
                html.Summary("목표 기반 분석 (선택)"),
                html.Div([
                    dcc.Checklist(
                        id="goal-enabled",
                        options=[{"label": "목표 기반 분석 사용", "value": "enabled"}],
                        value=[], inline=True,
                    ),
                    html.Label([html.Span("목표 수익률"), _number_input(
                        "goal-target", initial.config.target_return_percent, 68, min=0.1, step=1), html.Em("%")]),
                    html.Small("초기 투자금만 있는 경우에만 목표선을 계산합니다."),
                ])
            ], className="goal-options"),
            html.Div(id="goal-error", className="goal-error"),
            html.Div([html.P(message) for message in initial.warnings], id="goal-warning", className="goal-warning"),
            html.Section(_overview(initial), id="goal-overview", className="goal-overview"),
            html.Section([
                html.Div([
                    html.Strong("표시"),
                    dcc.Checklist(id="goal-layers", options=LAYER_OPTIONS, value=DEFAULT_LAYERS, inline=True),
                    html.Button("Reset View", id="goal-reset-view", n_clicks=0),
                ], className="goal-layer-controls"),
                html.P(
                    "연구 질문: 익절 후 어떤 재진입 규칙이 장기보유보다 높은 최종가치 또는 낮은 위험을 반복적으로 만들었는가?",
                    className="goal-overlap-note",
                ),
                html.Div([
                    html.Span("A", title="매수 후 계속 시장에 투자하는 기준전략입니다."),
                    html.Span("B", title="익절 후 같은 날 같은 가격으로 재매수하는 노출 통제전략입니다."),
                    html.Span("C", title="익절 후 설정한 개월 수만큼 현금으로 기다린 뒤 재진입합니다."),
                ], className="goal-strategy-help"),
                dcc.Graph(id="goal-unified-chart", figure=chart, config=GRAPH_CONFIG),
            ], className="goal-chart-shell"),
            html.Section(_strategy_summary(initial), id="goal-strategy-summary", className="goal-strategy-summary"),
            html.P(
                "S&P500 Price Index · 배당 제외 · FX OFF · 비용/슬리피지 0 · Same Close · "
                "Fractional Units · 금액 단위: simulation currency · 실제 원화 계좌 결과가 아님",
                className="goal-assumptions",
            ),
        ], className="goal-main"),
    ], className="goal-shell")


def create_goal_app(market_data: pd.DataFrame | None = None) -> Dash:
    market = market_data.copy() if market_data is not None else load_latest_market(PROJECT_ROOT)
    dates = pd.to_datetime(market["date"])
    bounds = (dates.min().normalize(), dates.max().normalize())
    default_start = max(bounds[0], pd.Timestamp("2020-01-02"))
    initial_config = GoalSimulationConfig(
        start_date=default_start.date().isoformat(), goal_enabled=False,
    )
    initial = run_goal_simulation(market, initial_config)
    app = Dash(
        __name__, assets_folder=str(PROJECT_ROOT / "assets"),
        title="ZERO MARKET LAB · 투자 전략 비교",
    )
    app.layout = _layout(initial, bounds)

    app.clientside_callback(
        """
        function(nClicks) {
            if (!nClicks) {
                return window.dash_clientside.no_update;
            }
            const value = id => document.getElementById(id).value;
            const goalToggle = document.querySelector('#goal-enabled input[type="checkbox"]');
            return {
                nonce: nClicks,
                start: value('goal-start'),
                initial_amount: value('goal-initial'),
                monthly: value('goal-monthly'),
                years: value('goal-years'),
                take_profit: value('goal-take-profit'),
                reentry: value('goal-reentry'),
                goal_values: goalToggle && goalToggle.checked ? ['enabled'] : [],
                target: value('goal-target')
            };
        }
        """,
        Output("goal-run-request", "data"),
        Input("goal-run", "n_clicks"),
        prevent_initial_call=True,
    )

    @app.callback(
        Output("goal-view-range", "data"),
        Input("goal-unified-chart", "relayoutData"),
        Input({"type": "goal-quick-range", "period": ALL}, "n_clicks"),
        Input("goal-reset-view", "n_clicks"),
        Input("goal-chart-store", "data"),
        prevent_initial_call=True,
    )
    def update_view_range(relayout, _clicks, _reset_clicks, stored_figure):
        started = perf_counter()
        triggered = ctx.triggered_id
        if isinstance(triggered, str) and triggered in {
            "goal-chart-store", "goal-reset-view"
        }:
            LOGGER.debug("viewport reset trigger=%s elapsed_ms=%.2f", triggered, (perf_counter() - started) * 1000)
            return None
        if isinstance(triggered, dict):
            selected = list(quick_view_range(triggered["period"], stored_figure))
            LOGGER.debug(
                "quick range period=%s range=%s elapsed_ms=%.2f",
                triggered["period"], selected, (perf_counter() - started) * 1000,
            )
            return selected
        if triggered == "goal-unified-chart":
            if relayout and relayout.get("xaxis.autorange") is True:
                return None
            if relayout and any(key.startswith("xaxis.range") for key in relayout):
                selected = x_range_from_relayout(relayout, stored_figure)
                LOGGER.debug(
                    "plotly relayout range=%s elapsed_ms=%.2f",
                    selected, (perf_counter() - started) * 1000,
                )
                return list(selected) if selected else None
        return no_update

    @app.callback(
        Output("goal-initial", "value"),
        Output("goal-monthly", "value"),
        Output("goal-years", "value"),
        Output("goal-take-profit", "value"),
        Output("goal-reentry", "value"),
        Input("goal-pension-preset", "n_clicks"),
        prevent_initial_call=True,
    )
    def select_pension_preset(_clicks):
        return pension_preset_values()

    @app.callback(
        Output("goal-error", "children"),
        Output("goal-warning", "children"),
        Output("goal-overview", "children"),
        Output("goal-strategy-summary", "children"),
        Output("goal-chart-store", "data"),
        Input("goal-run-request", "data"),
        prevent_initial_call=True,
    )
    def execute(request):
        if not request:
            return (no_update,) * 5
        started = perf_counter()
        try:
            config = build_config(
                request["start"], request["initial_amount"], request["monthly"],
                request["years"], request["take_profit"], request["reentry"],
                request["goal_values"], request["target"],
            )
            LOGGER.debug("run click config=%s", config)
            output = run_goal_simulation(market, config)
        except (GoalParameterError, TypeError, ValueError) as error:
            return str(error), [], no_update, no_update, no_update
        LOGGER.debug(
            "simulation complete requested_start=%s actual_start=%s elapsed_ms=%.2f",
            config.start_date, output.actual_start.date(), (perf_counter() - started) * 1000,
        )
        return (
            "", [html.P(message) for message in output.warnings],
            _overview(output), _strategy_summary(output),
            unified_research_figure(output).to_dict(),
        )

    @app.callback(
        Output("goal-unified-chart", "figure"),
        Input("goal-layers", "value"),
        Input("goal-chart-store", "data"),
        Input("goal-view-range", "data"),
    )
    def apply_layers(layers, stored_figure, view_range):
        return apply_visible_viewport(stored_figure, layers or [], view_range)

    return app
