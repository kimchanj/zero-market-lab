"""Goal-Based Investment Simulation Prototype verification."""

import pandas as pd
import pytest

from zero_market_lab.analytics import GoalStatus, analyze_goal
from zero_market_lab.backtest import run_case01_comparison, run_case01_strategy
from zero_market_lab.goal_ui import GoalSimulationConfig, run_goal_simulation
from zero_market_lab.goal_ui.app import (
    apply_layer_visibility,
    build_config,
    create_goal_app,
    pension_preset_values,
    quick_start_date,
)
from zero_market_lab.goal_ui.figures import unified_research_figure
from zero_market_lab.goal_ui.service import korean_date


def market(dates, closes):
    return pd.DataFrame({"date": dates, "close": closes})


def test_initial_investment_is_separate_and_bought_on_first_observation():
    source = market(["2026-01-02", "2026-01-05"], [100, 110])
    result = run_case01_strategy(source, 0, "A", initial_investment=1_000)
    assert result.events.event_type.tolist() == ["INITIAL_CONTRIBUTION", "BUY"]
    assert result.events.iloc[0].amount == 1_000
    assert result.daily_states.iloc[0].quantity == pytest.approx(10)
    assert result.daily_states.iloc[0].total_contribution == 1_000


def test_default_zero_initial_preserves_existing_event_path():
    source = market(["2026-01-02", "2026-02-02"], [100, 110])
    result = run_case01_strategy(source, 100, "A")
    assert result.events.event_type.tolist() == [
        "CONTRIBUTION", "BUY", "CONTRIBUTION", "BUY",
    ]


def test_hand_calculated_goal_date_days_and_target():
    source = market(["2026-01-01", "2026-01-02", "2026-01-03"], [100, 110, 120])
    result = run_case01_strategy(source, 0, "A", initial_investment=100)
    goal = analyze_goal(
        result, initial_investment=100, target_return=0.20,
        required_horizon_end="2026-01-03",
    )
    assert goal.status is GoalStatus.GOAL_REACHED
    assert goal.target_value == pytest.approx(120)
    assert goal.goal_date == pd.Timestamp("2026-01-03")
    assert goal.days_to_goal == 2
    assert goal.portfolio_value_at_goal == pytest.approx(120)


def test_goal_drawdown_before_recovery_is_negative_twenty_percent():
    source = market(
        ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"],
        [100, 80, 90, 120],
    )
    result = run_case01_strategy(source, 0, "A", initial_investment=100)
    goal = analyze_goal(
        result, initial_investment=100, target_return=0.20,
        required_horizon_end="2026-01-04",
    )
    assert goal.goal_date == pd.Timestamp("2026-01-04")
    assert goal.max_drawdown_before_goal == pytest.approx(-0.20)


def test_not_reached_and_insufficient_horizon_are_distinct():
    source = market(["2025-01-02", "2026-01-02"], [100, 105])
    result = run_case01_strategy(source, 0, "A", initial_investment=100)
    enough = analyze_goal(
        result, initial_investment=100, target_return=0.20,
        required_horizon_end="2026-01-02",
    )
    short = analyze_goal(
        result, initial_investment=100, target_return=0.20,
        required_horizon_end="2027-01-02",
    )
    assert enough.status is GoalStatus.GOAL_NOT_REACHED
    assert short.status is GoalStatus.INSUFFICIENT_HORIZON


def test_weekend_horizon_is_complete_when_dataset_continues_after_it():
    source = market(
        ["2020-01-03", "2021-01-01", "2021-01-04"],
        [100, 101, 101],
    )
    output = run_goal_simulation(source, GoalSimulationConfig(
        start_date="2020-01-03", initial_investment=100,
        target_return_percent=20, max_years=1,
    ))
    assert output.required_horizon_end == pd.Timestamp("2021-01-03")
    assert output.analyses["A"].status is GoalStatus.GOAL_NOT_REACHED


