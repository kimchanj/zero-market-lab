"""FRED CSV adapter. Preserve original bytes; normalize only explicit missing markers."""

from datetime import date, datetime, timezone
from hashlib import sha256
from io import BytesIO

import pandas as pd
import requests

SOURCE_URL = "https://fred.stlouisfed.org/series/SP500"
DOWNLOAD_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"


def download(start: str, end: str) -> tuple[bytes, str, str]:
    if date.fromisoformat(start) > date.fromisoformat(end):
        raise ValueError("Requested start must not exceed end")
    response = requests.get(
        DOWNLOAD_URL, params={"id": "SP500", "cosd": start, "coed": end}, timeout=60
    )
    response.raise_for_status()
    return response.content, response.url, datetime.now(timezone.utc).isoformat()


def normalize(raw: bytes) -> tuple[pd.DataFrame, list[str], int]:
    source = pd.read_csv(BytesIO(raw), dtype=str, keep_default_na=False)
    if list(source.columns) not in (["observation_date", "SP500"], ["DATE", "SP500"]):
        raise ValueError("Unexpected FRED CSV schema; expected date and SP500")
    dates = pd.to_datetime(source.iloc[:, 0], format="%Y-%m-%d", errors="raise")
    if dates.isna().any() or dates.duplicated().any() or not dates.is_monotonic_increasing:
        raise ValueError("FRED source dates must be valid, unique and ascending")
    missing = source["SP500"].isin(["", "."])
    excluded = source.loc[missing].iloc[:, 0].tolist()
    # Holidays may be blank. Do not infer that every missing row is a holiday.
    frame = pd.DataFrame({"date": dates[~missing],
                          "close": pd.to_numeric(source.loc[~missing, "SP500"], errors="raise")})
    return frame.reset_index(drop=True), excluded, len(source)


def provenance(frame: pd.DataFrame, raw: bytes, start: str, end: str,
               download_url: str, retrieved_at: str, excluded: list[str], raw_count: int) -> dict:
    return {
        "instrument": "S&P500", "series_type": "PRICE_RETURN", "series": "SP500",
        "source": "FRED; original source S&P Dow Jones Indices LLC",
        "source_url": SOURCE_URL, "download_url": download_url, "retrieved_at": retrieved_at,
        "requested_start_date": start, "requested_end_date": end,
        "actual_start_date": None if frame.empty else frame.date.min().date().isoformat(),
        "actual_end_date": None if frame.empty else frame.date.max().date().isoformat(),
        "frequency": "DAILY_CLOSE", "dividend_handling": "EXCLUDED", "adjusted": False,
        "adjustment_method": "Provider price index as published; no project adjustments",
        "currency": "USD", "unit": "INDEX_POINTS", "timezone": "America/New_York",
        "row_count": len(frame), "raw_row_count": raw_count,
        "excluded_missing_dates": excluded, "raw_sha256": sha256(raw).hexdigest(),
        "normalization_version": "1", "license_note": "See FRED series notes; no public redistribution included",
        "notes": ["Validation provider only; roughly ten years of daily history",
                  "Not Total Return, not ETF price; dividends excluded",
                  "Blank/dot observations excluded, never filled; no exchange-calendar completeness claim",
                  "adjusted=false means no project adjustment, not a claim about index methodology"],
    }
