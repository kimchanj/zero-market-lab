"""Visible-range autoscale regression tests for the dual-axis chart."""

import math
import base64

import numpy as np

import pytest

from zero_market_lab.goal_ui.viewport import (
    apply_visible_viewport,
    calculate_visible_axis_ranges,
    padded_range,
    quick_view_range,
    x_range_from_relayout,
)


def figure_fixture():
    dates = ["2020-01-02", "2020-03-23", "2020-06-01", "2022-01-03"]
    return {
        "data": [
            {"x": dates, "y": [3200, 2237, 3055, 4796], "meta": "market", "visible": True},
            {"x": dates, "y": [10_000_000, 7_000_000, 9_500_000, 16_000_000], "meta": "A", "visible": True},
            {"x": dates, "y": [10_000_000, 7_000_000, 9_500_000, 16_000_000], "meta": "B", "visible": True},
            {"x": dates, "y": [10_000_000, 8_000_000, 9_000_000, 14_000_000], "meta": "C", "visible": True},
            {
                "x": [dates[0], dates[-1]], "y": [12_000_000, 12_000_000],
                "meta": "target", "mode": "lines", "visible": True,
            },
            {"x": [dates[1]], "y": [99_000_000], "meta": "events", "visible": True},
        ],
        "layout": {"xaxis": {}, "yaxis": {}, "yaxis2": {"overlaying": "y", "side": "right"}},
    }


def test_visible_slice_uses_market_only_on_left_and_portfolios_on_right():
    left, right = calculate_visible_axis_ranges(
        figure_fixture(), "2020-03-01", "2020-06-30", ["market", "A", "B", "C"],
    )
    assert left == pytest.approx([2171.56, 3120.44])
    assert right == pytest.approx([6_800_000, 9_700_000])


def test_hidden_layers_and_event_markers_are_excluded():
    left, right = calculate_visible_axis_ranges(
        figure_fixture(), "2020-01-01", "2022-12-31", ["market", "C", "events"],
    )
    assert left[1] < 5_100
    assert right == pytest.approx([7_520_000, 14_480_000])


def test_target_line_is_included_on_right_without_using_marker_offset():
    _, right = calculate_visible_axis_ranges(
        figure_fixture(), "2020-03-01", "2020-06-30", ["C", "target", "events"],
    )
    assert right == pytest.approx([7_680_000, 12_320_000])


def test_flat_series_has_finite_nonzero_fallback_padding():
    result = padded_range([100, 100])
    assert result == [95, 105]
    assert all(math.isfinite(value) for value in result)


def test_nonnegative_portfolio_axis_never_pads_below_zero():
    figure = figure_fixture()
    figure["data"][1]["y"] = [1, 2, 3, 100]
    _, right = calculate_visible_axis_ranges(
        figure, "2020-01-01", "2022-12-31", ["A"],
    )
    assert right[0] == 0
    assert right[1] > 100


def test_plotly_typed_array_payload_is_used_for_autoscale():
    figure = figure_fixture()
    values = np.array([10.0, 20.0, 30.0, 40.0], dtype="float64")
    figure["data"][1]["y"] = {
        "dtype": "f8",
        "bdata": base64.b64encode(values.tobytes()).decode("ascii"),
    }
    _, right = calculate_visible_axis_ranges(
        figure, "2020-01-01", "2022-12-31", ["A"],
    )
    assert right == pytest.approx([7.6, 42.4])


def test_no_point_window_uses_nearest_observation_and_never_nan():
    left, right = calculate_visible_axis_ranges(
        figure_fixture(), "2021-01-01", "2021-01-02", ["market", "A"],
    )
    assert left is not None and right is not None
    assert left[0] < left[1]
    assert right[0] < right[1]
    assert all(math.isfinite(value) for value in left + right)


def test_no_active_axis_layer_returns_safe_autorange_signal():
    left, right = calculate_visible_axis_ranges(
        figure_fixture(), "2020-01-01", "2020-12-31", [],
    )
    assert left is None
    assert right is None


@pytest.mark.parametrize(
    "payload,expected",
    [
        ({"xaxis.range[0]": "2020-03-01", "xaxis.range[1]": "2020-06-01"},
         ("2020-03-01T00:00:00", "2020-06-01T00:00:00")),
        ({"xaxis.range": ["2020-03-01", "2020-06-01"]},
         ("2020-03-01T00:00:00", "2020-06-01T00:00:00")),
        ({"xaxis.autorange": True}, None),
    ],
)
def test_wheel_pan_and_reset_relayout_shapes(payload, expected):
    assert x_range_from_relayout(payload, figure_fixture()) == expected


def test_quick_range_and_all_share_the_same_viewport_path():
    one_year = quick_view_range("1Y", figure_fixture())
    all_range = quick_view_range("ALL", figure_fixture())
    assert one_year == ("2021-01-03T00:00:00", "2022-01-03T00:00:00")
    assert all_range == ("2020-01-02T00:00:00", "2022-01-03T00:00:00")


def test_apply_viewport_recalculates_zoom_pan_and_full_reset_ranges():
    figure = figure_fixture()
    zoomed = apply_visible_viewport(
        figure, ["market", "C"], ["2020-03-01", "2020-06-30"],
    )
    panned = apply_visible_viewport(
        figure, ["market", "C"], ["2021-06-01", "2022-06-01"],
    )
    reset = apply_visible_viewport(figure, ["market", "A", "B", "C"], None)
    assert zoomed["layout"]["yaxis"]["range"] != panned["layout"]["yaxis"]["range"]
    assert zoomed["layout"]["yaxis2"]["range"] != panned["layout"]["yaxis2"]["range"]
    assert [str(value) for value in reset["layout"]["xaxis"]["range"]] == [
        "2020-01-02 00:00:00", "2022-01-03 00:00:00",
    ]
    visible = {trace["meta"]: trace.get("visible") for trace in zoomed["data"]}
    assert visible["market"] is True
    assert visible["C"] is True
    assert visible["A"] is False
    assert visible["events"] is False


def test_apply_viewport_hides_axis_without_active_series():
    figure = figure_fixture()

    market_only = apply_visible_viewport(figure, ["market"], None)
    strategy_only = apply_visible_viewport(figure, ["A"], None)

    assert market_only["layout"]["yaxis"]["visible"] is True
    assert market_only["layout"]["yaxis2"]["visible"] is False
    assert strategy_only["layout"]["yaxis"]["visible"] is False
    assert strategy_only["layout"]["yaxis2"]["visible"] is True