def test_a_b_goal_invariant_and_c_is_independently_analyzed():
    source = market(
        ["2026-01-02", "2026-01-10", "2026-02-02", "2026-02-10", "2026-03-10"],
        [100, 105, 90, 120, 130],
    )
    results = run_case01_comparison(source, 0, initial_investment=100)
    goals = {
        code: analyze_goal(
            result, initial_investment=100, target_return=0.20,
            required_horizon_end="2026-03-10",
        )
        for code, result in results.items()
    }
    assert goals["A"].goal_date == goals["B"].goal_date
    assert goals["A"].days_to_goal == goals["B"].days_to_goal
    assert goals["A"].max_drawdown_before_goal == pytest.approx(
        goals["B"].max_drawdown_before_goal
    )
    assert results["C"].metadata["strategy_code"] == "C"


def test_service_warns_when_monthly_contribution_changes_target_interpretation():
    dates = pd.date_range("2020-01-02", "2021-01-04", freq="B")
    source = market(dates, [100 + i / 100 for i in range(len(dates))])
    output = run_goal_simulation(source, GoalSimulationConfig(
        start_date="2020-01-02", initial_investment=10_000,
        monthly_contribution=100, target_return_percent=20, max_years=1,
    ))
    assert output.warnings
    assert output.goal_active is False
    assert output.analyses == {}
    assert all(trace.meta != "target" for trace in unified_research_figure(output).data)


def test_korean_date_and_weekday_format():
    assert korean_date("2025-01-06") == "2025년 1월 6일 월요일"
    assert korean_date("2026-10-05") == "2026년 10월 5일 월요일"


def test_unified_chart_has_all_layers_dual_axes_hover_and_events():
    dates = pd.date_range("2020-01-02", "2021-01-04", freq="B")
    source = market(dates, [100 + i * 0.2 for i in range(len(dates))])
    output = run_goal_simulation(source, GoalSimulationConfig(start_date="2020-01-02"))
    figure = unified_research_figure(output)
    assert [trace.meta for trace in figure.data] == [
        "market", "A", "B", "C", "target", "target", "events",
    ]
    assert figure.data[0].yaxis == "y"
    assert all(trace.yaxis == "y2" for trace in figure.data[1:])
    assert figure.layout.yaxis2.overlaying == "y"
    assert figure.layout.hovermode == "x unified"
    assert figure.data[-1].visible is False
    assert any(trace.name == "목표 달성" for trace in figure.data)
    assert len(figure.layout.xaxis.tickformatstops) == 3
    assert "월요일" in figure.data[0].customdata[2]
    assert output.results["A"].daily_states.portfolio_value.tolist() == pytest.approx(
        output.results["B"].daily_states.portfolio_value.tolist()
    )
    assert "A 대비" in figure.data[3].hovertemplate
    assert "보유수량" in figure.data[1].hovertemplate
    assert "총 납입금" in figure.data[1].hovertemplate
    assert "평균매입가" in figure.data[1].hovertemplate
    assert "같은 종가·비용 0" in figure.data[2].hovertemplate
    assert "재진입 예정" in figure.data[3].hovertemplate
    assert figure.data[1].customdata[0][1] == pytest.approx(100)
    assert figure.data[1].customdata[0][4] == pytest.approx(10_000_000)
    assert "×" in figure.data[1].customdata[0][13]
    event_dates = set(pd.to_datetime(output.results["C"].events["date"]))
    waiting_index = next(
        index
        for index, row in output.results["C"].daily_states.iterrows()
        if row.strategy_state == "WAITING_REENTRY"
        and pd.Timestamp(row.date) not in event_dates
    )
    assert figure.data[3].customdata[waiting_index][8] == "현금 대기"
    assert figure.data[3].customdata[waiting_index][9] == "현금 대기"
    assert figure.data[3].customdata[waiting_index][10] != "—"
    assert output.results["C"].daily_states.portfolio_value.tolist() != pytest.approx(
        output.results["A"].daily_states.portfolio_value.tolist()
    )

    filtered = apply_layer_visibility(figure.to_dict(), ["market", "C", "events"])
    visible = {trace.meta: trace.visible for trace in filtered.data}
    assert visible["market"] is True
    assert visible["C"] is True
    assert visible["events"] is True
    assert visible["A"] is False
    assert visible["B"] is False
    assert visible["target"] is False


