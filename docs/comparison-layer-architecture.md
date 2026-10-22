# STEP 8.1–8.2 — Full-width Comparison Research Workspace

Parent: [ZERO_MARKET_LAB_META.md](../ZERO_MARKET_LAB_META.md). The existing
`/asset_discovery/` Research UI now contains a chart-first comparison workspace.
Paper Replay (`/` on the local replay server) keeps its Journal-first priority;
neither strategy nor Paper accounting rules are changed here.

## Purpose and UX

## STEP 8.2 화면 규칙

기준 자산·시작/종료일·표시 모드는 상단에 둔다. 1M/3M/6M/1Y/3Y/ALL은
마지막 **실제 관측일**을 끝으로 계산하고, SIM은 직전에 실행한 투자조건의
기간을 가져온다. 버튼은 연구 차트 기간만 바꾸며 전략이나 Paper 계좌를
재실행하지 않는다. 비교 Layer는 추가·숨김·복원·제거할 수 있다.

TradingView Lightweight Charts engine already vendored in this repository
remains the chart engine. All connected financial lines share **one full-width
Plot and one date axis**. Actual mode keeps native units and separate price
scales; Normalize 100 puts each series' first in-period observation at 100
on a common scale. This is relative price movement, not currency conversion
or investable return. Crosshair previews a date; clicking locks it. A compact
OHLCV/flow/comparator/Phase/Transit summary sits above the chart rather than
in a side panel. Numeric indicators use a small strip below the chart, with
missing values explicitly N/A. The investment and deeper research accordions
start closed so the comparison chart remains prominent.

The Quarter and Gate/Line bands share the chart time scale, including interpolation
between observed trading days for weekend Gate boundaries. Zoom and pan update
the Band. No fictitious market bar is inserted on a weekend or holiday.

Research is chart-first; Replay remains Journal-first. Research has a single
main chart, selected-date summary, layer chips and optional provenance/Transit
details. The larger existing strategy sections remain below for the investment
experiment workflow.

## Layer model and availability

`/api/comparison/catalog` describes every layer using `layer_id`, type,
indicator ID, symbol, display name, unit, source, frequency, timezone, render
type, scale type, axis policy, availability, date bounds and metadata. Financial
series are read from the existing local OHLCV catalog. The S&P 500 price index
is read from the existing local FRED-derived parquet; dividends are excluded.
Market data is **local research data** with unverified redistribution rights.

Connected data here: six seed stocks (when their local files exist), the S&P
500 price index, `PRICE_PHASE_V1` from the frozen Phase Engine, and the
approximate Solar Transit calendar. VIX, CNN Fear & Greed, US10Y, DXY,
USD/KRW, Gold, foreign flow, and market breadth have **no connected source**
in this checkout. They are visible as `NOT_CONNECTED` research candidates;
selecting one never manufactures values or a RISK-ON/OFF classification.
Source authority, historical range, refresh schedule, license, redistribution,
API reliability and timezone must be audited before any new connector is added.
CNN Fear & Greed, if connected later, is **US sentiment**, not a Korean market
index. A future Korean sentiment composite is a separate hypothesis.

Actual mode retains original values and units on separate price scales in the
same Plot. Normalize 100
mode uses each financial series' first observed value **inside the selected
period**. Categorical Phase and Gate are never normalized or plotted as
numeric price lines. Mixed currencies in Normalize 100 show relative paths,
not KRW-converted investment performance.

## Selected-date context and time integrity

The backend computes exact-date context. A comparator absent on the selected
base trading day remains missing; there is no forward fill or synthetic price.
The latest visible base bar can predate the requested end date. A different
market's holiday creates a visible `NO_SAME_DATE_OBSERVATION` status. Weekly
and monthly indicators are not connected; when added in the future, the last
observation date and frequency must be displayed explicitly.

`PRICE_PHASE_V1` runs only on source bars through the selected end date and
remains observational context. The Solar Gate/Line at each base market close
uses the STEP 8 UTC/KRX/US mapping without changing it. The interpretation
comes from `data/reference/human_design_gates.json`; Gate 32's failure theme
is a Human Design interpretation, not evidence that it causes a market move.
The USNO solar boundaries are approximate and not independently verified by a
high-precision ephemeris. The JSON gives short paraphrased labels and a source;
unsupported fear/pressure/circuit attributes are null.

Financial context displays value, unit, same-date status and source where
observed. FECM Phase and Transit display categorical state with their timing
and meaning. The `interpret_indicator` backend model supports fixed-scale,
reference-threshold and historical-percentile interpretations **only when a
real observation is supplied**. Thresholds are research references, not laws.
No black-box market mood or correlation-based causal claim is generated.

## API and safeguards

- `GET /api/comparison/catalog`
- `GET /api/comparison/series?base=005930&start=2026-01-01&end=2026-10-22&layers=SP500,HD_TRANSIT&display=NORMALIZE_100`
- `GET /api/comparison/calendar?year=2026`
- `GET /api/comparison/context?base=005930&start=2026-01-01&end=2026-10-08&layers=HD_TRANSIT`

