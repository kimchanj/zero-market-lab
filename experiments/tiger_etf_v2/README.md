# TIGER 미국S&P500 V2 Financial Chart

This isolated prototype renders validated, unadjusted daily OHLCV for KRX
`360750` with Lightweight Charts. It does not invoke Python when the user pans,
zooms, moves the crosshair, toggles layers, or changes a quick range.

```powershell
.venv\Scripts\python.exe scripts\fetch_tiger_360750.py --start 2020-08-01
.venv\Scripts\python.exe experiments\tiger_etf_v2\build_chart.py
.venv\Scripts\python.exe -m http.server 8061 --directory experiments\tiger_etf_v2
```

Open `http://127.0.0.1:8061/`. The payload builder fails before rendering if
OHLCV validation fails. No synthetic bar, forward-fill, strategy, or execution
assumption is present in this foundation.