@pytest.mark.parametrize(
    "period,expected",
    [
        ("1W", "2026-09-25"), ("1M", "2026-09-02"),
        ("3M", "2026-07-02"), ("6M", "2026-04-02"),
        ("1Y", "2025-10-02"), ("3Y", "2023-10-02"),
        ("ALL", "2016-10-03"),
    ],
)
def test_quick_start_date_uses_dataset_end(period, expected):
    assert quick_start_date(
        period, pd.Timestamp("2016-10-03"), pd.Timestamp("2026-10-02")
    ) == expected


def test_quick_start_date_clips_to_dataset_boundary():
    assert quick_start_date(
        "3Y", pd.Timestamp("2025-01-02"), pd.Timestamp("2026-10-02")
    ) == "2025-01-02"


def test_start_date_changes_engine_result_contributions_and_chart_range():
    dates = pd.date_range("2020-01-02", "2025-01-03", freq="B")
    source = market(dates, [100 + index * 0.1 for index in range(len(dates))])
    early = run_goal_simulation(source, GoalSimulationConfig(
        start_date="2020-01-02", initial_investment=0,
        monthly_contribution=500_000, max_years=3, goal_enabled=False,
    ))
    late = run_goal_simulation(source, GoalSimulationConfig(
        start_date="2022-01-03", initial_investment=0,
        monthly_contribution=500_000, max_years=3, goal_enabled=False,
    ))

    assert early.actual_start != late.actual_start
    assert early.evaluations["A"].final_portfolio_value != late.evaluations["A"].final_portfolio_value
    early_first_contribution = early.results["A"].events.loc[
        early.results["A"].events.event_type == "CONTRIBUTION", "date"
    ].iloc[0]
    late_first_contribution = late.results["A"].events.loc[
        late.results["A"].events.event_type == "CONTRIBUTION", "date"
    ].iloc[0]
    assert early_first_contribution != late_first_contribution
    early_range = unified_research_figure(early).layout.xaxis.range
    late_range = unified_research_figure(late).layout.xaxis.range
    assert early_range != late_range


def test_goal_dash_app_is_isolated_and_registers_callback():
    dates = pd.date_range("2020-01-02", "2026-01-05", freq="B")
    source = market(dates, [100 + i * 0.05 for i in range(len(dates))])
    app = create_goal_app(source)
    assert app.title == "ZERO MARKET LAB · 투자 전략 비교"
    assert len(app.callback_map) == 5
    layout_text = str(app.layout)
    assert "시뮬레이션 실행" in layout_text
    assert "goal-unified-chart" in layout_text
    assert "goal-layers" in layout_text
    assert "goal-strategy'" not in layout_text
    assert "type='date'" in layout_text
    assert "투자 조건" in layout_text
    assert "전략 조건" in layout_text
    assert "월 50만원 적립" in layout_text
    assert "Reset View" in layout_text
    assert "goal-run-request" in layout_text


def test_zero_initial_monthly_only_is_valid_and_first_month_is_not_duplicated():
    source = market(
        ["2026-01-02", "2026-01-05", "2026-02-02"],
        [100, 101, 102],
    )
    output = run_goal_simulation(source, GoalSimulationConfig(
        start_date="2026-01-02", initial_investment=0,
        monthly_contribution=500_000, max_years=1, goal_enabled=False,
    ))
    events = output.results["A"].events
    assert events.event_type.tolist() == ["CONTRIBUTION", "BUY", "CONTRIBUTION", "BUY"]
    assert events.loc[events.event_type == "CONTRIBUTION", "date"].tolist() == [
        pd.Timestamp("2026-01-02"), pd.Timestamp("2026-02-02"),
    ]
    assert output.evaluations["A"].total_contribution == 1_000_000


