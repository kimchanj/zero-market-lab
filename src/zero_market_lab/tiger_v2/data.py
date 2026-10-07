"""Acquisition parsing and fail-fast validation for TIGER 360750 OHLCV."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

import pandas as pd


SYMBOL = "360750"
YAHOO_SYMBOL = "360750.KS"
ACTUAL_FIRST_TRADING_DATE = date(2020, 8, 7)
REQUIRED_COLUMNS = ("date", "open", "high", "low", "close", "volume")
PRICE_COLUMNS = ("open", "high", "low", "close")


class DataValidationError(ValueError):
    """Raised when market data is unsafe for execution research."""


@dataclass(frozen=True)
class ValidationReport:
    row_count: int
    first_date: str
    last_date: str
    duplicate_dates: int
    null_required_values: int
    zero_volume_rows: int
    largest_calendar_gap_days: int
    missing_date_policy: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _kst_date(unix_seconds: int) -> date:
    kst = timezone(timedelta(hours=9))
    return datetime.fromtimestamp(unix_seconds, timezone.utc).astimezone(kst).date()


def parse_daum_chart(document: dict[str, Any]) -> tuple[pd.DataFrame, dict]:
    """Parse Daum's unadjusted daily-candle response.

    Acquisition must explicitly request ``adjusted=false``. The response keeps
    exchange-traded OHLCV and trading value in their raw units.
    """

    if document.get("code") != 200 or not isinstance(document.get("data"), list):
        raise DataValidationError(
            f"Daum chart response is unusable: {document.get('code')} {document.get('message')}"
        )
    rows = document["data"]
    if not rows:
        raise DataValidationError("Daum chart response contains no rows")
    frame = pd.DataFrame(
        {
            "date": [row.get("date") for row in rows],
            "open": [row.get("openingPrice") for row in rows],
            "high": [row.get("highPrice") for row in rows],
            "low": [row.get("lowPrice") for row in rows],
            "close": [row.get("tradePrice") for row in rows],
            "volume": [row.get("candleAccTradeVolume") for row in rows],
            "trading_value": [row.get("candleAccTradePrice") for row in rows],
        }
    )
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.date
    for column in PRICE_COLUMNS + ("trading_value",):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce").astype("Int64")
    metadata = {
        "symbol_code": rows[0].get("symbolCode"),
        "response_code": document.get("code"),
        "response_message": document.get("message"),
        "adjusted_request": False,
    }
    return frame, metadata


def parse_yahoo_chart(document: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Parse Yahoo chart JSON while keeping raw OHLC separate from adjustments.

    The quote array contains exchange-traded OHLCV. ``adjclose`` is retained only
    as an analysis field and must never be substituted into execution OHLC.
    """

    chart = document.get("chart", {})
    errors = chart.get("error")
    results = chart.get("result") or []
    if errors or len(results) != 1:
        raise DataValidationError(f"Yahoo chart response is unusable: {errors!r}")

    result = results[0]
    timestamps = result.get("timestamp") or []
    quotes = (result.get("indicators", {}).get("quote") or [{}])[0]
    adjusted = (result.get("indicators", {}).get("adjclose") or [{}])[0].get(
        "adjclose", [None] * len(timestamps)
    )
    fields = {name: quotes.get(name, []) for name in ("open", "high", "low", "close", "volume")}
    lengths = {len(timestamps), len(adjusted), *(len(values) for values in fields.values())}
    if lengths != {len(timestamps)} or not timestamps:
        raise DataValidationError(f"Yahoo arrays have inconsistent lengths: {sorted(lengths)}")

    frame = pd.DataFrame(
        {
            "date": [_kst_date(value) for value in timestamps],
            **fields,
            "adjusted_close": adjusted,
        }
    )
    for column in PRICE_COLUMNS + ("adjusted_close",):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce").astype("Int64")

    dividend_rows = []
    for event in (result.get("events", {}).get("dividends") or {}).values():
        dividend_rows.append(
            {"date": _kst_date(int(event["date"])), "distribution_per_share": float(event["amount"])}
        )
    distributions = pd.DataFrame(dividend_rows, columns=["date", "distribution_per_share"])
    if not distributions.empty:
        distributions = distributions.sort_values("date", ignore_index=True)

    metadata = result.get("meta", {})
    return frame, distributions, metadata


def validate_ohlcv(
    frame: pd.DataFrame,
    *,
    expected_first_date: date = ACTUAL_FIRST_TRADING_DATE,
) -> ValidationReport:
    """Validate execution-grade OHLCV without filling absent exchange sessions."""

    missing_columns = sorted(set(REQUIRED_COLUMNS).difference(frame.columns))
    if missing_columns:
        raise DataValidationError(f"Missing required columns: {missing_columns}")
    if frame.empty:
        raise DataValidationError("OHLCV contains no rows")

    dates = pd.to_datetime(frame["date"], errors="coerce")
    null_count = int(frame[list(REQUIRED_COLUMNS)].isna().sum().sum()) + int(dates.isna().sum())
    if null_count:
        raise DataValidationError(f"OHLCV contains {null_count} null/invalid required values")
    if not dates.is_monotonic_increasing:
        raise DataValidationError("Dates must be strictly ascending")
    duplicate_count = int(dates.duplicated().sum())
    if duplicate_count:
        raise DataValidationError(f"Duplicate trading dates: {duplicate_count}")
    actual_first = dates.iloc[0].date()
    if actual_first != expected_first_date:
        raise DataValidationError(
            f"Unexpected first trading date: {actual_first}; expected {expected_first_date}"
        )

    for column in PRICE_COLUMNS:
        if not (frame[column] > 0).all():
            raise DataValidationError(f"{column} must be positive")
    if not (frame["volume"] >= 0).all():
        raise DataValidationError("volume must be non-negative")
    if not (frame["high"] >= frame[["open", "close", "low"]].max(axis=1)).all():
        raise DataValidationError("High must be >= Open, Close, and Low")
    if not (frame["low"] <= frame[["open", "close", "high"]].min(axis=1)).all():
        raise DataValidationError("Low must be <= Open, Close, and High")

    gaps = dates.diff().dt.days.dropna()
    return ValidationReport(
        row_count=len(frame),
        first_date=actual_first.isoformat(),
        last_date=dates.iloc[-1].date().isoformat(),
        duplicate_dates=duplicate_count,
        null_required_values=0,
        zero_volume_rows=int((frame["volume"] == 0).sum()),
        largest_calendar_gap_days=int(gaps.max()) if not gaps.empty else 0,
        missing_date_policy=(
            "Provider observations only; weekends and KRX holidays are not rows. "
            "No forward-fill or synthetic bars. Exchange-calendar reconciliation is pending."
        ),
    )


def filter_date_range(frame: pd.DataFrame, start: str | date, end: str | date) -> pd.DataFrame:
    """Return an inclusive observed-session slice and reject an inverted range."""

    start_date = pd.Timestamp(start).date()
    end_date = pd.Timestamp(end).date()
    if start_date > end_date:
        raise ValueError("start must be on or before end")
    dates = pd.to_datetime(frame["date"]).dt.date
    return frame.loc[(dates >= start_date) & (dates <= end_date)].reset_index(drop=True)
