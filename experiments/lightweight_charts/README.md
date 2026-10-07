# Lightweight Charts 5.2.1 Spike

This isolated experiment evaluates TradingView Lightweight Charts as a future visualization layer.
It does not replace the STEP 5 Dash/Plotly UI and does not change backtest or strategy logic.

```powershell
.\.venv\Scripts\python.exe experiments/lightweight_charts/build_prototype.py
.\.venv\Scripts\python.exe -m http.server 8060 --directory experiments/lightweight_charts
```

Open `http://127.0.0.1:8060`. The prototype uses the existing real S&P500 daily close snapshot,
Case #01 comparison service, and Strategy C Event Log. It deliberately contains no fabricated OHLC or volume.
Lightweight Charts 5.2.1 is vendored only for repeatable prototype execution.

Use a focused URL such as
`http://127.0.0.1:8060/?from=2026-03-01&to=2026-10-02&events=core` to inspect a
Take Profit → cash wait → Reentry sequence without the monthly BUY markers.

The page includes the attribution required by the Lightweight Charts license and links to TradingView.
