"""Paper records advance one bar at a time and survive restart without rewriting history."""

from datetime import date
from decimal import Decimal
import json
import sqlite3

import pandas as pd
import pytest

from zero_market_lab.paper_trading.engine import (create_account, journal, open_store,
                                                  record_correction, run_day, status)


def prices():
    dates = pd.bdate_range("2024-01-01", periods=250)
    f = pd.DataFrame({"date": dates, "open": 100.0, "high": 101.0,
                      "low": 99.0, "close": 100.0, "volume": 1000})
    f.loc[241, ["open", "high", "low", "close"]] = [100, 110, 98, 100]
    f.loc[242, ["open", "high", "low", "close"]] = [101, 103, 100, 102]
    f.loc[243, ["open", "high", "low", "close"]] = [102, 106, 101, 104]
    return f


def setup_account(con, f, *, name="demo", capital=Decimal("500000")):
    return create_account(con, name=name, symbol="005930", currency="KRW",
                          capital=capital, start_date=f.iloc[240]["date"].date().isoformat())


def day(f, i):
    return f.iloc[i]["date"].date().isoformat()


PROVENANCE = {"provider": "SYNTHETIC_TEST", "retrieved_at": "2025-01-01T00:00:00+00:00",
              "adjustment": "UNADJUSTED"}


def test_buy_hold_sell_cash_benchmark_restart_and_immutable_config(tmp_path):
    db, f = tmp_path / "paper.sqlite3", prices()
    with open_store(db) as con:
        config = setup_account(con, f)
        initial = status(con, "demo")
        assert initial["cash"] == "500000" and initial["quantity"] == "0"
        assert initial["portfolio_value"] == "500000" and initial["days_processed"] == 0
        first = run_day(con, "demo", day(f, 240), f, PROVENANCE)
        assert first["cash"] == "500000" and first["quantity"] == "0"
        assert first["decision"] == "BUY" and first["execution_status"] == "NONE"
        assert first["s0_quantity"] != "0"
        assert run_day(con, "demo", day(f, 240), f, PROVENANCE) == first
        assert con.execute("SELECT count(*) FROM events WHERE account_id='demo'").fetchone()[0] == 3
        bought = run_day(con, "demo", day(f, 241), f, PROVENANCE)
        assert bought["execution_side"] == "BUY" and Decimal(bought["quantity"]) > 0
        assert bought["execution_status"] == "FILLED"  # today's high cannot sell today's new buy
        assert Decimal(bought["cash"]) < Decimal(first["cash"])
        assert bought["decision"] == "SELL"  # target is armed for a later bar
        assert Decimal(bought["portfolio_value"]) == Decimal(bought["cash"]) + Decimal(bought["quantity"]) * 100
        hold = run_day(con, "demo", day(f, 242), f, PROVENANCE)
        assert hold["decision"] == "HOLD" and hold["execution_status"] == "NONE"
        assert Decimal(hold["unrealized_pnl"]) > 0
        sold = run_day(con, "demo", day(f, 243), f, PROVENANCE)
        assert sold["execution_side"] == "SELL" and sold["quantity"] == "0"
        assert Decimal(sold["realized_pnl"]) > 0
        assert Decimal(sold["total_pnl"]) == Decimal(sold["realized_pnl"])
        assert sold["decision"] == "BUY"  # next-day reentry only
        assert Decimal(sold["portfolio_value"]) - Decimal(sold["s0_portfolio_value"]) == Decimal(sold["paper_minus_s0"])
        with pytest.raises(sqlite3.IntegrityError):
            con.execute("UPDATE accounts SET config='{}' WHERE account_id='demo'")
        con.rollback()
    with open_store(db) as con:
        restored = status(con, "demo")
        assert restored["days_processed"] == 4
        assert restored["last_journal"] == sold
        assert restored["config_hash"] == config["config_hash"]
        assert len(journal(con, "demo")) == 4


