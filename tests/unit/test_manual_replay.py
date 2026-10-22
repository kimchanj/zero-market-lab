"""Manual replay spends separate wallets only after the next observed open."""

from decimal import Decimal
import sqlite3

import pandas as pd
import pytest

from zero_market_lab.paper_trading.manual_replay import ManualReplayController


def test_two_currency_manual_orders_and_immutable_records(tmp_path):
    root = __import__("pathlib").Path(__file__).resolve().parents[2]
    dates = pd.to_datetime(["2026-08-25", "2026-08-26", "2026-08-27"])

    def frame(price):
        return pd.DataFrame({"date": dates, "open": [price] * 3,
                             "high": [price + 1] * 3, "low": [price - 1] * 3,
                             "close": [price] * 3, "volume": [1000] * 3})

    stocks = {"005930": frame(100), "NVDA": frame(10)}

    def loader(symbol):
        if symbol not in stocks:
            raise FileNotFoundError(symbol)
        return stocks[symbol], {"provider": "SYNTHETIC_TEST"}

    api = ManualReplayController(root, tmp_path / "manual.sqlite3", loader=loader)
    created = api.create(start_date="2026-08-25", initial_krw="1000", initial_usd="100")
    account = created["account_id"]
    with pytest.raises(ValueError, match="first replay day"):
        api.order(account, symbol="005930", side="BUY", budget="250")
    first = api.next_day(account)
    assert first["date"] == "2026-08-25"
    assert first["wallets"]["KRW"]["cash"] == "1000"
    assert Decimal(first["market_snapshot"]["005930"]["close"]) == 100
    api.order(account, symbol="005930", side="BUY", budget="250")
    pending = api.order(account, symbol="NVDA", side="BUY", budget="50")
    assert pending["wallets"]["KRW"]["cash"] == "1000"
    assert len(pending["pending_orders"]) == 2
    second = api.next_day(account)
    assert second["date"] == "2026-08-26"
    assert len(second["journal"]) == 2
    assert second["journal"][-1]["wallets"]["KRW"]["cash"] == second["wallets"]["KRW"]["cash"]
    assert second["journal"][-1]["wallets"]["KRW"]["equity"] == second["wallets"]["KRW"]["equity"]
    assert len(second["holdings"]) == 2
    assert Decimal(second["wallets"]["KRW"]["cash"]) == 800
    assert Decimal(second["wallets"]["USD"]["cash"]) > 50
    assert second["pending_orders"] == []
    with pytest.raises(ValueError, match="exceeds owned"):
        api.order(account, symbol="005930", side="SELL", quantity="3")
    api.order(account, symbol="005930", side="SELL", quantity="1")
    third = api.next_day(account)
    assert third["date"] == "2026-08-27"
    assert third["wallets"]["KRW"]["cash"] == "900"
    assert third["wallets"]["USD"]["cash"] == second["wallets"]["USD"]["cash"]
    assert next(item for item in third["holdings"] if item["symbol"] == "005930")["quantity"] == "1"
    with sqlite3.connect(api.db_path) as con, pytest.raises(sqlite3.DatabaseError, match="append-only"):
        con.execute("DELETE FROM manual_events WHERE account_id=?", (account,))
    assert ManualReplayController(root, api.db_path, loader=loader).state(account)["days_processed"] == 3
    extra = pd.DataFrame({"date": pd.to_datetime(["2026-08-28"]), "open": [100.0],
                          "high": [101.0], "low": [99.0], "close": [100.0], "volume": [1000]})
    stocks["005930"] = pd.concat([stocks["005930"], extra], ignore_index=True)
    restarted = ManualReplayController(root, api.db_path, loader=loader)
    assert restarted.state(account)["next_date"] == "2026-08-28"
    changed = stocks["005930"].copy()
    changed.loc[0, "close"] = 101.0
    stocks["005930"] = changed
    with pytest.raises(ValueError, match="snapshot changed"):
        ManualReplayController(root, api.db_path, loader=loader).state(account)
