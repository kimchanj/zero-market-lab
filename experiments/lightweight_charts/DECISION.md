# Chart Engine Spike Decision

## Decision

**Recommend: MIGRATE VISUALIZATION TO LIGHTWEIGHT CHARTS**, using a staged replacement of the
interactive financial chart surface. Keep the Python market-data, comparison, backtest, portfolio,
strategy, and event-log layers unchanged. Keep Plotly available for exported research figures while
the interactive workstation moves to Lightweight Charts.

This is an architecture recommendation, not a production migration in STEP 5. A supported Dash
integration boundary must be built and tested before replacing the current UI.

## 2026-10-06 interaction quality gate

The decision is now the result of the explicit Financial Chart Quality Gate rather than only an
architecture preference. The current Plotly/Dash viewport path sends every quick-range, wheel-zoom,
and pan range through `relayoutData → Python callback → full figure serialization → Plotly redraw`.
Browser testing showed that rapid quick-range requests could display the preceding range after about
1.2 seconds and required roughly 3 seconds between isolated clicks to settle reliably. The backtest
did not rerun, but the interactive chart still depended on Python round trips and visible redraws.

The Lightweight Charts prototype handled range buttons, series visibility, event visibility,
crosshair, wheel zoom, and drag pan entirely in the browser after the initial static payload load.
On this workstation it remained intact after 20 wheel events and 20 drag events with 2,514 market
points, three 2,514-point portfolio series, a contribution series, and 165 event records. Server logs
contained only the initial static GET requests during those interactions.

| Acceptance criterion | Plotly/Dash current UI | Lightweight Charts spike |
| --- | --- | --- |
| 2,500+ daily points and 4+ series | Pass | Pass |
| Repeated zoom/pan remains intact | Functionally pass, visible latency | Pass in 20+20 browser interaction run |
| Visible-range autoscale | Pass after Python callback | Native browser autoscale pass |
| Quick ranges | Exact after settling; rapid clicks can lag | Browser-local calendar ranges pass |
| Layer and marker toggle | Python figure callback | Browser-local pass |
| Crosshair | Detailed unified hover | Native crosshair, no server call |
| Viewport interaction without Python | **Fail** | **Pass** |

Final gate decision: **MIGRATE TO LIGHTWEIGHT CHARTS** for the production interactive financial
chart. Do not add new production chart layers to the Plotly viewport path. Migration itself remains a
separate reviewed change; this spike does not alter the existing production screen.

## Evidence

The prototype uses Lightweight Charts 5.2.1, the latest stable library release observed on
2026-10-05. It rendered 2,514 daily market points, 7,542 A/B/C portfolio points, a contribution
series, and 165 Strategy C events in two synchronized, resizable panes. Chrome measured initial
chart setup around 75 ms on this workstation; that browser-local observation is not a general
benchmark.

The full-period screenshot demonstrates dense ten-year navigation and all event types. The focused
2026 screenshot demonstrates TAKE_PROFIT/SELL → cash waiting → REENTRY beside the C portfolio path.
No OHLC or volume was fabricated.

Official sources:

- Release 5.2.1: https://github.com/tradingview/lightweight-charts/releases/tag/v5.2.1
- Getting started/build variants: https://tradingview.github.io/lightweight-charts/docs/5.0
- Panes: https://tradingview.github.io/lightweight-charts/tutorials/how_to/panes
- Series markers: https://tradingview.github.io/lightweight-charts/tutorials/how_to/series-markers
- Crosshair synchronization: https://tradingview.github.io/lightweight-charts/tutorials/how_to/set-crosshair-position

## Comparison

| Criterion | Plotly / Dash | Lightweight Charts 5.2.1 |
| --- | --- | --- |
| 10-year daily data | Proven adequate at 2,514 points | Prototype rendered smoothly; financial scale density is better |
| Wheel zoom / pan | Available and already linked through Dash callbacks | Native financial-chart interaction with fewer application callbacks |
| Crosshair | Spike lines/unified hover | Native crosshair; one chart synchronizes it across panes |
| Multi-pane | Separate graphs require range synchronization | Native panes share one time scale and support resize |
| Multiple charts | Dash callback or clientside sync required | Visible range and crosshair can be synchronized programmatically |
| Line series | Strong | Strong and visually dense |
| Future candlestick | Supported | First-class financial series; requires real OHLC |
| Histogram / volume | Supported | First-class series/pane; requires real proxy volume |
| Event markers | Possible but trace-heavy | Dedicated series-marker primitive |
| Custom annotations | Shapes/annotations are mature | Markers plus custom primitives/plugins |
| Custom primitives | Less finance-specific | Explicit primitive/plugin architecture |
| Responsive resize | Plotly responsive config plus resize signaling | `autoSize` and ResizeObserver behavior |
| Portfolio series | Proven | Proven in the second pane |
| Trade markers | Planned for STEP 6 | Capability proven with existing Strategy C Event Log |
| React required | No | No; standalone IIFE works directly in modern browsers |
| Dash integration | Native | Needs custom component, iframe/postMessage, or controlled client asset |
| Python data delivery | Native Python objects | JSON payload/API consumed in the browser |
| Testability | Python figure contracts are straightforward | Split tests: Python payload contracts plus browser/JS interaction tests |
| Maintenance | Single Python stack | Adds JavaScript API/version/license lifecycle |
| Long-term workstation fit | Good dashboard and analytical plotting | Better match for dense financial research interaction |

## Integration recommendation

Use the existing Python comparison service as the only calculation boundary. Deliver normalized
market/state/event JSON to a small browser chart adapter. For a production migration, prefer a
versioned custom Dash component or a narrowly defined client asset over scattering JavaScript in
callbacks. An iframe is acceptable for experiments but adds cross-frame state and testing friction.

Define a stable payload contract before migration:

- market: `{time, value}` daily close records;
- portfolio: A/B/C and contribution `{time, value}` records;
- events: existing `{time, type, price, quantity}` records;
- metadata: data semantics, strategy parameters, source, and limitations.

The chart adapter owns rendering, visible range, crosshair, marker filters, and pane sizing. Python
continues to own validation and every financial calculation.

## Future extensions and limits

- Real OHLC can feed candlestick/bar series without changing the backend boundary.
- SPY or a later ETF provider can supply a clearly labeled market-activity proxy in a histogram pane.
- Indicators can occupy additional panes or use plugins/custom series.
- Drawing tools and advanced annotations require separate primitive/plugin evaluation.
- Accessibility, browser compatibility, attribution, version upgrades, and browser E2E automation
  become explicit maintenance responsibilities.
- STEP 6 remains unstarted; the markers shown here only prove capability using existing events.
