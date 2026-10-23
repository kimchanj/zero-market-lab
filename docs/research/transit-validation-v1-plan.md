# STEP 10 preregistration — independent-asset Transit validation v1

Frozen on 2026-10-24 **before inspecting NVDA, MSFT or AAPL Gate outcomes**. The STEP 9 research commit `1750c5695258f697a1c838a9c6b15b73270dea3f` and its pinned local results are the immutable `DISCOVERY` dataset. This is an asset-held-out historical check, **not** independent-time or forward validation: the market dates, macro regime and Transit clock overlap. No result may become a trading rule or a Human Design causality claim.

## Discovery freeze and selected hypotheses

- Discovery period: `2020-08-24` through `2026-10-02`, assets `005930`, `000660`, `SP500`, run manifest `data/processed/research/step9_three_asset_v1_review/manifest.json`, summary SHA-256 `4bc47f15587540b710f044068e1354c32b5f54c3a770f5c9d5f047c240709659`.
- Primary negative-control question: Gate 32, previously `NO EVIDENCE` on all three assets. The question is whether three held-out assets also fail to show a repeatable Gate-specific difference. Gate 32 has **no preregistered positive or negative price direction** and cannot be promoted from this check.
- Freeze **every** distinct Gate with at least one `WEAK` STEP 9 asset–Gate row, not a handpicked high-return subset: `1, 4, 10, 20, 22, 23, 27, 31, 36, 44, 45, 46, 47, 48, 50, 51, 52, 56, 57, 58, 63` (21 Gates; 27 weak asset–Gate rows). Gate 20 already has conflicting discovery-asset effect directions; tiny effects such as Gate 56 are retained and cannot be quietly dropped. The registry preserves each discovery-asset effect and status. No other Gate may enter this v1 validation after its outcome is viewed.
- The pre-validation Registry freeze is `data/reference/research_registry.json`, SHA-256 `62cbfff3c24413f0ee795cfe144b8754a696822da44eaf45ed0cb88c54037668`. Later status updates must preserve the frozen candidate list and discovery evidence while appending history; they will change the file hash and are versioned as a separate validation event.

## Held-out assets, role and fixed period

- Validation assets are the three pre-existing US seed-universe large caps **NVDA, MSFT, AAPL**, chosen by pre-existing membership, complete locally stored daily OHLCV across the common comparison span, positive/ordered prices, no duplicate dates and recorded source/adjustment metadata. This selection did not use their Gate returns. The available selected local snapshots have 2,512 rows each from `2016-10-10` through `2026-10-07`; validation deliberately uses only `2020-08-24` through `2026-10-02` for comparison to STEP 9. Provider quote OHLCV excludes dividends; split-continuity metadata exists but provider adjustment semantics remain a limitation. No new download is part of this run.
- `dataset_role=VALIDATION` is mandatory in the validation manifest. Asset sets must be disjoint from `DISCOVERY`; `(symbol, observation_date)` keys cannot occur in both roles. Their calendar dates and macro observations can overlap, so three assets are not three independent economic regimes. No claim of independent-time evidence is allowed. Observations after the discovery cutoff are reserved for a separately preregistered forward study; this v1 run does not use them.
- Frozen input hashes, source versions and selected date bounds are recorded in the validation manifest. Raw/processed data and results remain Git ignored; only code, tests, registry and a concise report are reviewable Git candidates.

## Method and controls held constant

- Reuse STEP 9 `gate_intervals`, `asset_windows`, `price_metrics`, `random_control`, `bootstrap_interval`, `summarize` and `quarter_summary` rather than reimplementing metrics. Use the existing US 16:00 America/New_York close-to-Gate mapping. Retain Gate.Line observations but analyze at Gate level. Do not change Solar, Quarter, Strategy, Paper or Phase rules.
- Primary metrics remain first-to-last observed-close return, within-window MDD, unannualized daily volatility, 1,000 same-year ±45-day same-length nonoverlapping random controls, equal-bar Pre/Post returns, 2,000 annual-window bootstrap resamples, PRICE_PHASE_V1 context, Quarter and as-of VIX/US10Y/USDKRW/Broad Dollar. Validation random/master bootstrap seed is **1042** to separate this run from the frozen STEP 9 seed 42; deterministic per-window offsets and all control definitions remain identical.
- Apply the existing STEP 9 `NO EVIDENCE / WEAK / MODERATE / INSUFFICIENT SAMPLE` asset–Gate status rule unchanged. Only the 22 frozen Gates are interpreted and exported as validation results. Computing other Gate windows as context/Phase controls is permitted, but re-ranking all 64 Gates or adding a new candidate from validation is prohibited.

## Predefined outcome rules

- Gate 32 is `NO_EVIDENCE_CONFIRMED` only if each of the three held-out assets has ≥5 complete annual windows, existing STEP 9 status `NO EVIDENCE`, a mean-return bootstrap interval including zero, and a median random-return percentile in `[10, 90]`. Otherwise mark `UNRESOLVED` or `INSUFFICIENT_SAMPLE`; never call it `REPLICATED` or “proof of no effect.”
- A weak Gate receives a frozen discovery direction only if all its `WEAK` discovery-asset median observed-minus-random effects have the same nonzero sign **and** absolute effect ≥1 percentage point each. If not, label the discovery direction `AMBIGUOUS`; still report validation results but do not promote it. No direction may be chosen from held-out returns.
- For a direction-eligible Gate, one validation asset `SUPPORTS` only when it has ≥6 complete windows, the observed-minus-random median effect has the frozen sign and absolute size ≥1 percentage point, the median return random percentile is >90 for positive or <10 for negative, ≥70% annual raw returns have that sign, its mean-return 95% bootstrap interval excludes zero in that sign, and its same-start-Phase comparison is available with that sign. These are exploratory descriptive thresholds, not family-wise corrected significance.
- `REPLICATION_CANDIDATE` requires ≥2 of 3 validation assets to `SUPPORT`, the third not to show a ≥1 pp effect in the opposite direction, and a direction-eligible discovery hypothesis. Even that outcome remains short of strategy readiness until independent-time forward evidence. Do not assign `STRONG` in STEP 10.
- `FALSIFIED` is reserved for a direction-eligible Gate when ≥2 held-out assets have ≥6 complete windows and meet all magnitude, extreme random-percentile, ≥70% annual-sign, nonzero-CI and Phase conditions **in the opposite direction**. Ordinary or mixed results are `NOT_REPLICATED`, not falsification. Inadequate windows or unavailable controls produce `INSUFFICIENT_SAMPLE`. Gate 32 has no directional hypothesis, so its ordinary result is `NO_EVIDENCE_CONFIRMED`, never `FALSIFIED`.
- The Registry retains discovery evidence separately from validation evidence and appends a status-history event for each transition. Historical cross-asset validation alone cannot promote a hypothesis to a Strategy Candidate; independent future observations and user review are required.

## Ordered execution and stopping

1. Save this plan and freeze the Registry candidate IDs and discovery snapshots before examining validation Gate outcomes.
2. Reuse the STEP 9 pipeline on the three fixed assets and dates, export only frozen-Gate result tables, and assert disjoint asset identities and frozen input hashes.
3. Re-run with identical inputs and seed; require byte-identical result files and manifest.
4. Apply the above rules once; retain non-replication, insufficient samples and counter-evidence in the Registry and report.
5. Run synthetic Registry/role/transition/reproducibility tests and existing Python, JS and browser regressions. Do not commit or push until the user reviews the STEP 10 result.
