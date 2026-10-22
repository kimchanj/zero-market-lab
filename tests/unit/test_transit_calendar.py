"""Research calendar coverage and market-close mapping, not trading signals."""

from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
import json
from threading import Thread
from urllib.request import urlopen
from urllib.error import HTTPError

import pandas as pd
import pytest

from zero_market_lab.transit.calendar import (
    GATE_SEQUENCE, at_instant, at_market_close, gate_line, year_calendar,
)
from zero_market_lab.transit.metrics import gate_market_metrics
from zero_market_lab.paper_trading.replay_ui import ReplayController
from scripts.run_paper_replay_ui import handler_for


def test_full_2026_calendar_is_contiguous_and_uses_mandala_sequence():
    result = year_calendar(2026)
    gates, lines = result["gates"], result["lines"]
    assert {item["gate"] for item in gates} == set(range(1, 65))
    assert len(lines) in {384, 385}
    assert lines[0]["start_utc"] == "2026-01-01T00:00:00+00:00"
    assert lines[-1]["end_utc"] == "2027-01-01T00:00:00+00:00"
    assert all(left["end_utc"] == right["start_utc"] for left, right in zip(lines, lines[1:]))
    assert all(left["end_utc"] == right["start_utc"] for left, right in zip(gates, gates[1:]))
    indices = [GATE_SEQUENCE.index(item["gate"]) for item in gates]
    assert all((right - left) % 64 == 1 for left, right in zip(indices, indices[1:]))
    assert any(datetime.fromisoformat(item["start_utc"]).weekday() >= 5
               for item in gates[1:])  # weekend boundaries are retained


def test_market_close_mapping_and_gate_line_boundary():
    # 2026 Gate 41 entrance independently published as Jan 21 19:54 ET
    entrance = next(row for row in year_calendar(2026)["gates"] if row["gate"] == 41)
    actual = datetime.fromisoformat(entrance["start_utc"])
    expected = datetime(2026, 1, 22, 0, 54, tzinfo=timezone.utc)
    assert abs(actual - expected) < timedelta(minutes=10)
    assert at_instant(actual - timedelta(minutes=2))["gate"] != 41
    assert at_instant(actual + timedelta(minutes=2))["gate"] == 41
    assert gate_line(actual + timedelta(minutes=2)) == (41, 1)
    krx = at_market_close("2026-10-22", "KRW")
    nyse = at_market_close("2026-10-22", "USD")
    assert krx["market_close_utc"] == "2026-10-22T06:30:00+00:00"
    assert nyse["market_close_utc"] == "2026-10-22T20:00:00+00:00"
    assert (krx["gate"], krx["line"]) == (50, 3)


def test_gate_metrics_count_only_observed_closes_before_as_of():
    gate = next(row for row in year_calendar(2026)["gates"] if row["gate"] == 32)
    frame = pd.DataFrame({"date": ["2026-10-13", "2026-10-14", "2026-10-15",
                                    "2026-10-16", "2026-10-20"],
                          "close": [95, 100, 102, 99, 90], "volume": [100, 110, 130, 80, 70]})
    before = gate_market_metrics(frame, gate=32, start=gate["start_utc"],
                                 end=gate["end_utc"], currency="KRW", as_of="2026-10-16")
    assert before["first_date"] == "2026-10-14"
    assert before["last_date"] == "2026-10-16"
    assert before["sessions"] == 3
    assert before["return_pct"] == pytest.approx(-1)
    assert before["trading_value"] is None
    assert before["investor_flow"] is None


@pytest.mark.parametrize("gate,expected_utc", [
    (18, "2026-09-26T23:05:00+00:00"),
    (48, "2026-10-02T16:34:00+00:00"),
    (57, "2026-10-08T09:32:00+00:00"),
    (32, "2026-10-14T02:03:00+00:00"),
    (50, "2026-10-19T18:08:00+00:00"),
    (28, "2026-10-25T09:51:00+00:00"),
    (44, "2026-10-31T01:09:00+00:00"),
])
def test_selected_boundaries_against_published_calendar(gate, expected_utc):
    # https://thehumandesign.com/learn/calendar-2026.html lists EDT times.
    actual = next(row for row in year_calendar(2026)["gates"] if row["gate"] == gate)
    assert abs(datetime.fromisoformat(actual["start_utc"]) -
               datetime.fromisoformat(expected_utc)) < timedelta(minutes=20)


def test_transit_json_endpoints_are_read_only_and_typed(tmp_path):
    frame = pd.DataFrame({"date": ["2026-10-14", "2026-10-15", "2026-10-16"],
                          "open": [100, 101, 102], "high": [102, 103, 104],
                          "low": [99, 100, 98], "close": [100, 102, 99],
                          "volume": [100, 110, 90]})
    controller = ReplayController(tmp_path, tmp_path / "replay.sqlite3",
                                  loader=lambda symbol: (frame, {"provider": "SYNTHETIC_TEST"}))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(controller))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        with urlopen(base + "/api/transit/year?year=2026") as response:
            calendar = json.load(response)
        with urlopen(base + "/api/transit/current?date=2026-10-15&currency=KRW") as response:
            current = json.load(response)
        with urlopen(base + "/api/transit/market-year?symbol=000660&year=2026") as response:
            market_year = json.load(response)
        try:
            with urlopen(base + "/api/transit/gate-metrics?symbol=000660&year=2026&gate=32&as_of=2026-10-16") as response:
                metrics = json.load(response)
        except HTTPError as error:
            pytest.fail(error.read().decode("utf-8"))
        assert len({item["gate"] for item in calendar["gates"]}) == 64
        assert current["gate"] == 32
        assert market_year["mode"] == "READ_ONLY_HISTORICAL_RESEARCH"
        assert market_year["last_observed"] == "2026-10-16"
        assert len(market_year["bars"]) == 3
        assert metrics["metrics"][0]["sessions"] == 3
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
