# STEP 8 — Solar Transit Market Research Layer v0.1

This layer is **descriptive research context** inside the existing Paper Replay
workspace. It does not affect strategy decisions, PRICE_PHASE_V1, orders,
fills, or Paper accounting. No causal connection between a Human Design Gate
and a market move is assumed. The `/manual/` portfolio uses the same compact
Journal-first information priority and can display its current Gate context.

## Data and time rules

- The Rave Mandala wheel contains 64 Gates in zodiac order, beginning with Gate
  41 at tropical longitude 302°; each Gate spans 5.625° and each Line 0.9375°.
  The calendar is generated from solar longitude, **not** by dividing a year
  into 64 equal time windows. Its UTC half-open intervals cover Jan 1 through
  the following Jan 1 without gaps; boundaries on weekends remain on weekends.
- Solar longitude uses the [US Naval Observatory approximate solar coordinate
  formula](https://aa.usno.navy.mil/faq/sun_approx). USNO estimates about one
  arcminute of angular accuracy in this era. We numerically solve each Gate and
  Line crossing within that **approximate model**; the sub-second timestamps
  are computational precision, not observational accuracy. These are **model
  estimates**, pending independent high-precision ephemeris checks.
- Gate order and center assignment were cross-checked against the [Rave Mandala
  wheel table](https://sunmoonascent.com/human-design). Short Gate labels are
  paraphrased from [Soulether's Gate table](https://soulether.com/human-design/gates).
  The UI does not copy extended interpretive descriptions. Gate 32's
  `Fear: Failure` is tagged explicitly as a Human Design interpretation, not a
  market observation. Other fear themes remain unclassified pending source
  review.
- UTC is retained for boundaries; Asia/Seoul is shown in the UI. KRX daily bars
  map at 15:30 Asia/Seoul. US daily bars map at 16:00 America/New_York,
  including daylight-saving changes. No weekend/holiday price bar is invented.
  Solar and OHLCV data are separate until this market-close join.

The annual API is `/api/transit/year?year=2026`; a selected market date can be
queried with `/api/transit/current?date=YYYY-MM-DD&currency=KRW`. The market
summary endpoint `/api/transit/gate-metrics?symbol=005930&year=2026&gate=32&as_of=YYYY-MM-DD`
uses only observed bars through `as_of`. Missing trading value, investor flow,
program trades, and breadth are returned as `null`, not estimated. Return,
drawdown, max rise, mean daily return, daily volatility, total/average volume,
and volume change are
simple within-window observations; the first and last included market closes
define the measured return. Phase context is displayed elsewhere in Replay and
is not inferred from Transit.

## UI integration and lookahead boundary

The existing `/` Paper Replay retains Journal, Account, Today, and Position as
the prominent accordion sections. Price and strategy-vs-S0 charts remain small
and closed by default. A compact Gate band sits directly beneath the existing
price chart. The default **Replay** chart and Band only extend to processed
market dates. The same chart has an explicit **read-only annual research** mode,
fed by `/api/transit/market-year?symbol=005930&year=2025`, for complete past
calendar years. It never changes the Replay account, Journal, orders, or
strategy; its price markers are hidden to avoid implying Replay trades occurred
there. The current year can be partial if local data have not been refreshed.
The annual calendar selector in the collapsed-by-default Transit accordion
permits 2020–2026 Gate browsing. Journal date selection and Run Next Day refresh
the default selected-date header and detail via the returned date. The
selected Gate shows only a processed Replay phase for its current interval;
other Gate periods explicitly show that no Phase Replay was computed.

## Research hypothesis and falsification plan

Candidate H32: conditional on independently defined adverse market regimes,
market responses during Gate 32 might differ in magnitude from matched
windows. This is a question, not an expectation or a trading rule. Reject it if
the relation disappears against other Gates, same-season random windows, or
pre/post windows after accounting for multiple comparisons, regime, and
selection bias. STEP 8 presents descriptive values only and makes no
statistical or investment conclusion.

## Known limitations and next checks

### STEP 8.2 Four Quarters and Korean interpretation metadata

`data/reference/human_design_quarters.json` defines four named 16-Gate
quarters. Their sequence follows the frozen zodiac Gate order; the start,
turning and end Gates are validated on load. The visual boundaries are symbolic
Solar Transit context and use the same approximate longitude model as the Gate
calendar. Research chart boundaries are marked even if they fall on a market
holiday; this never creates a price observation. Quarter themes, Korean Center
and Gate descriptions in `human_design_gates.json` are short interpretive
metadata, not market observations or trading signals. Gate 32's failure theme
is explicitly labeled as interpretive. Detailed English metadata remains in
the optional Transit accordion, while compact Korean labels appear in the
chart hover summary. The chart band may switch between Gate and Gate.Line
detail as zoom changes, without changing underlying dates.

Quarter labels and 16-Gate structure were cross-checked with the
[Jovian Archive Human Design dictionary](https://jovianarchive.com/pages/human-design-dictionary).
The source provides a symbolic framework, not evidence for a financial
relationship. The calendar remains a model estimate pending independent
high-precision ephemeris verification.

The STEP 8.3 comparison overlay marks the start of each Quarter's turning Gate
(25/15/46/10) with a subtle **vertical** dashed line on the date axis. A short
Korean label identifies the Gate. Distinct solid vertical lines mark Quarter
starts; the Quarter band retains four category colors. These are timing
annotations, not price/yield values or trading signals. Gate.Line labels in
the lower band appear only when zoom leaves enough room. The source Gate and
Quarter calculations are unchanged.

- Gate 18/48/57/32/50/28/44 entrances were compared with the published
  [2026 Human Design calendar](https://thehumandesign.com/learn/calendar-2026.html)
  and fall within 20 minutes; Gate 41 entrance is within ten minutes. This is
  a cross-check, **not** independent ephemeris verification. Compare Line
  boundaries and all Gates against a high-precision licensed ephemeris before
  labeling event times “verified.” At KRX close on 2026-10-22 the model gives
  Gate 50 Line 3, matching the [current Human.Design transit
  reference](https://human.design/daily-impact) for that date; this is a
  point check, not a general Line accuracy certification.
- Trading value, flow, program activity, and breadth are not yet sourced.
  Their absence must remain visible rather than
  being filled with guesses.
- The local Paper Replay UI still needs user screen review. No STEP 8 commit or
  push is authorized before that review.
