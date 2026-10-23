# STEP 9 preregistration — Transit × Market Context v1

Frozen before looking at Gate returns or rankings on 2026-10-23. This is
exploratory association research, not a causal model, forecast, or trading rule.
The existing solar calendar, Quarter map, PRICE_PHASE_V1 and market data are
inputs; their definitions will not be retuned after seeing results. Gate 32 is
the sole predeclared detailed case. All 64 Gates receive identical metrics.

## Questions and falsification

- H1: Gate return and within-window risk distributions differ from same-season,
  same-length random windows. Falsified for v1 when the observed effect is small,
  the random percentile is unremarkable, or annual signs are inconsistent.
- H2: Gate-associated VIX/rates/FX context differs descriptively. Falsified when
  the association is small, stale/missing, or inconsistent by year and asset.
- H3: An apparent Gate association attenuates after conditioning on the frozen
  FECM Phase. If it does, a Gate-specific interpretation is weakened.
- H4: A pattern found in Samsung may not replicate in SK hynix or the S&P 500
  Price Index. Opposite directions are counter-evidence, not filtered out.

Negative and insufficient results are retained. No 64-Gate ranking becomes a
Buy/Sell recommendation. Sixty-four simultaneous comparisons, overlapping
asset exposures, seasonality and only about seven annual repetitions preclude
strong confirmatory claims.

## Data and immutable analysis definitions

- Requested span: 2020-01-01 through the latest locally observed common end
  date of Samsung 005930, SK hynix 000660 and FRED SP500 Price Index. Pin the
  resolved end date, snapshot paths, checksums and phase rule hash in the run
  manifest. Local raw/processed data and derived outputs remain Git ignored.
  Availability audit before outcome calculation found Samsung and SK hynix
  starting 2020-08-24 and ending 2026-10-08, while SP500 starts earlier but
  ends 2026-10-02. The **common comparison span is 2020-08-24–2026-10-02**.
  The 2026 Gate 32 window is beyond this local span, so it must be marked
  unavailable rather than manufactured or silently counted as a seventh year.
- A Gate window is the existing astronomical `[start_utc, end_utc)` interval,
  merged across calendar-year boundaries where necessary. A window is complete
  only when both original solar boundaries lie inside the analysis span.
  Keep partial windows in the dataset but exclude them from inferential
  summaries. `year` means the UTC year of the Gate's original entry instant.
- Map each observed asset bar by its existing regular-session close instant:
  15:30 Asia/Seoul for Korean assets, 16:00 America/New_York for SP500.
  Never create weekend/holiday bars. Gate.Line is retained per bar, but v1
  comparisons are at Gate level. A window with fewer than three observed bars
  is `INSUFFICIENT SAMPLE` for return-volatility analysis.
- Window return = last observed close / first observed close - 1, in percent;
  no dividends, FX conversion or investable execution are implied. MDD is
  the minimum close-to-prior-peak change within that window; max run-up is
  the maximum close-to-prior-trough change. Daily volatility is the population
  standard deviation of consecutive within-window close returns, in percent,
  **not annualized**. Positive/negative ratios use those daily returns.
  Volume change is last/first observed volume - 1 when both are valid.
- Pre and post controls use the immediately adjacent *same number of observed
  asset bars* as the Gate window, excluding the Gate bars. They are descriptive
  trend checks, not investment signals. Record missing controls explicitly.
- FRED context uses existing stored snapshots and the frozen lag/staleness
  rules (`as_of_observation` plus 10/21/35-day maximum ages). Each joined
  value retains observation date and selected market date; missing/stale is
  null, never zero. Start/end/change/mean refer to the as-of values available
  on each asset date. A repeated last-known value is not an independent new
  observation. VIX percentile uses only history available by that date.
- PRICE_PHASE_V1 runs once per full asset history with its existing config and
  warm-up, without future bars for each row. Report start/end labels and
  within-window distribution. `UNKNOWN` remains explicit. The local SP500
  Price Index has close-only observations, so its Phase and volume fields are
  unavailable; do not fabricate OHLCV to obtain a Phase label.
- Quarter uses the frozen four-Quarter reference map and is a grouping label,
  separate from FECM Phase.

## Controls, multiplicity and status rule

- Random control: for each complete asset–Gate–year window, find contiguous
  observed-bar windows of exactly the same bar count, with midpoint within
  ±45 calendar days of the actual midpoint, in the same calendar year, and
  with no overlap with the actual Gate's bars. Draw 1,000 candidate windows
  with replacement using NumPy PCG64 and master seed **42** plus a stable
  SHA-256-derived per-window offset. If no candidates exist, mark control
  unavailable; never relax the rule after seeing outcomes. Record percentile
  rank of actual return, MDD and volatility in each null distribution.
- For each Gate and asset, report count, mean/median/std/min/max, annual sign
  consistency, and median observed-minus-random-median return effect (percentage
  points). Bootstrap 2,000 resamples of whole annual Gate windows (seed 42,
  stable Gate/asset offset) for a 95% percentile CI of mean and median return.
  These are descriptive intervals, not family-wise corrected inference.
- Phase-conditioned comparison uses the same asset's complete Gate windows
  with the same **start Phase**, excluding the target Gate. Report group sizes,
  difference in median return and missing groups; no post-hoc Phase merging.
- Status is per Gate–asset. `INSUFFICIENT SAMPLE` if fewer than five complete
  windows with at least three bars or more than half the required controls are
  absent. Otherwise count four exploratory flags: (a) at least 70% same sign
  across years, (b) absolute median observed-minus-random median effect at
  least 1 percentage point, (c) median random percentile outside 10–90%,
  (d) bootstrap mean-return CI excludes zero. Zero/flat returns do not count
  toward sign agreement. Zero or one flag = `NO EVIDENCE`; two or three =
  `WEAK`. `MODERATE` additionally requires at least six years, all four flags,
  percentile outside 5–95%, same directional effect in at least one other
  asset, and the phase-conditioned effect in the same direction. `STRONG`
  requires at least ten independent annual windows and is therefore unavailable
  in this 2020–2026 study. These labels are exploratory research status, not
  probability of causality.

## Ordered execution and stopping rules

1. Freeze this plan before reading outcome rankings.
2. Validate dataset alignment/metrics/random controls on Samsung only with
   synthetic unit fixtures and actual-data sanity checks.
3. Run the identical definitions over all 64 Gates for Samsung, SK hynix and
   SP500. Keep full window, annual, Gate summary and Quarter tables.
4. Examine random, pre/post, Phase and cross-asset counter-evidence before
   writing Gate 32's case study or any interpretation.
5. If a source, alignment or metric fails validation, stop outcome interpretation
   and report the failure. Do not change the preregistered thresholds to improve
   findings. Any later rule change needs a clearly versioned follow-up study.

The analysis report must separate observed associations, controls, missing
data, counter-evidence, limitations and untested next questions. Results and
plots are derived local artifacts; code, tests, this plan and a concise research
report are the reviewable Git candidates. No commit or push before user review.
