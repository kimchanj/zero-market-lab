# STEP 10 — Research Registry and independent-asset validation v1

**Result: Gate 32 `NO_EVIDENCE_CONFIRMED`; 20 frozen weak Gates `NOT_REPLICATED`; Gate 58 `INSUFFICIENT_SAMPLE`. No replication candidate or falsification met the [preregistered rules](transit-validation-v1-plan.md).** These labels describe this limited historical check, not proof of no effect or a trading signal. The discovery evidence and negative validation findings are both preserved in [the Registry](../../data/reference/research_registry.json).

## Research lifecycle and freeze

The STEP 9 checkpoint `1750c5695258f697a1c838a9c6b15b73270dea3f` and its 2020-08-24–2026-10-02 Samsung, SK hynix and S&P 500 study are frozen as `DISCOVERY`. Its 192-row Gate summary SHA-256 is `4bc47f15587540b710f044068e1354c32b5f54c3a770f5c9d5f047c240709659`. Before viewing validation outcomes, the Registry and plan froze Gate 32 plus **every** Gate with at least one STEP 9 `WEAK` asset row: 1, 4, 10, 20, 22, 23, 27, 31, 36, 44, 45, 46, 47, 48, 50, 51, 52, 56, 57, 58, 63. The initial Registry file SHA-256 is recorded in the plan. Each entry retains its hypothesis, source commit, discovery evidence and counterevidence, frozen direction, validation evidence, and append-only status history. The 2020–2026 STEP 9 assets never appear as `VALIDATION` assets.

The first validation uses the three already-stored US seed-universe assets **NVDA, MSFT and AAPL** across the **same dates**. It is independent by *asset identity*, **not time**: they share market regimes, macro observations and Gate timing. This is not a forward test. All three local secondary-provider quote snapshots have 2,512 available OHLCV rows from 2016-10-10 through 2026-10-07; the run cuts them to the fixed comparison span. Quote prices exclude dividends; provider split-adjustment semantics and corporate-action continuity limit interpretation. The exact selected-frame SHA-256 values, source metadata, macro raw hashes, code hash, seed and period are in the ignored runtime manifest. No live fetch or data mutation was performed for this validation.

## Same method, fixed decision rule

The validation reuses STEP 9 Gate intervals, US-close alignment, first-to-last close return, within-window MDD, unannualized daily volatility, 1,000 same-year ±45-day equal-bar random windows, Pre/Post returns, 2,000 bootstrap resamples and PRICE_PHASE_V1 context. As-of VIX, US 10Y, USD/KRW and Broad Dollar series remain context, not causal controls. The master seed is **1042**, distinct from discovery seed 42. The pipeline computed contextual windows but exported/interpreted only the 22 preregistered Gates: **405 asset-window rows and 66 asset–Gate rows**. It did not select new Gates by ranking validation outcomes.

For a weak Gate to become a `REPLICATION_CANDIDATE`, its discovery-weak effects first needed a consistent, nontrivial frozen direction. At least two held-out assets then had to pass the full magnitude, random-percentile, annual-direction, nonzero bootstrap-CI and same-Phase checks, with no ≥1 percentage-point opposite effect on the third. `FALSIFIED` required equally strong evidence in the opposite direction on at least two assets. Ordinary or mixed observations are `NOT_REPLICATED`; inadequate windows are `INSUFFICIENT_SAMPLE`. This conservative exploratory rule is **not** a multiple-testing-adjusted significance test.

## Held-out results

Each cell gives the median observed-minus-random return in **percentage points / random-return percentile**. The percentile is descriptive position among matched random windows, not a p-value. Direction was frozen from discovery weak rows; `AMBIGUOUS` means conflicting or <1 pp discovery effects. The table retains all 22 Gates, including counterexamples.

