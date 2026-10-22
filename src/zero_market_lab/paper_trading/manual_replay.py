"""Append-only, local historical multi-asset manual paper portfolio.

Orders are entered after a replay day and filled no earlier than the selected
instrument's next observed open. KRW and USD wallets never convert or combine.
This is deliberately separate from immutable strategy/LIVE_FORWARD accounts.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import secrets
import sqlite3
from threading import RLock

from zero_market_lab.paper_trading.engine import (
    _bar_hash, _canonical, _d, _hash, _market_today, _money,
    _stamp, _validated_prices,
)
from zero_market_lab.asset_discovery.catalog import LocalOHLCVCatalog, load_universe
from zero_market_lab.simulator.execution import ConfigurableFeeModel, affordable_quantity
from zero_market_lab.simulator.models import CostConfig


def _manual_history_hash(frame):
    # Appending a float-valued row can promote an existing integer column to
    # float. Normalize numeric representations so unchanged prices keep their hash.
    return _hash({"bars": [
        {key: (str(row[key]) if key == "date" else str(_d(row[key]).normalize()))
         for key in ("date", "open", "high", "low", "close", "volume")}
        for _, row in frame.iterrows()]})


class ManualReplayController:
    FEE_RATE = Decimal("0.00015")
    FEE_VERSION = "paper-research-cost-v1"
    FILL_VERSION = "manual-next-observed-open-v1"

    def __init__(self, root: Path, db_path: Path, loader=None):
        self.db_path = db_path
        self.loader = loader or LocalOHLCVCatalog(root).load
        self.assets = {item["symbol"]: item for item in load_universe(
            root / "config/universe_seed_kr_us.json")}
        self.lock = RLock()
        self._cached_markets = None

    def _markets(self):
        if self._cached_markets is not None:
            return self._cached_markets
        result = {}
        for symbol, asset in self.assets.items():
            try:
                frame, provenance = self.loader(symbol)
                frame = _validated_prices(frame, symbol=symbol)
            except (FileNotFoundError, ValueError):
                continue
            result[symbol] = (frame, provenance, _manual_history_hash(frame), asset)
        if not result:
            raise FileNotFoundError("No local seed-universe OHLCV is available")
        self._cached_markets = result
        return result

    def meta(self):
        markets = self._markets()
        return {"mode": "HISTORICAL_MANUAL_REPLAY", "assets": [
            {"symbol": symbol, "name": asset["name"], "currency": asset["currency"],
             "first_date": frame.iloc[0]["date"], "last_date": frame.iloc[-1]["date"]}
            for symbol, (frame, _, _, asset) in markets.items()],
            "initial_krw": "10000000", "initial_usd": "0",
            "fee_model_version": self.FEE_VERSION, "fill_rule_version": self.FILL_VERSION}

    @contextmanager
    def _store(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.db_path, timeout=10)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("""CREATE TABLE IF NOT EXISTS manual_accounts (
            account_id TEXT PRIMARY KEY, created_at TEXT NOT NULL,
            config TEXT NOT NULL, config_hash TEXT NOT NULL)""")
        con.execute("""CREATE TABLE IF NOT EXISTS manual_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id TEXT NOT NULL REFERENCES manual_accounts(account_id),
            observation_date TEXT NOT NULL, kind TEXT NOT NULL,
            created_at TEXT NOT NULL, payload TEXT NOT NULL)""")
        con.execute("""CREATE UNIQUE INDEX IF NOT EXISTS unique_manual_day
            ON manual_events(account_id, observation_date) WHERE kind='DAY'""")
        for table in ("manual_accounts", "manual_events"):
            for action in ("UPDATE", "DELETE"):
                con.execute(f"""CREATE TRIGGER IF NOT EXISTS immutable_{table}_{action.lower()}
                    BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT, 'append-only manual replay'); END""")
        con.commit()
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    @staticmethod
    def _event(con, account_id, day, kind, payload):
        con.execute("INSERT INTO manual_events(account_id,observation_date,kind,created_at,payload) "
                    "VALUES (?,?,?,?,?)", (account_id, day, kind, _stamp(), _canonical(payload)))

    @staticmethod
    def _events(con, account_id):
        return [{"event_id": row["event_id"], "date": row["observation_date"],
                 "kind": row["kind"], **json.loads(row["payload"])} for row in con.execute(
            "SELECT event_id,observation_date,kind,payload FROM manual_events "
            "WHERE account_id=? ORDER BY event_id", (account_id,))]

    def _account(self, con, account_id, markets):
        row = con.execute("SELECT config,config_hash FROM manual_accounts WHERE account_id=?",
                          (account_id,)).fetchone()
        if row is None:
            raise KeyError("Manual replay account not found")
        config = json.loads(row["config"])
        for symbol, digest in config["data_hashes"].items():
            if symbol not in markets:
                raise ValueError("Frozen market snapshot changed; restore the original local data")
            frame = markets[symbol][0]
            frozen_end = config.get("data_last_dates", {}).get(symbol)
            observed_hash = (_manual_history_hash(frame.loc[frame["date"] <= frozen_end])
                             if frozen_end else markets[symbol][2])
            if observed_hash != digest:
                raise ValueError("Frozen market snapshot changed; restore the original local data")
        return config, row["config_hash"]

    def accounts(self):
        if not self.db_path.exists():
            return []
        with self._store() as con:
            return [{"account_id": row["account_id"], **json.loads(row["config"]),
                     "days_processed": con.execute(
                         "SELECT count(*) FROM manual_events WHERE account_id=? AND kind='DAY'",
                         (row["account_id"],)).fetchone()[0]}
                    for row in con.execute("SELECT account_id,config FROM manual_accounts "
                                           "ORDER BY created_at DESC")]

    def create(self, *, start_date: str, initial_krw: str, initial_usd: str):
        try:
            date.fromisoformat(start_date)
            krw, usd = Decimal(initial_krw), Decimal(initial_usd)
        except (ValueError, TypeError, InvalidOperation) as error:
            raise ValueError("Valid date, KRW cash, and USD cash required") from error
        if (not krw.is_finite() or not usd.is_finite() or krw != krw.to_integral_value()
                or usd != usd.quantize(Decimal("0.01")) or krw < 0 or usd < 0
                or krw + usd <= 0 or krw > 1_000_000_000 or usd > 1_000_000):
            raise ValueError("Cash must be nonnegative KRW whole units / USD cents")
        markets = self._markets()
        dates = self._dates(markets, start_date)
        if not dates:
            raise ValueError("Start date has no completed local market sessions")
        config = {"mode": "HISTORICAL_MANUAL_REPLAY", "start_date": start_date,
                  "initial_cash": {"KRW": str(krw), "USD": str(usd)},
                  "data_hashes": {symbol: item[2] for symbol, item in markets.items()},
                  "data_last_dates": {symbol: item[0].iloc[-1]["date"]
                                      for symbol, item in markets.items()},
                  "fee_model_version": self.FEE_VERSION,
                  "fill_rule_version": self.FILL_VERSION}
        account_id = f"manual-{start_date.replace('-', '')}-{secrets.token_hex(4)}"
        with self.lock, self._store() as con:
            con.execute("INSERT INTO manual_accounts VALUES (?,?,?,?)",
                        (account_id, _stamp(), _canonical(config), _hash(config)))
        return self.state(account_id)

    @staticmethod
    def _dates(markets, start):
        return sorted({day for frame, _, _, asset in markets.values()
                       for day in frame["date"]
                       if start <= day <= _market_today(asset["currency"]).isoformat()})

    @staticmethod
    def _pending(events):
        resolved = {event["order_id"] for event in events if event["kind"] in {"FILL", "REJECT"}}
        return [event for event in events if event["kind"] == "ORDER"
                and event["event_id"] not in resolved]

    def order(self, account_id: str, *, symbol: str, side: str,
              budget: str | None = None, quantity: str | None = None):
        markets = self._markets()
        with self.lock, self._store() as con:
            self._account(con, account_id, markets)
            events = self._events(con, account_id)
            days = [event for event in events if event["kind"] == "DAY"]
            if not days:
                raise ValueError("Run the first replay day before entering an order")
            if symbol not in markets or side not in {"BUY", "SELL"}:
                raise ValueError("Select a supported asset and BUY or SELL")
            if any(event["symbol"] == symbol for event in self._pending(events)):
                raise ValueError("An order for this asset is already pending")
            latest = days[-1]
            currency = markets[symbol][3]["currency"]
            if side == "BUY":
                try:
                    amount = Decimal(budget)
                except (TypeError, InvalidOperation) as error:
                    raise ValueError("Enter a buy budget") from error
                precision = Decimal(1) if currency == "KRW" else Decimal("0.01")
                if (not amount.is_finite() or amount != amount.quantize(precision)
                        or not 0 < amount <= Decimal(latest["wallets"][currency]["cash"])):
                    raise ValueError("Buy budget exceeds available cash or has invalid precision")
                details = {"budget": str(amount)}
            else:
                try:
                    shares = Decimal(quantity)
                except (TypeError, InvalidOperation) as error:
                    raise ValueError("Enter whole shares to sell") from error
                owned = Decimal(latest["holdings"].get(symbol, {}).get("quantity", "0"))
                if not shares.is_finite() or shares != shares.to_integral_value() or not 0 < shares <= owned:
                    raise ValueError("Sell quantity exceeds owned whole shares")
                details = {"quantity": str(shares)}
            self._event(con, account_id, latest["date"], "ORDER",
                        {"symbol": symbol, "side": side, "currency": currency,
                         "submitted_after": latest["date"], "execution_rule": self.FILL_VERSION,
                         **details})
        return self.state(account_id)

    def next_day(self, account_id: str):
        markets = self._markets()
        with self.lock, self._store() as con:
            config, config_hash = self._account(con, account_id, markets)
            events = self._events(con, account_id)
            days = [event for event in events if event["kind"] == "DAY"]
            latest = days[-1] if days else None
            remaining = [day for day in self._dates(markets, config["start_date"])
                         if latest is None or day > latest["date"]]
            if not remaining:
                return self.state(account_id)
            day = remaining[0]
            wallets = {currency: dict(values) for currency, values in (
                latest["wallets"] if latest else {
                    currency: {"cash": value, "realized_pnl": "0"}
                    for currency, value in config["initial_cash"].items()}).items()}
            holdings = {symbol: dict(values) for symbol, values in (
                latest["holdings"] if latest else {}).items()}
            fills = []
            for order in self._pending(events):
                symbol = order["symbol"]
                frame, _, _, asset = markets[symbol]
                row = frame.loc[frame["date"] == day]
                if order["date"] >= day or row.empty:
                    continue
                price = _d(row.iloc[0]["open"])
                currency = asset["currency"]
                fees = ConfigurableFeeModel(CostConfig(
                    buy_fee_rate=self.FEE_RATE, sell_fee_rate=self.FEE_RATE,
                    sell_tax_rate=Decimal(0)), 0 if currency == "KRW" else 2)
                wallet = wallets[currency]
                existing = holdings.get(symbol, {"quantity": "0", "cost": "0"})
                if order["side"] == "BUY":
                    available = min(_d(order["budget"]), _d(wallet["cash"]))
                    shares = affordable_quantity(available, price, Decimal(1), fees, Decimal(0))
                    if not shares:
                        self._event(con, account_id, day, "REJECT",
                                    {"order_id": order["event_id"], "reason": "NOT_AFFORDABLE"})
                        continue
                    gross = shares * price
                    fee = fees.buy_fee(gross)
                    used = gross + fee
                    wallet["cash"] = str(_money(_d(wallet["cash"]) - used, currency))
                    holdings[symbol] = {"quantity": str(_d(existing["quantity"]) + shares),
                                        "cost": str(_money(_d(existing["cost"]) + used, currency))}
                    proceeds = None
                else:
                    shares = _d(order["quantity"])
                    owned = _d(existing["quantity"])
                    if shares > owned or owned <= 0:
                        self._event(con, account_id, day, "REJECT",
                                    {"order_id": order["event_id"], "reason": "INSUFFICIENT_SHARES"})
                        continue
                    gross = shares * price
                    fee = fees.sell_fee(gross)
                    proceeds = _money(gross - fee, currency)
                    allocated = _money(_d(existing["cost"]) * shares / owned, currency)
                    wallet["cash"] = str(_money(_d(wallet["cash"]) + proceeds, currency))
                    wallet["realized_pnl"] = str(_money(
                        _d(wallet["realized_pnl"]) + proceeds - allocated, currency))
                    left = owned - shares
                    if left:
                        holdings[symbol] = {"quantity": str(left),
                                            "cost": str(_money(_d(existing["cost"]) - allocated, currency))}
                    else:
                        holdings.pop(symbol, None)
                fill = {"order_id": order["event_id"], "symbol": symbol, "side": order["side"],
                        "currency": currency, "quantity": str(shares), "price": str(price),
                        "gross": str(gross), "fee": str(fee),
                        "cash_after": wallet["cash"], "net_proceeds": str(proceeds) if proceeds is not None else None,
                        "data_bar_hash": _bar_hash(row.iloc[0]),
                        "fee_model_version": self.FEE_VERSION,
                        "fill_rule_version": self.FILL_VERSION}
                self._event(con, account_id, day, "FILL", fill)
                fills.append(fill)
            marks = {}
            for symbol, held in holdings.items():
                frame, _, _, _ = markets[symbol]
                known = frame.loc[frame["date"] <= day]
                if known.empty:
                    raise ValueError("Held asset lacks a historical mark")
                bar = known.iloc[-1]
                marks[symbol] = {"close": str(bar["close"]), "market_date": bar["date"],
                                 "bar_hash": _bar_hash(bar)}
            self._event(con, account_id, day, "DAY",
                        {"wallets": wallets, "holdings": holdings, "marks": marks,
                         "config_hash": config_hash, "fills": fills,
                         "data_sources": {symbol: item[1].get("provider", "UNVERIFIED")
                                          for symbol, item in markets.items()}})
        return self.state(account_id)

    def state(self, account_id: str):
        markets = self._markets()
        with self.lock, self._store() as con:
            config, config_hash = self._account(con, account_id, markets)
            events = self._events(con, account_id)
        days = [event for event in events if event["kind"] == "DAY"]
        latest = days[-1] if days else None
        wallets = latest["wallets"] if latest else {
            currency: {"cash": value, "realized_pnl": "0"}
            for currency, value in config["initial_cash"].items()}
        holdings = latest["holdings"] if latest else {}
        marks = latest["marks"] if latest else {}
        rows = []
        totals = {currency: {"cash": values["cash"], "purchase": "0", "valuation": "0",
                             "realized_pnl": values["realized_pnl"], "unrealized_pnl": "0",
                             "initial": config["initial_cash"][currency]}
                  for currency, values in wallets.items()}
        for symbol, held in holdings.items():
            asset = markets[symbol][3]
            currency = asset["currency"]
            qty, cost = _d(held["quantity"]), _d(held["cost"])
            close = _d(marks[symbol]["close"])
            value = _money(qty * close, currency)
            pnl = value - cost
            rows.append({"symbol": symbol, "name": asset["name"], "currency": currency,
                         "quantity": str(qty), "average_cost": str(_money(cost / qty, currency)),
                         "purchase": str(cost), "close": str(close), "valuation": str(value),
                         "unrealized_pnl": str(pnl),
                         "return_pct": str(pnl / cost * 100) if cost else "0",
                         "market_date": marks[symbol]["market_date"]})
            totals[currency]["purchase"] = str(_d(totals[currency]["purchase"]) + cost)
            totals[currency]["valuation"] = str(_d(totals[currency]["valuation"]) + value)
            totals[currency]["unrealized_pnl"] = str(
                _d(totals[currency]["unrealized_pnl"]) + pnl)
        for values in totals.values():
            values["equity"] = str(_d(values["cash"]) + _d(values["valuation"]))
            values["total_pnl"] = str(_d(values["equity"]) - _d(values["initial"]))
            values["return_pct"] = str(_d(values["total_pnl"]) / _d(values["initial"]) * 100) if _d(values["initial"]) else None
        remaining = [day for day in self._dates(markets, config["start_date"])
                     if latest is None or day > latest["date"]]
        daily_journal = []
        for day in days:
            daily_wallets = {}
            for currency, wallet in day["wallets"].items():
                valuation = sum((
                    _d(position["quantity"]) * _d(day["marks"][symbol]["close"])
                    for symbol, position in day["holdings"].items()
                    if markets[symbol][3]["currency"] == currency
                ), Decimal("0"))
                daily_wallets[currency] = {
                    "cash": wallet["cash"],
                    "equity": str(_money(_d(wallet["cash"]) + valuation, currency)),
                }
            daily_journal.append({"date": day["date"], "wallets": daily_wallets,
                                  "fills": day["fills"],
                                  "positions": len(day["holdings"])})
        market_snapshot = {}
        if latest:
            for symbol, (frame, provenance, _, asset) in markets.items():
                known = frame.loc[frame["date"] <= latest["date"]]
                if known.empty:
                    continue
                bar = known.iloc[-1]
                market_snapshot[symbol] = {"date": bar["date"],
                                           "open": str(bar["open"]),
                                           "high": str(bar["high"]),
                                           "low": str(bar["low"]),
                                           "close": str(bar["close"]),
                                           "volume": str(bar["volume"]),
                                           "currency": asset["currency"],
                                           "provider": provenance.get("provider", "UNVERIFIED")}
        return {"account_id": account_id, "mode": config["mode"],
                "start_date": config["start_date"], "date": latest["date"] if latest else None,
                "next_date": remaining[0] if remaining else None,
                "config_hash": config_hash, "fee_model_version": self.FEE_VERSION,
                "fill_rule_version": self.FILL_VERSION,
                "wallets": totals, "holdings": rows, "pending_orders": self._pending(events),
                "recent_events": [event for event in events if event["kind"] in {"FILL", "REJECT"}][-20:][::-1],
                "journal": daily_journal,
                "market_snapshot": market_snapshot,
                "days_processed": len(days)}
