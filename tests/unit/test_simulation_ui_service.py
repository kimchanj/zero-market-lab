"""The UI adapter must rerun the same engine for each submitted condition."""

from dataclasses import asdict
import json
from pathlib import Path
from threading import Thread
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from zero_market_lab.simulator.models import CostConfig, Instrument
from zero_market_lab.simulator.service import run_simulation
from zero_market_lab.research.news import CatalogNewsProvider
from scripts.run_research_ui import handler_for


@pytest.fixture
def bundle():
    instrument = Instrument("KRX:TEST", "TEST", "Test ETF", "ETF", "KRX", "KRW", "Asia/Seoul",
                            tick_size=1, lot_size=1, market_hours="09:00-15:30")
    return {
        "simulation": {"instrument": asdict(instrument), "costs": asdict(CostConfig()),
                       "provenance": {"source": "synthetic"}},
        "market": [
            {"date": "2024-01-02", "open": 100, "high": 101, "low": 98, "close": 100, "volume": 1000},
            {"date": "2024-01-03", "open": 102, "high": 106, "low": 101, "close": 105, "volume": 1000},
            {"date": "2024-01-04", "open": 100, "high": 101, "low": 98, "close": 100, "volume": 1000},
            {"date": "2024-01-05", "open": 107, "high": 108, "low": 106, "close": 107, "volume": 1000},
        ],
    }


def params(**changes):
    result = {"start": "2024-01-02", "end": "2024-01-05", "initial_capital": "500",
              "entry_percent": "1", "take_profit_percent": "5", "minimum_net_percent": "1"}
    result.update(changes)
    return result


def test_period_filters_every_result_surface(bundle):
    full = run_simulation(bundle, params())
    short = run_simulation(bundle, params(end="2024-01-03"))
    assert len(full["ledger"]) == len(full["chart"]["averageCost"]) == 4
    assert len(short["ledger"]) == len(short["chart"]["averageCost"]) == 2
    assert full["scope"]["actual_period"] == ["2024-01-02", "2024-01-05"]
    assert short["summary"]["end_date"] == "2024-01-03"
    assert len(full["chart"]["markers"]) > len(short["chart"]["markers"])
    assert short["ledger"][-1]["date"] == "2024-01-03"
    assert short["run_id"] != full["run_id"]


def test_funding_entry_take_profit_and_minimum_have_distinct_semantics(bundle):
    base = run_simulation(bundle, params())
    funded = run_simulation(bundle, params(initial_capital="1000"))
    entry = run_simulation(bundle, params(entry_percent="2"))
    target = run_simulation(bundle, params(take_profit_percent="3"))
    minimum = run_simulation(bundle, params(minimum_net_percent="2"))
    assert funded["summary"]["initial_capital"] == 1000
    assert funded["ledger"][0]["position_qty_after"] > base["ledger"][0]["position_qty_after"]
    assert entry["ledger"][0]["execution_price"] < base["ledger"][0]["execution_price"]
    assert target["ledger"][1]["take_profit_price"] < base["ledger"][1]["take_profit_price"]
    assert minimum["summary"] == base["summary"]
    assert minimum["chart"] == base["chart"]
    assert minimum["trades"][0]["required_exit_price"] > base["trades"][0]["required_exit_price"]
    assert minimum["ledger"][0]["required_exit_price"] > base["ledger"][0]["required_exit_price"]


def test_invalid_inputs_do_not_silently_reuse_old_result(bundle):
    with pytest.raises(ValueError, match="시작일"):
        run_simulation(bundle, params(start="2024-01-06"))
    with pytest.raises(ValueError, match="관측값이 없습니다"):
        run_simulation(bundle, params(start="2024-02-01", end="2024-02-02"))
    with pytest.raises(ValueError, match="initial_capital"):
        run_simulation(bundle, params(initial_capital="no"))


def test_waiting_entry_gap_is_prepared_from_ledger_for_hover(bundle):
    result = run_simulation(bundle, params(entry_percent="3", end="2024-01-02"))
    row = result["ledger"][0]
    assert row["status"] == "WAITING_ENTRY"
    assert row["entry_order_price"] == 97
    assert row["low"] == 98
    assert row["entry_gap"] == 1


def test_news_provider_failure_returns_safe_error_without_affecting_engine(bundle):
    class FailedProvider(CatalogNewsProvider):
        def search_news(self, *args, **kwargs):
            raise RuntimeError("provider private error")

    baseline = run_simulation(bundle, params())
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for((bundle, FailedProvider([]), "test")))
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/api/research"
        request = Request(url, data=json.dumps({"start":"2024-01-02", "end":"2024-01-05"}).encode(),
                          headers={"Content-Type":"application/json"}, method="POST")
        with pytest.raises(HTTPError) as error:
            urlopen(request)
        assert error.value.code == 502
        body = json.loads(error.value.read())
        assert "가격/매매 시뮬레이션에는 영향이 없습니다" in body["error"]
        assert "private error" not in body["error"]
        assert run_simulation(bundle, params())["summary"] == baseline["summary"]
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


def test_workspace_sections_and_simple_default_columns():
    html = (Path(__file__).resolve().parents[2] / "experiments/tiger_etf_v2/index.html").read_text(encoding="utf-8")
    assert html.count('class="workspace-section') == 6
    assert html.count('class="workspace-section research-fold"') == 1
    assert html.count('class="workspace-section technical-panel"') == 1
    assert html.count('open aria-label=') == 3
    assert "<th>체결가</th>" in html and "<th>보유일</th>" in html
    assert "<th>reason_code</th>" not in html
