# STEP 7 — Paper Trading Visual Simulator

This local browser screen is a **HISTORICAL_REPLAY** viewer/controller for the
existing append-only Paper Trading engine. It offers the six local Seed Universe
assets when their processed OHLCV is available: Samsung Electronics (`005930`),
SK hynix (`000660`), NAVER (`035420`), NVIDIA (`NVDA`), Microsoft (`MSFT`),
and Apple (`AAPL`). KRX replay accounts use KRW (default ₩10,000,000) and US
replay accounts use USD (default $10,000). New historical replay accounts can
select S0 Buy & Hold, S1 Fixed Take Profit, S2 Fixed TP/SL, or S7 Breakout
Trend Following. Existing account configurations and Journals stay immutable.
It is research replay, not a LIVE_FORWARD result or a live order service.

## Run

First, prepare processed OHLCV snapshots for the desired Seed Universe assets
using the project's data workflow. Missing symbols are omitted from the
selector. These local snapshots are ignored by Git and are not shipped with
this repository. Then run:

```powershell
.\.venv\Scripts\python.exe scripts/run_paper_replay_ui.py --port 8076
```

Open <http://127.0.0.1:8076/>. Choose an available asset and Start Date, then
Create Simulation. The date range and default capital follow the selected
asset and its currency. A fixed **per-entry buy budget** caps each purchase;
the remainder stays as account cash. S1 exposes an entry limit as a percentage
of the next session's open and a take-profit target as a percentage of the
executed buy price. These values are frozen in the new account config/hash.
Existing accounts retain their original symbol,
currency, settings, and Journal when another symbol is selected. No
Journal is written until **Run Next Day** is pressed. Each press selects the
next *observed market session* from the local series and calls the existing
`run_day` engine once. Weekends and missing sessions are skipped rather than
invented. The price chart contains bars only through the last processed day;
pre-start history remains available to the engine solely for indicator warm-up.

The screen shows the engine's Decision, Order, Execution, position, P/L, S0
benchmark, and daily Journal. Phase is clearly marked **Context Only** and
does not alter the chosen strategy. A decision marker belongs to the decision date; a fill
marker belongs to its later execution date. A BUY decision is never displayed
as a same-day low fill. The equity chart plots the selected Paper strategy and S0 Journal
values; JavaScript does not compute trading rules or accounting.

S0 buys once at the first replay session's open, up to the selected buy budget,
then holds. Its comparison S0 baseline still uses the full initial cash at the
first open, so a budget-limited S0 account can differ from that baseline. S2
uses fixed Open −1% buy, +5% take-profit, and −3% stop-loss levels. Its bracket
order activates on the session **after** entry; an unknown same-day high/low
sequence is not turned into a round trip. On later days when both stop and
target are touched, the stop wins; a gap below stop fills at the open. S7
observes today's completed close against the *prior* 20-day high for entry
and prior 10-day low for exit, then executes at the next session's open.
These replay rules have distinct version identifiers and can differ from the
strategy-family backtest's same-day stop treatment. This is not a broker or
live order service.

The compact replay workspace places Account Summary, Today Market/Decision,
and the daily Journal above the charts. These and Position Detail start open.
Price, strategy-vs-S0 equity, Phase, Order/Execution, and Technical/Data sections
start closed. All nine are independent native `details` sections with keyboard
toggle support. Each header retains key state from the API while collapsed;
the open/closed preferences are saved in this browser's `localStorage`.
Running the next day opens Today and Journal, briefly highlights and focuses
the new Journal row, and leaves charts in their user-chosen state. Charts are
created when opened so hidden containers are not measured at zero width.

**Previous View** and clicking a Journal row retrieve a processed date for
inspection. They do not reverse or edit the account. Select **Latest View** to
resume advancing. The latest replay account is restored on page reload; the
selector can open older accounts. Creating another simulation adds an account
without deleting past Journals. At the last observed bar the controller returns
`REPLAY_COMPLETE` and disables further advances.

The selector also offers **선택 계좌 숨기기** with a confirmation prompt. Hiding
removes that historical replay from the active list and switches to another
visible replay, if one exists. **숨긴 Replay 복원** returns it to the list and
opens its saved state. This only writes a separate UI visibility table;
original accounts, events, and Journals remain immutable and can be restored.
LIVE_FORWARD accounts cannot be hidden or restored from this screen. The
Account Summary cards use a single compact row on wide displays and wrap on
narrower screens.

