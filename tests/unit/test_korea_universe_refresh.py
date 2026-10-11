"""The provider's rolling window must not break a frozen paper history."""

from datetime import date, timedelta
import json
import sys

import pandas as pd
import pytest

from scripts import fetch_korea_universe as collector
from scripts.fetch_korea_universe import DataHistoryChangedError, merge_verified_history


def rows(count: int, *, start: int = 0) -> pd.DataFrame:
    first = date(2026, 1, 1)
    return pd.DataFrame([
        {"date": first + timedelta(days=i), "open": 100 + i, "high": 101 + i,
         "low": 99 + i, "close": 100 + i, "volume": 1000 + i,
         "trading_value": 100000 + i}
        for i in range(start, start + count)
    ])


def test_rolling_window_appends_without_dropping_accepted_history():
    previous = rows(4)
    incoming = rows(4, start=1)
    incoming["volume"] = incoming["volume"].astype("Int64")

    merged = merge_verified_history(previous, incoming)

    assert merged["date"].tolist() == rows(5)["date"].tolist()
    assert merged.iloc[0]["close"] == 100
    assert merged.iloc[-1]["close"] == 104
    pd.testing.assert_frame_equal(previous, rows(4))


def test_identical_refresh_keeps_file_content_unchanged():
    previous = rows(4)
    incoming = previous.copy()
    incoming["date"] = incoming["date"].astype(str)
    assert merge_verified_history(previous, incoming).to_csv(index=False) == previous.to_csv(index=False)


@pytest.mark.parametrize("incoming", [
    lambda: rows(3, start=4),
    lambda: rows(4, start=1).drop(index=1).reset_index(drop=True),
    lambda: rows(4, start=1).assign(close=[102, 102, 103, 104]),
])
def test_refresh_rejects_noncontiguous_or_revised_history(incoming):
    with pytest.raises(DataHistoryChangedError, match="DATA_HISTORY_CHANGED"):
        merge_verified_history(rows(4), incoming())


def test_changed_history_exits_nonzero_without_publishing_snapshot(tmp_path, monkeypatch, capsys):
    class FakeResponse:
        url = "https://finance.daum.net/api/charts/A000660/days"
        content = b"fixture"

        def raise_for_status(self):
            pass

        def json(self):
            return {"code": 200}

    previous = rows(4)
    changed = rows(4).assign(close=[100, 102, 102, 103])
    monkeypatch.setattr(collector, "ROOT", tmp_path)
    monkeypatch.setattr(collector, "load_universe", lambda _: [{"symbol": "000660", "market": "KRX"}])
    monkeypatch.setattr(collector, "latest_accepted_history", lambda _: previous.copy())
    monkeypatch.setattr(collector, "parse_daum_chart", lambda _: (changed.copy(), {"symbol_code": "KR7000660"}))
    monkeypatch.setattr(collector.requests, "get", lambda *args, **kwargs: FakeResponse())
    monkeypatch.setattr(sys, "argv", ["fetch_korea_universe.py", "--symbols", "000660"])

    with pytest.raises(SystemExit) as exit_info:
        collector.main()

    assert exit_info.value.code == 1
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "ERROR"
    assert "date=2026-01-02 field=close" in output["detail"]
    assert not list((tmp_path / "data/processed").rglob("ohlcv.csv"))