def test_both_investment_amounts_zero_is_readable_error():
    source = market(["2026-01-02", "2026-01-05"], [100, 101])
    with pytest.raises(ValueError, match="하나는 0보다 커야"):
        run_goal_simulation(source, GoalSimulationConfig(
            start_date="2026-01-02", initial_investment=0,
            monthly_contribution=0, goal_enabled=False,
        ))


def test_pension_preset_and_ui_config_mapping_are_exact():
    assert pension_preset_values() == (0.0, 500_000.0, 10, 5.0, 1)
    mapped = build_config(
        "2020-01-02", 0, 500_000, 10, 7, 2, [], 20,
    )
    assert mapped == GoalSimulationConfig(
        start_date="2020-01-02", initial_investment=0,
        monthly_contribution=500_000, max_years=10,
        take_profit_percent=7, reentry_months=2,
        goal_enabled=False, target_return_percent=20,
    )


def test_browser_numeric_strings_are_normalized_before_validation():
    dates = pd.date_range("2020-01-02", "2022-01-03", freq="B")
    source = market(dates, [100 + index * 0.1 for index in range(len(dates))])
    output = run_goal_simulation(source, GoalSimulationConfig(
        start_date="2020-01-02", initial_investment="0",
        monthly_contribution="500000", max_years="2",
        take_profit_percent="10", reentry_months="2",
        goal_enabled=False, target_return_percent="20",
    ))
    assert output.results["A"].metadata["monthly_contribution"] == 500_000
    assert output.evaluations["B"].take_profit_count > 0
    assert output.results["C"].metadata["cash_waiting_days"] > 0


def test_amount_period_and_strategy_parameters_reach_engine_and_change_results():
    dates = pd.date_range("2020-01-02", "2025-01-03", freq="B")
    closes = [100 + index * 0.08 for index in range(len(dates))]
    source = market(dates, closes)
    baseline = run_goal_simulation(source, GoalSimulationConfig(
        start_date="2020-01-02", initial_investment=0,
        monthly_contribution=500_000, max_years=3,
        take_profit_percent=5, reentry_months=1, goal_enabled=False,
    ))
    more_money = run_goal_simulation(source, GoalSimulationConfig(
        start_date="2020-01-02", initial_investment=1_000_000,
        monthly_contribution=700_000, max_years=4,
        take_profit_percent=10, reentry_months=2, goal_enabled=False,
    ))
    assert baseline.results["A"].metadata["initial_investment"] == 0
    assert baseline.results["A"].metadata["monthly_contribution"] == 500_000
    assert more_money.evaluations["A"].total_contribution > baseline.evaluations["A"].total_contribution
    assert more_money.evaluations["A"].final_portfolio_value > baseline.evaluations["A"].final_portfolio_value
    assert len(more_money.market) > len(baseline.market)
    assert more_money.evaluations["B"].take_profit_count < baseline.evaluations["B"].take_profit_count
    assert more_money.evaluations["C"].cash_waiting_days != baseline.evaluations["C"].cash_waiting_days
    assert more_money.evaluations["C"].final_portfolio_value != baseline.evaluations["C"].final_portfolio_value


def test_strategy_evaluation_delta_counts_and_b_equals_a_invariant():
    dates = pd.date_range("2020-01-02", "2023-01-03", freq="B")
    source = market(dates, [100 + index * 0.1 for index in range(len(dates))])
    output = run_goal_simulation(source, GoalSimulationConfig(
        start_date="2020-01-02", initial_investment=0,
        monthly_contribution=500_000, max_years=3,
        take_profit_percent=5, reentry_months=1, goal_enabled=False,
    ))
    a, b, c = (output.evaluations[code] for code in "ABC")
    assert b.final_portfolio_value == pytest.approx(a.final_portfolio_value)
    assert b.delta_vs_a == pytest.approx(0)
    assert "A와 동일" in b.verdict
    assert c.delta_vs_a == pytest.approx(c.final_portfolio_value - a.final_portfolio_value)
    assert c.take_profit_count == c.sell_count
    assert c.cash_waiting_days > 0
    assert c.time_in_market < a.time_in_market
