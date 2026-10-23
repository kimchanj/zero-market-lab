# STEP 9 — Transit × Market Context Research v1

**Result: exploratory negative evidence for Gate 32; no Gate is confirmed as a market cause or trading signal.** This study follows the [plan frozen before outcome inspection](transit-market-study-v1-plan.md). Its status labels describe limited, uncorrected observations, not predictive confidence. No Strategy, Paper, PRICE_PHASE_V1, astronomical Transit, Gate.Line or Quarter rule was changed.

## Purpose, hypotheses and falsification

The question is whether existing Solar Transit Gate windows have repeatable associations with observed market behavior, after same-season random windows, adjacent windows, frozen FECM Phase and other assets are examined. H1 asks whether price and risk distributions differ from random windows; H2 describes macro context; H3 asks whether apparent effects attenuate within Phase; H4 tests whether one asset's result fails to replicate. Reversed annual signs, ordinary random percentiles, small effects, cross-asset disagreement and confidence intervals crossing zero are retained as counter-evidence. The plan's status thresholds were not retuned after results.

## Inputs and reproducibility

The common observed comparison span is **2020-08-24–2026-10-02**, despite the requested 2020-01-01 start. Samsung Electronics 005930 and SK hynix 000660 use locally pinned Daum secondary-provider OHLCV (both 1,497 bars in this span); the S&P 500 uses locally pinned FRED/S&P Dow Jones **price index**, 1,535 close-only bars. The latter excludes dividends and does not have enough OHLCV to run PRICE_PHASE_V1; its Phase and volume are null. All three are unhedged local-currency observations, not directly comparable investment returns. Their snapshot hashes and the analysis-code SHA-256 are in `manifest.json`.

