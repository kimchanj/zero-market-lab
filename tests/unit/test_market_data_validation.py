"""All observations here are deterministic synthetic fixtures, not research data."""

import pandas as pd
import pytest

from zero_market_lab.market_data.loader import download, normalize, provenance
from zero_market_lab.market_data.validation import validate


def sample():
    return pd.DataFrame({"date": ["2024-01-02", "2024-01-03", "2024-01-04"], "close": [100., 101., 99.]})


def test_valid():
    assert validate(sample()).passed


@pytest.mark.parametrize("values", [[100, None, 99], [100, 0, 99], [100, -1, 99],
                                    [100, float("inf"), 99], [100, "bad", 99]])
def test_invalid_close(values):
    frame = sample()
    frame["close"] = values
    assert not validate(frame).passed


@pytest.mark.parametrize("dates", [["2024-01-02"] * 3,
    ["2024-01-04", "2024-01-03", "2024-01-02"], ["bad", "2024-01-03", "2024-01-04"],
    [None, "2024-01-03", "2024-01-04"]])
def test_invalid_dates(dates):
    frame = sample()
    frame["date"] = dates
    assert not validate(frame).passed


@pytest.mark.parametrize("frame", [pd.DataFrame(), sample().iloc[:0], sample().drop(columns="close")])
def test_empty_or_schema(frame):
    assert not validate(frame).passed


def metadata():
    return {"actual_start_date": "2024-01-02", "actual_end_date": "2024-01-04",
            "requested_start_date": "2024-01-02", "requested_end_date": "2024-01-04", "row_count": 3}


@pytest.mark.parametrize("key,value", [("row_count", 2), ("actual_start_date", "2024-01-05"),
    ("actual_end_date", "2024-01-03"), ("requested_start_date", "2024-01-03"),
    ("actual_start_date", None)])
def test_metadata_mismatch(key, value):
    info = metadata()
    info[key] = value
    assert not validate(sample(), info).passed


def test_matching_metadata():
    assert validate(sample(), metadata()).passed


def test_coverage_warning():
    info = metadata()
    info.update(requested_start_date="2000-01-01", requested_end_date="2024-01-05")
    result = validate(sample(), info)
    assert result.passed and len(result.warnings) == 2


def test_weekend_and_gap_warning():
    frame = pd.DataFrame({"date": ["2024-01-06", "2024-01-16"], "close": [100, 101]})
    assert len(validate(frame).warnings) == 2


def test_normalize_missing_and_provenance():
    raw = b"observation_date,SP500\n2024-01-01,.\n2024-01-02,100\n2024-01-03,\n2024-01-04,101\n"
    frame, excluded, count = normalize(raw)
    assert excluded == ["2024-01-01", "2024-01-03"] and count == 4
    assert frame.close.tolist() == [100, 101]
    info = provenance(frame, raw, "2024-01-01", "2024-01-04", "test", "test", excluded, count)
    assert info["row_count"] == 2 and len(info["raw_sha256"]) == 64
    assert info["dividend_handling"] == "EXCLUDED" and validate(frame, info).passed


@pytest.mark.parametrize("raw", [b"date,wrong\n2024-01-02,100\n",
    b"DATE,SP500\n2024-01-02,100\n2024-01-02,101\n",
    b"DATE,SP500\n2024-01-03,100\n2024-01-02,101\n",
    b"DATE,SP500\n2024-01-02,not-a-price\n"])
def test_malformed_source(raw):
    with pytest.raises(ValueError):
        normalize(raw)


def test_download_request_and_original_bytes(monkeypatch):
    class Response:
        content = b"DATE,SP500\n2024-01-02,100\n"
        url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=SP500"

        def raise_for_status(self):
            pass

    def fake_get(url, *, params, timeout):
        assert url.startswith("https://fred.stlouisfed.org/")
        assert params == {"id": "SP500", "cosd": "2024-01-02", "coed": "2024-01-04"}
        assert timeout == 60
        return Response()

    monkeypatch.setattr("zero_market_lab.market_data.loader.requests.get", fake_get)
    raw, _, retrieved = download("2024-01-02", "2024-01-04")
    assert raw == Response.content and retrieved.endswith("+00:00")


def test_download_failure_never_falls_back(monkeypatch):
    import requests

    def fail(*args, **kwargs):
        raise requests.ConnectionError("synthetic network failure")

    monkeypatch.setattr("zero_market_lab.market_data.loader.requests.get", fail)
    with pytest.raises(requests.ConnectionError):
        download("2024-01-02", "2024-01-04")


def test_invalid_requested_range():
    with pytest.raises(ValueError):
        download("2024-01-04", "2024-01-02")
