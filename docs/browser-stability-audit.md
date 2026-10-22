# STEP 8.4 — Browser stability audit

Status: local Chrome regression passed; user screen review pending. No commit,
push, new indicator, strategy, data source, or STEP 9 work is included.

## Baseline and evidence

- Baseline: `main` at `b88503c2d55bc2c5bf5dac6ec2dfc610da69263c`,
  2 commits ahead of `origin/main`. Existing unstaged and untracked research
  work was preserved.
- The user-supplied 15.6-second Chrome recording from 2026-10-22 22:52 shows
  a chart that continues to draw while the status line reports
  `Cannot set properties of null (setting 'textContent')`. The recording's
  header and date panel are from an older open page than the current HTML.
- Initial headless Chrome inspection of the current page found one console
  resource error per load: `GET /favicon.ico` returned 404. Project API
  failures and unhandled promises were zero.

## Reproduced defects and fixes

| ID | Steps and actual result | Cause | Fix | Regression |
| --- | --- | --- | --- | --- |
| BUG-001 | Keep an older Research tab open without `#cmp-data-status`; run comparison. The chart renders, then the status line shows a null `textContent` error. | The newly added technical data-status element is optional in an older DOM, but `run()` wrote to it unconditionally. | Update that optional element only when it exists. The calculation and API response still complete; no broad exception suppression was added. | The browser test removes `#cmp-data-status`, runs comparison again and requires a working chart and successful status. |
| BUG-002 | At 600px browser width, open `+ 비교 추가`; the popover extends past the viewport. | The popover remained left-anchored until the 550px breakpoint. | Right-anchor the popover below 850px. | Browser test checks the actual popover bounds at 600px. |
| BUG-003 | Load or reload the Research page; Chrome logs a resource 404. | Chrome requests `/favicon.ico` even with an inline icon, while the local server rejects it. | Return a no-content 204 for that browser resource. | CDP Network and Console listeners require zero 4xx, errors and unhandled promises. |

## Runtime lifecycle audit

- Crosshair and click subscriptions occur once in `initChart()`. `run()`
  replaces data series on the existing chart and does not register handlers.
- `resetChart()` removes each live series then clears its array. Subsequent
  updates create new series; no removed reference is updated. Chart canvas
  count remained 7 throughout the repeated test.
- Request generation tokens prevent late series responses from replacing the
  latest asset/range. Band render IDs plus the same generation prevent late
  calendar responses from replacing newer markers. Rapid asset switching
  ended on the last selected asset.
- Context dates use `YYYY-MM-DD` keys. Absent comparison observations remain
  absent; previous published macro observations retain their observation
  date. Fast hover did not show `undefined`, `null`, or `NaN`.
- Tooltip pointer events are disabled while hovering and enabled only when
  pinned. The Escape and ResizeObserver listeners are installed once. The
  chart instance is reused rather than repeatedly created or disposed.
- Removing Transit clears the band; re-adding it recreates one set of tiles.
  Period and zoom changes recalculate markers without accumulation.

## Actual Chrome interaction run

`node tests/browser/comparison_stability.cjs` drives a local Chrome through
the DevTools protocol and captures Console, Runtime and Network events. It
covered initial load; hover A/B/C and 30 rapid moves; 10 leave/reenter and
10 popover open/close cycles; lock/Escape; five add/remove cycles each for
VIX, US10Y, USD/KRW and Broad Dollar; S&P500 with Actual/Normalize toggles;
Transit remove/re-add; wheel zoom and drag pan; 1M/3M/6M/1Y/3Y/ALL three
times each; SIM without and with an investment period; Samsung/SK hynix/NAVER
switches and a rapid request race; three date ranges; reload; 600px viewport;
last-known macro date; a Korean trading day (2026-07-03) without an S&P 500
observation; and an older DOM missing the optional technical node.

Final result: **0 console/runtime errors, 0 HTTP/network failures, 0 unhandled
promises**. Nineteen standard checkpoints retained chart canvases and valid
state. A further eight-minute sustained run completed 26 cycles of 1M/ALL,
hover, US10Y add/remove and popover interaction. Combined with the standard
run, the Chrome session lasted about ten minutes. Its final chart still had
7 canvases, 25 turning markers and 398 Gate tiles for the full range; the
error counters remained 0/0/0. The
server at `http://127.0.0.1:8085/asset_discovery/` was restarted to load the
favicon response. Browser extensions were not part of the isolated Chrome
test. This verifies the scripted interactions, not every possible manual
gesture or the user's already-open tab until refreshed.

The full Python suite passed (314 tests), as did the nine existing JS tests,
`pip check`, JavaScript syntax, and `git diff --check`. The STEP 8 checkpoint was
subsequently approved and pushed; STEP 9 has not started.

## Period and accordion follow-up

The Research Workspace now uses one period state for shortcut selection, date
inputs, and comparison requests. The chart and its Transit band render from the
same response period. Manual dates clear the active shortcut; SIM without a
saved investment period leaves the current period intact and reports why.

The whole market comparison area uses a compact accordion, open by default.
On reopening or window resize, the chart is measured again against the visible
viewport with a 390–610 px chart range and room for its date axis and Transit
band. At 1920×1080, the scripted Chrome check found the band inside the viewport.
Ten close/open cycles retained the same chart canvas count and working hover.

The expanded browser regression checks every shortcut followed by comparison
execution, a sequential shortcut override, SIM, manual dates, layer/asset changes
around accordion toggles, and the original market-context and old-DOM cases.
Final isolated Chrome result: 0 console/runtime errors, 0 network failures,
0 unhandled promises. Python 314 and JS 9 tests passed.
