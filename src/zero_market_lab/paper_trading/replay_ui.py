"""Read-only presentation and one-session controller for historical Paper replay.

All decisions, fills, accounting, and S0 values come from the frozen Paper
engine. This module only chooses the next observed date and projects records
for a local browser; it cannot access or advance LIVE_FORWARD accounts.
"""

from __future__ import annotations

from zero_market_lab.transit.calendar import at_market_close
from zero_market_lab.transit.calendar import year_calendar
from zero_market_lab.transit.metrics import gate_market_metrics

from datetime import date
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import secrets

import pandas as pd

from zero_market_lab.asset_discovery.catalog import LocalOHLCVCatalog, load_universe
from zero_market_lab.paper_trading.engine import (
    _market_today, _validated_prices, create_account, journal, open_store, run_day, status,
)


class ReplayController:
    STRATEGIES = {"S0": "S0_BUY_AND_HOLD", "S1": "S1_FIXED_TAKE_PROFIT",
                  "S2": "S2_FIXED_TP_SL", "S7": "S7_BREAKOUT_TREND_FOLLOWING"}
    def __init__(self, root: Path, db_path: Path, loader=None):
        self.root = root
        self.db_path = db_path
        self.loader = loader or LocalOHLCVCatalog(root).load
        universe = root / "config/universe_seed_kr_us.json"
        assets = load_universe(universe) if universe.exists() else [
            {"symbol": "000660", "name": "SK hynix", "currency": "KRW"}]
        self.assets = {asset["symbol"]: asset for asset in assets}

    def _asset(self, symbol: str) -> dict:
        if symbol not in self.assets:
            raise ValueError("Asset is outside the supported seed universe")
        return self.assets[symbol]

    def _market(self, symbol: str) -> tuple[pd.DataFrame, dict]:
        self._asset(symbol)
        frame, provenance = self.loader(symbol)
        return _validated_prices(frame, symbol=symbol), provenance

    def _config(self, con, account_id: str) -> dict:
        row = con.execute("SELECT config FROM accounts WHERE account_id=?", (account_id,)).fetchone()
        if row is None:
            raise KeyError("Replay account does not exist")
        cfg = json.loads(row["config"])
        if cfg["mode"] != "HISTORICAL_REPLAY" or cfg["symbol"] not in self.assets:
            raise ValueError("Only supported historical replay accounts are available in this UI")
        return cfg

    def meta(self, symbol: str | None = None) -> dict:
        available = []
        for candidate in self.assets.values():
            try:
                candidate_frame, _ = self._market(candidate["symbol"])
            except (FileNotFoundError, ValueError):
                continue
            if (candidate_frame["date"] <= _market_today(candidate["currency"]).isoformat()).any():
                available.append({"symbol": candidate["symbol"], "name": candidate["name"],
                                  "currency": candidate["currency"]})
        if not available:
            raise ValueError("No completed local daily bars are available")
        symbol = symbol or ("000660" if any(a["symbol"] == "000660" for a in available)
                            else available[0]["symbol"])
        asset = self._asset(symbol)
        if not any(a["symbol"] == symbol for a in available):
            raise FileNotFoundError(f"Local daily bars unavailable for {symbol}")
        frame, provenance = self._market(symbol)
        eligible = frame.loc[frame["date"] <= _market_today(asset["currency"]).isoformat()]
        return {"mode": "HISTORICAL_REPLAY", "symbol": symbol, "asset_name": asset["name"],
                "currency": asset["currency"], "available_assets": available,
                "available_strategies": [
                    {"code": "S0", "name": "S0 Buy & Hold"},
                    {"code": "S1", "name": "S1 Fixed Take Profit"},
                    {"code": "S2", "name": "S2 Fixed TP / SL"},
                    {"code": "S7", "name": "S7 Breakout Trend Following"}],
                "strategy_id": "S1_FIXED_TAKE_PROFIT",
                "default_capital": "10000000" if asset["currency"] == "KRW" else "10000",
                "first_observation": eligible.iloc[0]["date"],
                "latest_observation": eligible.iloc[-1]["date"],
                "suggested_start": eligible.iloc[max(0, len(eligible) - 30)]["date"],
                "provider": provenance.get("provider", "UNVERIFIED"),
                "adjustment": provenance.get("adjustment", "UNKNOWN")}

    def accounts(self) -> list[dict]:
        return self._listed_accounts(hidden_only=False)

    def hidden_accounts(self) -> list[dict]:
        return self._listed_accounts(hidden_only=True)

    def _listed_accounts(self, *, hidden_only: bool) -> list[dict]:
        if not self.db_path.exists():
            return []
        with open_store(self.db_path) as con:
            self._ensure_hidden_table(con)
            rows = con.execute("SELECT account_id, config, created_at FROM accounts ORDER BY created_at DESC").fetchall()
            hidden = {row["account_id"] for row in con.execute(
                "SELECT account_id FROM replay_hidden_accounts")}
            result = []
            for row in rows:
                if (row["account_id"] in hidden) != hidden_only:
                    continue
                cfg = json.loads(row["config"])
                if cfg["mode"] == "HISTORICAL_REPLAY" and cfg["symbol"] in self.assets:
                    state = status(con, row["account_id"])
                    result.append({"account_id": row["account_id"],
                                   "symbol": cfg["symbol"], "asset_name": self.assets[cfg["symbol"]]["name"],
                                   "currency": cfg["currency"],
                                   "strategy_id": cfg["strategy_id"],
                                   "start_date": cfg["start_date"],
                                   "capital": cfg["initial_capital"],
                                   "days_processed": state["days_processed"],
                                   "last_date": (state["last_journal"] or {}).get("journal_date"),
                                   "created_at": row["created_at"]})
            return result

    @staticmethod
    def _ensure_hidden_table(con) -> None:
        # UI preference only; the append-only account, event, and Journal tables stay intact.
        con.execute("CREATE TABLE IF NOT EXISTS replay_hidden_accounts "
                    "(account_id TEXT PRIMARY KEY, hidden_at TEXT NOT NULL)")

    def hide_account(self, account_id: str) -> dict:
        with open_store(self.db_path) as con:
            self._config(con, account_id)
            self._ensure_hidden_table(con)
            con.execute("INSERT OR IGNORE INTO replay_hidden_accounts VALUES (?, datetime('now'))",
                        (account_id,))
            con.commit()
        return {"account_id": account_id, "hidden": True}

    def restore_account(self, account_id: str) -> dict:
        with open_store(self.db_path) as con:
            self._config(con, account_id)
            self._ensure_hidden_table(con)
            con.execute("DELETE FROM replay_hidden_accounts WHERE account_id=?", (account_id,))
            con.commit()
        return {"account_id": account_id, "hidden": False}

    def create(self, *, start_date: str, capital: str = "10000000",
               symbol: str = "000660", strategy: str = "S1",
               entry_offset_pct: str = "-1", take_profit_pct: str = "5",
               buy_budget: str | None = None) -> dict:
        asset = self._asset(symbol)
        if strategy not in self.STRATEGIES:
            raise ValueError("Unsupported replay strategy")
        try:
            amount = Decimal(capital)
            entry_offset = Decimal(entry_offset_pct)
            take_profit = Decimal(take_profit_pct)
            budget = Decimal(buy_budget) if buy_budget is not None else None
        except (InvalidOperation, TypeError) as error:
            raise ValueError("Capital, buy budget, and S1 percentages must be numeric") from error
        minimum = 10000 if asset["currency"] == "KRW" else 100
        if not amount.is_finite() or amount != amount.to_integral_value() or not minimum <= amount <= 1000000000:
            raise ValueError(f"Initial capital must be {minimum:,}–1,000,000,000 whole {asset['currency']}")
        if (not entry_offset.is_finite() or not take_profit.is_finite()
                or not -20 <= entry_offset <= 0 or not 0 < take_profit <= 100):
            raise ValueError("S1 entry must be -20–0% and take-profit must be 0–100%")
        if strategy != "S1" and (entry_offset != -1 or take_profit != 5):
            raise ValueError("Only S1 accepts custom entry and take-profit percentages")
        if budget is not None and (not budget.is_finite() or budget != budget.to_integral_value()
                                   or not 0 < budget <= amount):
            raise ValueError("Buy budget must be a whole positive amount no greater than capital")
        try:
            date.fromisoformat(start_date)
        except (TypeError, ValueError) as error:
            raise ValueError("Start date must use YYYY-MM-DD") from error
        frame, _ = self._market(symbol)
        eligible = frame.loc[(frame["date"] >= start_date) &
                             (frame["date"] <= _market_today(asset["currency"]).isoformat())]
        if eligible.empty or start_date < frame.iloc[0]["date"]:
            raise ValueError("Start date is outside completed local market data")
        account_id = f"replay-{symbol}-{start_date.replace('-', '')}-{secrets.token_hex(4)}"
        with open_store(self.db_path) as con:
            created = create_account(con, name=account_id, symbol=symbol, currency=asset["currency"],
                                     capital=amount, start_date=start_date,
                                     mode="HISTORICAL_REPLAY", strategy_id=self.STRATEGIES[strategy],
                                     entry_offset_pct=entry_offset, tp_pct=take_profit,
                                     buy_budget=budget)
        return {"account_id": account_id, "config_hash": created["config_hash"],
                "first_session": eligible.iloc[0]["date"], "state": self.state(account_id)}

    def next_day(self, account_id: str) -> dict:
        with open_store(self.db_path) as con:
            cfg = self._config(con, account_id)
            current = status(con, account_id)
            frame, provenance = self._market(cfg["symbol"])
            last_date = (current["last_journal"] or {}).get("journal_date")
            remaining = frame.loc[(frame["date"] >= cfg["start_date"]) &
                                  (frame["date"] <= _market_today(cfg["currency"]).isoformat())]
            if last_date:
                remaining = remaining.loc[remaining["date"] > last_date]
            if remaining.empty:
                return {"result": "REPLAY_COMPLETE", "state": self.state(account_id)}
            as_of = remaining.iloc[0]["date"]
            recorded = run_day(con, account_id, as_of, frame, provenance)
        return {"result": "DAY_RECORDED", "journal_date": recorded["journal_date"],
                "state": self.state(account_id)}

    def transit_metrics(self, symbol: str, year: int, gate: int,
                        as_of: str | None = None) -> dict:
        asset = self._asset(symbol)
        calendar = year_calendar(year)
        if not 1 <= gate <= 64:
            raise ValueError("Gate must be 1–64")
        if as_of:
            date.fromisoformat(as_of)
        intervals = [item for item in calendar["gates"] if item["gate"] == gate]
        frame, provenance = self._market(symbol)
        parts = [gate_market_metrics(frame, gate=gate, start=item["start_utc"],
                                     end=item["end_utc"], currency=asset["currency"],
                                     as_of=as_of) for item in intervals]
        return {"symbol": symbol, "year": year, "gate": gate,
                "intervals": intervals, "metrics": parts,
                "market_provenance": provenance,
                "transit_provenance": calendar["provenance"]}

    def transit_market_year(self, symbol: str, year: int) -> dict:
        asset = self._asset(symbol)
        year_calendar(year)  # validate range and retain a separate calendar source
        frame, provenance = self._market(symbol)
        today = _market_today(asset["currency"]).isoformat()
        visible = frame.loc[(frame["date"] >= f"{year}-01-01") &
                            (frame["date"] <= f"{year}-12-31") &
                            (frame["date"] <= today)]
        return {"symbol": symbol, "year": year,
                "bars": [self._bar(row) for _, row in visible.iterrows()],
                "first_observed": visible.iloc[0]["date"] if not visible.empty else None,
                "last_observed": visible.iloc[-1]["date"] if not visible.empty else None,
                "complete_calendar_year": year < date.fromisoformat(today).year,
                "provenance": provenance,
                "mode": "READ_ONLY_HISTORICAL_RESEARCH"}

    def state(self, account_id: str, view_date: str | None = None) -> dict:
        with open_store(self.db_path) as con:
            cfg = self._config(con, account_id)
            current = status(con, account_id)
            all_days = journal(con, account_id)
            if view_date and view_date not in {row["journal_date"] for row in all_days}:
                raise ValueError("View date must be a processed Journal date")
            selected = view_date or ((all_days[-1]["journal_date"]) if all_days else None)
            days = [row for row in all_days if selected and row["journal_date"] <= selected]
            latest = days[-1] if days else None
            events = con.execute(
                "SELECT observation_date, kind, payload FROM events WHERE account_id=? "
                "ORDER BY observation_date, kind", (account_id,)).fetchall()
        by_date: dict[str, dict] = {}
        for item in events:
            if selected and item["observation_date"] <= selected and item["kind"] in {"DECISION", "ORDER", "EXECUTION"}:
                by_date.setdefault(item["observation_date"], {})[item["kind"].lower()] = json.loads(item["payload"])
        frame, provenance = self._market(cfg["symbol"])
        visible = frame.loc[(frame["date"] >= cfg["start_date"]) &
                            (frame["date"] <= selected)] if selected else frame.iloc[0:0]
        observed = frame.loc[(frame["date"] >= cfg["start_date"]) &
                             (frame["date"] <= _market_today(cfg["currency"]).isoformat())]
        after = observed.loc[observed["date"] > (all_days[-1]["journal_date"] if all_days else "")]
        next_session = after.iloc[0]["date"] if not after.empty else None
        rows = []
        for day in days:
            day_date = day["journal_date"]
            market_row = visible.loc[visible["date"] == day_date].iloc[0]
            rows.append({"journal": day, "market": self._bar(market_row),
                         **by_date.get(day_date, {})})
        pending = self._pending(days, by_date)
        previous_close = Decimal(days[-2]["close"]) if len(days) > 1 else None
        price_change_pct = (str(((Decimal(latest["close"]) / previous_close - 1) * 100)
                                .quantize(Decimal("0.01"))) if latest and previous_close else None)
        entry_date = None
        if latest and Decimal(latest["quantity"]) > 0:
            buys = [date_key for date_key, event in by_date.items()
                    if event.get("execution", {}).get("side") == "BUY"]
            entry_date = buys[-1] if buys else None
        return {"account_id": account_id, "mode": cfg["mode"], "evidence_type": "HISTORICAL_REPLAY",
                "symbol": cfg["symbol"], "asset_name": self._asset(cfg["symbol"])["name"],
                "currency": cfg["currency"], "strategy_id": cfg["strategy_id"],
                "entry_offset_pct": cfg["entry_offset_pct"], "take_profit_pct": cfg["tp_pct"],
                "stop_loss_pct": cfg.get("stop_loss_pct"), "buy_budget": cfg.get("buy_budget"),
                "strategy_version": cfg["strategy_version"], "phase_role": "CONTEXT_ONLY",
                "initial_capital": cfg["initial_capital"], "start_date": cfg["start_date"],
                "config_hash": current["config_hash"], "latest_processed_date":
                (all_days[-1]["journal_date"] if all_days else None), "view_date": selected,
                "days_processed": current["days_processed"], "next_session": next_session,
                "replay_complete": next_session is None, "viewing_history": bool(view_date and
                view_date != (all_days[-1]["journal_date"] if all_days else None)),
                "summary": self._summary(cfg, latest), "position": self._position(latest, entry_date, days, pending),
                "market": rows[-1]["market"] if rows else None,
                "price_change_pct": price_change_pct,
                "phase": latest["phase"] if latest else None,
                "signal": latest["signal"] if latest else None,
                "decision": by_date.get(selected, {}).get("decision") if selected else None,
                "order": by_date.get(selected, {}).get("order") if selected else None,
                "execution": by_date.get(selected, {}).get("execution") if selected else None,
                "pending_order": pending, "journal": rows,
                "transit": at_market_close(selected, cfg["currency"]) if selected else None,
                "chart": {"price": [self._bar(row) for _, row in visible.iterrows()],
                          "equity": [{"date": day["journal_date"], "strategy": day["portfolio_value"],
                                      "s0": day["s0_portfolio_value"]} for day in days],
                          "markers": self._markers(by_date)},
                "provenance": {"provider": provenance.get("provider"),
                               "adjustment": provenance.get("adjustment"),
                               "retrieved_at": provenance.get("retrieved_at")}}

    @staticmethod
    def _bar(row) -> dict:
        return {"date": row["date"], "open": float(row["open"]), "high": float(row["high"]),
                "low": float(row["low"]), "close": float(row["close"]), "volume": int(row["volume"])}

    @staticmethod
    def _summary(cfg: dict, latest: dict | None) -> dict:
        if not latest:
            return {"cash": cfg["initial_capital"], "quantity": "0", "market_value": "0",
                    "portfolio_value": cfg["initial_capital"], "realized_pnl": "0",
                    "unrealized_pnl": "0", "total_pnl": "0", "net_return_pct": "0",
                    "purchase_amount": "0", "valuation_return_pct": "0",
                    "s0_equity": None, "vs_s0": None, "vs_s0_pct": None}
        s0 = Decimal(latest["s0_portfolio_value"])
        purchase = Decimal(latest["entry_cost"]) if Decimal(latest["quantity"]) > 0 else Decimal(0)
        return {"cash": latest["cash"], "quantity": latest["quantity"],
                "market_value": latest["market_value"], "portfolio_value": latest["portfolio_value"],
                "realized_pnl": latest["realized_pnl"], "unrealized_pnl": latest["unrealized_pnl"],
                "total_pnl": latest["total_pnl"],
                "net_return_pct": str(Decimal(latest["net_return"]) * 100),
                "purchase_amount": str(purchase),
                "valuation_return_pct": str(Decimal(latest["unrealized_pnl"]) / purchase * 100) if purchase else "0",
                "s0_equity": latest["s0_portfolio_value"], "vs_s0": latest["paper_minus_s0"],
                "vs_s0_pct": str(Decimal(latest["paper_minus_s0"]) / s0 * 100) if s0 else None}

    @staticmethod
    def _pending(days: list[dict], by_date: dict[str, dict]) -> dict | None:
        if not days:
            return None
        latest = days[-1]
        executed = {event["execution"]["order_id"] for event in by_date.values() if "execution" in event}
        orders = [event["order"] for event in by_date.values() if "order" in event]
        for order in reversed(orders):
            if order["order_id"] in executed:
                continue
            if order["side"] == "SELL" and Decimal(latest["quantity"]) > 0:
                return order
            if order["side"] == "BUY" and order["valid_after"] == latest["journal_date"]:
                return order
        return None

    @staticmethod
    def _position(latest: dict | None, entry_date: str | None,
                  days: list[dict], pending: dict | None) -> dict:
        if not latest or Decimal(latest["quantity"]) == 0:
            return {"status": "NO POSITION", "quantity": "0", "average_entry": None,
                    "entry_date": None, "hold_days": 0, "close": latest["close"] if latest else None,
                    "market_value": "0", "unrealized_pnl": "0", "take_profit_price": None,
                    "stop_loss_price": None}
        return {"status": "OPEN", "quantity": latest["quantity"],
                "average_entry": latest["average_entry_price"], "entry_date": entry_date,
                "hold_days": sum(day["journal_date"] >= entry_date for day in days) if entry_date else None,
                "close": latest["close"], "market_value": latest["market_value"],
                "unrealized_pnl": latest["unrealized_pnl"],
                "take_profit_price": (pending["requested_price"] if pending and
                                      pending["side"] == "SELL" and
                                      pending["requested_price"] != "NEXT_OPEN" else None),
                "stop_loss_price": pending.get("stop_price") if pending else None}

    @staticmethod
    def _markers(by_date: dict[str, dict]) -> list[dict]:
        markers = []
        for day, event in by_date.items():
            decision = event.get("decision", {}).get("decision")
            if decision in {"BUY", "SELL"}:
                markers.append({"date": day, "kind": "DECISION", "side": decision})
            execution = event.get("execution", {}).get("side")
            if execution in {"BUY", "SELL"}:
                markers.append({"date": day, "kind": "EXECUTION", "side": execution})
        return markers
