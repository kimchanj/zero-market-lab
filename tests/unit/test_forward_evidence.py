"""Deterministic prospective lifecycle without live provider requests."""

from datetime import date, datetime, timedelta, timezone
from hashlib import sha256

import pytest

from zero_market_lab.research.forward_evidence import (
    active_bars, append_correction, connect, evaluate_window, ingest, runtime_summary,
)
from zero_market_lab.research.transit_analysis import gate_intervals
from zero_market_lab.research.forward_validation import FROZEN_AT
from zero_market_lab.transit.calendar import at_market_close


def bar(day: str, close: float = 100.0, **extra) -> dict:
    value = {"symbol": "NVDA", "provider": "fixture", "series": "daily-ohlcv",
             "observation_date": day, "collected_at": "2026-10-24T03:00:00Z",
             "observation_id": sha256(f"fixture:{day}:{close}".encode()).hexdigest(),
             "source_hash": sha256(b"fixture").hexdigest(),
             "open": close, "high": close + 1, "low": close - 1,
             "close": close, "volume": 1000.0}
    return value | extra


def sample_window():
    gates = {1, 4, 10, 20, 22, 23, 27, 31, 32, 36, 44, 45, 46, 47, 48,
             50, 51, 52, 56, 57, 58, 63}
    interval = next(item for item in gate_intervals("2027-01-01", "2027-06-30")
                    if item["gate"] in gates and item["start_utc"] > FROZEN_AT)
    start = date.fromisoformat(interval["start_utc"][:10]) - timedelta(days=30)
    bars = []
    for offset in range(100):
        day = start + timedelta(days=offset)
        if day.weekday() < 5:
            collected = datetime.fromisoformat(at_market_close(day.isoformat(),
                                                                "USD")["market_close_utc"]) + timedelta(hours=1)
            bars.append(bar(day.isoformat(), close=100 + offset / 10,
                            collected_at=collected.isoformat()))
    return interval, bars


def test_ingest_boundaries_duplicate_and_mutation(tmp_path):
    now = datetime(2027, 1, 1, tzinfo=timezone.utc)
    with connect(tmp_path / "forward.db") as db:
        assert ingest(db, bar("2026-10-07"), now=now) == "INELIGIBLE"
        assert ingest(db, bar("2026-10-08", collected_at=FROZEN_AT), now=now) == "INELIGIBLE"
        assert ingest(db, bar("2026-10-08"), now=now) == "INGESTED"
        assert ingest(db, bar("2026-10-08"), now=now) == "DUPLICATE"
        assert ingest(db, bar("2026-10-08", close=101), now=now) == "SOURCE_MUTATION"
        assert runtime_summary(db)["observations"] == 2
        assert db.execute("SELECT count(*) FROM events WHERE kind='SOURCE_MUTATION'").fetchone()[0] == 1
        with pytest.raises(ValueError, match="SOURCE_MUTATION"):
            active_bars(db, "NVDA")
        append_correction(db, "NVDA", "2026-10-08", "Provider correction checked",
                          now=now)
        assert active_bars(db, "NVDA")[0]["close"] == 101
        assert db.execute("SELECT count(*) FROM events WHERE kind='CORRECTION_APPENDED'").fetchone()[0] == 1