def test_lookahead_gap_and_prior_bar_correction_fail_closed(tmp_path):
    f, db = prices(), tmp_path / "paper.sqlite3"
    with open_store(db) as con:
        setup_account(con, f)
        original = run_day(con, "demo", day(f, 240), f, PROVENANCE)
        modified_future = f.copy()
        modified_future.loc[241:, ["open", "high", "low", "close"]] = [500, 501, 499, 500]
        assert run_day(con, "demo", day(f, 240), modified_future, PROVENANCE) == original
        with open_store(tmp_path / "independent.sqlite3") as other:
            setup_account(other, f)
            assert run_day(other, "demo", day(f, 240), modified_future, PROVENANCE) == original
        with pytest.raises(ValueError, match="next available"):
            run_day(con, "demo", day(f, 242), f, PROVENANCE)
        with pytest.raises(ValueError, match="MARKET_DATA_NOT_AVAILABLE"):
            run_day(con, "demo", "2024-12-28", f, PROVENANCE)
        changed_prior = f.copy()
        changed_prior.loc[240, "close"] = 99
        with pytest.raises(ValueError, match="Historical market bar changed"):
            run_day(con, "demo", day(f, 241), changed_prior, PROVENANCE)
        correction = record_correction(con, "demo", day(f, 241), "Vendor revised an old bar")
        assert correction["kind"] == "DATA_CORRECTION"
        assert len(journal(con, "demo")) == 1


def test_insufficient_capital_and_no_partial_commit(tmp_path, monkeypatch):
    import zero_market_lab.paper_trading.engine as paper
    f = prices()
    f.loc[241, ["open", "high", "low", "close"]] = [200, 205, 190, 200]
    with open_store(tmp_path / "paper.sqlite3") as con:
        setup_account(con, f, capital=Decimal("110"))
        first = run_day(con, "demo", day(f, 240), f, PROVENANCE)
        assert first["decision"] == "BUY"
        second = run_day(con, "demo", day(f, 241), f, PROVENANCE)
        assert second["order_status"] == "BUY_BLOCKED_INSUFFICIENT_CAPITAL"
        assert second["decision"] == "CASH" and second["quantity"] == "0"
        assert second["cash"] == "110"
        original = paper._event

        def fail_on_journal(connection, account, day, kind, payload):
            if kind == "JOURNAL":
                raise RuntimeError("synthetic persistence failure")
            return original(connection, account, day, kind, payload)

        monkeypatch.setattr(paper, "_event", fail_on_journal)
        with pytest.raises(RuntimeError, match="persistence failure"):
            run_day(con, "demo", day(f, 242), f, PROVENANCE)
        assert con.execute("SELECT count(*) FROM events WHERE observation_date=?",
                           (day(f, 242),)).fetchone()[0] == 0


def test_live_mode_requires_new_date_and_fresh_provenance(tmp_path):
    f = prices()
    with open_store(tmp_path / "paper.sqlite3") as con:
        create_account(con, name="live", symbol="005930", currency="KRW",
                       capital=Decimal(500000), start_date=date.today().isoformat(),
                       mode="LIVE_FORWARD")
        with pytest.raises(ValueError, match="before account start_date"):
            run_day(con, "live", day(f, 240), f, PROVENANCE)
        assert status(con, "live")["evidence_type"] == "PAPER_FORWARD"
        assert status(con, "live")["days_processed"] == 0


def test_live_forward_rejects_intraday_retrieval_and_accepts_later_refresh(tmp_path, monkeypatch):
    import zero_market_lab.paper_trading.engine as paper
    f = prices()
    observed = day(f, 249)
    clock = [date(2024, 1, 1)]
    monkeypatch.setattr(paper, "_market_today", lambda currency: clock[0])
    monkeypatch.setattr(paper, "_stamp", lambda: "2024-01-01T00:00:00+00:00")
    with open_store(tmp_path / "live.sqlite3") as con:
        create_account(con, name="live", symbol="005930", currency="KRW",
                       capital=Decimal(500000), start_date=observed, mode="LIVE_FORWARD")
        clock[0] = date(2025, 1, 1)
        with pytest.raises(ValueError, match="post-close"):
            run_day(con, "live", observed, f,
                    {**PROVENANCE, "retrieved_at": observed + "T02:00:00+00:00"})
        later = (pd.Timestamp(observed) + pd.Timedelta(days=1)).date().isoformat()
        result = run_day(con, "live", observed, f,
                         {**PROVENANCE, "retrieved_at": later + "T02:00:00+00:00"})
        assert result["evidence_type"] == "PAPER_FORWARD"
        assert status(con, "live")["days_processed"] == 1