| Gate | Frozen direction | NVDA effect / percentile | MSFT effect / percentile | AAPL effect / percentile | Registry outcome |
|---:|---|---:|---:|---:|---|
| 1 | AMBIGUOUS | +3.51 / 78.9 | +1.04 / 68.6 | +0.28 / 50.4 | NOT_REPLICATED |
| 4 | POSITIVE | +3.88 / 75.8 | +1.27 / 62.2 | +1.25 / 69.2 | NOT_REPLICATED |
| 10 | AMBIGUOUS | +2.16 / 81.4 | +0.64 / 58.4 | +1.52 / 75.1 | NOT_REPLICATED |
| 20 | AMBIGUOUS | +5.17 / 91.1 | +1.04 / 62.7 | +0.15 / 50.9 | NOT_REPLICATED |
| 22 | POSITIVE | +2.01 / 55.6 | −1.33 / 33.9 | −2.52 / 16.9 | NOT_REPLICATED |
| 23 | AMBIGUOUS | +4.19 / 72.5 | −0.48 / 42.8 | −0.02 / 49.0 | NOT_REPLICATED |
| 27 | POSITIVE | +4.70 / 85.2 | +2.61 / 79.8 | +1.01 / 65.4 | NOT_REPLICATED |
| 31 | NEGATIVE | +0.48 / 55.9 | −0.45 / 43.2 | −0.39 / 39.7 | NOT_REPLICATED |
| 32 | NONE | +0.37 / 55.1 | −0.25 / 45.1 | +1.30 / 68.6 | NO_EVIDENCE_CONFIRMED |
| 36 | POSITIVE | +2.49 / 67.8 | +1.95 / 76.6 | +1.19 / 67.8 | NOT_REPLICATED |
| 44 | POSITIVE | +5.87 / 83.8 | −0.28 / 46.5 | −0.01 / 44.4 | NOT_REPLICATED |
| 45 | POSITIVE | −0.96 / 42.7 | +0.71 / 63.1 | −0.48 / 40.1 | NOT_REPLICATED |
| 46 | NEGATIVE | +1.23 / 58.2 | +0.26 / 51.4 | −0.61 / 37.8 | NOT_REPLICATED |
| 47 | POSITIVE | +0.47 / 52.7 | +0.29 / 58.3 | −0.88 / 35.3 | NOT_REPLICATED |
| 48 | POSITIVE | +4.64 / 83.8 | +1.77 / 79.5 | +0.82 / 59.8 | NOT_REPLICATED |
| 50 | AMBIGUOUS | +1.97 / 66.1 | +1.00 / 67.9 | −0.41 / 41.9 | NOT_REPLICATED |
| 51 | AMBIGUOUS | +2.32 / 67.3 | +1.25 / 78.2 | −0.10 / 51.9 | NOT_REPLICATED |
| 52 | NEGATIVE | +1.52 / 65.6 | +0.91 / 67.7 | +2.03 / 89.0 | NOT_REPLICATED |
| 56 | AMBIGUOUS | +1.29 / 55.8 | −0.53 / 36.7 | +0.93 / 63.5 | NOT_REPLICATED |
| 57 | POSITIVE | +0.74 / 54.2 | +0.42 / 56.5 | −0.21 / 57.0 | NOT_REPLICATED |
| 58 | POSITIVE | −0.92 / 37.0 | +0.12 / 52.1 | −0.23 / 44.0 | INSUFFICIENT_SAMPLE |
| 63 | NEGATIVE | −3.41 / 32.2 | −0.88 / 39.3 | −2.77 / 18.6 | NOT_REPLICATED |

Among these fixed Gates, AAPL has 6 `WEAK`, 15 `NO EVIDENCE` and 1 `INSUFFICIENT SAMPLE` asset labels; MSFT has 5/16/1; NVDA has 9/12/1. These exploratory asset labels do **not** satisfy the preregistered replication rule. Gate 36, for example, is `WEAK` on all three held-out assets, but its median random percentiles are only 67.8, 76.6 and 67.8, well short of the >90 threshold. Gate 20's NVDA percentile 91.1 is one asset, with an **ambiguous discovery direction**. Gate 57's previously conspicuous SK hynix observation does not carry across: held-out effects +0.74, +0.42 and −0.21 pp. Gate 58 has only four complete annual windows per held-out asset; it is not interpreted as a negative replication result.

