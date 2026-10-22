"""Official context snapshots stay immutable and obey observation availability."""

from pathlib import Path

import pandas as pd
import pytest
import zero_market_lab.research.comparison as comparison_module

from zero_market_lab.research.comparison import ComparisonResearch
from zero_market_lab.research.context_data import (
    FRED_SERIES, FredContextProvider, as_of_observation, latest_snapshot,
    validate_fred_csv,
)


def test_fred_parser_rejects_bad_schema_duplicates_and_nonfinite():
    series = FRED_SERIES["VIX"]
    good = b"observation_date,VIXCLS\n2026-10-01,20\n2026-10-02,.\n2026-10-03,21.5\n"
    frame, missing = validate_fred_csv(good, series)
    assert frame["date"].tolist() == ["2026-10-01", "2026-10-03"]
    assert missing == ["2026-10-02"]
    for bad in (b"date,VIXCLS\n2026-10-01,20\n",
                b"observation_date,VIXCLS\n2026-10-01,20\n2026-10-01,21\n",
                b"observation_date,VIXCLS\n2026-10-01,inf\n",
                b"observation_date,VIXCLS\n2026-10-01,0\n"):
        with pytest.raises(ValueError):
            validate_fred_csv(bad, series)


def test_available_observation_never_reads_future_day():
    frame = pd.DataFrame({"date": ["2026-10-01", "2026-10-05"], "value": [20., 30.]})
    assert as_of_observation(frame, "2026-10-01", 1) is None
    assert as_of_observation(frame, "2026-10-03", 1)["value"] == 20
    assert as_of_observation(frame, "2026-10-06", 1)["value"] == 30
    assert as_of_observation(frame, "2026-10-05", 1)["value"] == 20


class FakeResponse:
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=VIXCLS"

    def __init__(self, content):
        self.content = content

    def raise_for_status(self):
        pass


class FakeSession:
    def __init__(self, content):
        self.content = content

    def get(self, *_args, **_kwargs):
        return FakeResponse(self.content)


def test_snapshot_is_local_append_only_and_detects_history_rewrite(tmp_path: Path):
    first = b"observation_date,VIXCLS\n2026-10-01,20\n2026-10-02,21\n"
    provider = FredContextProvider(tmp_path, FakeSession(first))
    manifest = provider.persist("2026-10-01", "2026-10-02", ("VIX",))
    assert manifest["series"]["VIX"]["rows"] == 2
    assert latest_snapshot(tmp_path, "VIX")[0]["value"].tolist() == [20., 21.]
    provider.session.content = b"observation_date,VIXCLS\n2026-10-01,25\n2026-10-02,21\n"
    with pytest.raises(ValueError, match="DATA_HISTORY_CHANGED"):
        provider.persist("2026-10-01", "2026-10-02", ("VIX",))
    assert len(list((tmp_path / "data/processed/context").glob("*/manifest.json"))) == 1


def test_comparison_exposes_lagged_real_context_without_changing_price(monkeypatch):
    frame = pd.DataFrame({"date": ["2026-10-13", "2026-10-14", "2026-10-16"],
                          "value": [21.0, 22.0, 30.0]})
    metadata = {"original_source": "Cboe", "frequency": "DAILY_OBSERVATION",
                "timezone": "America/New_York", "available_from": "2026-10-13",
                "available_to": "2026-10-16", "provider": "FRED", "series_id": "VIXCLS",
                "source_url": "https://fred.stlouisfed.org/series/VIXCLS", "raw_sha256": "test"}
    monkeypatch.setattr(comparison_module, "latest_snapshot",
                        lambda root, layer: (frame, metadata) if layer == "VIX" else None)
    root = Path(__file__).resolve().parents[2]
    def prices(_symbol):
        return pd.DataFrame({"date": ["2026-10-14", "2026-10-15", "2026-10-16"],
                             "open": [100, 102, 104], "high": [101, 103, 105],
                             "low": [99, 101, 103], "close": [100, 102, 104],
                             "volume": [1000, 1000, 1000]}), {"provider": "TEST"}
    packet = ComparisonResearch(root, loader=prices).series(
        base="005930", start="2026-10-14", end="2026-10-16", layers=["VIX"])
    assert [point["value"] for point in packet["series"][0]["points"]] == [100, 102, 104]
    context = packet["context_by_date"]
    assert context["2026-10-14"]["layers"]["VIX"]["value"] == 21
    assert context["2026-10-15"]["layers"]["VIX"]["value"] == 22
    assert context["2026-10-16"]["layers"]["VIX"]["value"] == 22
    assert context["2026-10-16"]["layers"]["VIX"]["observation_date"] == "2026-10-14"
    assert context["2026-10-16"]["layers"]["VIX"]["status"] == "LAST_KNOWN_OBSERVATION"
