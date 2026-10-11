# Entry filter + CASH research v1

Research question: does withholding **new** entries in an established adverse
trend reduce open losses and capital lock more effectively than repeated fixed
stop/re-entry? This is a falsifiable comparison, not a recommendation or an
automatic search for the best return.

## Fixed rules and controls

- S0, S1, S2, S4 and S7 remain available. S4 is an S2-derived SMA100 entry
  filter **with** TP, SL and time exit; it is not the S1-TF experiment.
- `S1_TREND_FILTERED_TAKE_PROFIT` keeps S1's entry limit, TP and no-stop exit.
  `S2_TREND_FILTERED_TP_SL` keeps S2's limit, TP and SL. Both change entry
  permission only. A held position is never sold merely because the filter
  turns false.
- Before day *t* opens: require `Close[t−1] > SMA200[t−1]` and
  `SMA200[t−1] > SMA200[t−6]`. SMA200 is a simple average of 200 **completed**
  trading closes. Filtered strategies require at least 205 previous trading
  observations before the evaluation begins; otherwise their cell is
  `INSUFFICIENT_DATA`. No parameter search is used.
- After permission, S1 uses its configured `Open × (1 + entry_offset)` limit;
  S2 uses Open −1%. No fill occurs unless the day's low reaches the limit.
  Today’s close and today’s moving average cannot affect today's permission.
- If the limit would have filled but permission failed, a `BLOCKED_ENTRY`
  research event records its hypothetical price. Its 20/60-session future
  returns are attached **after the simulation**, only when those observations
  actually exist. They never feed an order decision.
- `cash_days` counts completed evaluation sessions with no end-of-day holding;
  `cash_ratio = cash_days / evaluated sessions`. `entry_blocked_days` counts
  flat-day filter failures, while `blocked_entry_opportunity_count` counts
  failures on days whose price also reached the otherwise-valid entry limit.

The comparison matrix uses one locally cached OHLCV frame and fixed rows: S0,
S7, S1/S1-TF TP3/5, and S2/S2-TF TP3/5 with SL5/7/10. Base UI S2 can also
use user-entered TP/SL. Costs and initial capital are identical per compared
row. Closed-trade expectancy excludes terminal unrealized P/L. Portfolio value
always includes `cash + quantity × latest close`; no hypothetical future sale
cost is deducted.

## Actual local observations, 2026-10-10 cutoff

The cached price series ends 2026-10-08. Base 1Y S1 TP5 vs S1-TF TP5:

| Asset | S1 final | S1-TF final | S1 MDD | S1-TF MDD | Finding |
| --- | ---: | ---: | ---: | ---: | --- |
| Samsung Electronics | KRW 950,792 | KRW 950,792 | −35.41% | −35.41% | Filter did not block June entry; no difference in this window |
| SK hynix | KRW 1,136,109 | KRW 1,136,109 | −18.90% | −18.90% | No entry difference in this window |
| NAVER | KRW 428,492 | KRW 440,910 | −18.74% | −18.46% | One entry opportunity blocked; both still ended with an open loss |

At the fixed TP5/SL7 comparison for NAVER, S2 ended at KRW 331,415 with
MDD −38.12%; S2-TF ended at KRW 353,274 with MDD −31.12%, and blocked 100
otherwise valid entry opportunities. Its greater cash exposure may avoid
repeat losses but also forgo upside. This one window cannot establish a
general advantage.

Paired monthly-start windows use the **same 205-observation-qualified** starts
for S1 and S1-TF; 6M has 58 overlapping starts and 1Y has 52 for each Korean
seed. The table shows `S1 → S1-TF` at TP5; MDD is the average portfolio
drawdown across windows, not the worst drawdown.

| Asset | Window | Median net return | Average MDD | Average cash ratio | End with open position |
| --- | --- | ---: | ---: | ---: | ---: |
| Samsung Electronics | 6M | +3.72% → +0.53% | −16.90% → −10.41% | 7.23% → 48.30% | 94.83% → 62.07% |
| Samsung Electronics | 1Y | +7.87% → +7.74% | −23.73% → −17.05% | 5.72% → 40.93% | 94.23% → 78.85% |
| SK hynix | 6M | +15.52% → +5.26% | −17.33% → −12.31% | 8.76% → 38.84% | 90.38% → 71.15% |
| SK hynix | 1Y | +33.86% → +26.36% | −23.26% → −19.97% | 10.45% → 31.10% | 82.69% → 78.85% |
| NAVER | 6M | −7.00% → −2.32% | −20.07% → −13.54% | 3.14% → 42.94% | 100.00% → 68.97% |
| NAVER | 1Y | −6.80% → −6.29% | −26.83% → −22.48% | 1.97% → 34.98% | 100.00% → 84.62% |

Samsung's June entry is examined separately in
[the open-position case](s1-open-position-risk-case.md). The filter passed the
pre-entry conditions, so it did **not** prevent the expensive June position.
Paired rolling results still show lower average drawdown and fewer terminal
open positions, at the cost of much more cash waiting and sometimes less
capital growth. These heavily overlapping windows are not independent
probability trials. Three well-known Korean stocks are a selected sample;
missing/delisted stocks, dividends, corporate actions, and account-specific
costs limit inference.

## Future position-sizing boundary

The current engine uses full available cash for integer shares. A later
`PositionSizing` component could accept capital, entry, stop distance, lot,
fees and slippage, then return an affordable integer quantity. Candidate
policies are `FULL_CAPITAL`, `FIXED_RISK_0_5_PERCENT`, `FIXED_RISK_1_PERCENT`,
and `FIXED_RISK_2_PERCENT`. No fixed-risk sizing, Kelly sizing, ruin probability,
live order execution or automatic candidate recommendation is implemented here.
