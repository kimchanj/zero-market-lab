from datetime import date
import json
from pathlib import Path

import pandas as pd
import pytest

from zero_market_lab.tiger_v2.data import (
    ACTUAL_FIRST_TRADING_DATE,
    DataValidationError,
    filter_date_range,
    parse_daum_chart,
    validate_ohlcv,
)
from zero_market_lab.tiger_v2.payload import build_chart_payload, quick_range_start


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def valid_ohlcv() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.to_datetime(["2020-08-07", "2020-08-10", "2020-08-11"]),
            "open": [10030, 10010, 10045],
            "high": [10045, 10050, 10055],
            "low": [9970, 10005, 10030],
            "close": [10010, 10035, 10045],
            "volume": [122948, 207014, 81106],
            "trading_value": [1231519935, 2074999395, 814795085],
        }
    )


def test_parse_daum_unadjusted_payload() -> None:
    document = {
        "code": 200,
        "message": "OK",
        "data": [
            {
                "symbolCode": "KR7360750004",
                "date": "2020-08-07",
                "openingPrice": 10030,
                "highPrice": 10045,
                "lowPrice": 9970,
                "tradePrice": 10010,
                "candleAccTradeVolume": 122948,
                "candleAccTradePrice": 1231519935,
            }
        ],
    }
    frame, metadata = parse_daum_chart(document)
    assert frame.iloc[0].to_dict()["close"] == 10010
    assert metadata == {
        "symbol_code": "KR7360750004",
        "response_code": 200,
        "response_message": "OK",
        "adjusted_request": False,
    }


def test_ohlc_integrity_and_volume_pass(valid_ohlcv: pd.DataFrame) -> None:
    report = validate_ohlcv(valid_ohlcv)
    assert report.row_count == 3
    assert report.zero_volume_rows == 0


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        ("high", 9000, "High must"),
        ("low", 10040, "Low must"),
        ("open", 0, "open must be positive"),
        ("volume", -1, "volume must be non-negative"),
    ],
)
def test_invalid_price_or_volume_fails(
    valid_ohlcv: pd.DataFrame, column: str, value: int, message: str
) -> None:
    valid_ohlcv.loc[0, column] = value
    with pytest.raises(DataValidationError, match=message):
        validate_ohlcv(valid_ohlcv)


def test_date_order_and_duplicate_fail(valid_ohlcv: pd.DataFrame) -> None:
    reversed_frame = valid_ohlcv.iloc[::-1].reset_index(drop=True)
    with pytest.raises(DataValidationError, match="strictly ascending"):
        validate_ohlcv(reversed_frame)
    duplicated = pd.concat([valid_ohlcv.iloc[[0]], valid_ohlcv.iloc[[0]]], ignore_index=True)
    with pytest.raises(DataValidationError, match="Duplicate"):
        validate_ohlcv(duplicated)


def test_actual_first_trading_date_is_enforced(valid_ohlcv: pd.DataFrame) -> None:
    assert ACTUAL_FIRST_TRADING_DATE == date(2020, 8, 7)
    valid_ohlcv.loc[0, "date"] = pd.Timestamp("2020-08-06")
    with pytest.raises(DataValidationError, match="Unexpected first trading date"):
        validate_ohlcv(valid_ohlcv)


def test_missing_required_value_fails(valid_ohlcv: pd.DataFrame) -> None:
    valid_ohlcv.loc[1, "close"] = None
    with pytest.raises(DataValidationError, match="null/invalid"):
        validate_ohlcv(valid_ohlcv)


def test_range_filter_is_inclusive(valid_ohlcv: pd.DataFrame) -> None:
    selected = filter_date_range(valid_ohlcv, "2020-08-08", "2020-08-10")
    assert selected["date"].dt.date.tolist() == [date(2020, 8, 10)]


def test_candlestick_and_volume_payload(valid_ohlcv: pd.DataFrame) -> None:
    payload = build_chart_payload(
        valid_ohlcv,
        pd.DataFrame(columns=["date", "distribution_per_share"]),
        {"source": "test"},
    )
    assert payload["candles"][0] == {
        "time": "2020-08-07",
        "open": 10030.0,
        "high": 10045.0,
        "low": 9970.0,
        "close": 10010.0,
        "adjustedClose": None,
        "changePercent": None,
    }
    assert payload["volume"][0]["value"] == 122948
    assert payload["volume"][0]["color"] == "#ef535080"


@pytest.mark.parametrize(
    ("quick_range", "expected"),
    [("1M", "2026-09-06"), ("3M", "2026-07-06"), ("6M", "2026-04-06"),
     ("1Y", "2025-10-06"), ("3Y", "2023-10-06"), ("ALL", "2020-08-07")],
)
def test_quick_ranges(quick_range: str, expected: str) -> None:
    assert quick_range_start("2026-10-06", quick_range, "2020-08-07") == expected


def test_actual_provenance_records_validated_first_date() -> None:
    candidates = sorted(
        path
        for path in (ROOT / "data" / "provenance").glob("tiger_360750_*.json")
        if "crosscheck" not in path.name
    )
    assert candidates, "actual TIGER provenance is required"
    provenance = json.loads(candidates[-1].read_text(encoding="utf-8"))
    assert provenance["actual_range"][0] == "2020-08-07"
    assert provenance["validation"]["null_required_values"] == 0
    assert provenance["validation"]["duplicate_dates"] == 0
    assert provenance["row_count"] >= 1500


def test_financial_chart_uses_browser_side_candles_volume_and_ranges() -> None:
    chart_dir = ROOT / "experiments" / "tiger_etf_v2"
    javascript = (chart_dir / "chart.js").read_text(encoding="utf-8")
    html = (chart_dir / "index.html").read_text(encoding="utf-8")
    assert "CandlestickSeries" in javascript
    assert "HistogramSeries" in javascript
    assert "subscribeCrosshairMove" in javascript
    assert "chart.timeScale().setVisibleRange" in javascript
    assert all(f'data-range="{name}"' in html for name in ("1M", "3M", "6M", "1Y", "3Y", "ALL"))
