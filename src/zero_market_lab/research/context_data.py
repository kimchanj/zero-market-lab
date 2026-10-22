"""Local, append-only snapshots of sourced market context observations.

Financial context is descriptive. Observation dates are not publication times.
The reader applies a conservative availability lag before joining to a market
date, and never converts a missing observation to zero.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from io import BytesIO
import json
from math import isfinite
from pathlib import Path

import pandas as pd
import requests


FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"


@dataclass(frozen=True)
class FredContextSeries:
    layer_id: str
    series_id: str
    name: str
    unit: str
    original_source: str
    license_note: str
    # Conservative date lag, not a claim of the exact release timestamp.
    krx_lag_days: int
    us_lag_days: int


FRED_SERIES = {
    "VIX": FredContextSeries("VIX", "VIXCLS", "VIX", "index points", "Cboe",
                             "Cboe copyrighted; private non-commercial local research only; no redistribution",
                             1, 0),
    "US10Y": FredContextSeries("US10Y", "DGS10", "미국 10년물 국채수익률", "%", "Federal Reserve H.15",
                               "FRED citation requested; check source terms before publication",
                               2, 2),
    "USDKRW": FredContextSeries("USDKRW", "DEXKOUS", "원/달러 환율 · 1 USD=KRW", "KRW per USD",
                                "Federal Reserve H.10 New York noon buying rate",
                                "FRED citation requested; H.10 delayed release; no redistribution assumed",
                                14, 14),
    "BROAD_USD": FredContextSeries("BROAD_USD", "DTWEXBGS", "미 달러 광의지수", "Jan 2006=100",
                                   "Federal Reserve H.10",
                                   "FRED citation requested; distinct from ICE DXY; no redistribution assumed",
                                   14, 14),
}


def validate_fred_csv(raw: bytes, series: FredContextSeries) -> tuple[pd.DataFrame, list[str]]:
    table = pd.read_csv(BytesIO(raw), dtype=str, keep_default_na=False)
    if list(table.columns) not in (["observation_date", series.series_id], ["DATE", series.series_id]):
        raise ValueError(f"Unexpected FRED schema for {series.series_id}")
    stamps = pd.to_datetime(table.iloc[:, 0], format="%Y-%m-%d", errors="raise")
    if stamps.empty or stamps.isna().any() or stamps.duplicated().any() or not stamps.is_monotonic_increasing:
        raise ValueError("FRED dates must be nonempty, unique and ascending")
    raw_values = table[series.series_id]
    missing = raw_values.isin(("", "."))
    values = pd.to_numeric(raw_values.loc[~missing], errors="raise")
    if values.isna().any() or not values.map(lambda value: isfinite(value) and value > 0).all():
        raise ValueError("FRED context values must be finite and positive")
    frame = pd.DataFrame({"date": stamps.loc[~missing].dt.strftime("%Y-%m-%d"),
                          "value": values.astype(float)}).reset_index(drop=True)
    if frame.empty:
        raise ValueError("No observed FRED values")
    return frame, table.loc[missing].iloc[:, 0].tolist()


def latest_snapshot(root: Path, layer_id: str) -> tuple[pd.DataFrame, dict] | None:
    folders = sorted((root / "data/processed/context").glob("*/manifest.json"), reverse=True)
    for manifest_path in folders:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        item = manifest.get("series", {}).get(layer_id)
        if item:
            frame = pd.read_parquet(manifest_path.parent / f"{layer_id.lower()}.parquet")
            if (frame.empty or frame["date"].duplicated().any() or
                not frame["date"].is_monotonic_increasing or
                not frame["value"].map(lambda value: isfinite(value) and value > 0).all() or
                len(frame) != item["rows"] or frame.iloc[0]["date"] != item["available_from"] or
                frame.iloc[-1]["date"] != item["available_to"]):
                raise ValueError(f"Invalid stored context snapshot: {layer_id}")
            raw_path = root / "data/raw/context" / manifest_path.parent.name / f"{layer_id.lower()}.csv"
            if not raw_path.is_file() or sha256(raw_path.read_bytes()).hexdigest() != item["raw_sha256"]:
                raise ValueError(f"Raw context checksum mismatch: {layer_id}")
            return frame, item
    return None


def as_of_observation(frame: pd.DataFrame, selected_date: str, lag_days: int) -> dict | None:
    cutoff = (date.fromisoformat(selected_date) - timedelta(days=lag_days)).isoformat()
    position = int(frame["date"].searchsorted(cutoff, side="right"))
    if position == 0:
        return None
    row = frame.iloc[position - 1]
    return {"value": float(row["value"]), "observation_date": str(row["date"]),
            "selected_date": selected_date, "lag_days": lag_days,
            "status": "EXACT_OBSERVATION" if str(row["date"]) == selected_date else "LAST_KNOWN_OBSERVATION"}


class FredContextProvider:
    def __init__(self, root: Path, session=None):
        self.root = root
        self.session = session or requests

    def fetch(self, start: str, end: str, series: FredContextSeries) -> tuple[bytes, str]:
        if date.fromisoformat(start) > date.fromisoformat(end):
            raise ValueError("Invalid FRED date range")
        response = self.session.get(FRED_CSV_URL,
                                    params={"id": series.series_id, "cosd": start, "coed": end},
                                    timeout=60)
        response.raise_for_status()
        return response.content, response.url

    def validate(self, raw: bytes, series: FredContextSeries) -> tuple[pd.DataFrame, list[str]]:
        return validate_fred_csv(raw, series)

    def persist(self, start: str, end: str, layer_ids: tuple[str, ...]) -> dict:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        raw_folder = self.root / "data/raw/context" / stamp
        processed_folder = self.root / "data/processed/context" / stamp
        staged = {}
        for layer_id in layer_ids:
            series = FRED_SERIES[layer_id]
            raw, url = self.fetch(start, end, series)
            frame, missing = self.validate(raw, series)
            prior = latest_snapshot(self.root, layer_id)
            if prior:
                old = prior[0].set_index("date")["value"]
                new = frame.set_index("date")["value"]
                overlap = old.index.intersection(new.index)
                if not old.loc[overlap].equals(new.loc[overlap]):
                    raise ValueError(f"DATA_HISTORY_CHANGED: {layer_id}")
                frame = pd.concat([prior[0], frame.loc[~frame["date"].isin(prior[0]["date"])]],
                                  ignore_index=True).sort_values("date").reset_index(drop=True)
            staged[layer_id] = (series, raw, url, frame, missing)
        raw_folder.mkdir(parents=True, exist_ok=False)
        processed_folder.mkdir(parents=True, exist_ok=False)
        manifest = {"snapshot_id": stamp, "requested_start": start, "requested_end": end,
                    "downloaded_at": datetime.now(timezone.utc).isoformat(), "series": {}}
        for layer_id, (series, raw, url, frame, missing) in staged.items():
            (raw_folder / f"{layer_id.lower()}.csv").write_bytes(raw)
            frame.to_parquet(processed_folder / f"{layer_id.lower()}.parquet", index=False)
            manifest["series"][layer_id] = {
                "provider": "FRED", "original_source": series.original_source,
                "series_id": series.series_id, "source_url": f"https://fred.stlouisfed.org/series/{series.series_id}",
                "download_url": url, "downloaded_at": manifest["downloaded_at"],
                "frequency": "DAILY_OBSERVATION", "unit": series.unit,
                "timezone": "America/New_York", "license_note": series.license_note,
                "raw_sha256": sha256(raw).hexdigest(), "available_from": frame.iloc[0]["date"],
                "available_to": frame.iloc[-1]["date"], "rows": len(frame),
                "missing_observation_dates": missing,
                "availability_policy": {"KRX_lag_days": series.krx_lag_days,
                                        "US_lag_days": series.us_lag_days},
            }
        (processed_folder / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return manifest

    def provenance(self, layer_id: str) -> dict | None:
        snapshot = latest_snapshot(self.root, layer_id)
        return snapshot[1] if snapshot else None
