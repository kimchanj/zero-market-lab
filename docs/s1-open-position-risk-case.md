# Case: June entry, open loss through October

Observation as of 2026-10-10, using the locally cached Samsung Electronics (`005930`)
daily OHLCV, 1Y evaluation, KRW 500,000 initial capital, S1 Open −1% entry,
TP +5%, and the run's research cost assumptions. The last available close is
2026-10-08; the strategy did not receive the 2026-10-10 future close.

| Item | S1 observation |
| --- | ---: |
| Open entry date / price / quantity | 2026-06-26 / KRW 350,000 / 3 shares |
| Latest close | KRW 263,000 |
| Target | KRW 367,500 |
| Holding duration | 70 observed trading days |
| Realized P/L from completed trades | +KRW 711,950 |
| Terminal unrealized P/L | −KRW 261,158 |
| Worst close-marked open P/L | −KRW 429,158 (−40.87% on open cost) |
| Total portfolio / total P/L | KRW 950,792 / +KRW 450,792 |
| Same-period S0 final portfolio | KRW 1,344,929 |

The completed trades alone hide the open loss. The worst open loss uses daily
**closes**, not intraday lows. Terminal portfolio marks the still-held shares to
the latest close without deducting future sale costs.

## Did the entry-only MA200 filter block this entry?

No. Before the 2026-06-26 session, the last known close was KRW 358,500,
above prior MA200 KRW 168,516. Prior MA200 was above its value five trading
sessions earlier (KRW 161,705.5). Both conditions passed, so S1-TF also bought
on 2026-06-26. Its 1Y final portfolio, MDD, and terminal open loss are the
same as S1's. This case **falsifies** any claim that this simple filter prevents
local peak entries. Its stated purpose is to reduce new entries during an
established downtrend, not to identify price peaks.

The filter's consequence should be judged across paired rolling starts, other
assets, adverse periods, and opportunity cost, with all outcomes reported.