def test_window_open_pending_context_finalize_and_idempotency(tmp_path):
    interval, rows = sample_window()
    research_id = f"TRANSIT_GATE_{interval['gate']}_V1"
    close = datetime.fromisoformat(interval["end_utc"])
    early = datetime.fromisoformat(interval["start_utc"]) + timedelta(days=2)
    with connect(tmp_path / "forward.db") as db:
        # OPEN sees only observations already collected by the early processing clock.
        early_rows = [row for row in rows if
                      datetime.fromisoformat(at_market_close(row["observation_date"],
                                                             "USD")["market_close_utc"]) <= early]
        assert evaluate_window(db, research_id=research_id, asset="NVDA", interval=interval,
                               bars=early_rows, now=early) == "OPEN"
        assert runtime_summary(db)["evidence"] == 0
        late = datetime.fromisoformat(rows[-1]["collected_at"]) + timedelta(days=1)
        assert evaluate_window(db, research_id=research_id, asset="NVDA", interval=interval,
                               bars=rows, now=late) == "PENDING_CONTEXT"
        days = [row["observation_date"] for row in rows]
        context = {day: {layer: {"value": 1.0, "observation_date": day,
                                 "percentile": 50.0} for layer in
                         ("VIX", "US10Y", "USDKRW", "BROAD_USD")} for day in days}
        phases = {day: "WINTER" for day in days}
        quarter = {"id": "Q1"}
        assert evaluate_window(db, research_id=research_id, asset="NVDA", interval=interval,
                               bars=rows, now=late, context=context, phase_map=phases,
                               quarter=quarter) == "FINALIZED"
        assert evaluate_window(db, research_id=research_id, asset="NVDA", interval=interval,
                               bars=rows, now=late, context=context, phase_map=phases,
                               quarter=quarter) == "FINALIZED"
        assert runtime_summary(db)["evidence"] == 1
        import json
        payload = json.loads(db.execute("SELECT payload FROM evidence").fetchone()[0])
        assert payload["phase_at_start"] == "WINTER"
        assert payload["quarter_id"] == "Q1"
        assert payload["metrics"]["return_pct"] > 0
        assert db.execute("SELECT count(*) FROM events WHERE kind='WINDOW_FINALIZED'").fetchone()[0] == 1
        extra_day = date.fromisoformat(rows[-1]["observation_date"]) + timedelta(days=1)
        while extra_day.weekday() >= 5:
            extra_day += timedelta(days=1)
        extra = bar(extra_day.isoformat(), close=111,
                    collected_at=(datetime.fromisoformat(at_market_close(extra_day.isoformat(),
                                                                            "USD")["market_close_utc"])
                                  + timedelta(hours=1)).isoformat())
        future = datetime.fromisoformat(extra["collected_at"]) + timedelta(days=1)
        assert evaluate_window(db, research_id=research_id, asset="NVDA", interval=interval,
                               bars=rows + [extra], now=future, context=context,
                               phase_map=phases, quarter=quarter) == "FINALIZED"
        assert runtime_summary(db)["evidence"] == 1
        changed_context = {day: {layer: dict(value) for layer, value in layers.items()}
                           for day, layers in context.items()}
        window_day = next(row["observation_date"] for row in rows if
                          datetime.fromisoformat(interval["start_utc"]) <=
                          datetime.fromisoformat(at_market_close(row["observation_date"],
                                                                 "USD")["market_close_utc"]) <
                          datetime.fromisoformat(interval["end_utc"]))
        changed_context[window_day]["VIX"]["value"] = 2.0
        with pytest.raises(ValueError, match="explicit correction"):
            evaluate_window(db, research_id=research_id, asset="NVDA", interval=interval,
                            bars=rows, now=late, context=changed_context,
                            phase_map=phases, quarter=quarter, allow_correction=True)
        changed = [dict(row) for row in rows]
        changed[-1]["observation_id"] = "corrected"
        with pytest.raises(ValueError, match="explicit correction"):
            evaluate_window(db, research_id=research_id, asset="NVDA", interval=interval,
                            bars=changed, now=late, context=context, phase_map=phases,
                            quarter=quarter)
        assert evaluate_window(db, research_id=research_id, asset="NVDA", interval=interval,
                               bars=changed, now=late, context=context, phase_map=phases,
                               quarter=quarter,
                               allow_correction=True) == "FINALIZED"
        assert runtime_summary(db)["evidence"] == 2
        newest = db.execute("SELECT supersedes_evidence_id FROM evidence ORDER BY revision DESC").fetchone()
        assert newest[0]


def test_closed_window_without_post_control_cannot_finalize(tmp_path):
    interval, rows = sample_window()
    research_id = f"TRANSIT_GATE_{interval['gate']}_V1"
    end = datetime.fromisoformat(interval["end_utc"])
    before_post = [row for row in rows if
                   datetime.fromisoformat(at_market_close(row["observation_date"],
                                                          "USD")["market_close_utc"]) < end]
    with connect(tmp_path / "forward.db") as db:
        assert evaluate_window(db, research_id=research_id, asset="NVDA", interval=interval,
                               bars=before_post, now=end + timedelta(days=1)) == "PENDING_CONTROL"
        assert runtime_summary(db)["evidence"] == 0
