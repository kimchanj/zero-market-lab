(() => {
  const started = performance.now();
  const data = window.PROTOTYPE_DATA;
  const {
    ColorType,
    CrosshairMode,
    LineSeries,
    LineStyle,
    createChart,
    createSeriesMarkers,
  } = window.LightweightCharts;

  const container = document.getElementById('chart');
  const chart = createChart(container, {
    autoSize: true,
    layout: {
      background: { type: ColorType.Solid, color: '#ffffff' },
      textColor: '#34465b',
      fontFamily: 'Inter, Segoe UI, Arial, sans-serif',
      fontSize: 11,
      panes: {
        enableResize: true,
        separatorColor: '#d7e0ea',
        separatorHoverColor: '#8aa4bf',
      },
    },
    grid: {
      vertLines: { color: '#eef2f6' },
      horzLines: { color: '#eef2f6' },
    },
    crosshair: {
      mode: CrosshairMode.Normal,
      vertLine: { color: '#64748b', width: 1, style: LineStyle.Dashed, labelVisible: true },
      horzLine: { color: '#94a3b8', width: 1, style: LineStyle.Dotted, labelVisible: true },
    },
    rightPriceScale: { borderColor: '#cbd5e1', scaleMargins: { top: 0.08, bottom: 0.08 } },
    timeScale: {
      borderColor: '#cbd5e1',
      timeVisible: true,
      secondsVisible: false,
      rightOffset: 2,
      barSpacing: 6,
      minBarSpacing: 0.5,
    },
    handleScroll: { mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true },
    handleScale: { axisPressedMouseMove: true, mouseWheel: true, pinch: true },
  });

  const market = chart.addSeries(LineSeries, {
    title: 'S&P500 Price', color: '#1f2937', lineWidth: 2,
    priceLineVisible: false, lastValueVisible: true,
  }, 0);
  const portfolioA = chart.addSeries(LineSeries, {
    title: 'A Buy & Hold', color: '#315efb', lineWidth: 3,
    priceLineVisible: false, lastValueVisible: true,
  }, 1);
  const portfolioB = chart.addSeries(LineSeries, {
    title: 'B Immediate', color: '#ef553b', lineWidth: 2,
    lineStyle: LineStyle.Dashed, priceLineVisible: false, lastValueVisible: true,
  }, 1);
  const portfolioC = chart.addSeries(LineSeries, {
    title: 'C 1M Delay', color: '#00a67e', lineWidth: 2,
    lineStyle: LineStyle.Dotted, priceLineVisible: false, lastValueVisible: true,
  }, 1);
  const contribution = chart.addSeries(LineSeries, {
    title: 'Contribution', color: '#94a3b8', lineWidth: 1,
    lineStyle: LineStyle.Dashed, priceLineVisible: false, lastValueVisible: false,
  }, 1);

  market.setData(data.market);
  portfolioA.setData(data.portfolios.A);
  portfolioB.setData(data.portfolios.B);
  portfolioC.setData(data.portfolios.C);
  contribution.setData(data.contribution);

  const seriesByCode = { market, A: portfolioA, B: portfolioB, C: portfolioC, contribution };
  document.querySelectorAll('.series input').forEach(input => {
    input.addEventListener('change', () => {
      seriesByCode[input.value].applyOptions({ visible: input.checked });
    });
  });

  const markerStyles = {
    BUY: { position: 'belowBar', color: '#315efb', shape: 'circle', text: 'B' },
    TAKE_PROFIT: { position: 'aboveBar', color: '#f59e0b', shape: 'square', text: 'TP' },
    SELL: { position: 'aboveBar', color: '#ef4444', shape: 'arrowDown', text: 'S' },
    REENTRY: { position: 'belowBar', color: '#00a67e', shape: 'arrowUp', text: 'R' },
  };
  const markerApi = createSeriesMarkers(market, []);
  const query = new URLSearchParams(window.location.search);
  if (query.get('events') === 'core') {
    const buyToggle = document.querySelector('.events input[value="BUY"]');
    if (buyToggle) buyToggle.checked = false;
  }
  function updateMarkers() {
    const active = new Set(
      [...document.querySelectorAll('.events input:checked')].map(item => item.value)
    );
    const markers = data.strategyCEvents
      .filter(event => active.has(event.type))
      .map((event, index) => ({
        time: event.time,
        ...markerStyles[event.type],
        id: `${event.type}-${event.time}-${index}`,
      }));
    markerApi.setMarkers(markers);
  }
  document.querySelectorAll('.events input').forEach(input => {
    input.addEventListener('change', updateMarkers);
  });
  updateMarkers();

  const panes = chart.panes();
  if (panes.length >= 2) {
    panes[0].setStretchFactor(3);
    panes[1].setStretchFactor(2);
  }

  const legend = document.getElementById('legend');
  const format = value => value === undefined ? '—' : value.toLocaleString(undefined, { maximumFractionDigits: 0 });
  chart.subscribeCrosshairMove(param => {
    if (!param.time) {
      legend.textContent = 'Move the crosshair to inspect Market → Strategy results.';
      return;
    }
    const value = series => {
      const point = param.seriesData.get(series);
      return point ? point.value : undefined;
    };
    legend.textContent = `${param.time}  ·  Market ${format(value(market))}`
      + `  |  A ${format(value(portfolioA))}`
      + `  ·  B ${format(value(portfolioB))}`
      + `  ·  C ${format(value(portfolioC))}`
      + `  ·  Contribution ${format(value(contribution))}`;
  });

  const finalDate = new Date(`${data.period[1]}T00:00:00Z`);
  const rangeStart = range => {
    const from = new Date(finalDate);
    if (range === '1W') from.setUTCDate(from.getUTCDate() - 7);
    if (range === '1M') from.setUTCMonth(from.getUTCMonth() - 1);
    if (range === '3M') from.setUTCMonth(from.getUTCMonth() - 3);
    if (range === '6M') from.setUTCMonth(from.getUTCMonth() - 6);
    if (range === '1Y') from.setUTCFullYear(from.getUTCFullYear() - 1);
    if (range === '3Y') from.setUTCFullYear(from.getUTCFullYear() - 3);
    return from.toISOString().slice(0, 10);
  };
  document.querySelectorAll('[data-range]').forEach(button => {
    button.addEventListener('click', () => {
      const range = button.dataset.range;
      if (range === 'ALL') {
        chart.timeScale().fitContent();
        return;
      }
      chart.timeScale().setVisibleRange({
        from: rangeStart(range),
        to: data.period[1],
      });
    });
  });

  const focusFrom = query.get('from');
  const focusTo = query.get('to');
  if (focusFrom && focusTo) {
    chart.timeScale().setVisibleRange({ from: focusFrom, to: focusTo });
  } else {
    chart.timeScale().fitContent();
  }
  const elapsed = performance.now() - started;
  document.getElementById('performance').textContent =
    `${data.market.length.toLocaleString()} rows · ${data.strategyCEvents.length} C events · setup ${elapsed.toFixed(1)} ms`;
})();
