"""The replay controller projects the frozen Paper engine without advancing unseen days."""

from datetime import date
from decimal import Decimal
from http.server import ThreadingHTTPServer
import json
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pandas as pd
import pytest

from zero_market_lab.paper_trading.engine import create_account, journal, open_store, status
from zero_market_lab.paper_trading.replay_ui import ReplayController
from scripts.run_paper_replay_ui import handler_for


PROVENANCE = {"provider": "SYNTHETIC_TEST", "adjustment": "UNADJUSTED",
              "retrieved_at": "2025-01-01T00:00:00+00:00"}


def market():
    dates = pd.bdate_range("2024-01-01", periods=270)
    frame = pd.DataFrame({"date": dates, "open": 100.0, "high": 101.0,
                          "low": 99.0, "close": 100.0, "volume": 1000})
    frame.loc[241, ["open", "high", "low", "close"]] = [100, 110, 98, 100]
    frame.loc[242, ["open", "high", "low", "close"]] = [101, 103, 100, 102]
    frame.loc[243, ["open", "high", "low", "close"]] = [102, 106, 101, 104]
    return frame


def controller(tmp_path, frame):
    return ReplayController(tmp_path, tmp_path / "replay.sqlite3",
                            loader=lambda symbol: (frame, PROVENANCE))


def test_25_sessions_engine_parity_history_read_only_and_restart(tmp_path):
    frame = market()
    api = controller(tmp_path, frame)
    start = frame.iloc[240]["date"].date().isoformat()
    account = api.create(start_date=start)["account_id"]
    assert api.state(account)["journal"] == []
    assert api.state(account)["chart"]["price"] == []
    assert api.state(account)["next_session"] == start

    observed = []
    for index in range(25):
        packet = api.next_day(account)
        day = frame.iloc[240 + index]["date"].date().isoformat()
        observed.append(day)
        assert packet["journal_date"] == day
        state = packet["state"]
        assert state["view_date"] == day
        assert len(state["journal"]) == index + 1
        assert len(state["chart"]["price"]) == index + 1
        if index == 0:
            assert state["price_change_pct"] is None
        else:
            assert state["price_change_pct"] is not None
        assert max(bar["date"] for bar in state["chart"]["price"]) == day
        with open_store(api.db_path) as con:
            engine = status(con, account)
            assert state["summary"]["portfolio_value"] == engine["portfolio_value"]
            assert state["summary"]["cash"] == engine["cash"]
            assert state["summary"]["quantity"] == engine["quantity"]
            assert state["summary"]["s0_equity"] == engine["last_journal"]["s0_portfolio_value"]
            assert len(journal(con, account)) == index + 1

    assert observed[0] != observed[-1]
    assert any(marker["side"] == "BUY" and marker["kind"] == "DECISION"
               for marker in state["chart"]["markers"])
    assert any(marker["side"] == "BUY" and marker["kind"] == "EXECUTION"
               for marker in state["chart"]["markers"])
    assert all(bar["date"] <= observed[-1] for bar in state["chart"]["price"])
    history = api.state(account, observed[2])
    assert history["viewing_history"]
    assert history["view_date"] == observed[2]
    assert len(history["chart"]["price"]) == 3
    assert history["days_processed"] == 25
    assert controller(tmp_path, frame).state(account)["summary"] == state["summary"]
    assert controller(tmp_path, frame).accounts()[0]["account_id"] == account
    with pytest.raises(ValueError, match="processed Journal"):
        api.state(account, "2024-01-02")


def test_replay_complete_and_live_forward_isolation(tmp_path):
    frame = market().iloc[:242].copy()
    api = controller(tmp_path, frame)
    start = frame.iloc[240]["date"].date().isoformat()
    account = api.create(start_date=start)["account_id"]
    api.next_day(account)
    second = api.next_day(account)
    assert second["state"]["replay_complete"]
    assert second["state"]["next_session"] is None
    assert api.next_day(account)["result"] == "REPLAY_COMPLETE"
    with open_store(api.db_path) as con:
        assert status(con, account)["days_processed"] == 2
        create_account(con, name="live", symbol="000660", currency="KRW",
                       capital=Decimal(10000000), start_date=date.today().isoformat(),
                       mode="LIVE_FORWARD")
    assert all(item["account_id"] != "live" for item in api.accounts())
    with pytest.raises(ValueError, match="historical replay"):
        api.next_day("live")
    with open_store(api.db_path) as con:
        assert status(con, "live")["days_processed"] == 0


