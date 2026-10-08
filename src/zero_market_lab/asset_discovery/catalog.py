"""Local-only market-data catalog; absence is explicit, never synthetic by default."""

from __future__ import annotations

import json
from pathlib import Path
import re

import pandas as pd


def load_universe(path: Path) -> list[dict]:
    assets = json.loads(path.read_text(encoding="utf-8"))["assets"]
    symbols = [item["symbol"] for item in assets]
    if len(symbols) != len(set(symbols)) or any(
        not ((item["market"] == "KRX" and re.fullmatch(r"\d{6}", item["symbol"])) or
             (item["market"] == "US" and re.fullmatch(r"[A-Z]{1,5}", item["symbol"])))
        for item in assets
    ):
        raise ValueError("Universe contains duplicate or invalid symbols")
    return assets


class LocalOHLCVCatalog:
    def __init__(self, root: Path):
        self.root = root
        self.read_count: dict[str, int] = {}
        self._cache: dict[str, tuple[pd.DataFrame, dict]] = {}

    def load(self, symbol: str) -> tuple[pd.DataFrame, dict]:
        if symbol not in self._cache:
            if not (re.fullmatch(r"\d{6}", symbol) or re.fullmatch(r"[A-Z]{1,5}", symbol)):
                raise ValueError("Invalid symbol")
            namespace = f"korea_{symbol}" if symbol.isdigit() else f"us_{symbol}"
            paths = sorted(path for path in (self.root / "data/processed" / namespace).glob("*/ohlcv.*")
                           if path.suffix in {".csv", ".json", ".parquet"})
            legacy = sorted((self.root / "data/processed/samsung_005930").glob("*/samsung_005930_ohlcv.csv")) if symbol == "005930" else []
            paths += legacy
            if not paths:
                raise FileNotFoundError(symbol)
            path = max(paths, key=lambda item: (item.parent.name,
                                               {".csv": 3, ".parquet": 2, ".json": 1}.get(item.suffix, 0)))
            self.read_count[symbol] = self.read_count.get(symbol, 0) + 1
            manifest = path.parent / "metadata.json"
            provenance = (json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists()
                          else {"provider": ("Daum Finance secondary provider" if "samsung_005930" in str(path)
                                             else "LOCAL_CSV_UNVERIFIED"),
                                "adjustment": "UNADJUSTED" if "samsung_005930" in str(path) else "UNKNOWN",
                                "retrieved_at": None, "source_url": None})
            provenance["path"] = str(path)
            if path.suffix == ".csv":
                frame = pd.read_csv(path)
            elif path.suffix == ".parquet":
                frame = pd.read_parquet(path)
            else:
                frame = pd.read_json(path)
            self._cache[symbol] = (frame, provenance)
        frame, provenance = self._cache[symbol]
        return frame.copy(), provenance.copy()