Pinned FRED context is [VIXCLS](https://fred.stlouisfed.org/series/VIXCLS), [DGS10](https://fred.stlouisfed.org/series/DGS10), [DEXKOUS](https://fred.stlouisfed.org/series/DEXKOUS), and [DTWEXBGS](https://fred.stlouisfed.org/series/DTWEXBGS). The last is the **Broad U.S. Dollar Index, not ICE DXY**. SP500 series provenance is [FRED SP500](https://fred.stlouisfed.org/series/SP500). The analysis reads stored local snapshots, not live values from these pages. The existing as-of policy applies provider lags and maximum ages; stale or unavailable macro observations stay null and observation dates are preserved. A structural audit found all recorded observation dates on or before their selected market dates, and no null macro means in complete windows. Last-known repeats are not independent observations.

Run from the repository root with its existing virtual environment:

```powershell
.\.venv\Scripts\python.exe scripts/run_transit_market_research.py --output data/processed/research/<new-run-name>
.\.venv\Scripts\python.exe scripts/plot_transit_market_research.py data/processed/research/<new-run-name>
```

The frozen run used seed **42**, 1,000 NumPy PCG64 same-season draws per complete window, 2,000 bootstrap resamples per Gate–asset, and source/config hashes in the manifest. A second full calculation produced byte-identical Window, 64-Gate and Quarter CSV files. The result folder refuses overwrites. Derived market CSV/Parquet and charts remain Git ignored under `data/processed/research/` and `artifacts/`.

## Window and control definitions

Existing astronomical `[Gate entry, next entry)` boundaries are used without shifting. Existing market-close mappings assign each observed daily bar; Gate.Line is recorded but not separately tested. Return is last/first observed close minus one. MDD and maximum run-up use *within-window* preceding close peaks/troughs. Volatility is population standard deviation of consecutive daily close returns, **unannualized**. Positive/negative day ratios exclude the first bar; volume change is last/first volume when present. Pre/post controls use the immediately adjacent *equal number of observed bars* and exclude Gate bars. Their return is descriptive, not an execution price.

Each random candidate has the same observed-bar count, a midpoint within ±45 calendar days of the actual midpoint, the same midpoint year, and no overlapping Gate bar. Sampling is with replacement. A random percentile is the position of the actual window metric among 1,000 same-season returns, MDDs or volatilities. The candidate pool can include dates later than the target Gate: this is a **retrospective null distribution**, never a live predictive input. Phase is generated once by the frozen PRICE_PHASE_V1 for each Korean asset using only historical bars up to each label. Quarter is a separate pre-existing symbolic grouping. These controls cannot remove all seasonality, overlap, macro confounding or multiple testing.

The dataset has **1,176 asset–window rows** (392 solar windows × 3), of which **1,122 are complete** under the plan's ≥3-observed-bar rule: Samsung 371, SK hynix 371, SP500 380. The remaining 54 are explicitly `INSUFFICIENT SAMPLE`. All 64 Gates exist for each asset in the **192-row summary**; every complete row has a random return control, and there are no duplicate asset–year–Gate keys. Three to seven annual windows per Gate–asset are available; the median is six. The 2026 Gate 32 entry is outside the common local span and is **unavailable**, not a seventh outcome.

## All-Gate observations

| Asset | Complete windows | All-window median return | Median within-window MDD | Median daily volatility | Gate status: no evidence / weak / insufficient |
|---|---:|---:|---:|---:|---:|
| Samsung 005930 | 371 | +0.14% | −1.33% | 1.10% | 53 / 7 / 4 |
| SK hynix 000660 | 371 | +0.43% | −1.88% | 1.74% | 46 / 14 / 4 |
| SP500 price index | 380 | +0.33% | −0.57% | 0.55% | 54 / 6 / 4 |

No Gate–asset reached the preregistered `MODERATE` or `STRONG` criteria. The 27 `WEAK` labels among 192 exploratory comparisons are **not discoveries**: 64 Gates × 3 assets, only about six annual repeats, correlated semiconductor exposures, no family-wise correction, and many random windows make extremes expected. No Gate was `WEAK` in all three assets. Only SK hynix Gate 4 had all four exploratory flags, but its five complete years fail the ≥6-year condition. The full summary retains mean, median, standard deviation, min/max, positive ratio, MDD, volatility, macro context, random effect/percentile, bootstrap intervals and Phase comparison for **every** Gate.

Observed high/low medians are reported solely to expose selection risk. SK hynix's highest observed medians were Gates 57 (+4.49%), 48 (+4.33%) and 4 (+4.07%), each with only five complete windows and `WEAK` status; its lowest was Gate 7 (−3.90%, `NO EVIDENCE`). Samsung's highest was Gate 39 (+3.26%, `NO EVIDENCE`), lowest Gate 33 (−2.12%, `NO EVIDENCE`). SP500's highest was Gate 51 (+1.23%, `WEAK`), lowest Gate 63 (−1.42%, `WEAK`). These are uncorrected observed medians, not “best Gate” rankings or suggested entry/exit dates.

For perspective, the smallest absolute observed-minus-random median return effects were Samsung Gate 2 (+0.002 pp), SK hynix Gate 43 (+0.010 pp) and SP500 Gate 53 (+0.009 pp), all `NO EVIDENCE`. These near-zero examples are retained alongside the visually extreme observations.

## Gate 32 — prespecified detailed case

Gate 32 belongs to the pre-existing **Duality Quarter**. The table keeps all six complete years and all three assets. `%ile` is actual return's within-year same-season random percentile; `Pre/Post` are equal-bar adjacent returns. Phase is the frozen start label; SP500 has no Phase.

| Asset | Year | Bars | Return | MDD | VIX mean / Δ | US10Y Δ pp | USD/KRW Δ | Broad USD Δ | Phase | Random %ile | Pre / Post |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| Samsung | 2020 | 4 | −1.48% | −2.30% | 26.71 / +1.34 | −0.03 | −0.70% | −0.66% | UNKNOWN | 22.3 | +1.67% / −1.15% |
| Samsung | 2021 | 4 | +1.73% | 0.00% | 17.03 / −2.33 | 0.00 | +0.39% | −0.24% | AUTUMN | 87.3 | −3.91% / −0.14% |
| Samsung | 2022 | 4 | −0.89% | −1.41% | 31.46 / −1.44 | +0.11 | −1.46% | −0.51% | WINTER | 41.9 | −1.78% / +3.96% |
| Samsung | 2023 | 4 | +3.27% | −1.42% | 18.41 / −0.10 | +0.20 | −0.11% | +0.69% | AUTUMN | 89.5 | +2.41% / −1.16% |
| Samsung | 2024 | 5 | −2.63% | −2.95% | 19.90 / −1.35 | −0.06 | +2.57% | +0.77% | WINTER | 51.8 | −2.15% / −5.25% |
| Samsung | 2025 | 4 | +6.88% | 0.00% | 21.45 / +6.28 | 0.00 | +0.11% | −0.04% | SUMMER | 84.9 | +8.49% / −1.63% |
| SK hynix | 2020 | 4 | +0.23% | −2.07% | 26.71 / +1.34 | −0.03 | −0.70% | −0.66% | UNKNOWN | 41.5 | +5.76% / −1.53% |
| SK hynix | 2021 | 4 | +4.16% | −1.32% | 17.03 / −2.33 | 0.00 | +0.39% | −0.24% | WINTER | 84.4 | −3.87% / +2.15% |
| SK hynix | 2022 | 4 | −2.72% | −3.03% | 31.46 / −1.44 | +0.11 | −1.46% | −0.51% | WINTER | 36.6 | +4.06% / +3.66% |
| SK hynix | 2023 | 4 | +1.29% | −3.31% | 18.41 / −0.10 | +0.20 | −0.11% | +0.69% | SUMMER | 65.6 | +4.35% / +1.03% |
| SK hynix | 2024 | 5 | −0.11% | −4.44% | 19.90 / −1.35 | −0.06 | +2.57% | +0.77% | AUTUMN | 54.1 | +6.84% / +5.29% |
| SK hynix | 2025 | 4 | +13.12% | 0.00% | 21.45 / +6.28 | 0.00 | +0.11% | −0.04% | SUMMER | 89.8 | +15.28% / −1.44% |
| SP500 | 2020 | 4 | −0.80% | −0.81% | 26.71 / +1.34 | −0.06 | −0.31% | −0.68% | unavailable | 30.7 | +3.36% / +0.78% |
| SP500 | 2021 | 3 | +1.09% | 0.00% | 16.49 / −0.55 | 0.00 | −0.11% | −0.32% | unavailable | 92.1 | +0.06% / +0.67% |
| SP500 | 2022 | 3 | +3.82% | 0.00% | 31.30 / −1.52 | +0.09 | −0.41% | −1.05% | unavailable | 95.5 | +2.26% / +1.56% |
| SP500 | 2023 | 4 | −2.19% | −2.19% | 18.93 / +4.19 | +0.20 | −0.11% | +0.69% | unavailable | 4.2 | −0.70% / −0.89% |
| SP500 | 2024 | 5 | +0.08% | −0.76% | 19.41 / −1.67 | −0.06 | +2.57% | +0.77% | unavailable | 39.5 | +2.09% / −0.78% |
| SP500 | 2025 | 4 | +0.30% | −0.63% | 21.89 / −0.03 | 0.00 | +0.11% | −0.04% | unavailable | 46.5 | −1.47% / +0.05% |

For Gate 32, median returns are **+0.42% Samsung, +0.76% SK hynix, +0.19% SP500**. Median MDDs are **−1.42%, −2.55%, −0.70%**. Relative to matched random-window medians, observed median effects are **+0.96, +0.71, −0.26 percentage points**, while median return percentiles are **68.35, 59.85, 43.00**. All are ordinary rather than extreme random positions. Bootstrap 95% descriptive intervals for *mean* return are **[−1.32, +3.83]**, **[−0.63, +7.03]** and **[−1.03, +1.97]** percent, respectively. Each includes zero. The 2025 gains, especially +13.12% for SK hynix, do not repeat in 2024 or 2022.

VIX rose inside Gate 32 in only **two of six** years for each Korean asset; the Korean Gate 32 mean VIX was 22.49 versus 19.59 across all complete Gate windows. This is an **unmatched descriptive comparison**, potentially October/period driven, not evidence of Gate-specific risk. US10Y, USD/KRW and the Broad Dollar changes switch signs by year. Korean pre-window medians were −0.05% (Samsung) and +5.05% (SK hynix), Gate medians +0.42% and +0.76%, and post-window medians −1.16% and +1.59%; some motion was already under way before Gate entry. The SP500 pre/Gate/post medians were +1.08%/+0.19%/+0.36%.

The pooled same-start-Phase-minus-other-Gates median differences are only **+0.27 pp** for each Korean asset, versus +0.42/+0.76% raw Gate medians; this comparison pools four tiny Gate 32 Phase strata and is not a causal adjustment. Within Samsung's Gate 32, AUTUMN (n=2) and WINTER (n=2) have opposite median signs; one SUMMER and one UNKNOWN year cannot establish within-Phase repetition. SK hynix also has ≤2 Gate 32 observations per Phase. SP500 Phase is unavailable. **Gate 32 status: `NO EVIDENCE` for all three assets, 0 of 4 exploratory flags each.**

## Quarter and cross-asset counterchecks

| Quarter | Samsung median return / MDD / daily vol | SK hynix median return / MDD / daily vol | SP500 median return / MDD / daily vol |
|---|---|---|---|
| Initiation | +0.59% / −1.18% / 1.01% | +0.47% / −2.24% / 2.00% | −0.11% / −0.96% / 0.68% |
| Civilization | −0.13% / −1.47% / 1.25% | −0.26% / −2.15% / 1.66% | +0.40% / −0.52% / 0.53% |
| Duality | 0.00% / −1.46% / 1.13% | +1.01% / −1.92% / 1.82% | +0.32% / −0.58% / 0.52% |
| Mutation | +0.33% / −1.24% / 0.95% | +0.56% / −1.54% / 1.51% | +0.53% / −0.38% / 0.49% |

Each Quarter aggregates roughly 90–101 complete windows per asset, but windows share years, regimes and price trends. Different cross-asset directions, notably Civilization and Initiation, are counter-evidence to a universal Gate/Quarter reading. Quarter is a context label, not a market mechanism.

## Falsification, limits and next questions

The predeclared Gate 32 directional association **fails to survive** annual consistency, random-window extremity, bootstrap uncertainty and cross-asset comparison. H2 macro differences remain only descriptive because no matched macro null or regime-adjusted estimate was preregistered. H3 cannot be settled with one or two Gate 32 windows per Phase. H4's non-replication is visible across annual asset returns; none of the `WEAK` Gate labels spans all three assets. These are negative/insufficient findings worth preserving, not proof that every possible association is absent.

Key limits: approximately six annual repetitions per Gate, 192 simultaneous uncorrected comparisons, correlated assets, close-only dividend-excluded SP500, missing SP500 Phase/volume, KRW/USD units not converted, short three-to-five-bar Gate 32 windows, last-known macro repeats, changing economic regimes, and an availability-truncated 2020/2026 edge. `WEAK` is an internal descriptive label, not a p-value, forecast or tradable edge. A later preregistered study could use genuinely later out-of-sample years, a matched macro null, broader assets and family-wise/multiple-testing correction; it must leave this v1 result intact. No Gate-based trading strategy or recommendation follows from this step.

Review artifacts from this run: `data/processed/research/step9_three_asset_v1_review/` contains the full Window Parquet/CSV, 192-row Gate summary, Quarter table and manifest; `artifacts/step9-transit-market/` contains self-contained 64-Gate and Gate 32 charts. Those folders are local derived outputs and intentionally excluded from Git. Code, tests, this report and the preregistration are **uncommitted pending user review**.
