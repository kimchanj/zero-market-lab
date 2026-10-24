# STEP 11 handoff — Foundation verified; STEP 11.1 remains

Read `ZERO_MARKET_LAB_META.md`, `transit-forward-validation-v1-plan.md` and `forward-validation-architecture.md` first. Preserve the uncommitted working tree. The approved STEP 10 checkpoint is `a83d52cc02b26312dfb0ef6adddd75a9e775e1e3`. Do not amend its discovery/validation evidence. No commit or push before user review.

Implemented: canonical 2026-10-02 historical cutoff; protocol freeze `2026-10-23T15:32:48Z`; six-asset, 22-Gate pre-registration; separate empty `forward_validation` state for each Registry entry; strict observation-date/collection-time/provenance eligibility helper; one-time Registry initializer; status-only `--dry-run` CLI; ten focused STEP 10/11 tests passed. Current forward windows = **0**. An explicit no-evidence safety amendment also freezes each asset's pre-existing maximum observation date. Re-fetching a 2026-10-03–07 US bar after protocol freeze does not make it Forward evidence; Korean stock bars through 2026-10-08 are likewise excluded.

Next implementation sequence:

1. Add ignored runtime append-only observation and event store. Validate source timestamp, provider/series/hash, OHLCV and calendar. Re-importing an identical observation must be a no-op; revised source data must append a `SOURCE_MUTATION` event and stop normal evidence creation. Add correction events without deleting the original record.
2. Reuse the existing Gate interval, market-close, metric, PRICE_PHASE_V1 and as-of macro code to identify OPEN/CLOSED windows. Require every Window bar to satisfy both cutoff and freeze eligibility. Add Post-window, mature same-season random control and late macro checks before FINALIZED; test OPEN, PENDING_CONTEXT/PENDING_CONTROL, CLOSED and FINALIZED transitions with synthetic data.
3. Append immutable forward Window evidence with `(research_id, asset, gate, window_start_utc)` key, input/result hashes and calculated_at. Re-running unchanged inputs must not duplicate evidence. Keep bulky series/events in ignored runtime files and only small summaries in Registry.
4. Extend CLI beyond status-only dry-run only after those tests pass. Add a runtime manifest and full Python/JS/browser regression. STEP 9/10 result hashes must remain unchanged. No real forward result should be claimed until *newly collected* eligible observations and a complete window exist.
5. Optionally add a compact Research Evidence Accordion/tooltip to the existing workspace after data contracts stabilize. No new Dashboard or fake progress indicator.

Verification already run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/unit/test_forward_validation.py tests/unit/test_transit_registry.py
.\.venv\Scripts\python.exe scripts/run_forward_validation.py --dry-run
git diff --check
git status --short
```

Full regression: **334 Python tests**, **9 JS tests**, **21 browser checkpoints** passed. Browser Console/Network/Unhandled counts were **0/0/0**; `pip check` and whitespace check passed. STEP 9 Discovery summary and STEP 10 Validation manifest/summary hashes still match their pinned values.

The current `run_forward_validation.py` intentionally refuses to run without `--dry-run`. This is a safety boundary, not a completed forward engine. **STEP 11 Forward Validation Foundation is complete** under the scoped Foundation definition: preregistration, two time boundaries, 22 empty Registry states, zero-window semantics, dry-run safety, tests and documentation. Actual observation ingestion, append-only evidence and window lifecycle are **NOT IMPLEMENTED** and belong to proposed STEP 11.1 after user review. STEP 11.1 and STEP 12 remain unstarted.
