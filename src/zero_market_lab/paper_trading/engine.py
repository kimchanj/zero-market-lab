"""One daily bar at a time. Close decisions can execute no earlier than the next bar."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo

import pandas as pd

from zero_market_lab.market_phase.engine import PhaseEngine, RULE_CONFIG_HASH, VERSION as PHASE_VERSION
from zero_market_lab.simulator.execution import (ConfigurableFeeModel, affordable_quantity,
                                                  quantize_money, required_buy_cash)
from zero_market_lab.simulator.models import CostConfig
from zero_market_lab.simulator.strategy_family import _to_tick

SCHEMA_VERSION = 1
STRATEGY_ID = "S1_FIXED_TAKE_PROFIT"
STRATEGY_VERSION = "strategy-family-s1-v1"
FILL_RULE_VERSION = "daily-ohlcv-s1-v1"
FEE_MODEL_VERSION = "paper-research-cost-v1"
MODES = ("HISTORICAL_REPLAY", "LIVE_FORWARD")


def _market_today(currency: str) -> date:
    return datetime.now(ZoneInfo("Asia/Seoul" if currency == "KRW" else "America/New_York")).date()


def _canonical(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value: dict) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _d(value) -> Decimal:
    return Decimal(str(value))


def _money(value: Decimal, currency: str) -> Decimal:
    return quantize_money(value, 0 if currency == "KRW" else 2)


def _stamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bar_hash(row: pd.Series) -> str:
    return _hash({key: str(row[key]) for key in ("date", "open", "high", "low", "close", "volume")})


def _history_hash(frame: pd.DataFrame) -> str:
    return _hash({"bars": [_bar_hash(row) for _, row in frame.iterrows()]})


def open_store(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("CREATE TABLE IF NOT EXISTS schema_meta (version INTEGER NOT NULL)")
    version = con.execute("SELECT version FROM schema_meta").fetchone()
    if version is None:
        con.execute("INSERT INTO schema_meta VALUES (?)", (SCHEMA_VERSION,))
    elif version[0] != SCHEMA_VERSION:
        raise ValueError(f"Unsupported paper schema version: {version[0]}")
    con.execute("""CREATE TABLE IF NOT EXISTS accounts (
        account_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, config TEXT NOT NULL,
        config_hash TEXT NOT NULL)""")
    con.execute("""CREATE TABLE IF NOT EXISTS events (
        event_id TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts(account_id),
        observation_date TEXT NOT NULL, kind TEXT NOT NULL, created_at TEXT NOT NULL,
        payload TEXT NOT NULL, UNIQUE(account_id, observation_date, kind))""")
    con.execute("CREATE INDEX IF NOT EXISTS events_by_account ON events(account_id, observation_date, kind)")
    for table in ("accounts", "events"):
        for action in ("UPDATE", "DELETE"):
            con.execute(f"""CREATE TRIGGER IF NOT EXISTS immutable_{table}_{action.lower()}
                BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT, 'append-only paper record'); END""")
    con.commit()
    return con


def _event(con: sqlite3.Connection, account: str, day: str, kind: str, payload: dict) -> None:
    con.execute("INSERT INTO events VALUES (?,?,?,?,?,?)",
                (f"{account}:{day}:{kind}", account, day, kind, _stamp(), _canonical(payload)))


def _records(con: sqlite3.Connection, account: str, kind: str) -> list[dict]:
    return [json.loads(row["payload"]) for row in con.execute(
        "SELECT payload FROM events WHERE account_id=? AND kind=? ORDER BY observation_date",
        (account, kind))]


def create_account(con: sqlite3.Connection, *, name: str, symbol: str, currency: str,
                   capital: Decimal, start_date: str, mode: str = "HISTORICAL_REPLAY",
                   entry_offset_pct: Decimal = Decimal("-1"), tp_pct: Decimal = Decimal("5"),
                   buy_fee_rate: Decimal = Decimal("0.00015"),
                   sell_fee_rate: Decimal = Decimal("0.00015"),
                   sell_tax_rate: Decimal = Decimal(0),
                   slippage_rate: Decimal = Decimal(0)) -> dict:
    date.fromisoformat(start_date)
    if (not name or ":" in name or mode not in MODES or capital <= 0
            or currency not in {"KRW", "USD"} or not (-20 <= entry_offset_pct <= 0)
            or not (0 < tp_pct <= 100) or any(x < 0 for x in
                    (buy_fee_rate, sell_fee_rate, sell_tax_rate, slippage_rate))
            or any(x >= 1 for x in (buy_fee_rate, sell_fee_rate, sell_tax_rate))
            or slippage_rate > Decimal("0.05")):
        raise ValueError("Invalid account configuration")
    if mode == "LIVE_FORWARD" and date.fromisoformat(start_date) < _market_today(currency):
        raise ValueError("LIVE_FORWARD start_date cannot be in the past")
    config = {"name": name, "symbol": symbol, "currency": currency,
              "start_date": start_date, "initial_capital": str(capital), "mode": mode,
              "strategy_id": STRATEGY_ID, "strategy_version": STRATEGY_VERSION,
              "entry_offset_pct": str(entry_offset_pct), "tp_pct": str(tp_pct),
              "buy_fee_rate": str(buy_fee_rate), "sell_fee_rate": str(sell_fee_rate),
              "sell_tax_rate": str(sell_tax_rate), "slippage_rate": str(slippage_rate),
              "fee_model_version": FEE_MODEL_VERSION,
              "fill_rule_version": FILL_RULE_VERSION,
              "phase_engine_version": PHASE_VERSION,
              "phase_rule_config_hash": RULE_CONFIG_HASH}
    with con:
        con.execute("INSERT INTO accounts VALUES (?,?,?,?)",
                    (name, _stamp(), _canonical(config), _hash(config)))
    return {"account_id": name, "config_hash": _hash(config), "config": config}


def _account(con: sqlite3.Connection, account: str) -> tuple[dict, str, str]:
    row = con.execute("SELECT * FROM accounts WHERE account_id=?", (account,)).fetchone()
    if row is None:
        raise KeyError(f"Unknown paper account: {account}")
    cfg = json.loads(row["config"])
    if _hash(cfg) != row["config_hash"]:
        raise ValueError("Paper account configuration hash mismatch")
    return cfg, row["created_at"], row["config_hash"]


def _validated_prices(frame: pd.DataFrame, *, symbol: str) -> pd.DataFrame:
    required = {"date", "open", "high", "low", "close", "volume"}
    if frame.empty or not required.issubset(frame.columns):
        raise ValueError("OHLCV data unavailable")
    f = frame[list(required)].copy()
    f["date"] = pd.to_datetime(f["date"], errors="raise")
    if f["date"].isna().any() or f["date"].duplicated().any() or not f["date"].is_monotonic_increasing:
        raise ValueError("OHLCV dates must be unique and ascending")
    for key in ("open", "high", "low", "close", "volume"):
        f[key] = pd.to_numeric(f[key], errors="raise")
    if (f[["open", "high", "low", "close", "volume"]].isna().any().any()
            or (f[["open", "high", "low", "close"]] <= 0).any().any()
            or (f["volume"] < 0).any()
            or (f["high"] < f[["open", "close", "low"]].max(axis=1)).any()
            or (f["low"] > f[["open", "close", "high"]].min(axis=1)).any()):
        raise ValueError(f"Invalid OHLCV for {symbol}")
    f["date"] = f["date"].dt.strftime("%Y-%m-%d")
    return f


def status(con: sqlite3.Connection, account: str) -> dict:
    cfg, _, config_hash = _account(con, account)
    journal = _records(con, account, "JOURNAL")
    latest = journal[-1] if journal else None
    current = latest or {"cash": cfg["initial_capital"], "quantity": "0",
                         "portfolio_value": cfg["initial_capital"],
                         "realized_pnl": "0", "unrealized_pnl": "0", "total_pnl": "0"}
    return {"account_id": account, "mode": cfg["mode"], "evidence_type":
            "PAPER_FORWARD" if cfg["mode"] == "LIVE_FORWARD" else "HISTORICAL_REPLAY",
            "symbol": cfg["symbol"], "strategy_id": cfg["strategy_id"],
            "start_date": cfg["start_date"], "initial_capital": cfg["initial_capital"],
            "config_hash": config_hash, "last_journal": latest,
            **{field: current[field] for field in ("cash", "quantity", "portfolio_value",
                                                   "realized_pnl", "unrealized_pnl", "total_pnl")},
            "days_processed": len(journal)}


def journal(con: sqlite3.Connection, account: str) -> list[dict]:
    _account(con, account)
    return _records(con, account, "JOURNAL")


def run_day(con: sqlite3.Connection, account: str, as_of_date: str, frame: pd.DataFrame,
            provenance: dict) -> dict:
    """Process exactly the next observed date. Existing journal entries are immutable."""
    requested = date.fromisoformat(as_of_date)
    cfg, created_at, config_hash = _account(con, account)
    if requested > _market_today(cfg["currency"]):
        raise ValueError("as_of_date is in the future")
    if as_of_date < cfg["start_date"]:
        raise ValueError("Cannot create a paper result before account start_date")
    existing = con.execute("SELECT payload FROM events WHERE account_id=? AND observation_date=? AND kind='JOURNAL'",
                           (account, as_of_date)).fetchone()
    if existing:
        return json.loads(existing[0])
    prices = _validated_prices(frame, symbol=cfg["symbol"])
    prefix = prices.loc[prices["date"] <= as_of_date].reset_index(drop=True)
    if prefix.empty or prefix.iloc[-1]["date"] != as_of_date:
        raise ValueError("MARKET_DATA_NOT_AVAILABLE or NO_MARKET_SESSION; no journal appended")
    if cfg["mode"] == "LIVE_FORWARD":
        created_market_date = datetime.fromisoformat(created_at).astimezone(
            ZoneInfo("Asia/Seoul" if cfg["currency"] == "KRW" else "America/New_York")).date()
        if requested <= created_market_date:
            raise ValueError("LIVE_FORWARD requires a market date after account creation")
        retrieved = provenance.get("retrieved_at")
        if not retrieved:
            raise ValueError("LIVE_FORWARD requires a verified refresh after account creation")
        retrieved_at = datetime.fromisoformat(retrieved.replace("Z", "+00:00"))
        if retrieved_at.tzinfo is None:
            raise ValueError("LIVE_FORWARD requires timezone-aware provider retrieval time")
        retrieved_market_date = retrieved_at.astimezone(
            ZoneInfo("Asia/Seoul" if cfg["currency"] == "KRW" else "America/New_York")).date()
        if retrieved_at < datetime.fromisoformat(created_at) or retrieved_market_date <= requested:
            raise ValueError("LIVE_FORWARD requires a post-close refresh after the observation date")
    old = journal(con, account)
    dates = prefix["date"].tolist()
    possible = [d for d in dates if d >= cfg["start_date"] and (not old or d > old[-1]["journal_date"])]
    if not possible or possible[0] != as_of_date:
        raise ValueError("Process the next available market date first; no backfill or skip")
    if old:
        previous = old[-1]
        old_prefix = prefix.loc[prefix["date"] <= previous["journal_date"]]
        if (old_prefix.empty or old_prefix.iloc[-1]["date"] != previous["journal_date"]
                or _history_hash(old_prefix) != previous["source_history_hash"]):
            raise ValueError("Historical market bar changed; append correction event before review")
    row = prefix.iloc[-1]
    phase = PhaseEngine().run(prefix, symbol=cfg["symbol"],
                              data_source=provenance.get("provider", "UNVERIFIED"))["rows"][-1]
    currency = cfg["currency"]
    fee_config = CostConfig(buy_fee_rate=_d(cfg["buy_fee_rate"]),
                            sell_fee_rate=_d(cfg["sell_fee_rate"]),
                            sell_tax_rate=_d(cfg["sell_tax_rate"]))
    fees = ConfigurableFeeModel(fee_config, 0 if currency == "KRW" else 2)
    slip_rate = _d(cfg["slippage_rate"])
    capital = _d(cfg["initial_capital"])
    cash = _d(old[-1]["cash"]) if old else capital
    qty = _d(old[-1]["quantity"]) if old else Decimal(0)
    entry_price = _d(old[-1]["average_entry_price"]) if old else Decimal(0)
    entry_cost = _d(old[-1]["entry_cost"]) if old else Decimal(0)
    realized = _d(old[-1]["realized_pnl"]) if old else Decimal(0)
    bench_cash = _d(old[-1]["s0_cash"]) if old else capital
    bench_qty = _d(old[-1]["s0_quantity"]) if old else Decimal(0)
    open_price, high, low, close = (_d(row[key]) for key in ("open", "high", "low", "close"))
    stock = currency == "KRW"
    tick = Decimal(1) if stock else Decimal("0.01")
    execution = None
    order_status = "NONE"
    prior_orders = _records(con, account, "ORDER")
    pending_sell = next((o for o in reversed(prior_orders) if o["side"] == "SELL"
                         and not any(e["order_id"] == o["order_id"] for e in _records(con, account, "EXECUTION"))), None)
    prior_buy = (prior_orders[-1] if prior_orders and old and prior_orders[-1]["side"] == "BUY"
                 and prior_orders[-1]["valid_after"] == old[-1]["journal_date"] else None)
    if not old:  # S0 benchmark starts at first paper bar; S1 waits for its first close decision.
        bench_qty = affordable_quantity(bench_cash, open_price, Decimal(1), fees, slip_rate)
        if bench_qty:
            notional = bench_qty * open_price
            bench_cash -= required_buy_cash(bench_qty, open_price, fees, slip_rate)
    if qty > 0 and pending_sell and high >= _d(pending_sell["requested_price"]):
        fill = _d(pending_sell["requested_price"])
        gross = qty * fill
        fee, tax = fees.sell_fee(gross), fees.tax(gross)
        slip = _money(gross * slip_rate, currency)
        cash += gross - fee - tax - slip
        pnl = gross - fee - tax - slip - entry_cost
        realized += pnl
        execution = {"order_id": pending_sell["order_id"], "side": "SELL",
                     "execution_date": as_of_date, "fill_price": str(fill), "quantity": str(qty),
                     "gross_amount": str(gross), "fee": str(fee), "tax": str(tax),
                     "slippage": str(slip), "net_amount": str(gross-fee-tax-slip),
                     "realized_pnl": str(pnl), "fill_rule_version": FILL_RULE_VERSION}
        qty = entry_price = entry_cost = Decimal(0)
        order_status = "FILLED"
    elif qty == 0 and prior_buy and prior_buy["valid_after"] < as_of_date:
        limit = _to_tick(open_price * (Decimal(1) + _d(cfg["entry_offset_pct"]) / 100),
                         up=False, stock=stock, default_tick=tick)
        if low <= limit:
            bought = affordable_quantity(cash, limit, Decimal(1), fees, slip_rate)
            if bought:
                gross = bought * limit
                fee, slip = fees.buy_fee(gross), _money(gross * slip_rate, currency)
                entry_cost = gross + fee + slip
                cash -= entry_cost
                qty, entry_price = bought, limit
                execution = {"order_id": prior_buy["order_id"], "side": "BUY",
                             "execution_date": as_of_date, "fill_price": str(limit),
                             "quantity": str(qty), "gross_amount": str(gross),
                             "fee": str(fee), "tax": "0", "slippage": str(slip),
                             "net_amount": str(entry_cost), "realized_pnl": "0",
                             "fill_rule_version": FILL_RULE_VERSION}
                order_status = "FILLED"
            else:
                order_status = "BUY_BLOCKED_INSUFFICIENT_CAPITAL"
        else:
            order_status = "LIMIT_NOT_TOUCHED"
    if qty > 0:
        target = _to_tick(entry_price * (Decimal(1) + _d(cfg["tp_pct"]) / 100),
                          up=True, stock=stock, default_tick=tick)
        if pending_sell and not execution:
            decision, reason, order = "HOLD", "Existing take-profit order remains active", None
        else:
            decision, reason = "SELL", "Place take-profit order for a later session"
            order = {"order_id": f"{account}:{as_of_date}:SELL", "decision_id": f"{account}:{as_of_date}:DECISION",
                     "symbol": cfg["symbol"], "side": "SELL", "order_type": "GTC_LIMIT",
                     "requested_price": str(target), "quantity": str(qty),
                     "valid_after": as_of_date, "status": "PENDING"}
    else:
        one_share = required_buy_cash(Decimal(1), close, fees, slip_rate)
        if cash < one_share:
            decision, reason, order = "CASH", "NOT_AFFORDABLE at today's close", None
        else:
            decision, reason = "BUY", "Queue next-session Open-offset limit order"
            order = {"order_id": f"{account}:{as_of_date}:BUY", "decision_id": f"{account}:{as_of_date}:DECISION",
                     "symbol": cfg["symbol"], "side": "BUY", "order_type": "NEXT_SESSION_OPEN_OFFSET_LIMIT",
                     "requested_price": f"OPEN{cfg['entry_offset_pct']}%", "quantity": "MAX_AFFORDABLE",
                     "valid_after": as_of_date, "status": "PENDING"}
    decision_row = {"decision_id": f"{account}:{as_of_date}:DECISION", "account_id": account,
                    "decision_date": as_of_date, "symbol": cfg["symbol"],
                    "strategy_id": cfg["strategy_id"], "strategy_version": cfg["strategy_version"],
                    "strategy_config_hash": config_hash, "phase_engine_version": PHASE_VERSION,
                    "phase_snapshot": phase["current_phase"], "signal": decision,
                    "decision": decision, "reason": reason, "reference_price": str(close),
                    "available_at": phase["available_at"]}
    value = cash + qty * close
    unrealized = qty * close - entry_cost if qty else Decimal(0)
    total = value - capital
    if abs(total - realized - unrealized) > Decimal("0.02"):
        raise ValueError("Paper accounting identity failed")
    bench_value = bench_cash + bench_qty * close
    result = {"journal_date": as_of_date, "account_id": account, "symbol": cfg["symbol"],
              "evidence_type": "PAPER_FORWARD" if cfg["mode"] == "LIVE_FORWARD" else "HISTORICAL_REPLAY",
              "mode": cfg["mode"], "strategy_id": cfg["strategy_id"],
              "strategy_version": cfg["strategy_version"], "strategy_config_hash": config_hash,
              "phase": phase["current_phase"], "phase_engine_version": PHASE_VERSION,
              "phase_rule_config_hash": RULE_CONFIG_HASH, "signal": decision,
              "decision": decision, "decision_reason": reason,
              "order_status": order_status, "execution_status": "FILLED" if execution else "NONE",
              "execution_side": execution["side"] if execution else None,
              "quantity": str(qty), "average_entry_price": str(entry_price),
              "entry_cost": str(entry_cost), "close": str(close), "cash": str(cash),
              "market_value": str(qty * close), "portfolio_value": str(value),
              "realized_pnl": str(realized), "unrealized_pnl": str(unrealized),
              "total_pnl": str(total), "net_return": str(total/capital),
              "s0_cash": str(bench_cash), "s0_quantity": str(bench_qty),
              "s0_portfolio_value": str(bench_value),
              "paper_minus_s0": str(value - bench_value),
              "data_source": provenance.get("provider", "UNVERIFIED"),
              "data_timestamp": provenance.get("retrieved_at"),
              "adjustment_policy": provenance.get("adjustment", "UNKNOWN"),
              "source_bar_hash": _bar_hash(row),
              "source_history_hash": _history_hash(prefix),
              "fee_model_version": FEE_MODEL_VERSION, "fill_rule_version": FILL_RULE_VERSION}
    con.execute("BEGIN IMMEDIATE")
    try:
        if execution:
            _event(con, account, as_of_date, "EXECUTION", execution)
        _event(con, account, as_of_date, "DECISION", decision_row)
        if order:
            _event(con, account, as_of_date, "ORDER", order)
        _event(con, account, as_of_date, "JOURNAL", result)
        con.commit()
    except Exception:
        con.rollback()
        raise
    return result


def record_correction(con: sqlite3.Connection, account: str, day: str, reason: str) -> dict:
    """Audit a vendor correction; never mutate original decisions or resume silently."""
    _account(con, account)
    if not reason.strip():
        raise ValueError("Correction reason required")
    payload = {"kind": "DATA_CORRECTION", "account_id": account,
               "recorded_date": day, "reason": reason.strip(), "recorded_at": _stamp()}
    with con:
        _event(con, account, day, "DATA_CORRECTION", payload)
    return payload
