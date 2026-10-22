"""Research comparison uses observed same-date bars without changing paper rules."""

from http.server import ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.request import urlopen

import pandas as pd
import pytest
import zero_market_lab.research.comparison as comparison_module

from scripts.run_research_ui import handler_for, load_context
from zero_market_lab.research.comparison import ComparisonResearch, gate_metadata, interpret_indicator
from zero_market_lab.transit.calendar import CENTERS
from zero_market_lab.transit.quarters import load_quarters

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def disconnected_context_is_deterministic(monkeypatch):
    # Local private FRED snapshots must not change the expectations of older tests.
    monkeypatch.setattr(comparison_module, "latest_snapshot", lambda root, layer: None)


def _fake_loader(symbol):
    base = {"date": ["2026-10-14", "2026-10-15", "2026-10-16"],
            "open": [100, 110, 120], "high": [105, 115, 125],
            "low": [95, 105, 115], "close": [100, 110, 120],
            "volume": [1000, 1100, 1200]}
    if symbol == "000660":
        base = {key: [values[1]] for key, values in base.items()}
        base["close"] = [220]
    return pd.DataFrame(base), {"provider": "SYNTHETIC_TEST_ONLY", "adjustment": "TEST"}


def test_gate_metadata_is_complete_and_does_not_invent_fear_themes():
    rows = gate_metadata(ROOT)
    assert len(rows) == 64
    assert {row["gate"] for row in rows} == set(range(1, 65))
    assert {row["center"] for row in rows} == set(CENTERS)
    assert all(row["short_keynote"] and row["source"] and row["version"] for row in rows)
    assert all(row["center_ko"] and row["short_keynote_ko"] and row["short_description_ko"] for row in rows)
    assert all(row["quarter_id"] for row in rows)
    assert next(row for row in rows if row["gate"] == 32)["fear_theme"] == "Failure"
    assert all(row["fear_theme"] is None for row in rows if row["gate"] != 32)


def test_four_quarters_cover_every_gate_with_distinct_start_turning_and_end():
    quarters, gate_map = load_quarters(ROOT)
    assert [(item["start_gate"], item["turning_gate"], item["end_gate"]) for item in quarters] == [
        (13, 25, 24), (2, 15, 33), (7, 46, 44), (1, 10, 19)]
    assert set(gate_map) == set(range(1, 65))
    assert all(item["name"] and item["name_ko"] and item["theme"] and item["theme_ko"]
               for item in quarters)
    assert gate_map[32]["id"] == "duality"


def test_comparison_normalizes_first_observation_and_never_fills_missing_market_day():
    research = ComparisonResearch(ROOT, loader=_fake_loader)
    packet = research.series(base="005930", start="2026-10-14", end="2026-10-15",
                             layers=["000660", "VIX", "HD_TRANSIT"], display="NORMALIZE_100")
    base, other, vix, gate = packet["series"]
    assert [point["display_value"] for point in base["points"]] == pytest.approx([100, 110])
    assert other["points"][0]["display_value"] == 100
    assert vix["points"] == [] and vix["availability"] == "NOT_CONNECTED"
    assert gate["points"] == []  # categorical Gate is not a numeric price series
    first = packet["context_by_date"]["2026-10-14"]
    assert first["layers"]["000660"]["value"] is None
    assert first["layers"]["000660"]["availability"] == "NO_SAME_DATE_OBSERVATION"
    assert first["layers"]["VIX"]["value"] is None
    assert first["transit"]["gate"] == 32
    assert first["transit"]["quarter"]["name_ko"] == "이중성의 쿼터"
    assert first["transit"]["center_ko"] == "비장 센터"
    assert first["base"]["open"] == 100 and first["base"]["volume"] == 1000
    assert all(first["investor_flow"][key]["value"] is None
               for key in ("individual", "institution", "foreign"))
    assert first["investor_flow"]["foreign"]["status"] == "NOT_CONNECTED"
    assert packet["series"][0]["points"][-1]["date"] == "2026-10-15"
    assert "2026-10-16" not in packet["context_by_date"]


def test_actual_mode_keeps_original_units_and_phase_is_context_only():
    research = ComparisonResearch(ROOT, loader=_fake_loader)
    packet = research.series(base="005930", start="2026-10-14", end="2026-10-16",
                             layers=["000660", "PRICE_PHASE_V1"], display="ACTUAL")
    assert packet["series"][0]["points"][0]["display_value"] == 100
    assert packet["series"][1]["points"][0]["display_value"] == 220
    assert packet["context_by_date"]["2026-10-15"]["phase"] == "UNKNOWN"
    assert packet["context_by_date"]["2026-10-14"]["transit"] is None
    assert packet["context_by_date"]["2026-10-15"]["base"]["daily_change_pct"] == pytest.approx(10)


def test_single_day_hover_uses_prior_observed_close_without_future_data():
    packet = ComparisonResearch(ROOT, loader=_fake_loader).series(
        base="005930", start="2026-10-15", end="2026-10-15", layers=[], display="ACTUAL")
    only = packet["context_by_date"]["2026-10-15"]
    assert only["base"]["daily_change_pct"] == pytest.approx(10)
    assert only["base"]["volume"] == 1100
    assert list(packet["context_by_date"]) == ["2026-10-15"]


def test_indicator_interpretation_requires_observation_and_preserves_scale():
    assert interpret_indicator("FEAR_GREED", None)["status"] == "NOT_CONNECTED"
    assert interpret_indicator("FEAR_GREED", 22)["status"] == "Extreme Fear"
    assert interpret_indicator("VIX", 31)["scale_type"] == "REFERENCE_THRESHOLD"
    assert interpret_indicator("VIX", 31)["status"] == "Elevated"
    assert interpret_indicator("US10Y", 4.5, [3.5, 4.0, 4.5])["percentile"] == 100
    with pytest.raises(ValueError):
        interpret_indicator("FEAR_GREED", 102)


def test_comparison_http_catalog_series_and_calendar():
    research = ComparisonResearch(ROOT, loader=_fake_loader)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(load_context(), comparison_controller=research))
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with urlopen(base + "/api/comparison/catalog") as response:
            catalog = json.load(response)
        assert next(row for row in catalog["layers"] if row["layer_id"] == "VIX")["availability"] == "NOT_CONNECTED"
        with urlopen(base + "/api/comparison/series?base=005930&start=2026-10-14&end=2026-10-15&layers=000660%2CHD_TRANSIT&display=NORMALIZE_100") as response:
            payload = json.load(response)
        assert payload["series"][0]["points"][0]["display_value"] == 100
        assert payload["context_by_date"]["2026-10-14"]["transit"]["gate"] == 32
        with urlopen(base + "/api/comparison/calendar?year=2026") as response:
            assert len(json.load(response)["gates"]) >= 64
        with pytest.raises(HTTPError) as failure:
            urlopen(base + "/api/comparison/series?base=005930&start=2026-10-14&end=2026-10-15&layers=BOGUS")
        assert failure.value.code == 400
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)
