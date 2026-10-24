"""STEP 11 prospective boundary and empty-registry invariants."""

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

import pytest

from zero_market_lab.research.forward_validation import (
    eligible_observation, initialize_forward, plan_contents, verify_forward,
)
from zero_market_lab.research.registry import discovery_fingerprint


ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "data/reference/research_registry.json"


def _original() -> dict:
    result = json.loads(REGISTRY.read_text(encoding="utf-8"))
    result.pop("forward_protocol", None)
    for entry in result["entries"]:
        entry.pop("forward_validation", None)
    return result


def _observation(**overrides) -> dict:
    item = {"symbol": "NVDA", "provider": "test-provider", "series": "daily-ohlcv",
            "observation_date": "2026-10-03", "collected_at": "2026-10-23T15:32:49Z",
            "source_hash": sha256(b"bar").hexdigest()}
    item.update(overrides)
    return item


def test_cutoff_and_collection_freeze_are_both_strict():
    now = datetime(2026, 10, 24, tzinfo=timezone.utc)
    assert eligible_observation(_observation(observation_date="2026-10-08"), now=now)
    assert not eligible_observation(_observation(observation_date="2026-10-02"), now=now)
    assert not eligible_observation(_observation(observation_date="2026-10-07"), now=now)
    assert not eligible_observation(_observation(observation_date="2026-10-07",
                                                 collected_at="2026-10-24T00:00:00Z"), now=now)
    assert not eligible_observation(_observation(collected_at="2026-10-23T15:32:48Z"), now=now)
    assert not eligible_observation(_observation(collected_at="2026-10-07T00:00:00Z"), now=now)
    assert not eligible_observation(_observation(symbol="005930", observation_date="2026-10-08"), now=now)
    assert eligible_observation(_observation(symbol="005930", observation_date="2026-10-09"), now=now)


def test_provenance_and_clock_fail_closed():
    now = datetime(2026, 10, 24, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="Future collection"):
        eligible_observation(_observation(collected_at="2026-10-25T00:00:00Z"), now=now)
    with pytest.raises(ValueError, match="SHA-256"):
        eligible_observation(_observation(source_hash="missing"), now=now)
    with pytest.raises(ValueError, match="universe"):
        eligible_observation(_observation(symbol="OTHER"), now=now)


def test_init_preserves_history_and_waits_for_real_forward_data():
    original = _original()
    snapshot = deepcopy(original)
    plan = plan_contents(ROOT)
    result = initialize_forward(original, plan_bytes=plan)
    assert original == snapshot
    assert discovery_fingerprint(result) == discovery_fingerprint(original)
    assert result["datasets"] == original["datasets"]
    assert len(result["entries"]) == 22
    assert all(entry["forward_validation"]["windows_completed"] == 0 for entry in result["entries"])
    verify_forward(result, plan_bytes=plan)
    with pytest.raises(ValueError, match="already initialized"):
        initialize_forward(result, plan_bytes=plan)
    result["entries"][0]["forward_validation"]["evidence"].append({"fake": True})
    with pytest.raises(ValueError, match="Unexpected forward evidence"):
        verify_forward(result, plan_bytes=plan)
