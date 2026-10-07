"""STEP 5 service, figure and Dash application verification."""

import pandas as pd
import pytest

from zero_market_lab.ui.app import (
    GRAPH_CONFIG,
    create_app,
    quick_range_dates,
    transition_workspace,
)
from zero_market_lab.ui.figures import market_figure, portfolio_figure
from zero_market_lab.ui.service import (
    Case01ComparisonConfig,
    ParameterValidationError,
    run_comparison,
    same_exposure,
)


def market_fixture():
    return pd.DataFrame(
        {
            "date": [
                "2026-01-02", "2026-01-12", "2026-02-02",
                "2026-02-12", "2026-03-02", "2026-03-12",
            ],
            "close": [100.0, 105.0, 110.0, 120.0, 115.0, 125.0],
        }
    )


def config(**changes):
    values = {
        "start_date": "2026-01-02",
        "end_date": "2026-03-12",
        "monthly_contribution": 100.0,
        "take_profit_percent": 5.0,
        "reentry_months": 1,
    }
    values.update(changes)
    return Case01ComparisonConfig(**values)


@pytest.mark.parametrize(
    "changes,expected",
    [
        ({"start_date": "2026-03-12", "end_date": "2026-01-02"}, "앞서야"),
        ({"monthly_contribution": 0}, "Monthly Contribution"),
        ({"monthly_contribution": 1_000_000_001}, "Monthly Contribution"),
        ({"take_profit_percent": 0}, "Take Profit"),
        ({"take_profit_percent": 101}, "Take Profit"),
        ({"reentry_months": 0}, "Reentry Months"),
        ({"start_date": "2025-12-31"}, "데이터 범위"),
        ({"end_date": "2026-03-13"}, "데이터 범위"),
    ],
)
def test_parameter_validation_is_human_readable(changes, expected):
    with pytest.raises(ParameterValidationError, match=expected):
        run_comparison(market_fixture(), config(**changes))


def test_comparison_service_filters_dates_and_is_deterministic():
    selected = config(start_date="2026-01-12", end_date="2026-03-02")
    first = run_comparison(market_fixture(), selected)
    second = run_comparison(market_fixture(), selected)
    assert first.market.date.tolist() == ["2026-01-12", "2026-02-02", "2026-02-12", "2026-03-02"]
    for code in "ABC":
        pd.testing.assert_frame_equal(
            first.results[code].daily_states,
            second.results[code].daily_states,
        )


def test_comparison_service_preserves_a_b_same_close_invariant():
    output = run_comparison(market_fixture(), config(take_profit_percent=7.0))
    a = output.results["A"].daily_states
    b = output.results["B"].daily_states
    for column in ("portfolio_value", "quantity", "cash"):
        pd.testing.assert_series_equal(a[column], b[column], check_names=False)


def test_metrics_include_delta_vs_a_and_overlap_explanation_data():
    output = run_comparison(market_fixture(), config())
    metrics = {row["strategy"]: row for row in output.metrics}
    assert metrics["A"]["delta_vs_a"] == pytest.approx(0)
    assert metrics["B"]["delta_vs_a"] == pytest.approx(0)
    assert metrics["C"]["delta_vs_a"] == pytest.approx(
        metrics["C"]["final_portfolio_value"]
        - metrics["A"]["final_portfolio_value"]
    )
    assert output.insights["a_b_overlap"] is True


def test_overlap_explanation_tolerates_float_roundoff():
    output = run_comparison(market_fixture(), config(monthly_contribution=500_000.0))
    output.results["B"].daily_states.loc[0, "portfolio_value"] += 1e-10
    a = output.results["A"].daily_states
    b = output.results["B"].daily_states
    assert a.portfolio_value.iloc[0] != b.portfolio_value.iloc[0]
    assert same_exposure(output.results["A"], output.results["B"]) is True


@pytest.mark.parametrize(
    "period,expected",
    [
        ("1W", "2026-03-05"),
        ("1M", "2026-02-12"),
        ("3M", "2026-01-02"),
        ("6M", "2026-01-02"),
        ("1Y", "2026-01-02"),
        ("3Y", "2026-01-02"),
        ("5Y", "2026-01-02"),
        ("ALL", "2026-01-02"),
    ],
)
def test_quick_ranges_use_latest_date_and_clip_to_dataset(period, expected):
    start, end = quick_range_dates(
        period, pd.Timestamp("2026-01-02"), pd.Timestamp("2026-03-12")
    )
    assert start == expected
    assert end == "2026-03-12"


def test_workspace_sidebar_header_and_research_transitions():
    initial = transition_workspace(None, None)
    sidebar = transition_workspace("sidebar-toggle", initial)
    assert sidebar["sidebar_collapsed"] is True
    header = transition_workspace("header-toggle", sidebar)
    assert header["header_collapsed"] is True
    research = transition_workspace("research-toggle", initial)
    assert research == {
        "header_collapsed": True,
        "sidebar_collapsed": True,
        "research_mode": True,
    }
    restored = transition_workspace("research-toggle", research)
    assert restored == {
        "header_collapsed": False,
        "sidebar_collapsed": False,
        "research_mode": False,
    }


def test_research_query_initializes_compact_workspace():
    state = transition_workspace("url", None, "?research=1")
    assert state["research_mode"] is True
    assert state["header_collapsed"] is True
    assert state["sidebar_collapsed"] is True


def test_strategy_behavior_metrics_change_with_parameters():
    baseline = run_comparison(market_fixture(), config())
    changed = run_comparison(
        market_fixture(), config(take_profit_percent=20, reentry_months=2)
    )
    base_c = next(row for row in baseline.metrics if row["strategy"] == "C")
    changed_c = next(row for row in changed.metrics if row["strategy"] == "C")
    assert base_c["take_profit_count"] > changed_c["take_profit_count"]
    assert base_c != changed_c


def test_market_figure_contract():
    figure = market_figure(run_comparison(market_fixture(), config()))
    assert [trace.name for trace in figure.data] == ["S&P 500 Daily Close"]
    assert figure.layout.xaxis.type == "date"
    assert figure.layout.xaxis.tickformatstops
    assert figure.layout.xaxis.showspikes is True
    assert figure.layout.hovermode == "x unified"


def test_portfolio_figure_contract():
    figure = portfolio_figure(run_comparison(market_fixture(), config()))
    assert [trace.name for trace in figure.data] == [
        "A — Buy & Hold",
        "B — +5% / Immediate",
        "C — +5% / 1M Delay",
        "Total Contribution",
    ]
    assert figure.layout.xaxis.type == "date"
    assert figure.layout.hovermode == "x unified"
    assert figure.layout.dragmode == "pan"


def test_dash_app_layout_and_callbacks_smoke():
    app = create_app(market_fixture())
    assert app.layout is not None
    assert len(app.callback_map) == 4
    assert "market-chart" in str(app.callback_map)
    assert "portfolio-chart" in str(app.callback_map)
    assert "workspace-state" in str(app.callback_map)
    assert "relayoutData" in str(app.callback_map)
    assert "start-date" in str(app.layout)
    assert "end-date" in str(app.layout)
    assert GRAPH_CONFIG["scrollZoom"] is True
    assert GRAPH_CONFIG["responsive"] is True
