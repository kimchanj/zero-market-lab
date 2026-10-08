# Walk-Forward design — interface only

Proposed interface: `run_walk_forward(universe_snapshot, strategy_version, selection_rule, selection_window=12 months, forward_window=3 months, rebalance_frequency=3 months)`.

For each rolling window, freeze a point-in-time universe and data snapshot at the **selection cutoff**. Compute behavior profiles and strategy results only on the preceding 12 months. Apply a versioned deterministic selection rule to choose candidate symbols; record every candidate and rejection reason. Lock that selection, parameters, fee assumptions, and code hashes. Then run a distinct three-month forward evaluation. Do not re-rank assets using forward prices. Advance both windows three months and repeat.

Each window should persist selection and forward date boundaries, selected assets, strategy ID/version, selection-rule/config hash, training/forward return and MDD, coverage and missing-data flags, run/input hashes, and selection persistence across windows. A later query can ask whether historically suitable assets retained their fit out of sample. It must not claim that a single strong forward window validates a strategy.

Open design checks: point-in-time membership and delistings, adjusted versus unadjusted price treatment, calendar alignment, corporate actions, publication lag of ancillary data, and transaction cost sensitivity. The current curated 30-name list is **not** adequate as an unbiased historical universe. No Walk-Forward results are produced yet.
