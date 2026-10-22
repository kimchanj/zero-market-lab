"""Compare private FRED raw observations with processed local snapshots."""

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zero_market_lab.research.context_data import (  # noqa: E402
    FRED_SERIES, latest_snapshot, validate_fred_csv,
)


def validate(root: Path) -> dict:
    report = {}
    for layer_id, definition in FRED_SERIES.items():
        snapshot = latest_snapshot(root, layer_id)
        if snapshot is None:
            raise FileNotFoundError(f"No local snapshot for {layer_id}")
        processed, metadata = snapshot
        raw_path = None
        for manifest in sorted((root / "data/processed/context").glob("*/manifest.json"), reverse=True):
            item = json.loads(manifest.read_text(encoding="utf-8"))["series"].get(layer_id)
            if item == metadata:
                raw_path = root / "data/raw/context" / manifest.parent.name / f"{layer_id.lower()}.csv"
                break
        if raw_path is None:
            raise FileNotFoundError(f"No source manifest for {layer_id}")
        raw, missing = validate_fred_csv(raw_path.read_bytes(), definition)
        joined = raw.merge(processed, on="date", suffixes=("_raw", "_processed"), validate="one_to_one")
        if len(joined) != len(raw) or not (joined["value_raw"] == joined["value_processed"]).all():
            raise ValueError(f"Raw/processed mismatch: {layer_id}")
        indices = sorted({0, len(joined) // 2, len(joined) - 1})
        report[layer_id] = {
            "series_id": definition.series_id, "unit": definition.unit,
            "source": metadata["original_source"], "frequency": metadata["frequency"],
            "range": [metadata["available_from"], metadata["available_to"]],
            "rows": metadata["rows"], "missing_dates": len(missing),
            "samples": [{"date": str(joined.iloc[i]["date"]),
                         "raw": float(joined.iloc[i]["value_raw"]),
                         "processed": float(joined.iloc[i]["value_processed"])}
                        for i in indices],
        }
    return report


if __name__ == "__main__":
    print(json.dumps(validate(ROOT), ensure_ascii=False, indent=2))