def test_hide_replay_only_removes_it_from_selector_and_preserves_journal(tmp_path):
    api = controller(tmp_path, market())
    start = market().iloc[240]["date"].date().isoformat()
    first = api.create(start_date=start)["account_id"]
    second = api.create(start_date=start)["account_id"]
    api.next_day(first)
    with open_store(api.db_path) as con:
        create_account(con, name="live", symbol="000660", currency="KRW",
                       capital=Decimal(10000000), start_date=date.today().isoformat(),
                       mode="LIVE_FORWARD")
    assert {a["account_id"] for a in api.accounts()} == {first, second}
    assert api.hide_account(first) == {"account_id": first, "hidden": True}
    assert [a["account_id"] for a in controller(tmp_path, market()).accounts()] == [second]
    assert [a["account_id"] for a in api.hidden_accounts()] == [first]
    assert api.state(first)["days_processed"] == 1
    with open_store(api.db_path) as con:
        assert len(journal(con, first)) == 1
        assert status(con, "live")["days_processed"] == 0
    with pytest.raises(ValueError, match="historical replay"):
        api.hide_account("live")
    with pytest.raises(ValueError, match="historical replay"):
        api.restore_account("live")
    with pytest.raises(KeyError, match="does not exist"):
        api.hide_account("missing")
    assert api.restore_account(first) == {"account_id": first, "hidden": False}
    assert {a["account_id"] for a in controller(tmp_path, market()).accounts()} == {first, second}
    assert api.hidden_accounts() == []
    assert api.state(first)["days_processed"] == 1


def test_seed_asset_selection_keeps_currency_and_account_history_separate(tmp_path):
    universe = tmp_path / "config/universe_seed_kr_us.json"
    universe.parent.mkdir()
    universe.write_text(json.dumps({"assets": [
        {"symbol": "000660", "name": "SK hynix", "market": "KRX", "currency": "KRW"},
        {"symbol": "NVDA", "name": "NVIDIA", "market": "US", "currency": "USD"},
        {"symbol": "MSFT", "name": "Microsoft", "market": "US", "currency": "USD"}]}), encoding="utf-8")
    api = ReplayController(tmp_path, tmp_path / "replay.sqlite3",
                           loader=lambda symbol: (market(), PROVENANCE) if symbol != "MSFT"
                           else (_ for _ in ()).throw(FileNotFoundError(symbol)))
    assert {asset["symbol"] for asset in api.meta()["available_assets"]} == {"000660", "NVDA"}
    assert api.meta("NVDA")["currency"] == "USD"
    start = market().iloc[240]["date"].date().isoformat()
    kr = api.create(start_date=start, symbol="000660")["account_id"]
    us = api.create(start_date=start, symbol="NVDA", capital="10000")["account_id"]
    assert api.next_day(us)["state"]["currency"] == "USD"
    assert api.state(us)["asset_name"] == "NVIDIA"
    assert api.state(kr)["days_processed"] == 0
    assert {item["symbol"] for item in api.accounts()} == {"000660", "NVDA"}
    with pytest.raises(ValueError, match="seed universe"):
        api.create(start_date=start, symbol="INVALID")


def test_s1_buy_budget_preserves_cash_and_versions_new_account(tmp_path):
    frame = market()
    api = controller(tmp_path, frame)
    start = frame.iloc[240]["date"].date().isoformat()
    account = api.create(start_date=start, capital="10000", buy_budget="250",
                         entry_offset_pct="-1", take_profit_pct="7")["account_id"]
    api.next_day(account)
    state = api.next_day(account)["state"]
    assert state["summary"]["quantity"] == "2"
    assert Decimal(state["summary"]["cash"]) > 9750
    assert state["buy_budget"] == "250"
    assert state["take_profit_pct"] == "7"
    assert state["strategy_version"] == "paper-s1-budget-v1"
    with open_store(api.db_path) as con:
        assert status(con, account)["days_processed"] == 2
        recorded = journal(con, account)[-1]
        assert recorded["fill_rule_version"] == "daily-ohlcv-s1-budget-v1"
        assert Decimal(state["summary"]["purchase_amount"]) == Decimal(recorded["entry_cost"])
        assert Decimal(state["summary"]["market_value"]) - Decimal(recorded["entry_cost"]) == Decimal(state["summary"]["unrealized_pnl"])


def test_s0_partial_open_buy_and_s2_stop_priority(tmp_path):
    frame = market()
    frame.loc[242, ["open", "high", "low", "close"]] = [101, 110, 95, 100]
    api = controller(tmp_path, frame)
    start = frame.iloc[240]["date"].date().isoformat()
    hold = api.create(start_date=start, capital="10000", buy_budget="250", strategy="S0")["account_id"]
    first = api.next_day(hold)["state"]
    assert first["execution"]["side"] == "BUY"
    assert first["execution"]["fill_price"] == "100.0"
    assert first["summary"]["quantity"] == "2"
    assert Decimal(first["summary"]["cash"]) > 9750
    assert api.next_day(hold)["state"]["decision"]["decision"] == "HOLD"
    stop = api.create(start_date=start, capital="10000", buy_budget="250", strategy="S2")["account_id"]
    api.next_day(stop)
    entry = api.next_day(stop)["state"]
    assert entry["pending_order"]["stop_price"] == "96"
    exit_state = api.next_day(stop)["state"]
    assert exit_state["execution"]["side"] == "SELL"
    assert exit_state["execution"]["fill_price"] == "96"
    assert exit_state["summary"]["quantity"] == "0"


