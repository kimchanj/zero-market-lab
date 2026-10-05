"""Download, validate and chart one FRED SP500 snapshot (no backtest)."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd
import plotly.graph_objects as go

from zero_market_lab.market_data.loader import download, normalize, provenance
from zero_market_lab.market_data.validation import validate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", required=True, help="YYYY-MM-DD, inclusive")
    parser.add_argument("--end", required=True, help="YYYY-MM-DD, inclusive")
    args = parser.parse_args()
    raw, url, retrieved = download(args.start, args.end)
    snapshot = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    raw_dir = ROOT / "data" / "raw" / snapshot
    raw_dir.mkdir(parents=True, exist_ok=False)
    (raw_dir / "fred_sp500.csv").write_bytes(raw)
    # Preserve acquisition context even if normalization subsequently fails.
    (raw_dir / "request.json").write_text(json.dumps({"url": url, "retrieved_at": retrieved,
        "requested_start_date": args.start, "requested_end_date": args.end}, indent=2), encoding="utf-8")
    frame, excluded, raw_count = normalize(raw)
    metadata = provenance(frame, raw, args.start, args.end, url, retrieved, excluded, raw_count)
    result = validate(frame, metadata)
    if excluded:
        result.warnings.append(f"Excluded {len(excluded)} explicit missing observations; dates in metadata")
    metadata["validation"] = result.as_dict()
    metadata_path = raw_dir / "fred_sp500.metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps({"metadata": str(metadata_path), **metadata}, indent=2))
    if not result.passed:
        return 1
    processed = ROOT / "data" / "processed" / snapshot
    processed.mkdir(parents=True, exist_ok=False)
    parquet_path = processed / "sp500_price_daily.parquet"
    frame.to_parquet(parquet_path, index=False)
    pd.testing.assert_frame_equal(frame, pd.read_parquet(parquet_path))
    chart_dir = ROOT / "artifacts" / snapshot
    chart_dir.mkdir(parents=True, exist_ok=False)
    fig = go.Figure(go.Scatter(x=frame.date, y=frame.close, mode="lines", name="SP500"))
    fig.update_layout(title="S&P 500 Price Index — Daily Close<br>"
        "<sup>Source: FRED / S&P Dow Jones Indices | Dividend Excluded</sup>",
        xaxis_title="Date (US market observation date)", yaxis_title="Index points",
        template="plotly_white", hovermode="x unified", height=650)
    chart_path = chart_dir / "sp500_price_daily.html"
    fig.write_html(chart_path, include_plotlyjs=True)
    print(f"VALIDATION PASS | {len(frame)} rows | {metadata['actual_start_date']} .. {metadata['actual_end_date']}")
    print(f"PROCESSED: {parquet_path}\nCHART: {chart_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
