"""Generic OHLCV provider contract and a validated DataFrame adapter."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Protocol, Sequence

import pandas as pd

from .models import Instrument, MarketBar


class OHLCVProvider(Protocol):
    def load_ohlcv(
        self, instrument: Instrument, start: date, end: date, interval: str = "1D"
    ) -> Sequence[MarketBar]: ...


class FrameOHLCVProvider:
    """Adapt normalized frames without leaking provider details into the engine."""

    def __init__(self, frame: pd.DataFrame):
        self._frame = frame.copy()

    def load_ohlcv(
        self, instrument: Instrument, start: date, end: date, interval: str = "1D"
    ) -> list[MarketBar]:
        if interval != "1D":
            raise ValueError("FrameOHLCVProvider currently supports 1D bars only")
        required = {"date", "open", "high", "low", "close", "volume"}
        missing = sorted(required.difference(self._frame.columns))
        if missing:
            raise ValueError(f"Missing OHLCV columns: {missing}")
        frame = self._frame.copy()
        frame["date"] = pd.to_datetime(frame["date"], errors="raise")
        frame = frame.loc[
            (frame["date"].dt.date >= start) & (frame["date"].dt.date <= end)
        ].sort_values("date")
        if frame.empty:
            raise ValueError("No OHLCV bars in requested range")
        if frame["date"].duplicated().any():
            raise ValueError("Duplicate OHLCV dates")
        bars = []
        optional = ("trading_value", "nav", "bid", "ask")
        for row in frame.to_dict("records"):
            values = {
                key: None if key not in row or pd.isna(row[key]) else Decimal(str(row[key]))
                for key in optional
            }
            bars.append(
                MarketBar(
                    timestamp=pd.Timestamp(row["date"]).to_pydatetime(),
                    open=Decimal(str(row["open"])), high=Decimal(str(row["high"])),
                    low=Decimal(str(row["low"])), close=Decimal(str(row["close"])),
                    volume=Decimal(str(row["volume"])), **values,
                )
            )
        return bars
