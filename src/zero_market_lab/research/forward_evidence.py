"""Append-only prospective observations and conservative Gate evidence lifecycle.

Runtime SQLite is deliberately outside version control. No trading signal is
produced here; incomplete windows never become evidence.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
import sqlite3

import pandas as pd

from zero_market_lab.research.forward_validation import ASSETS, eligible_observation
from zero_market_lab.research.transit_analysis import (
    CONTEXT, StudyConfig, _context_metrics, price_metrics, random_control,
)
from zero_market_lab.transit.calendar import at_market_close


METHOD = "TRANSIT_FORWARD_V1"
SCHEMA = """
CREATE TABLE IF NOT EXISTS observations (
 id TEXT PRIMARY KEY, symbol TEXT NOT NULL, day TEXT NOT NULL,
 provider TEXT NOT NULL, series TEXT NOT NULL, collected_at TEXT NOT NULL,
 source_hash TEXT NOT NULL, row_hash TEXT NOT NULL, payload TEXT NOT NULL,
 UNIQUE(symbol, day, provider, row_hash)
);
CREATE TABLE IF NOT EXISTS events (
 id TEXT PRIMARY KEY, kind TEXT NOT NULL, occurred_at TEXT NOT NULL,
 payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS windows (
 key TEXT PRIMARY KEY, research_id TEXT NOT NULL, asset TEXT NOT NULL,
 gate INTEGER NOT NULL, start_utc TEXT NOT NULL, end_utc TEXT NOT NULL,
 status TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence (
 id TEXT PRIMARY KEY, window_key TEXT NOT NULL, revision INTEGER NOT NULL,
 input_hash TEXT NOT NULL, result_hash TEXT NOT NULL, created_at TEXT NOT NULL,
 supersedes_evidence_id TEXT, payload TEXT NOT NULL,
 UNIQUE(window_key, input_hash)
);
"""


def digest(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                             separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    return db


def _event(db: sqlite3.Connection, kind: str, key: object, payload: dict,
           when: str) -> bool:
    event_id = digest([METHOD, kind, key])
    cursor = db.execute("INSERT OR IGNORE INTO events VALUES (?,?,?,?)",
                        (event_id, kind, when, json.dumps(payload, sort_keys=True)))
    return bool(cursor.rowcount)


def _validate_bar(row: dict) -> None:
    symbol = row["symbol"]
    if symbol not in ASSETS:
        raise ValueError("Asset outside frozen universe")
    day = date.fromisoformat(row["observation_date"])
    if day.weekday() >= 5:
        raise ValueError("Weekend market observation")
    close = float(row["close"])
    if not isfinite(close) or close <= 0:
        raise ValueError("Invalid close")
    fields = ("open", "high", "low", "volume")
    if symbol != "SP500" and any(row.get(key) is None for key in fields):
        raise ValueError("Equity observation requires OHLCV")
    if symbol == "SP500" and any(row.get(key) is not None for key in fields):
        raise ValueError("SP500 is a close-only price index")
    if symbol != "SP500":
        opening, high, low, volume = (float(row[key]) for key in fields)
        if (not all(map(isfinite, (opening, high, low, volume))) or
                min(opening, high, low) <= 0 or volume < 0 or
                low > min(opening, close) or high < max(opening, close)):
            raise ValueError("Invalid OHLCV")
    at_market_close(day.isoformat(), "KRW" if symbol in {"005930", "000660"} else "USD")


def ingest(db: sqlite3.Connection, row: dict, *, now: datetime) -> str:
    """Return INELIGIBLE, DUPLICATE, INGESTED or SOURCE_MUTATION."""
    _validate_bar(row)
    if not eligible_observation(row, now=now):
        return "INELIGIBLE"
    content = {key: row.get(key) for key in
               ("symbol", "observation_date", "open", "high", "low", "close", "volume")}
    row_hash = digest(content)
    prior = db.execute("SELECT * FROM observations WHERE symbol=? AND day=? AND provider=? "
                       "ORDER BY rowid", (row["symbol"], row["observation_date"],
                                                 row["provider"])).fetchall()
    if any(item["row_hash"] == row_hash for item in prior):
        return "DUPLICATE"
    identity = digest([row["symbol"], row["observation_date"], row["provider"], row_hash])
    when = now.astimezone(timezone.utc).isoformat()
    with db:
        db.execute("INSERT INTO observations VALUES (?,?,?,?,?,?,?,?,?)",
                   (identity, row["symbol"], row["observation_date"], row["provider"],
                    row["series"], row["collected_at"], row["source_hash"], row_hash,
                    json.dumps(row, sort_keys=True)))
        if prior:
            _event(db, "SOURCE_MUTATION", identity,
                   {"event_id": digest([METHOD, "SOURCE_MUTATION", identity]),
                    "symbol": row["symbol"], "observation_date": row["observation_date"],
                    "old_hash": prior[-1]["row_hash"], "new_hash": row_hash,
                    "provider": row["provider"], "detected_at": when}, when)
            return "SOURCE_MUTATION"
        _event(db, "OBSERVATION_INGESTED", identity,
               {"observation_id": identity, "symbol": row["symbol"],
                "observation_date": row["observation_date"]}, when)
    return "INGESTED"


def append_correction(db: sqlite3.Connection, symbol: str, day: str,
                      reason: str, *, now: datetime) -> str:
    """Explicitly accept the newest source revision; never remove prior rows."""
    if not reason.strip():
        raise ValueError("Correction reason required")
    revisions = db.execute("SELECT * FROM observations WHERE symbol=? AND day=? "
                           "ORDER BY rowid", (symbol, day)).fetchall()
    if len({row["row_hash"] for row in revisions}) < 2:
        raise ValueError("No source mutation to correct")
    latest = revisions[-1]
    key = [symbol, day, latest["row_hash"]]
    when = now.astimezone(timezone.utc).isoformat()
    with db:
        _event(db, "CORRECTION_APPENDED", key,
               {"symbol": symbol, "observation_date": day,
                "accepted_hash": latest["row_hash"], "reason": reason,
                "detected_at": when}, when)
    return latest["row_hash"]


def active_bars(db: sqlite3.Connection, symbol: str) -> list[dict]:
    """Stop at a source revision until an explicit correction is approved."""
    rows = db.execute("SELECT * FROM observations WHERE symbol=? ORDER BY day,rowid",
                      (symbol,)).fetchall()
    result: list[dict] = []
    corrected = {payload["observation_date"]: payload["accepted_hash"]
                 for row in db.execute("SELECT payload FROM events WHERE kind='CORRECTION_APPENDED' "
                                       "ORDER BY rowid")
                 if (payload := json.loads(row["payload"])).get("symbol") == symbol and
                 "accepted_hash" in payload}
    by_day: dict[str, list[sqlite3.Row]] = {}
    for item in rows:
        by_day.setdefault(item["day"], []).append(item)
    for day, revisions in by_day.items():
        newest = revisions[-1]
        if len({item["row_hash"] for item in revisions}) > 1 and corrected.get(day) != newest["row_hash"]:
            raise ValueError("SOURCE_MUTATION requires explicit correction")
        result.append(json.loads(newest["payload"]) | {"observation_id": newest["id"]})
    return result


def window_key(research_id: str, asset: str, gate: int, start_utc: str) -> str:
    return digest([research_id, asset, gate, start_utc])


def _transition(db: sqlite3.Connection, key: str, research_id: str, asset: str,
                interval: dict, status: str, when: str) -> None:
    existing = db.execute("SELECT status FROM windows WHERE key=?", (key,)).fetchone()
    if existing and existing["status"] == status:
        return
    if existing and existing["status"] == "FINALIZED":
        return
    event = {"OPEN": "WINDOW_OPENED", "CLOSED": "WINDOW_CLOSED",
             "PENDING_CONTEXT": "CONTEXT_PENDING", "FINALIZED": "WINDOW_FINALIZED"}.get(status)
    with db:
        db.execute("INSERT INTO windows VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(key) DO UPDATE "
                   "SET status=excluded.status, updated_at=excluded.updated_at",
                   (key, research_id, asset, interval["gate"], interval["start_utc"],
                    interval["end_utc"], status, when))
        if event:
            _event(db, event, [key, status], {"window_key": key, "status": status}, when)


def evaluate_window(db: sqlite3.Connection, *, research_id: str, asset: str,
                    interval: dict, bars: list[dict], now: datetime,
                    context: dict[str, dict] | None = None,
                    phase_map: dict[str, str] | None = None,
                    quarter: dict | None = None,
                    allow_correction: bool = False) -> str:
    """No result until full price, pre/post control, random and as-of context exist."""
    if interval["gate"] != int(research_id.split("_")[2]):
        raise ValueError("Research Gate mismatch")
    key = window_key(research_id, asset, interval["gate"], interval["start_utc"])
    start = datetime.fromisoformat(interval["start_utc"])
    end = datetime.fromisoformat(interval["end_utc"])
    clock = now.astimezone(timezone.utc)
    when = clock.isoformat()
    if not bars or start <= datetime.fromisoformat("2026-10-23T15:32:48Z"):
        return "WAITING_FOR_DATA"
    if any(not eligible_observation(item, now=now) or item["symbol"] != asset
           for item in bars):
        raise ValueError("Non-forward observation supplied to window")
    existing = db.execute("SELECT * FROM evidence WHERE window_key=? ORDER BY revision DESC",
                          (key,)).fetchone()
    currency = "KRW" if asset in {"005930", "000660"} else "USD"
    ordered = sorted(bars, key=lambda item: item["observation_date"])
    # Freeze the original evidence's available universe. Later bars must not
    # retrospectively change its same-season control or input fingerprint.
    if existing:
        evaluation_as_of = json.loads(existing["payload"])["evaluation_as_of"]
        ordered = [item for item in ordered if item["observation_date"] <= evaluation_as_of]
    positions = [i for i, item in enumerate(ordered)
                 if start <= datetime.fromisoformat(at_market_close(item["observation_date"],
                                                                    currency)["market_close_utc"]) < end]
    if not positions:
        return "WAITING_FOR_DATA"
    if clock < end:
        _transition(db, key, research_id, asset, interval, "OPEN", when)
        return "OPEN"
    _transition(db, key, research_id, asset, interval, "CLOSED", when)
    if len(positions) < 3:
        return "CLOSED"
    n = len(positions)
    # Require contiguous rows within the supplied eligible series and equal-bar controls.
    if positions != list(range(positions[0], positions[-1] + 1)) or positions[0] < n or positions[-1] + n >= len(ordered):
        _transition(db, key, research_id, asset, interval, "PENDING_CONTROL", when)
        return "PENDING_CONTROL"
    frame = pd.DataFrame([{"date": item["observation_date"], "close": float(item["close"]),
                           "volume": item.get("volume")} for item in ordered])
    midpoint = (start + (end - start) / 2).date()
    config = StudyConfig(start=ordered[0]["observation_date"],
                         end=ordered[-1]["observation_date"])
    control = random_control(frame, positions, year=start.year, midpoint=midpoint,
                             config=config, key=f"{asset}:{interval['start_utc']}")
    if not control["random_candidate_count"]:
        _transition(db, key, research_id, asset, interval, "PENDING_CONTROL", when)
        return "PENDING_CONTROL"
    days = [ordered[i]["observation_date"] for i in positions]
    if context is None or any(context.get(day, {}).get(layer, {}).get("value") is None
                              for day in days for layer in CONTEXT):
        _transition(db, key, research_id, asset, interval, "PENDING_CONTEXT", when)
        return "PENDING_CONTEXT"
    ids = [item["observation_id"] for item in ordered]
    input_hash = digest({"ids": ids, "context": {day: context[day] for day in days},
                         "phase": {day: (phase_map or {}).get(day) for day in days},
                         "quarter": quarter, "interval": interval, "method": METHOD})
    if existing and existing["input_hash"] == input_hash:
        return "FINALIZED"
    if existing and input_hash != existing["input_hash"]:
        old_ids = json.loads(existing["payload"])["observation_ids"]
        if not allow_correction or old_ids == ids:
            raise ValueError("Evidence input changed; explicit correction required")
    closes = frame["close"].to_numpy(dtype=float)
    metrics = price_metrics(closes[positions])
    pre = price_metrics(closes[positions[0] - n:positions[0]])["return_pct"]
    post = price_metrics(closes[positions[-1] + 1:positions[-1] + 1 + n])["return_pct"]
    payload = {"research_id": research_id, "asset": asset, "gate": interval["gate"],
               "window_start": interval["start_utc"], "window_end": interval["end_utc"],
               "status": "FINALIZED", "metrics": metrics,
               "pre_return_pct": pre, "post_return_pct": post, "random": control,
               "macro": _context_metrics(days, context), "method": METHOD,
               "phase_at_start": (phase_map or {}).get(days[0]),
               "phase_at_end": (phase_map or {}).get(days[-1]),
               "phase_distribution": {phase: sum((phase_map or {}).get(day) == phase
                                                    for day in days) / len(days)
                                      for phase in sorted({(phase_map or {}).get(day) for day in days} - {None})},
               "gate_lines_observed": [at_market_close(day, currency)["line"] for day in days],
               "quarter_id": quarter["id"] if quarter else None,
               "evaluation_as_of": ordered[-1]["observation_date"],
               "observation_ids": ids}
    result_hash = digest(payload)
    revision = 1 if not existing else existing["revision"] + 1
    evidence_id = digest([key, input_hash, result_hash])
    with db:
        db.execute("INSERT INTO evidence VALUES (?,?,?,?,?,?,?,?)",
                   (evidence_id, key, revision, input_hash, result_hash, when,
                    existing["id"] if existing else None,
                    json.dumps(payload, sort_keys=True)))
        if existing:
            _event(db, "CORRECTION_APPENDED", evidence_id,
                   {"evidence_id": evidence_id, "supersedes_evidence_id": existing["id"]}, when)
        _transition(db, key, research_id, asset, interval, "FINALIZED", when)
    return "FINALIZED"


def runtime_summary(db: sqlite3.Connection) -> dict:
    return {table: db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in ("observations", "windows", "evidence", "events")}


def registry_projection(db: sqlite3.Connection, registry: dict) -> dict:
    """Small derived runtime view; frozen Git Registry remains untouched."""
    entries = []
    for item in registry["entries"]:
        rows = db.execute("SELECT e.id,e.created_at,e.payload,w.end_utc FROM evidence e "
                          "JOIN windows w ON e.window_key=w.key WHERE w.research_id=? "
                          "ORDER BY e.created_at", (item["research_id"],)).fetchall()
        distinct = db.execute("SELECT count(DISTINCT window_key) FROM evidence e "
                              "JOIN windows w ON e.window_key=w.key WHERE w.research_id=?",
                              (item["research_id"],)).fetchone()[0]
        entries.append({"research_id": item["research_id"],
                        "forward_status": "PROVISIONAL" if distinct else "WAITING_FOR_DATA",
                        "windows_completed": distinct,
                        "latest_window_end": max((row["end_utc"] for row in rows), default=None),
                        "evidence_refs": [row["id"] for row in rows],
                        "summary": "No eligible prospective window yet" if not distinct
                        else "Prospective descriptive evidence; no strategy promotion"})
    return {"protocol_id": METHOD, "entries": entries}
