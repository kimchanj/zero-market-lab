"""Approximate solar Gate/Line calendar, independent of market and strategy code.

The Sun longitude follows the US Naval Observatory's published low-order
algorithm (about one arcminute over 1800–2200), not a 365/64-day split.
Boundary instants are root-solved from longitude; they are *model estimates*,
not certified ephemeris event times.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
import json
from math import floor, radians, sin
from pathlib import Path
from zoneinfo import ZoneInfo

UTC = timezone.utc
KST = ZoneInfo("Asia/Seoul")
GATE_SEQUENCE = (
    41, 19, 13, 49, 30, 55, 37, 63, 22, 36, 25, 17, 21, 51, 42, 3,
    27, 24, 2, 23, 8, 20, 16, 35, 45, 12, 15, 52, 39, 53, 62, 56,
    31, 33, 7, 4, 29, 59, 40, 64, 47, 6, 46, 18, 48, 57, 32, 50,
    28, 44, 1, 43, 14, 34, 9, 5, 26, 11, 10, 58, 38, 54, 61, 60,
)
CENTERS = {
    "Head": (64, 61, 63),
    "Ajna": (47, 24, 4, 17, 43, 11),
    "Throat": (62, 23, 56, 35, 12, 45, 33, 8, 31, 20, 16),
    "G": (1, 13, 25, 46, 2, 15, 10, 7),
    "Heart": (21, 40, 26, 51),
    "Spleen": (48, 57, 44, 50, 32, 28, 18),
    "Solar Plexus": (6, 37, 22, 36, 30, 55, 49),
    "Sacral": (34, 5, 14, 29, 59, 9, 3, 42, 27),
    "Root": (58, 38, 54, 53, 60, 52, 19, 39, 41),
}
assert sorted(GATE_SEQUENCE) == list(range(1, 65))
assert sorted(gate for gates in CENTERS.values() for gate in gates) == list(range(1, 65))


@lru_cache(maxsize=1)
def _gate_metadata() -> dict[int, dict]:
    path = Path(__file__).resolve().parents[3] / "data/reference/human_design_gates.json"
    rows = json.loads(path.read_text(encoding="utf-8"))["gates"]
    if len(rows) != 64 or {row["gate"] for row in rows} != set(range(1, 65)):
        raise ValueError("Gate metadata must cover unique Gates 1–64")
    return {row["gate"]: row for row in rows}

PROVENANCE = {
    "source": "US Naval Observatory approximate solar coordinates; Rave Mandala gate wheel",
    "solar_method": "https://aa.usno.navy.mil/faq/sun_approx",
    "gate_wheel": "https://sunmoonascent.com/human-design",
    "gate_metadata": "https://soulether.com/human-design/gates (short labels paraphrased)",
    "source_version": "USNO J2000 low-order formula / wheel 302 degrees Aquarius",
    "accuracy": "Solar longitude approx. 1 arcminute; boundary times model-estimated, not ephemeris-verified",
    "timezone": "UTC source instants; Asia/Seoul display; half-open intervals",
}


def solar_longitude(instant: datetime) -> float:
    """Geocentric apparent tropical longitude in degrees, UTC-aware input."""
    if instant.tzinfo is None:
        raise ValueError("A timezone-aware instant is required")
    utc = instant.astimezone(UTC)
    epoch = datetime(2000, 1, 1, 12, tzinfo=UTC)
    days = (utc - epoch).total_seconds() / 86400
    anomaly = radians((357.529 + 0.98560028 * days) % 360)
    mean = 280.459 + 0.98564736 * days
    return (mean + 1.915 * sin(anomaly) + 0.020 * sin(2 * anomaly)) % 360


def gate_line(instant: datetime) -> tuple[int, int]:
    offset = (solar_longitude(instant) - 302.0) % 360
    slot = floor(offset / 5.625)
    line = floor((offset - slot * 5.625) / 0.9375) + 1
    return GATE_SEQUENCE[slot], min(6, line)


def _unwrapped(instant: datetime, reference: datetime) -> float:
    """Longitude unwrapped relative to a nearby reference (< 180 days)."""
    value = (solar_longitude(instant) - 302.0) % 360
    reference_value = (solar_longitude(reference) - 302.0) % 360
    return reference_value + ((value - reference_value + 180) % 360 - 180)


def _boundary(start: datetime, end: datetime, target: float) -> datetime:
    reference = start
    for _ in range(38):
        midpoint = start + (end - start) / 2
        if _unwrapped(midpoint, reference) < target:
            start = midpoint
        else:
            end = midpoint
    return end


def _segment(start: datetime, end: datetime) -> dict:
    midpoint = start + (end - start) / 2
    gate, line = gate_line(midpoint)
    metadata = _gate_metadata()[gate]
    return {
        "year": midpoint.year, "gate": gate, "line": line, "center": metadata["center"],
        "gate_name": metadata["gate_name"], "keynote": metadata["short_keynote"],
        "fear_or_theme": (f"Fear: {metadata['fear_theme']} (HD interpretation)"
                          if metadata["fear_theme"] else "미분류"),
        "source": PROVENANCE["solar_method"],
        "source_version": PROVENANCE["source_version"],
        "start_utc": start.isoformat(), "end_utc": end.isoformat(),
        "start_kst": start.astimezone(KST).isoformat(),
        "end_kst": end.astimezone(KST).isoformat(),
        "start_ny": start.astimezone(ZoneInfo("America/New_York")).isoformat(),
        "end_ny": end.astimezone(ZoneInfo("America/New_York")).isoformat(),
    }


@lru_cache(maxsize=16)
def year_calendar(year: int) -> dict:
    if not 2000 <= year <= 2100:
        raise ValueError("Transit calendar supports years 2000–2100")
    start = datetime(year, 1, 1, tzinfo=UTC)
    end = datetime(year + 1, 1, 1, tzinfo=UTC)
    boundaries = [start]
    cursor = start
    step = timedelta(hours=6)
    while cursor < end:
        following = min(cursor + step, end)
        initial = (solar_longitude(cursor) - 302.0) % 360
        final = _unwrapped(following, cursor)
        if final < initial:
            final += 360
        first_slot = floor(initial / 0.9375) + 1
        last_slot = floor(final / 0.9375)
        for slot in range(first_slot, last_slot + 1):
            crossing = _boundary(cursor, following, slot * 0.9375)
            if boundaries[-1] < crossing < end:
                boundaries.append(crossing)
        cursor = following
    boundaries.append(end)
    lines = [_segment(left, right) for left, right in zip(boundaries, boundaries[1:])]
    gates = []
    for segment in lines:
        if gates and gates[-1]["gate"] == segment["gate"]:
            gates[-1]["end_utc"] = segment["end_utc"]
            gates[-1]["end_kst"] = segment["end_kst"]
            gates[-1]["end_ny"] = segment["end_ny"]
        else:
            gates.append({key: value for key, value in segment.items() if key != "line"})
    return {"year": year, "lines": lines, "gates": gates, "provenance": PROVENANCE}


def at_instant(instant: datetime) -> dict:
    if instant.tzinfo is None:
        raise ValueError("A timezone-aware instant is required")
    utc = instant.astimezone(UTC)
    calendar = year_calendar(utc.year)
    segment = next(row for row in calendar["lines"]
                   if datetime.fromisoformat(row["start_utc"]) <= utc
                   < datetime.fromisoformat(row["end_utc"]))
    return {**segment, "provenance": PROVENANCE}


@lru_cache(maxsize=8192)
def at_market_close(market_date: str, currency: str = "KRW") -> dict:
    observed = date.fromisoformat(market_date)
    if currency == "KRW":
        zone, hour, minute = KST, 15, 30
    elif currency == "USD":
        zone, hour, minute = ZoneInfo("America/New_York"), 16, 0
    else:
        raise ValueError("Unsupported market currency")
    instant = datetime(observed.year, observed.month, observed.day, hour, minute, tzinfo=zone)
    return {**at_instant(instant), "market_close_utc": instant.astimezone(UTC).isoformat(),
            "market_date": market_date, "mapping_rule": f"{currency} regular-session close"}