def test_s7_close_breakout_enters_and_exits_at_next_open(tmp_path):
    frame = market()
    frame.loc[240, ["open", "high", "low", "close"]] = [100, 103, 99, 102]
    frame.loc[241, ["open", "high", "low", "close"]] = [100, 103, 99, 102]
    frame.loc[242, ["open", "high", "low", "close"]] = [100, 101, 97, 98]
    frame.loc[243, ["open", "high", "low", "close"]] = [97, 100, 96, 98]
    api = controller(tmp_path, frame)
    start = frame.iloc[240]["date"].date().isoformat()
    account = api.create(start_date=start, capital="10000", buy_budget="250", strategy="S7")["account_id"]
    signal = api.next_day(account)["state"]
    assert signal["decision"]["decision"] == "BUY"
    assert signal["execution"] is None
    entered = api.next_day(account)["state"]
    assert entered["execution"]["side"] == "BUY"
    assert entered["execution"]["fill_price"] == "100.0"
    queued_exit = api.next_day(account)["state"]
    assert queued_exit["decision"]["decision"] == "SELL"
    assert queued_exit["execution"] is None
    exited = api.next_day(account)["state"]
    assert exited["execution"]["side"] == "SELL"
    assert exited["execution"]["fill_price"] == "97.0"


def test_replay_strategy_inputs_are_frozen_and_invalid_budget_rejected(tmp_path):
    api = controller(tmp_path, market())
    start = market().iloc[240]["date"].date().isoformat()
    assert {s["code"] for s in api.meta()["available_strategies"]} == {"S0", "S1", "S2", "S7"}
    first = api.create(start_date=start, capital="10000", buy_budget="3000",
                       entry_offset_pct="-2", take_profit_pct="6", strategy="S1")["account_id"]
    state = api.state(first)
    assert state["entry_offset_pct"] == "-2"
    assert state["take_profit_pct"] == "6"
    assert state["buy_budget"] == "3000"
    with pytest.raises(ValueError, match="Buy budget"):
        api.create(start_date=start, capital="10000", buy_budget="11000")
    with pytest.raises(ValueError, match="Only S1"):
        api.create(start_date=start, strategy="S2", entry_offset_pct="-2")
    with pytest.raises(ValueError, match="Unsupported replay strategy"):
        api.create(start_date=start, strategy="S3")


def test_local_api_create_advance_state_and_reject_cross_origin(tmp_path):
    frame = market()
    api = controller(tmp_path, frame)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(api))
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f"http://127.0.0.1:{server.server_port}"

    def get(path):
        with urlopen(base + path) as response:
            return json.load(response)

    def post(path, payload, origin=None):
        headers = {"Content-Type": "application/json"}
        if origin:
            headers["Origin"] = origin
        with urlopen(Request(base + path, data=json.dumps(payload).encode(),
                             headers=headers, method="POST")) as response:
            return json.load(response)

    try:
        assert get("/api/meta")["mode"] == "HISTORICAL_REPLAY"
        assert get("/api/accounts") == []
        start = frame.iloc[240]["date"].date().isoformat()
        created = post("/api/replay/create", {"start_date": start})
        account = created["account_id"]
        assert created["state"]["chart"]["price"] == []
        advanced = post(f"/api/replay/{account}/next", {})
        assert advanced["journal_date"] == start
        assert get(f"/api/replay/{account}/state")["days_processed"] == 1
        with pytest.raises(HTTPError) as error:
            post(f"/api/replay/{account}/next", {}, "http://evil.invalid")
        assert error.value.code == 403
        assert get(f"/api/replay/{account}/state")["days_processed"] == 1
        with pytest.raises(HTTPError) as error:
            post(f"/api/replay/{account}/hide", {}, "http://evil.invalid")
        assert error.value.code == 403
        assert post(f"/api/replay/{account}/hide", {})["hidden"] is True
        assert get("/api/accounts") == []
        assert len(get("/api/accounts/hidden")) == 1
        assert get(f"/api/replay/{account}/state")["days_processed"] == 1
        assert post(f"/api/replay/{account}/restore", {})["hidden"] is False
        assert len(get("/api/accounts")) == 1
        assert get("/api/accounts/hidden") == []
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


@pytest.mark.parametrize("start,capital", [
    ("2023-12-31", "10000000"), ("not-a-date", "10000000"),
    ("2025-12-31", "10000000"), ("2024-12-01", "-1"),
])
def test_invalid_start_or_capital_rejected(tmp_path, start, capital):
    api = controller(tmp_path, market())
    with pytest.raises(ValueError):
        api.create(start_date=start, capital=capital)
