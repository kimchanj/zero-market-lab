"""Pure visible-range calculations for the dual-axis research chart."""

import base64
import math
from typing import Iterable

import numpy as np
import pandas as pd


LEFT_LAYERS = {"market"}
RIGHT_LAYERS = {"A", "B", "C", "target"}


def _timestamp(value: object) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_localize(None)
    return timestamp


def figure_x_bounds(figure: dict) -> tuple[pd.Timestamp, pd.Timestamp]:
    dates: list[pd.Timestamp] = []
    for trace in figure.get("data", []):
        if trace.get("meta") not in {"market", "A", "B", "C"}:
            continue
        dates.extend(_timestamp(value) for value in _array_values(trace.get("x", [])))
    if not dates:
        raise ValueError("Chart figure has no dated observations")
    return min(dates), max(dates)


def quick_view_range(period: str, figure: dict) -> tuple[str, str]:
    start, end = figure_x_bounds(figure)
    offsets = {
        "1W": pd.DateOffset(weeks=1),
        "1M": pd.DateOffset(months=1),
        "3M": pd.DateOffset(months=3),
        "6M": pd.DateOffset(months=6),
        "1Y": pd.DateOffset(years=1),
        "3Y": pd.DateOffset(years=3),
    }
    if period == "ALL":
        selected_start = start
    elif period in offsets:
        selected_start = max(start, end - offsets[period])
    else:
        raise ValueError(f"Unsupported quick range: {period}")
    return selected_start.isoformat(), end.isoformat()


def x_range_from_relayout(
    relayout: dict | None,
    figure: dict,
) -> tuple[str, str] | None:
    """Normalize Plotly wheel, pan, reset and double-click payload shapes."""
    if not relayout:
        return None
    if relayout.get("xaxis.autorange") is True:
        return None
    if "xaxis.range" in relayout:
        values = relayout["xaxis.range"]
        if isinstance(values, (list, tuple)) and len(values) == 2:
            return _timestamp(values[0]).isoformat(), _timestamp(values[1]).isoformat()
    if "xaxis.range[0]" in relayout and "xaxis.range[1]" in relayout:
        return (
            _timestamp(relayout["xaxis.range[0]"]).isoformat(),
            _timestamp(relayout["xaxis.range[1]"]).isoformat(),
        )
    return None


def _array_values(values: object) -> list[object]:
    """Expand Plotly 6 typed-array JSON as well as ordinary sequences."""
    if isinstance(values, dict) and "bdata" in values and "dtype" in values:
        raw = base64.b64decode(values["bdata"])
        array = np.frombuffer(raw, dtype=np.dtype(values["dtype"]))
        return array.tolist()
    if values is None:
        return []
    return list(values)


def _finite_values(values: Iterable[object] | object) -> list[float]:
    clean = []
    for value in _array_values(values):
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            clean.append(number)
    return clean


def padded_range(values: Iterable[object], padding_ratio: float = 0.08) -> list[float] | None:
    clean = _finite_values(values)
    if not clean:
        return None
    low, high = min(clean), max(clean)
    span = high - low
    padding = span * padding_ratio
    if span == 0:
        padding = max(abs(low) * 0.05, 1.0)
    return [low - padding, high + padding]


def _trace_visible_values(
    trace: dict,
    x_start: pd.Timestamp,
    x_end: pd.Timestamp,
) -> list[float]:
    x_values = _array_values(trace.get("x", []))
    y_values = _array_values(trace.get("y", []))
    pairs = []
    for x_value, y_value in zip(x_values, y_values):
        try:
            date = _timestamp(x_value)
            number = float(y_value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            pairs.append((date, number))
    visible = [number for date, number in pairs if x_start <= date <= x_end]
    if visible or not pairs:
        return visible
    # A sub-observation window uses the nearest real observation instead of an
    # arbitrary huge or non-finite fallback range.
    center = x_start + (x_end - x_start) / 2
    nearest = min(pairs, key=lambda pair: abs(pair[0] - center))
    return [nearest[1]]


def calculate_visible_axis_ranges(
    figure: dict,
    x_start: str | pd.Timestamp,
    x_end: str | pd.Timestamp,
    visible_layers: Iterable[str],
    padding_ratio: float = 0.08,
) -> tuple[list[float] | None, list[float] | None]:
    """Return independent left/right ranges from visible X data and layers."""
    start, end = _timestamp(x_start), _timestamp(x_end)
    if start > end:
        start, end = end, start
    enabled = set(visible_layers)
    left_values: list[float] = []
    right_values: list[float] = []
    for trace in figure.get("data", []):
        layer = trace.get("meta")
        if layer not in enabled or trace.get("visible") in {False, "legendonly"}:
            continue
        if layer == "events":
            continue
        if layer == "target" and trace.get("mode") == "lines":
            # A visible target is intentionally included even when its two
            # endpoint coordinates fall outside the current viewport.
            values = _finite_values(trace.get("y", []))[:1]
        else:
            values = _trace_visible_values(trace, start, end)
        if layer in LEFT_LAYERS:
            left_values.extend(values)
        elif layer in RIGHT_LAYERS:
            right_values.extend(values)
    left_range = padded_range(left_values, padding_ratio)
    right_range = padded_range(right_values, padding_ratio)
    if right_range is not None and right_values and min(right_values) >= 0:
        right_range[0] = max(0.0, right_range[0])
    return left_range, right_range


def apply_visible_viewport(
    figure: dict,
    visible_layers: Iterable[str],
    x_range: tuple[str, str] | list[str] | None,
) -> dict:
    """Apply X viewport and independent Y ranges without changing simulation data."""
    import plotly.graph_objects as go

    rendered = go.Figure(figure)
    enabled = set(visible_layers)
    for trace in rendered.data:
        trace.visible = trace.meta in enabled
    full_start, full_end = figure_x_bounds(figure)
    start, end = (
        (_timestamp(x_range[0]), _timestamp(x_range[1]))
        if x_range
        else (full_start, full_end)
    )
    left, right = calculate_visible_axis_ranges(
        rendered.to_dict(), start, end, enabled,
    )
    rendered.update_xaxes(range=[start, end], autorange=False)
    rendered.layout.yaxis.update(
        range=left, autorange=left is None, visible=left is not None,
    )
    rendered.layout.yaxis2.update(
        range=right, autorange=right is None, visible=right is not None,
    )
    return rendered.to_dict()
