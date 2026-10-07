"""Static and builder contracts for the isolated chart-engine spike."""

import hashlib
import importlib.util
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
SPIKE = ROOT / "experiments" / "lightweight_charts"


def _builder_module():
    spec = importlib.util.spec_from_file_location(
        "lwc_spike_builder", SPIKE / "build_prototype.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_lightweight_charts_vendor_is_fixed_and_integrity_checked():
    vendor = SPIKE / "vendor" / "lightweight-charts.standalone.production.js"
    digest = hashlib.sha256(vendor.read_bytes()).hexdigest()
    assert digest == "e21cc5caa0226ef30bd8549c50b9ef926615f2a4ee6b4e486353477a55f598cf"
    assert (SPIKE / "vendor" / "NOTICE").is_file()


def test_prototype_uses_two_panes_markers_crosshair_and_responsive_size():
    source = (SPIKE / "prototype.js").read_text(encoding="utf-8")
    assert "autoSize: true" in source
    assert "CrosshairMode.Normal" in source
    assert "createSeriesMarkers" in source
    assert "setStretchFactor" in source
    assert "subscribeCrosshairMove" in source
    assert "setVisibleRange" in source
    assert "applyOptions({ visible: input.checked })" in source
    assert "from.setUTCMonth(from.getUTCMonth() - 3)" in source
    assert source.count("}, 1);") >= 4
    assert "CandlestickSeries" not in source
    assert "HistogramSeries" not in source


def test_builder_serializes_existing_market_state_and_event_shapes():
    builder = _builder_module()
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-02", "2026-01-05"]),
            "close": [100.0, 105.0],
        }
    )
    assert builder._series(frame, "close") == [
        {"time": "2026-01-02", "value": 100.0},
        {"time": "2026-01-05", "value": 105.0},
    ]
    assert builder.EVENT_TYPES == {"BUY", "TAKE_PROFIT", "SELL", "REENTRY"}


def test_prototype_declares_no_fake_volume_or_ohlc():
    builder = (SPIKE / "build_prototype.py").read_text(encoding="utf-8")
    page = (SPIKE / "index.html").read_text(encoding="utf-8")
    assert '"volume": None' in builder
    assert '"ohlc": None' in builder
    assert "No volume: the price index has no trading volume." in page
    assert "TradingView Lightweight Charts™ © 2025 TradingView, Inc." in page
