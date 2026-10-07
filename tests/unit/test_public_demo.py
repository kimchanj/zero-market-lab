"""Public deployment must run without third-party market data or local files."""

from datetime import date
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from scripts.build_public_demo import build
from scripts.run_research_ui import handler_for, load_context


def test_synthetic_demo_is_separate_from_local_market_cache(tmp_path: Path):
    report = build(date(2020, 10, 7), tmp_path)
    context = load_context("PUBLIC_DEMO", tmp_path)
    bundle = context[0]
    assert report["mode"] == "PUBLIC_DEMO" and report["bars"] > 30
    assert bundle["simulation"]["provenance"]["synthetic"] is True
    assert bundle["simulation"]["instrument"]["symbol"] == "SYNTH-ETF"
    assert all(row["low"] <= row["open"] <= row["high"] and
               row["low"] <= row["close"] <= row["high"] for row in bundle["market"])
    for name in ("tiger_data.js", "simulation_data.js", "research_input.json"):
        content = (tmp_path / name).read_text(encoding="utf-8")
        assert "A360750" not in content and "Daum Finance" not in content
    bundle["simulation"]["provenance"]["synthetic"] = False
    (tmp_path / "research_input.json").write_text(json.dumps(bundle), encoding="utf-8")
    with pytest.raises(ValueError, match="synthetic"):
        load_context("PUBLIC_DEMO", tmp_path)


def test_public_server_uses_synthetic_assets_engine_and_empty_news(tmp_path: Path):
    build(date(2020, 10, 7), tmp_path)
    context = load_context("PUBLIC_DEMO", tmp_path)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(context, "PUBLIC_DEMO", tmp_path))
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    root = f"http://127.0.0.1:{server.server_port}"
    origin = root
    try:
        assert b"PUBLIC_DEMO" in urlopen(root + "/tiger_etf_v2/tiger_data.js").read()
        try:
            urlopen(root + "/tiger_etf_v2/research_input.json")
            assert False, "Private demo bundle was publicly served"
        except HTTPError as error:
            assert error.code == 404
        params = {"start": "2020-08-07", "end": "2020-10-07", "initial_capital": "500000",
                  "entry_percent": "1", "take_profit_percent": "5", "minimum_net_percent": "1"}
        request = Request(root + "/api/simulate", data=json.dumps(params).encode(), method="POST",
                          headers={"Content-Type": "application/json", "Origin": origin})
        result = json.load(urlopen(request))
        assert result["provenance"]["synthetic"] is True
        assert result["ledger"] and result["summary"]["initial_capital"] == 500000
        research = Request(root + "/api/research", data=json.dumps({
            "start": "2020-08-07", "end": "2020-10-07", "run_id": result["run_id"]}).encode(),
            method="POST", headers={"Content-Type": "application/json", "Origin": origin})
        packet = json.load(urlopen(research))
        assert packet["snapshot"]["news"] == []
        bad_origin = Request(root + "/api/simulate", data=json.dumps(params).encode(), method="POST",
                             headers={"Content-Type": "application/json", "Origin": "https://other.example"})
        try:
            urlopen(bad_origin)
            assert False, "Cross-origin simulation request was accepted"
        except HTTPError as error:
            assert error.code == 403
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


def test_default_public_demo_contains_a_complete_trade_lifecycle(tmp_path: Path):
    build(date(2026, 10, 7), tmp_path)
    payload = load_context("PUBLIC_DEMO", tmp_path)[0]["simulation"]
    actions = {row["action"] for row in payload["ledger"]}
    assert {"BUY", "SELL"} <= actions
    assert payload["summary"]["completed_trades"] >= 1
    assert payload["open_position"] is not None
