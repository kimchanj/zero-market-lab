# Market Context Data Foundation — STEP 8.3

The comparison workspace reads private local snapshots and shows dated
observations beside prices. It does **not** feed Strategy, Paper, Phase or
LIVE_FORWARD decisions. The [source audit](market-context-source-audit.md)
lists connected and missing layers and their usage limits.

| UI name | Provider and original source | Series ID | Unit | Frequency | Local observed range |
| --- | --- | --- | --- | --- | --- |
| VIX | FRED / Cboe | VIXCLS | Index points | Daily close | 2016-10-03–2026-10-20 |
| 미국 10년물 국채수익률 | FRED / Federal Reserve H.15 | DGS10 | Percent yield | Daily observation | 2016-10-03–2026-10-20 |
| 원/달러 환율 (1 USD = KRW) | FRED / Federal Reserve H.10 | DEXKOUS | KRW per USD | Daily observation | 2016-10-03–2026-10-16 |
| 미 달러 광의지수 | FRED / Federal Reserve H.10 | DTWEXBGS | Jan 2006 = 100 | Daily observation | 2016-10-03–2026-10-16 |

`DTWEXBGS` is a **nominal broad dollar index**, never labeled ICE DXY. The
four local source CSVs, processed Parquet files and manifest are at
`data/raw/context/<snapshot>/` and `data/processed/context/<snapshot>/`.
They are ignored by Git and excluded from public Pages. The snapshot manifest
records download UTC time, provider, original source, URL, series ID, units,
timezone, observed range, row count, absent dates, SHA-256 and lag policy.

## Dates, missing data and future leakage

Each daily value carries its **observation date**. That date is not a verified
release timestamp. Until a point-in-time release calendar exists, a selected
KRX date may use only observations dated at least 1 calendar day earlier for
VIX, 2 days earlier for US10Y and 14 days earlier for H.10 FX/dollar series.
For a US asset the assumed delays are 0, 2 and 14 days respectively. This
conservative rule is a research assumption rather than a release-time claim.
The UI displays the selected context date and distinct observation date, and
labels previous known observations. It never selects an observation after the
chosen cutoff. VIX older than 10 days, US10Y older than 21 days, and H.10
series older than 35 days become N/A. No zero fill, price forward fill,
interpolation, fabricated data or retroactive overwrite is allowed. Financial
asset prices require their own exact observation date; cross-market holidays
remain missing.

The loader validates ascending unique dates and finite positive values. The
collector rejects a changed historical overlap; a deliberate revision would
need a separately reviewed snapshot. On read, raw file SHA-256, processed
row count, bounds and ordering are checked. The UI keeps a partial/insufficient
context label because KRX investor flow and other sources are absent.
Descriptions and historical percentiles are contextual and do not imply
causation or a risk-on/off signal.

## Source-to-snapshot samples

`python scripts/validate_market_context_snapshot.py` compared **all raw
observations** with overlapping processed rows in the local snapshot
`20261022T062654423697Z`; three representative raw→processed samples per
series are shown below. The validator fails on any mismatch.

| Series | Earliest | Middle | Latest |
| --- | --- | --- | --- |
| VIXCLS | 2016-10-03: 13.57→13.57 | 2021-11-01: 16.41→16.41 | 2026-10-20: 17.31→17.31 |
| DGS10 | 2016-10-03: 1.63→1.63 | 2021-10-08: 1.61→1.61 | 2026-10-20: 5.12→5.12 |
| DEXKOUS | 2016-10-03: 1104.79→1104.79 | 2021-10-13: 1193.89→1193.89 | 2026-10-16: 1334.03→1334.03 |
| DTWEXBGS | 2016-10-03: 112.5077→112.5077 | 2021-10-14: 114.2053→114.2053 | 2026-10-16: 121.4048→121.4048 |

The local Korean stock data end 2026-10-08, so later FRED observations do
not extend its chart. [KRX's individual-stock investor trading menu](https://data.krx.co.kr/contents/MDC/MAIN/main/index.cmd?vsView=Y)
exists, but an authorized reproducible extraction, timestamp contract and
rights for individual/institution/foreign flows remain unresolved. Keep them
`NOT_CONNECTED` for Korean stocks and `NOT_APPLICABLE` for US stocks.
Gold, Fear & Greed and licensed ICE DXY are also unconnected. The
[FRED terms](https://fred.stlouisfed.org/legal/terms/) and Cboe copyright
require a separate public redistribution review. Nothing in these local
files should be committed or deployed publicly.