## Architecture and data boundary

`experiments/paper_replay/` is presentation only. The local stdlib HTTP server
in `scripts/run_paper_replay_ui.py` exposes narrow endpoints backed by
`ReplayController` in `src/zero_market_lab/paper_trading/replay_ui.py`. The
controller calls the existing `create_account`, `run_day`, `status`, and
`journal` functions. It does not change the Paper Engine, Strategy, Phase,
cost model, fill rule, or accounting. It rejects LIVE_FORWARD account IDs and
binds the server to `127.0.0.1`. There is no LIVE_FORWARD creation or run API.

The UI's SQLite file is `artifacts/paper_trading/replay_ui.sqlite3`, separate
from the Pilot DB. It and its WAL files, price data, and generated charts are
local ignored runtime artifacts. The UI does not call external services.
Displayed market OHLCV is the local processed snapshot with its provider and
adjustment provenance; the latest local file may not be a newly refreshed bar.
The price series is unadjusted, so corporate actions can affect interpretation.

## Verification

Unit tests project 25 synthetic observed sessions through the controller,
compare cash/quantity/equity/S0 with the engine Journal, verify past views do
not mutate the account, check restart persistence, replay completion, and
LIVE_FORWARD isolation. A separate local 25-session SK hynix smoke run used
observed sessions from 2026-08-24 to 2026-09-29; this is **historical**
evidence only. Browser review checks creation, next-day advance, Previous View,
charts, and Journal against the local API. The browser-created account's 2-day
equity and date matched the existing Paper CLI `status` on the same SQLite DB;
a server restart retained all accounts. No manual trading result should be
interpreted as future performance.

## Manual portfolio replay — review pending

The strategy Replay at `/` retains one frozen asset and strategy per account.
The separate `/manual/` workspace is a **historical manual portfolio**, with
its own ignored SQLite DB (`artifacts/paper_trading/manual_replay.sqlite3`).
Users can choose any of the six locally available seed assets and submit
manual BUY/SELL orders after opening a replay day. Orders fill at that asset's
**next observed trading session open**, never at the already inspected close.
The order, fill/rejection, and daily account snapshot are append-only; existing
strategy accounts and LIVE_FORWARD records are not changed.

KRW and USD are separate seeded cash wallets. The default is ₩10,000,000 and
$0; a user who wants to buy US assets must explicitly enter USD starting cash.
There is no FX conversion or combined cross-currency total. Buys use a cash
budget and whole shares; the budget includes the research buy fee. Sells use a
whole-share quantity. The fee assumption is 0.015% on each side, zero sell
tax, zero slippage (`paper-research-cost-v1`); it is **not** an official broker
fee or a historical tax schedule. Open positions are marked at the latest
observed close on or before each replay day. A snapshot hash is frozen for
every available asset and checked when reopening an account; append-only new
bars are allowed after a server restart, while revised historical prices
require the original snapshot to be restored before continuation.
Unadjusted prices, corporate actions, distributions, and stale cross-market
marks limit the interpretation of the portfolio result.

The manual balance screen groups total equity, cash, cost basis, market value,
and P/L by currency, followed by a per-stock holdings table and pending orders.
No KRW and USD amount is silently added together. The strategy Replay account
summary also shows a broker-style holdings row, using the Paper Engine's cost
basis and unrealized P/L rather than recalculating accounting in JavaScript.

The `/manual/` layout now starts with a compact Daily Investment Journal,
followed by Account Summary, Today Market / Decision, and Position Detail.
Order / Execution, Transit Context, and Technical sections start closed. Their
headers show current values while collapsed. Run Next Day scrolls the new
Journal row into view; each day is projected from its append-only DAY snapshot,
so historical KRW and USD equity values do not depend on today's holdings.
The selected asset's latest observed OHLCV is shown with its observation date;
on a cross-market holiday it may precede the portfolio replay date. Manual
orders remain user decisions, not algorithmic S1 decisions. The KRW order
budget input uses a whole-won browser step, while USD uses cents, matching the
server's currency validation.
