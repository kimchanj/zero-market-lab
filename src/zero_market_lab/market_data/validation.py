"""Strict normalized-data checks, independent of the data provider."""

from dataclasses import dataclass, field
import math

import pandas as pd


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict:
        return {"passed": self.passed, "errors": self.errors, "warnings": self.warnings}


def validate(frame: pd.DataFrame, metadata: dict | None = None) -> ValidationResult:
    """Reject bad order/values; never silently sort, deduplicate or fill prices."""
    result = ValidationResult()
    if not {"date", "close"}.issubset(frame.columns):
        result.errors.append("Required columns: date, close")
        return result
    if frame.empty:
        result.errors.append("Empty dataset")
        return result
    dates = pd.to_datetime(frame["date"], format="%Y-%m-%d", errors="coerce")
    close = pd.to_numeric(frame["close"], errors="coerce")
    if dates.isna().any():
        result.errors.append("Unparseable or null date")
    if dates.duplicated().any():
        result.errors.append("Duplicate date")
    if not dates.is_monotonic_increasing:
        result.errors.append("Dates must be ascending")
    if close.isna().any():
        result.errors.append("Null or nonnumeric close")
    if not close.map(lambda v: pd.notna(v) and math.isfinite(v) and v > 0).all():
        result.errors.append("Close must be finite and > 0")
    if dates.notna().all():
        if (dates.dt.dayofweek >= 5).any():
            result.warnings.append("Weekend observation")
        if (dates.diff().dt.days > 7).any():
            result.warnings.append("Suspicious gap > 7 calendar days")
        if metadata is not None:
            try:
                start = pd.Timestamp(metadata["actual_start_date"])
                end = pd.Timestamp(metadata["actual_end_date"])
                requested_start = pd.Timestamp(metadata["requested_start_date"])
                requested_end = pd.Timestamp(metadata["requested_end_date"])
                if any(pd.isna(v) for v in (start, end, requested_start, requested_end)):
                    raise ValueError("null metadata date")
                if start > end or requested_start > requested_end:
                    result.errors.append("Invalid metadata date range")
                if start != dates.min() or end != dates.max():
                    result.errors.append("Actual date bounds do not match dataset")
                if metadata["row_count"] != len(frame):
                    result.errors.append("Metadata row_count mismatch")
                if dates.min() < requested_start or dates.max() > requested_end:
                    result.errors.append("Observation outside requested period")
                if start > requested_start:
                    result.warnings.append("Actual start later than requested start")
                if end < requested_end:
                    result.warnings.append("Actual end earlier than requested end")
            except (KeyError, TypeError, ValueError):
                result.errors.append("Missing or invalid metadata bounds/count")
    return result
