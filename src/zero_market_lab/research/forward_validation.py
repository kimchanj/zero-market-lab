"""Frozen STEP 11 protocol guard; no historical replay or trading decisions."""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
from hashlib import sha256
from pathlib import Path
import re

from zero_market_lab.research.registry import discovery_fingerprint, validate_registry


PROTOCOL_ID = "TRANSIT_FORWARD_V1"
CUTOFF = "2026-10-02"
FROZEN_AT = "2026-10-23T15:32:48Z"
SOURCE_COMMIT = "a83d52cc02b26312dfb0ef6adddd75a9e775e1e3"
ASSETS = ("005930", "000660", "SP500", "NVDA", "MSFT", "AAPL")
PREEXISTING_MAX_DATE = {"005930": "2026-10-08", "000660": "2026-10-08",
                        "SP500": "2026-10-02", "NVDA": "2026-10-07",
                        "MSFT": "2026-10-07", "AAPL": "2026-10-07"}
PLAN = "docs/research/transit-forward-validation-v1-plan.md"


def _instant(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timestamp requires timezone")
    return parsed.astimezone(timezone.utc)


def eligible_observation(observation: dict, *, now: datetime) -> bool:
    """Only post-freeze collections of post-cutoff market dates can enter Forward."""
    if now.tzinfo is None:
        raise ValueError("Processing clock requires timezone")
    if observation["symbol"] not in ASSETS:
        raise ValueError("Asset is outside the frozen forward universe")
    if not observation.get("provider") or not observation.get("series"):
        raise ValueError("Provider and series provenance are required")
    if not re.fullmatch(r"[0-9a-f]{64}", observation.get("source_hash", "")):
        raise ValueError("Source SHA-256 is required")
    observed = date.fromisoformat(observation["observation_date"])
    collected = _instant(observation["collected_at"])
    if collected > now.astimezone(timezone.utc):
        raise ValueError("Future collection timestamp")
    return (observed > date.fromisoformat(CUTOFF) and
            observed > date.fromisoformat(PREEXISTING_MAX_DATE[observation["symbol"]]) and
            collected > _instant(FROZEN_AT))


def initialize_forward(registry: dict, *, plan_bytes: bytes) -> dict:
    """Add empty forward state once, preserving STEP 9/10 evidence verbatim."""
    validate_registry(registry)
    if "forward_protocol" in registry or any("forward_validation" in x for x in registry["entries"]):
        raise ValueError("Forward protocol already initialized")
    result = deepcopy(registry)
    original_fingerprint = discovery_fingerprint(registry)
    plan_hash = sha256(plan_bytes).hexdigest()
    result["forward_protocol"] = {
        "protocol_id": PROTOCOL_ID, "historical_cutoff": CUTOFF,
        "frozen_at": FROZEN_AT, "source_commit": SOURCE_COMMIT,
        "preregistration": PLAN, "preregistration_sha256": plan_hash,
        "assets": list(ASSETS),
        "preexisting_max_observation_date": PREEXISTING_MAX_DATE.copy(),
        "research_ids": [entry["research_id"] for entry in registry["entries"]],
    }
    for entry in result["entries"]:
        entry["forward_validation"] = {
            "status": "WAITING_FOR_DATA", "preregistration_id": PROTOCOL_ID,
            "cutoff_date": CUTOFF, "started_at": FROZEN_AT,
            "windows_completed": 0, "latest_window_end": None,
            "evidence": [], "events": [], "result_summary": "No eligible prospective window yet",
        }
    validate_registry(result)
    if discovery_fingerprint(result) != original_fingerprint:
        raise ValueError("Discovery evidence changed during forward initialization")
    return result


def verify_forward(registry: dict, *, plan_bytes: bytes) -> None:
    validate_registry(registry)
    protocol = registry["forward_protocol"]
    if (protocol["protocol_id"] != PROTOCOL_ID or
            protocol["historical_cutoff"] != CUTOFF or
            protocol["frozen_at"] != FROZEN_AT or
            protocol["source_commit"] != SOURCE_COMMIT or
            protocol["preregistration_sha256"] != sha256(plan_bytes).hexdigest() or
            protocol["assets"] != list(ASSETS) or
            protocol["preexisting_max_observation_date"] != PREEXISTING_MAX_DATE or
            protocol["research_ids"] != [entry["research_id"] for entry in registry["entries"]]):
        raise ValueError("Forward protocol differs from frozen plan")
    for entry in registry["entries"]:
        state = entry["forward_validation"]
        if (state["status"] != "WAITING_FOR_DATA" or
                state["preregistration_id"] != PROTOCOL_ID or
                state["cutoff_date"] != CUTOFF or
                state["windows_completed"] != 0 or
                state["evidence"] or state["events"]):
            raise ValueError("Unexpected forward evidence or status")


def plan_contents(root: Path) -> bytes:
    return (root / PLAN).read_bytes()
