"""Unified Plotly research chart for the Goal Simulation Prototype."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from .service import GoalSimulationOutput, korean_date


TICK_STOPS = [
    {"dtickrange": [None, 86_400_000 * 120], "value": "%m-%d"},
    {"dtickrange": [86_400_000 * 120, 86_400_000 * 730], "value": "%Y-%m"},
    {"dtickrange": [86_400_000 * 730, None], "value": "%Y"},
]

STRATEGY_STYLE = {
    "A": {"color": "#1f5a89", "dash": "solid", "width": 2.3},
    "B": {"color": "#e28b27", "dash": "dash", "width": 1.8},
    "C": {"color": "#0b8f72", "dash": "solid", "width": 2.4},
}
STRATEGY_LABEL = {
    "A": "A 장기보유",
    "B": "B 즉시 재진입",
    "C": "C 한 달 대기",
}


def _event_text(output: GoalSimulationOutput, code: str) -> dict[pd.Timestamp, str]:
    names = {
        "INITIAL_CONTRIBUTION": "초기 투자금 입금",
        "CONTRIBUTION": "월 적립",
        "BUY": "매수",
        "TAKE_PROFIT": "익절 조건 충족",
        "SELL": "전량 매도",
        "REENTRY": "재진입",
    }
    mapped: dict[pd.Timestamp, list[str]] = {}
    for row in output.results[code].events.itertuples(index=False):
        if row.event_type in names:
            mapped.setdefault(pd.Timestamp(row.date), []).append(names[row.event_type])
    if output.goal_active:
        goal = output.analyses[code]
        if goal.goal_reached:
            mapped.setdefault(pd.Timestamp(goal.goal_date), []).append("목표 달성")
    return {date: " · ".join(items) for date, items in mapped.items()}


def _state_label(value: object) -> str:
    return {
        "INVESTED": "투자 중",
        "WAITING_REENTRY": "현금 대기",
    }.get(str(value), str(value))


def _date_or_dash(value: object) -> str:
    return "—" if pd.isna(value) else korean_date(pd.Timestamp(value))


def unified_research_figure(output: GoalSimulationOutput) -> go.Figure:
    """Render market, A/B/C, target, goal and C events on one time axis."""
    figure = go.Figure()
    dates = pd.to_datetime(output.market["date"])
    korean_dates = [korean_date(value) for value in dates]
    target = output.analyses["A"].target_value if output.goal_active else None
    c_values = output.results["C"].daily_states["portfolio_value"].to_numpy()
    a_values = output.results["A"].daily_states["portfolio_value"].to_numpy()
    c_delta = c_values - a_values
    actions = {code: _event_text(output, code) for code in "ABC"}
    c_actions = actions["C"]
    labels = dict(STRATEGY_LABEL)
    labels["B"] = f"B +{float(output.config.take_profit_percent):g}% 즉시 재진입"
    labels["C"] = (
        f"C +{float(output.config.take_profit_percent):g}% / "
        f"{int(float(output.config.reentry_months))}개월 대기"
    )

    figure.add_trace(go.Scatter(
        x=dates,
        y=output.market["close"],
        mode="lines",
        name="S&P500",
        yaxis="y",
        line={"color": "#7b8794", "width": 1.35},
        customdata=np.array(korean_dates, dtype=object),
        hovertemplate="%{customdata}<br>S&P500 %{y:,.2f}<extra></extra>",
        meta="market",
    ))

    for code in "ABC":
        states = output.results[code].daily_states
        custom = []
        for index, date in enumerate(pd.to_datetime(states["date"])):
            row = states.iloc[index]
            state = _state_label(row["strategy_state"])
            action = actions[code].get(
                date, "현금 대기" if state == "현금 대기" else "보유",
            )
            custom.append([
                korean_dates[index], float(row["market_price"]),
                float(row["quantity"]), float(row["cash"]),
                float(row["portfolio_value"]), float(row["total_contribution"]),
                float(row["portfolio_value"] - row["total_contribution"]),
                float(row["average_purchase_price"]), state, action,
                _date_or_dash(row["reentry_target_date"]),
                float(c_delta[index]) if code == "C" else 0.0,
                target or 0.0,
                (
                    f"{float(row['quantity']):,.4f} × "
                    f"{float(row['market_price']):,.2f} + "
                    f"{float(row['cash']):,.0f} ≈ "
                    f"{float(row['portfolio_value']):,.0f}"
                ),
            ])
        extra = ""
        if code == "B":
            extra = (
                "<br><br>B 설명 같은 종가·비용 0에서 즉시 재매수하므로 "
                "A와 평가금액이 동일합니다."
            )
        elif code == "C":
            extra = (
                "<br>재진입 예정 %{customdata[10]}"
                "<br>A 대비 %{customdata[11]:+,.0f}"
            )
        goal_line = "<br>목표금액 %{customdata[12]:,.0f}" if output.goal_active else ""
        figure.add_trace(go.Scatter(
            x=states["date"],
            y=states["portfolio_value"],
            mode="lines",
            name=labels[code],
            yaxis="y2",
            line=STRATEGY_STYLE[code],
            customdata=np.array(custom, dtype=object),
            hovertemplate=(
                "%{customdata[0]}<br>시장가격 %{customdata[1]:,.2f}"
                "<br><br>" + labels[code]
                + "<br>보유수량 %{customdata[2]:,.4f}"
                + "<br>현금 %{customdata[3]:,.0f}"
                + "<br>평가금액 %{customdata[4]:,.0f}"
                + "<br>총 납입금 %{customdata[5]:,.0f}"
                + "<br>투자손익 %{customdata[6]:+,.0f}"
                + "<br>평균매입가 %{customdata[7]:,.2f}"
                + "<br>전략 상태 %{customdata[8]}"
                + "<br>현재 행동 %{customdata[9]}"
                + goal_line + extra
                + "<br><br>계산: %{customdata[13]}"
                + "<br>보유수량 × 시장가격 + 현금 = 평가금액"
                + "<extra></extra>"
            ),
            meta=code,
        ))

    if output.goal_active:
        figure.add_trace(go.Scatter(
            x=[dates.iloc[0], dates.iloc[-1]],
            y=[target, target],
            mode="lines",
            name=f"목표 +{float(output.config.target_return_percent):g}%",
            yaxis="y2",
            line={"color": "#8e5bb7", "width": 1.6, "dash": "dot"},
            hovertemplate=f"목표금액 {target:,.0f}<extra></extra>",
            meta="target",
        ))

        goal_x, goal_y, goal_text = [], [], []
        for code in "ABC":
            item = output.analyses[code]
            if item.goal_reached:
                goal_x.append(item.goal_date)
                goal_y.append(item.portfolio_value_at_goal)
                goal_text.append(f"{labels[code]} · {korean_date(item.goal_date)}")
        figure.add_trace(go.Scatter(
            x=goal_x,
            y=goal_y,
            mode="markers",
            name="목표 달성",
            yaxis="y2",
            marker={
                "size": 10, "color": "#8e5bb7", "symbol": "star",
                "line": {"width": 1, "color": "white"},
            },
            customdata=np.array(goal_text, dtype=object),
            hovertemplate="%{customdata}<br>%{y:,.0f}<extra></extra>",
            meta="target",
        ))

    c_states = output.results["C"].daily_states.set_index("date")
    event_x, event_y, event_text, event_symbol, event_color = [], [], [], [], []
    styles = {
        "TAKE_PROFIT": ("triangle-up", "#d46b24"),
        "SELL": ("triangle-down", "#b34343"),
        "REENTRY": ("diamond", "#0b8f72"),
    }
    for row in output.results["C"].events.itertuples(index=False):
        if row.event_type not in styles:
            continue
        date = pd.Timestamp(row.date)
        event_x.append(date)
        event_y.append(float(c_states.loc[date, "portfolio_value"]))
        event_text.append(f"{korean_date(date)} · C {c_actions[date]}")
        symbol, color = styles[row.event_type]
        event_symbol.append(symbol)
        event_color.append(color)
    figure.add_trace(go.Scatter(
        x=event_x,
        y=event_y,
        mode="markers",
        name="C 거래 표시",
        yaxis="y2",
        marker={"size": 8, "symbol": event_symbol, "color": event_color},
        customdata=np.array(event_text, dtype=object),
        hovertemplate="%{customdata}<br>평가금액 %{y:,.0f}<extra></extra>",
        visible=False,
        meta="events",
    ))

    figure.update_layout(
        title={"text": "S&P500 · Strategy A/B/C 투자 경로", "x": 0.01, "xanchor": "left"},
        height=570,
        margin={"l": 66, "r": 78, "t": 58, "b": 48},
        paper_bgcolor="white",
        plot_bgcolor="white",
        hovermode="x unified",
        hoverlabel={"bgcolor": "white", "font": {"size": 12}},
        legend={"orientation": "h", "y": 1.08, "x": 1, "xanchor": "right"},
        xaxis={
            "title": "날짜", "showgrid": True, "gridcolor": "#e8edf3",
            "tickformatstops": TICK_STOPS, "rangeslider": {"visible": False},
        },
        yaxis={
            "title": "S&P500 지수", "showgrid": True,
            "gridcolor": "#e8edf3", "tickformat": ",.0f", "side": "left",
        },
        yaxis2={
            "title": "전략 평가금액 · simulation currency", "overlaying": "y",
            "side": "right", "showgrid": False, "tickformat": "~s",
        },
    )
    # The stored base figure also carries a deterministic full-range scale so
    # a new simulation cannot briefly inherit Plotly's stale or padded axes.
    from .viewport import calculate_visible_axis_ranges

    default_layers = ["market", "A", "B", "C"]
    if output.goal_active:
        default_layers.append("target")
    left_range, right_range = calculate_visible_axis_ranges(
        figure.to_dict(), dates.iloc[0], dates.iloc[-1], default_layers,
    )
    figure.layout.xaxis.update(range=[dates.iloc[0], dates.iloc[-1]], autorange=False)
    figure.layout.yaxis.update(range=left_range, autorange=False)
    figure.layout.yaxis2.update(range=right_range, autorange=False)
    return figure