These extend the existing local Research server. The series endpoint returns
the observed series, same-date context and sanitized provenance. It validates
symbols, date order, period length and layer IDs. No endpoint places orders or
rewrites historical Paper events. The browser adds/removes only view layers;
source files are unaffected.

## Validation, limitations and next study

Unit tests cover metadata 1–64, Quarter ordering, source nullability,
Normalize 100, missing cross-market day, prior observed close outside a
one-day selected window, as-of exclusion, categorical Transit, Phase context,
scale classification and HTTP endpoints. Browser checks cover layer
add/remove, Actual/Normalize modes, date lock, Gate and Quarter bands,
unavailable indicators, and SIM period binding. The full existing
Strategy/Phase/Paper/Transit suite passed (310 tests on 2026-10-22).

Current local S&P 500 data ends 2026-10-02 and local Samsung data ends
2026-10-08; requested periods can extend later, but no later price is invented.
The selected-date panel currently gives no Macro/Sentiment/Flow conclusion
because these sources are not connected. High-precision Transit boundary
verification, genuine indicator sources, historical percentiles, weekly data
contracts, and matched-window statistical comparison belong to later steps.
STEP 9 must keep same-season/random-window controls and must not turn Gate
coincidence into a trading signal.

## Data source audit — STEP 8.2

The entries below are **candidates**, not connected feeds or permission to
redistribute their data. The UI currently shows N/A for them.

| Candidate | Source and authority | Frequency / history | License and integration decision |
| --- | --- | --- | --- |
| VIX | [Cboe via FRED VIXCLS](https://fred.stlouisfed.org/series/VIXCLS/) | Daily close; historical series exists | FRED identifies Cboe copyright. Do not ship a connector or redistribute until permission is reviewed. |
| CNN Fear & Greed | CNN public index display | Historical/API contract not verified | No official stable research API or redistribution permission verified; keep disconnected. US sentiment only. |
| US 10Y | [Federal Reserve H.15 via FRED DGS10](https://fred.stlouisfed.org/series/DGS10) | Daily observation, holidays missing; historical series exists | FRED labels public domain with citation requested, but live API/refresh timing and revision handling need a separate connector review. |
| USD/KRW | [Federal Reserve via FRED DEXKOUS](https://fred.stlouisfed.org/series/DEXKOUS) | Daily observation, publication lag; historical series exists | Review rate direction, release lag and terms before connecting. Never infer a Korean session's FX from later publication. |
| DXY | ICE U.S. Dollar Index | Historical and frequency contract not audited | ICE index terms not audited; disconnected. |
| Gold | LBMA or an explicitly licensed exchange/ETF series | Instrument, adjustment and history not chosen | No source/license chosen; disconnected. |
| KRX individual / institution / foreign / program flow | [KRX information system](https://data.krx.co.kr/) | Daily reporting is a possible source; coverage and release time require verification | [KRX/Koscom data usage policy](https://data.krx.co.kr/inc/datasale/Market%20Data%20Usage%20Polices_ko.pdf) needs contract/redistribution review. No fabricated flows. |

For every future connector, freeze series ID, observation date, **available-at
timestamp**, units, timezone, release lag, revisions, missing-day rule,
download record and redistribution terms before use. Current Korean stock
context exposes individual/institution/foreign flow as `NOT_CONNECTED`, not 0.
US stocks show `NOT_APPLICABLE` for Korean investor classes. The compact
context cannot infer RISK-ON/OFF from unconnected Macro/Sentiment/Flow fields.

STEP 8.3's verified local context connection, source limits and conservative
observation-date mapping are recorded in `docs/market-context-data-foundation.md`
and `docs/market-context-source-audit.md`.
The earlier candidate table is retained as the STEP 8.2 baseline; four FRED
series are now locally connected, while KRX stock-level flows remain N/A.
No STEP 8.1/8.2/8.3 commit/push before user screen review.

## Chart-first workspace — STEP 8.3 UI revision

The comparison chart now occupies the full available page width and a 610px
desktop plot. Controls, period shortcuts and active-layer chips stay compact.
The add-layer catalog opens only on demand as a searchable popover. Its entries
come from the server catalog and are limited to `AVAILABLE` observations or
`RESEARCH_ONLY` Phase/Transit context. `NOT_CONNECTED` entries remain in the
catalog and collapsed data-status details, but not in the main picker.

The selected date's OHLCV, daily change, selected comparison observations,
Phase and Transit appear in a small chart-internal tooltip only during hover
or after click pinning. The tooltip moves to the opposite side of the chart,
closes on pointer exit when unpinned, and unpins with Escape or its close
button. An observation on an earlier date is labeled with its own date; no
comparison value is filled across missing observations. Long descriptions and
source metadata remain in collapsed details. Unconnected investor-flow rows
are omitted from the tooltip. This changes presentation only; comparison,
strategy, paper, phase and calendar calculations retain their contracts.
