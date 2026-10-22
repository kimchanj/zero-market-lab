# STEP 8.3 — Market context source and availability audit

Status: **partial connection, local research only**. Audited 2026-10-22.
The comparison UI is evidence display, not a trade signal. No STEP 9 inference
or order logic is introduced. This record extends
`docs/comparison-layer-architecture.md` and follows `ZERO_MARKET_LAB_META.md`.

| Layer | Source / local file | Coverage / frequency / last observation | State and reason |
| --- | --- | --- | --- |
| Samsung 005930 OHLCV | Daum secondary provider; existing ignored local OHLCV snapshot | 2020-08-24–2026-10-08; daily; 2026-10-08 | AVAILABLE for observed dates only |
| S&P 500 price index | FRED / S&P Dow Jones; `data/processed/*/sp500_price_daily.parquet` | Through 2026-10-02 locally; daily | AVAILABLE; excludes dividends |
| VIX | [FRED VIXCLS](https://fred.stlouisfed.org/series/VIXCLS), original Cboe; `data/raw/context/<snapshot>/vix.csv`, processed Parquet | 2016-10-03–2026-10-20; 2,559 observed days | AVAILABLE locally, private noncommercial research only; Cboe copyright prevents publishing raw values without permission |
| US 10Y | [FRED DGS10](https://fred.stlouisfed.org/series/DGS10), Federal Reserve H.15; analogous `us10y.*` | 2016-10-03–2026-10-20; 2,511 observed days | AVAILABLE locally; percent yield, not bond total return |
| USD/KRW | [FRED DEXKOUS](https://fred.stlouisfed.org/series/DEXKOUS), Federal Reserve H.10; analogous `usdkrw.*` | 2016-10-03–2026-10-16; 2,506 observed days | AVAILABLE locally with conservative release delay; KRW per USD, not a transaction FX quote |
| Broad U.S. dollar | [FRED DTWEXBGS](https://fred.stlouisfed.org/series/DTWEXBGS), Federal Reserve H.10; analogous `broad_usd.*` | 2016-10-03–2026-10-16; 2,504 observed days | AVAILABLE locally; **not ICE DXY** |
| ICE DXY | ICE index; no licensed local series | None | NOT_CONNECTED; no entitlement confirmed |
| Gold | Instrument/source and adjustment not frozen | None | NOT_CONNECTED; no defensible series chosen |
| Fear & Greed | No verified licensed historical API | None | NOT_CONNECTED; no scraped proxy |
| KRX individual / institution / foreign flow | [KRX per-stock investor trading menu](https://data.krx.co.kr/contents/MDC/MAIN/main/index.cmd?vsView=Y); no approved local export | None | NOT_CONNECTED; automated per-stock source/usage permission and publication timing not verified |
| Program trading | No validated per-stock provider | None | NOT_CONNECTED |
| Market breadth | No frozen universe or source | None | NOT_CONNECTED |

The local FRED snapshot ID is `20261022T062654423697Z`, with raw CSV,
processed Parquet and an ignored manifest at
`data/processed/context/<snapshot>/manifest.json`. The manifest contains the
series ID, original source, URL, download time (UTC), unit, timezone, date
range, row count, missing observations, raw SHA-256 and availability policy.
These files are ignored by Git; none belongs in public Pages artifacts.
`scripts/refresh_market_context.py` fetches official FRED graph CSV and
rejects schema errors, duplicate/unsorted dates, nonfinite/nonpositive values
and changed overlapping history. No missing value becomes zero. If FRED
revises history, the job fails with `DATA_HISTORY_CHANGED`; compare and
version that revision explicitly before accepting it. The reader checks
snapshot count/range and raw checksum.

## Date contract

The data carry **observation dates**, not verified intraday release
timestamps. To avoid presenting future information as known, the UI uses
conservative *calendar-day* lags when mapping to a selected exchange date:
VIX 1 day for KRX / 0 for US; DGS10 2 / 2; H.10 exchange/dollar series
14 / 14. These are research assumptions, **not claims about actual official
publication times**. The actual prior observation date, lag and source are
shown. A missing or excessively old value remains N/A; the UI does not
interpolate or fill price bars. The context is descriptive and is not used by
Paper Trading, Strategy or Phase engines. A future point-in-time release
calendar is required before using these observations in a trading backtest.

US versus KRX holidays and different closes are handled by taking the last
observed US value no later than the selected date minus the lag; same-date
assumption is never applied to KRX for US indicators. A 10/08 KRX close, for
example, can show VIX observed 10/07. `available_to` can exceed the price
dataset's final date, but no price is extrapolated. Historical percentile
descriptions use only preceding/selected eligible observations (up to 252).

## Rights and remaining work

[FRED terms](https://fred.stlouisfed.org/legal/terms/) and the individual
source pages govern use. VIXCLS identifies Cboe copyright. Keep the current
FRED values in the private local workspace and exclude them from GitHub Pages,
repository data files and public API deployment. [KRX/Koscom's data usage
policy](https://data.krx.co.kr/inc/datasale/Market%20Data%20Usage%20Polices_ko.pdf)
requires review before redistribution; KRX Open API access also requires
registration/approval. Do not infer stock-level investor flows from
market-wide numbers. KRX flow remains the main unfinished P0 item.
Verify an authorized per-stock export/API, its units (amount versus shares),
subject taxonomy, announcement time, history, corrections and rights before
turning the three N/A cards into values. Gold, Fear & Greed and ICE DXY remain
unconnected. The broad dollar index is explicitly labeled as an alternative,
never silently relabeled DXY.