### Gate 32 negative control

All three held-out assets have six complete Gate 32 windows (2020–2025) and the unchanged STEP 9 summary rule labels each `NO EVIDENCE`. NVDA/MSFT/AAPL median Gate returns are +0.86%/−0.12%/+1.71%; corresponding within-window median MDDs are −1.59%/−0.55%/−0.82%, and mean unannualized daily volatilities are 1.44%/0.57%/0.68%. Median random-return percentiles **55.1/45.1/68.6** are ordinary. The 95% bootstrap intervals for **mean** Gate return are **[−4.18, +3.27]%, [−0.63, +2.19]%, [−0.63, +2.55]%**, all crossing zero. The frozen rule therefore records `NO_EVIDENCE_CONFIRMED`, meaning a repeated absence of sufficient evidence under this design, **not proof of a zero effect**.

## Reproducibility and provenance

Run from the repository root with its existing virtual environment after the pinned local datasets are available:

```powershell
.\.venv\Scripts\python.exe scripts/run_transit_validation.py --output data/processed/research/<new-run>
.\.venv\Scripts\python.exe scripts/run_transit_validation.py --output data/processed/research/<second-new-run>
.\.venv\Scripts\python.exe scripts/finalize_transit_validation.py data/processed/research/<new-run> data/processed/research/<second-new-run>
```

The finalizer updates the Registry only if all four output files match byte for byte, the frozen discovery summary still matches, the plan and analysis-code hashes match the manifest, and the role, asset set, period, seed, Gate set and discovery fingerprint match the freeze. Finalization is intentionally one-time for the current Registry; a later independent study needs its own plan and version. The two actual runs had identical SHA-256 values:

| File | SHA-256 |
|---|---|
| `manifest.json` | `af7fd6b3b90a7405e4fcf3dccebaf23c92b861e30407b9a2b0d8359e5336b10e` |
| `validation_windows.parquet` | `2c84479d8ff4c1240c80d8d69c3dca577f03b2500bc447e19864308b07dcc8e3` |
| `validation_windows.csv` | `126866a9ba6f91f7b4f3defdb4509807faa8745796fac6165c8e5a65dd4f1883` |
| `validation_summary.csv` | `39a084f2b8cf86d01153d3002a907e597d9f0a89f27dda62a9027e52ea63dee4` |

The original STEP 9 Discovery window Parquet/CSV, Gate CSV and Quarter CSV were recomputed with the shared pipeline and each stayed byte-identical to its pinned original, protecting the previous result from this refactor. The new validation runtime directory and its reproduction directory are Git ignored; the reviewable files are the Registry, plan, report, scripts, code, tests and JOURNAL.

Review checks: **331 Python tests**, **9 existing JS tests**, and **21 browser regression checkpoints** passed; the browser reported zero console errors, network failures and unhandled promises. `pip check` and `git diff --check` passed. The initial restricted run could not create test fixtures or launch Chrome; full reruns in the permitted execution context passed. No new Registry panel or Gate-hover badge was added to the UI in this research-only step; the existing workspace regression stayed green.

## Interpretation and next evidence

This check has ~4–7 annual windows per selected Gate and only one shared historical period. US mega-cap returns are correlated; the common Gate schedule and macro context create dependence between assets. The discovery scan involved 192 exploratory comparisons, without family-wise correction. Phase strata and Gate-level macro averages are sparse/descriptive. Random windows are a retrospective null and can include later dates; they are not forward signals. Investor flow, Fear & Greed, Gold and ICE DXY remain unavailable, while Broad Dollar is **not** ICE DXY. Human Design is not established as a cause of market movement.

The next validation axis must be **new observations after the pinned cutoff**, preregistered without changing this result. Even a later asset-level replication would need independent-time forward evidence and user review before any strategy candidacy. STEP 10 makes no Gate-based trading decision, Paper Trading rule or STEP 11 implementation. The Registry is the project memory of what was tested, what contradicted it, and what remains unresolved.
