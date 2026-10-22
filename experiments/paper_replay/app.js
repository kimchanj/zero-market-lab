(() => {
  'use strict';

  const $ = id => document.getElementById(id);
  let displayCurrency = 'KRW';
  const won = (value, unit = displayCurrency) => value == null ? '—' : unit === 'USD'
    ? `$${Number(value).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`
    : `₩${Number(value).toLocaleString('ko-KR', {maximumFractionDigits: 0})}`;
  const number = value => value == null ? '—' : Number(value).toLocaleString('ko-KR');
  const percent = value => value == null ? '—' : `${Number(value) > 0 ? '+' : ''}${Number(value).toFixed(2)}%`;
  const signedWon = value => value == null ? '—' :
    `${Number(value) < 0 ? '-' : Number(value) > 0 ? '+' : ''}${won(Math.abs(Number(value)))}`;
  const strategyCode = id => id?.split('_')[0] || 'S1';
  const strategyName = id => ({S0: 'Buy & Hold', S1: 'Fixed Take Profit',
    S2: 'Fixed TP / SL', S7: 'Breakout Trend Following'})[strategyCode(id)] || id;
  let accountId = null;
  let state = null;
  let highlightDate = null;
  let priceChart, candleSeries, markerApi, equityChart, strategySeries, s0Series;
  let researchMarket = null;
  const sectionIds = ['journal', 'summary', 'today', 'position', 'price', 'equity', 'phase', 'orders', 'transit', 'technical'];
  const section = id => $(`section-${id}`);
  // Keep the Journal first in DOM and visual reading order without duplicating it.
  section('summary').before(section('journal'));
  const transitCalendars = new Map();
  let selectedTransit = null;
  const storedSections = (() => {
    try { return JSON.parse(localStorage.getItem('paper-replay-sections-v1')); }
    catch { return null; }
  })();
  if (storedSections && typeof storedSections === 'object') {
    for (const id of sectionIds) if (typeof storedSections[id] === 'boolean') section(id).open = storedSections[id];
  }
  function saveSections() {
    try { localStorage.setItem('paper-replay-sections-v1', JSON.stringify(
      Object.fromEntries(sectionIds.map(id => [id, section(id).open])))); } catch { /* Optional preference. */ }
  }
  for (const id of sectionIds) section(id).addEventListener('toggle', () => {
    saveSections();
    if ((id === 'price' || id === 'equity') && section(id).open && state) {
      requestAnimationFrame(() => renderCharts(state));
    }
  });

  async function request(path, options = {}) {
    const response = await fetch(path, {cache: 'no-store', ...options});
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `요청 실패 (${response.status})`);
    return payload;
  }

  function error(message) {
    $('error').textContent = message;
    $('error').hidden = !message;
  }

  function tone(element, value) {
    element.classList.toggle('positive', Number(value) > 0);
    element.classList.toggle('negative', Number(value) < 0);
  }

  function put(id, value) { $(id).textContent = value; }

  function chartColors() {
    const lib = window.LightweightCharts;
    return {background: {type: lib.ColorType.Solid, color: '#101d2c'},
      textColor: '#91a8c1', grid: {vertLines: {color: '#203246'}, horzLines: {color: '#203246'}},
      rightPriceScale: {borderColor: '#36506a'}, timeScale: {borderColor: '#36506a', timeVisible: false}};
  }
  function initPriceChart() {
    if (priceChart || !window.LightweightCharts) return;
    const lib = window.LightweightCharts;
    const priceBox = $('price-chart');
    priceChart = lib.createChart(priceBox, {...chartColors(), width: priceBox.clientWidth, height: priceBox.clientHeight,
      localization: {locale: 'ko-KR'}});
    candleSeries = priceChart.addSeries(lib.CandlestickSeries, {
      upColor: '#51c9a4', downColor: '#e9838b', borderUpColor: '#51c9a4',
      borderDownColor: '#e9838b', wickUpColor: '#51c9a4', wickDownColor: '#e9838b',
      priceFormat: {type: 'price', precision: 0, minMove: 1}});
    markerApi = lib.createSeriesMarkers(candleSeries, []);
    new ResizeObserver(() => {
      priceChart.applyOptions({width: priceBox.clientWidth, height: priceBox.clientHeight});
      if (!state) return;
      if ($('price-mode').value === 'research' && researchMarket?.symbol === state.symbol) {
        renderTransitBand(state, researchMarket.bars, `${researchMarket.year}-01-01`,
          researchMarket.complete_calendar_year ? `${researchMarket.year}-12-31`
            : researchMarket.last_observed);
      } else renderTransitBand(state);
    }).observe(priceBox);
  }
  function initEquityChart() {
    if (equityChart || !window.LightweightCharts) return;
    const lib = window.LightweightCharts;
    const equityBox = $('equity-chart');
    equityChart = lib.createChart(equityBox, {...chartColors(), width: equityBox.clientWidth,
      height: equityBox.clientHeight, localization: {locale: 'ko-KR'}});
    strategySeries = equityChart.addSeries(lib.LineSeries, {color: '#63aaff', lineWidth: 2,
      priceFormat: {type: 'price', precision: 0, minMove: 1}});
    s0Series = equityChart.addSeries(lib.LineSeries, {color: '#d7a462', lineWidth: 2,
      priceFormat: {type: 'price', precision: 0, minMove: 1}});
    new ResizeObserver(() => equityChart.applyOptions({width: equityBox.clientWidth,
      height: equityBox.clientHeight})).observe(equityBox);
  }

  function renderCharts(packet) {
    const priceFormat = {type: 'price', precision: packet.currency === 'USD' ? 2 : 0,
      minMove: packet.currency === 'USD' ? 0.01 : 1};
    if (section('price').open) {
      initPriceChart();
      if (priceChart) {
        candleSeries.applyOptions({priceFormat});
        // Whitespace dates preserve real calendar spacing through weekends.
        const research = $('price-mode').value === 'research' && researchMarket?.symbol === packet.symbol
          && researchMarket?.year === Number($('price-year').value);
        const sourceBars = research ? researchMarket.bars : packet.chart.price;
        if (research) {
          put('head-transit', `연구 ${researchMarket.year}`);
          put('head-transit-center', 'Gate 선택');
          put('head-transit-keynote', '연간 가격·Gate 맥락');
        }
        put('head-price', research ? `${sourceBars.length} bars · 연구 ${researchMarket.year}`
          : `${sourceBars.length} bars`);
        put('head-price-close', research ? `${researchMarket.last_observed || '—'} 종가 ${won(sourceBars.at(-1)?.close)}`
          : `종가 ${won(packet.market?.close)}${packet.price_change_pct == null ? '' : ` · ${percent(packet.price_change_pct)}`}`);
        const bars = new Map(sourceBars.map(bar => [bar.date, bar]));
        const first = research ? `${researchMarket.year}-01-01` : sourceBars[0]?.date;
        const last = research ? (researchMarket.complete_calendar_year
          ? `${researchMarket.year}-12-31` : researchMarket.last_observed) : sourceBars.at(-1)?.date;
        const daily = [];
        if (first && last) for (let day = Date.parse(`${first}T00:00:00Z`);
          day <= Date.parse(`${last}T00:00:00Z`); day += 86400000) {
          const date = new Date(day).toISOString().slice(0, 10);
          const bar = bars.get(date);
          daily.push(bar ? {time: date, open: bar.open, high: bar.high,
            low: bar.low, close: bar.close} : {time: date});
        }
        candleSeries.setData(daily);
        markerApi.setMarkers((research ? [] : packet.chart.markers).map(item => ({time: item.date,
          position: item.side === 'BUY' ? 'belowBar' : 'aboveBar',
          shape: item.kind === 'EXECUTION' ? 'circle' : item.side === 'BUY' ? 'arrowUp' : 'arrowDown',
          color: item.side === 'BUY' ? '#58d6af' : '#ffad79',
          text: `${item.side} ${item.kind === 'EXECUTION' ? '체결' : '결정'}`})));
        if (sourceBars.length) priceChart.timeScale().fitContent();
        renderTransitBand(packet, sourceBars, first, last);
        if (research) put('price-chart-note', `연간 연구 보기 · ${researchMarket.year} · ${researchMarket.bars.length}개 관측 시세 (${researchMarket.first_observed || '없음'} ~ ${researchMarket.last_observed || '없음'}) · 매매 Replay 상태와 분리 · ${researchMarket.complete_calendar_year ? '완결 연도' : '현재 연도 일부만 확보'}`);
        else put('price-chart-note', 'Replay 처리일까지 표시합니다. 결정은 당일 종가 이후, 체결은 이후 거래일입니다.');
      }
    }
    if (section('equity').open) {
      initEquityChart();
      if (equityChart) {
        strategySeries.applyOptions({priceFormat});
        s0Series.applyOptions({priceFormat});
        strategySeries.setData(packet.chart.equity.map(row => ({time: row.date, value: Number(row.strategy)})));
        s0Series.setData(packet.chart.equity.map(row => ({time: row.date, value: Number(row.s0)})));
        if (packet.chart.equity.length) equityChart.timeScale().fitContent();
      }
    }
  }

  async function calendarFor(year) {
    if (!transitCalendars.has(year)) transitCalendars.set(year,
      request(`/api/transit/year?year=${year}`).catch(failure => {
        transitCalendars.delete(year); throw failure;
      }));
    return transitCalendars.get(year);
  }
  const shortTime = value => value ? value.replace('T', ' ').slice(0, 16) : '—';
  async function renderTransitDetails(segment, packet) {
    if (!segment) return;
    selectedTransit = segment;
    const gateLabel = `${segment.gate}.${segment.line || '1–6'}`;
    put('transit-gate', gateLabel);
    put('transit-name', segment.gate_name || `Gate ${segment.gate}`);
    put('transit-center', segment.center);
    put('transit-keynote', segment.keynote);
    put('transit-start', shortTime(segment.start_kst));
    put('transit-end', shortTime(segment.end_kst));
    put('transit-theme', segment.fear_or_theme);
    put('transit-source', 'USNO 태양 황경 근사식 · 경계 시각 추정');
    const currentInstant = packet.transit?.market_close_utc;
    const isReplayCurrent = currentInstant && segment.start_utc <= currentInstant && currentInstant < segment.end_utc;
    put('transit-phase', isReplayCurrent && packet.phase
      ? `${packet.phase} · 현재 처리된 Replay` : '미산출 · 이 구간의 Phase Replay 없음');
    document.querySelectorAll('#transit-band .transit-slice').forEach(tile => {
      tile.classList.toggle('selected', Number(tile.dataset.gate) === Number(segment.gate));
    });
    put('head-transit', gateLabel);
    put('head-transit-center', segment.center);
    put('head-transit-keynote', segment.keynote);
    const year = Number(segment.start_utc.slice(0, 4));
    const query = new URLSearchParams({symbol: packet.symbol, year, gate: segment.gate,
      as_of: packet.view_date || packet.start_date});
    put('transit-metrics', '관측된 거래일 지표 조회 중…');
    try {
      const result = await request(`/api/transit/gate-metrics?${query}`);
      if (selectedTransit !== segment || state !== packet) return;
      const m = result.metrics[0];
      put('transit-metrics', m?.sessions
        ? `${m.sessions}거래일 · 기간수익 ${percent(m.return_pct)} · MDD ${percent(m.mdd_pct)} · 최대상승 ${percent(m.max_rise_pct)} · 일평균 ${percent(m.avg_daily_return_pct)} · 일변동성 ${percent(m.volatility_daily_pct)} · 총거래량 ${Math.round(m.total_volume).toLocaleString()} · 거래량 변화 ${percent(m.volume_change_pct)} · 거래대금/투자자수급/프로그램매매 미제공`
        : '이 구간에는 현재 조회 시점까지 관측된 거래일이 없습니다.');
    } catch (failure) { put('transit-metrics', `시장 지표를 불러오지 못했습니다: ${failure.message}`); }
  }
  function renderTransitBand(packet, sourceBars = packet.chart.price,
                             rangeStart = sourceBars[0]?.date,
                             rangeEnd = sourceBars.at(-1)?.date) {
    const band = $('transit-band'); band.replaceChildren();
    const guide = $('transit-guide'); guide.hidden = true;
    if (!priceChart || !sourceBars.length || !rangeStart || !rangeEnd) return;
    const firstDate = rangeStart;
    const lastDate = rangeEnd;
    if (firstDate === lastDate && packet.transit) {
      const tile = document.createElement('button'); tile.type = 'button';
      tile.className = 'transit-slice'; tile.style.left = '0'; tile.style.width = '100%';
      tile.dataset.gate = packet.transit.gate; tile.classList.add('current');
      tile.style.background = '#243e5a'; tile.textContent = `Gate ${packet.transit.gate}`;
      tile.title = `${packet.transit.gate}.${packet.transit.line} · ${packet.transit.center} · ${packet.transit.keynote} · ${packet.transit.fear_or_theme}\n${shortTime(packet.transit.start_kst)} – ${shortTime(packet.transit.end_kst)} KST`;
      tile.addEventListener('click', () => { section('transit').open = true;
        renderTransitDetails(packet.transit, packet); });
      band.append(tile);
      return;
    }
    const years = Array.from({length: Number(lastDate.slice(0, 4)) - Number(firstDate.slice(0, 4)) + 1},
      (_, index) => Number(firstDate.slice(0, 4)) + index);
    Promise.all(years.map(calendarFor)).then(calendars => {
      if (state !== packet || !section('price').open) return;
      const scale = priceChart.timeScale();
      const left = scale.timeToCoordinate(firstDate);
      const right = scale.timeToCoordinate(lastDate);
      if (left == null || right == null) return;
      const days = (Date.parse(`${lastDate}T00:00:00Z`) - Date.parse(`${firstDate}T00:00:00Z`)) / 86400000;
      const spacing = days ? (right - left) / days : 0;
      const coordinate = instant => left + (Date.parse(instant.slice(0, 10) + 'T00:00:00Z') - Date.parse(`${firstDate}T00:00:00Z`)) / 86400000 * spacing
        + ((Number(instant.slice(11, 13)) * 60 + Number(instant.slice(14, 16))) / 1440) * spacing;
      const clipLeft = left, clipRight = right + spacing;
      const markerDate = packet.view_date;
      const markerX = markerDate ? scale.timeToCoordinate(markerDate) : null;
      if (markerX != null && markerX >= clipLeft && markerX <= clipRight) {
        guide.style.left = `${markerX}px`;
        guide.hidden = false;
      }
      const currentInstant = packet.transit?.market_close_utc;
      for (const gate of calendars.flatMap(item => item.gates)) {
        const start = Math.max(clipLeft, coordinate(packet.currency === 'USD' ? gate.start_ny : gate.start_kst));
        const end = Math.min(clipRight, coordinate(packet.currency === 'USD' ? gate.end_ny : gate.end_kst));
        if (end <= start) continue;
        const tile = document.createElement('button'); tile.type = 'button';
        tile.className = 'transit-slice'; tile.style.left = `${start}px`;
        tile.dataset.gate = gate.gate;
        if (currentInstant && gate.start_utc <= currentInstant && currentInstant < gate.end_utc) tile.classList.add('current');
        if (selectedTransit && Number(selectedTransit.gate) === Number(gate.gate)) tile.classList.add('selected');
        tile.style.width = `${Math.max(1, end - start)}px`;
        tile.style.background = gate.center === 'Spleen' ? '#245074' : '#243e5a';
        tile.textContent = String(gate.gate);
        tile.title = `Gate ${gate.gate} · Lines 1–6 · ${gate.center} · ${gate.keynote} · ${gate.fear_or_theme}\n${shortTime(gate.start_kst)} – ${shortTime(gate.end_kst)} KST`;
        tile.addEventListener('click', () => { section('transit').open = true; renderTransitDetails(gate, packet); });
        band.append(tile);
      }
    }).catch(failure => { band.textContent = `Transit calendar unavailable: ${failure.message}`; });
  }
  async function loadResearchMarket(packet) {
    if (!packet || $('price-mode').value !== 'research') return;
    const year = Number($('price-year').value);
    put('price-chart-note', `${year}년 과거 시세를 조회 중…`);
    try {
      const market = await request(`/api/transit/market-year?symbol=${encodeURIComponent(packet.symbol)}&year=${year}`);
      if (state !== packet || $('price-mode').value !== 'research' || Number($('price-year').value) !== year) return;
      researchMarket = market;
      if (!market.bars.length) put('price-chart-note', `${year}년 관측된 시세가 없습니다.`);
      renderCharts(packet);
    } catch (failure) { put('price-chart-note', `연간 시세 조회 실패: ${failure.message}`); }
  }
  $('price-mode').addEventListener('change', () => {
    const research = $('price-mode').value === 'research';
    $('price-year-wrap').hidden = !research;
    if (state) {
      if (research) loadResearchMarket(state);
      else { renderTransit(state); renderCharts(state); }
    }
  });
  $('price-year').addEventListener('change', () => { if (state) loadResearchMarket(state); });
  function renderTransit(packet) {
    const segment = packet.transit;
    if (!segment) {
      put('head-transit', '거래일 진행 전');
      put('head-transit-center', '—');
      put('head-transit-keynote', 'Research Context');
      return;
    }
    const year = Number(packet.view_date.slice(0, 4));
    const select = $('transit-year');
    if (!select.options.length) for (let value = 2020; value <= 2026; value++) {
      const option = document.createElement('option'); option.value = value; option.textContent = value;
      select.append(option);
    }
    select.value = String(year);
    renderTransitYear(year, packet);
    renderTransitDetails(segment, packet);
  }
  async function renderTransitYear(year, packet) {
    try {
      const calendar = await calendarFor(year);
      if (state !== packet || Number($('transit-year').value) !== year) return;
      put('transit-year-note', `${calendar.gates.length}개 연도 내 구간 · 64 Gate · USNO 근사 모델`);
      const band = $('transit-year-band'); band.replaceChildren();
      for (const gate of calendar.gates) {
        const tile = document.createElement('button'); tile.type = 'button';
        tile.textContent = String(gate.gate);
        tile.title = `Gate ${gate.gate} · ${gate.center}\n${shortTime(gate.start_kst)} – ${shortTime(gate.end_kst)} KST`;
        tile.addEventListener('click', () => renderTransitDetails(gate, packet));
        band.append(tile);
      }
    } catch (failure) { put('transit-year-note', `Calendar unavailable: ${failure.message}`); }
  }
  $('transit-year').addEventListener('change', () => {
    if (state) renderTransitYear(Number($('transit-year').value), state);
  });

  function renderJournal(packet) {
    const body = $('journal-body');
    body.replaceChildren();
    for (const item of [...packet.journal].reverse()) {
      const j = item.journal;
      const row = document.createElement('tr');
      row.tabIndex = -1;
      row.classList.toggle('selected', j.journal_date === packet.view_date);
      row.classList.toggle('new-row', j.journal_date === highlightDate);
      const values = [j.journal_date, j.phase, `${j.signal} / ${j.decision}`,
        item.order ? `${item.order.side} ${item.order.requested_price}` : '—',
        item.execution ? `${item.execution.side} ${won(item.execution.fill_price)}` : '—',
        number(j.quantity), won(j.cash), won(j.portfolio_value), won(j.s0_portfolio_value),
        signedWon(j.realized_pnl), signedWon(j.unrealized_pnl)];
      for (const value of values) {
        const cell = row.insertCell();
        cell.textContent = value;
      }
      row.addEventListener('click', () => loadState(j.journal_date));
      body.append(row);
    }
    put('journal-count', `${packet.journal.length}개 조회 · 전체 ${packet.days_processed}개 거래일`);
  }

  function renderHeaders(packet) {
    const s = packet.summary;
    const p = packet.position;
    const m = packet.market;
    const last = packet.journal.at(-1)?.journal;
    const previousPhase = packet.journal.length > 1 ? packet.journal.at(-2).journal.phase : null;
    let phaseSince = null;
    let priorPhase = null;
    for (const item of packet.journal) {
      if (item.journal.phase !== priorPhase) phaseSince = item.journal.journal_date;
      priorPhase = item.journal.phase;
    }
    put('head-equity', won(s.portfolio_value));
    put('head-return', `${signedWon(s.total_pnl)} / ${percent(s.net_return_pct)}`);
    put('head-cash', `현금 ${won(s.cash)}`);
    tone($('head-return'), s.total_pnl);
    put('head-decision', packet.decision?.decision || 'NOT PROCESSED');
    put('head-market', m ? `${m.date} · 종가 ${won(m.close)}` : '종가 —');
    put('head-phase', `Phase ${packet.phase || '—'}`);
    put('head-journal', `${packet.journal.length}거래일${packet.viewing_history ? ` / 전체 ${packet.days_processed}` : ''}`);
    put('head-journal-date', `최근 ${packet.view_date || '—'} · ${packet.decision?.decision || '—'}`);
    put('head-journal-equity', `총자산 ${won(s.portfolio_value)}`);
    put('head-position', p.status === 'OPEN' ? `${number(p.quantity)}주 보유` : 'NO POSITION');
    put('head-position-avg', p.status === 'OPEN' ? `평균 ${won(p.average_entry)} · ${number(p.hold_days)}거래일` : '');
    put('head-position-pnl', p.status === 'OPEN' ? `미실현 ${signedWon(p.unrealized_pnl)}` : '');
    tone($('head-position-pnl'), p.unrealized_pnl);
    put('head-price', `${packet.chart.price.length} bars`);
    put('head-price-close', `종가 ${won(m?.close)}${packet.price_change_pct == null ? '' : ` · ${percent(packet.price_change_pct)}`}`);
    const code = strategyCode(packet.strategy_id);
    put('head-vs-s0', `${code} − S0 ${signedWon(s.vs_s0)} / ${percent(s.vs_s0_pct)}`);
    put('head-s0-equity', `${code} ${won(s.portfolio_value)} · S0 ${won(s.s0_equity)}`);
    tone($('head-vs-s0'), s.vs_s0);
    put('head-phase-detail', packet.phase || 'NOT PROCESSED');
    put('head-phase-previous', previousPhase && previousPhase !== packet.phase ? `이전 ${previousPhase}` : 'Context Only');
    put('phase-current', packet.phase || '—');
    put('phase-previous', previousPhase || '—');
    put('phase-since', phaseSince || '—');
    const pending = packet.pending_order;
    const execution = packet.execution;
    put('head-order', pending ? `${pending.side} 대기` : execution ? `${execution.side} 체결` : 'NONE');
    put('head-order-detail', pending ? `${pending.requested_price}` : execution ? `${number(execution.quantity)}주 @ ${won(execution.fill_price)}` : '');
    put('today-order', packet.order ? `${packet.order.side} · ${packet.order.requested_price} · ${packet.order.status}` : 'NONE');
    put('head-provider', (packet.provenance.provider || 'UNVERIFIED').split(' ')[0]);
    put('head-adjustment', packet.provenance.adjustment || 'UNKNOWN');
    put('head-data-date', packet.view_date || '—');
    put('tech-strategy', packet.strategy_version || '—');
    put('tech-phase', last?.phase_engine_version || '—');
    put('tech-fee', last?.fee_model_version || '—');
    put('tech-fill', last?.fill_rule_version || '—');
    put('tech-hash', last?.source_history_hash || '—');
    put('tech-retrieved', packet.provenance.retrieved_at || '—');
  }

  function render(packet) {
    state = packet;
    accountId = packet.account_id;
    displayCurrency = packet.currency;
    $('empty-state').hidden = true;
    $('workspace').hidden = false;
    if (!$('price-year').options.length) for (let year = 2020; year <= 2026; year++) {
      const option = document.createElement('option'); option.value = year; option.textContent = year;
      $('price-year').append(option);
    }
    if (!researchMarket) $('price-year').value = packet.view_date?.slice(0, 4) || '2025';
    const code = strategyCode(packet.strategy_id);
    const s0FirstOpen = code === 'S0' && packet.journal.length === 1;
    put('workspace-asset', `HISTORICAL REPLAY · ${packet.asset_name} ${packet.symbol} · ${code}`);
    const rule = code === 'S1' ? ` · 매수 시가 ${packet.entry_offset_pct}% · 익절 +${packet.take_profit_pct}%`
      : code === 'S2' ? ` · 매수 시가 -1% · 익절 +5% · 손절 -${packet.stop_loss_pct}%`
      : code === 'S7' ? ' · 20일 고가 돌파 / 10일 저가 이탈' : ' · 첫 거래일 시가 매수';
    put('run-meta', `${code} ${strategyName(packet.strategy_id)} · 시작 ${packet.start_date} · 초기 ${won(packet.initial_capital)} · 1회 매수 ${packet.buy_budget == null ? '가용 현금 전액' : won(packet.buy_budget)}${rule} · 처리 ${packet.days_processed}거래일`);
    put('current-date', packet.view_date || 'NOT PROCESSED');
    put('view-mode', packet.viewing_history ? '과거 Journal 조회 · 계좌는 최신 상태 유지' : '현재 Replay 상태');
    put('today-decision-note', s0FirstOpen ? '시작일 시가 사전약정 · Phase는 종가 관찰' : '당일 종가 이후 결정');
    put('price-chart-note', code === 'S0'
      ? 'S0는 선택한 첫 거래일 시가에 사전약정 매수합니다. 이후에는 보유하며 처리된 날짜까지만 표시합니다.'
      : '처리한 날짜까지만 표시합니다. 결정은 당일 종가 이후, 체결은 이후 거래일입니다.');
    const s = packet.summary;
    const lastDay = packet.journal.at(-1);
    const lastBuy = [...packet.journal].reverse().find(day => day.execution?.side === 'BUY')?.execution;
    const budget = packet.buy_budget == null ? '가용 현금 전액' : won(packet.buy_budget);
    if (packet.execution?.side === 'BUY') {
      put('buy-status-title', '오늘 매수 체결');
      put('buy-status-detail', `${number(packet.execution.quantity)}주 × ${won(packet.execution.fill_price)} · 비용 포함 실제 사용 ${won(packet.execution.net_amount)} / 한도 ${budget} · 남은 현금 ${won(s.cash)}`);
    } else if (lastDay?.journal?.order_status === 'LIMIT_NOT_TOUCHED') {
      put('buy-status-title', '오늘 매수 미체결');
      put('buy-status-detail', `저가가 지정가에 닿지 않았습니다. 지출 ${won(0)} · 현금 ${won(s.cash)} 유지 · 다음 주문 한도 ${budget}`);
    } else if (packet.pending_order?.side === 'BUY') {
      put('buy-status-title', '다음 거래일 매수 대기');
      put('buy-status-detail', `시가 대비 ${packet.entry_offset_pct}% 지정가 · 최대 지출 ${budget} · 체결 전 현금 ${won(s.cash)} · 실제 수량은 다음 거래일 시가와 거래비용으로 결정`);
    } else if (lastBuy) {
      put('buy-status-title', '최근 매수 기록');
      put('buy-status-detail', `${number(lastBuy.quantity)}주 × ${won(lastBuy.fill_price)} · 당시 비용 포함 사용 ${won(lastBuy.net_amount)} / 한도 ${budget} · 현재 현금 ${won(s.cash)}`);
    } else {
      put('buy-status-title', '매수 전 · 현금 보유');
      put('buy-status-detail', `현재 현금 ${won(s.cash)} · 1회 매수 최대 ${budget} · 주문 체결 시에만 실제 매수액 차감`);
    }
    put('initial', won(s.purchase_amount));
    put('balance-capital', won(packet.initial_capital));
    put('equity', won(s.portfolio_value));
    put('cash', won(s.cash));
    put('market-value', won(s.market_value));
    put('total-pnl', signedWon(s.total_pnl));
    put('net-return', percent(s.net_return_pct));
    put('realized', signedWon(s.realized_pnl));
    put('unrealized', signedWon(s.unrealized_pnl));
    put('valuation-return', percent(s.valuation_return_pct));
    put('s0', won(s.s0_equity));
    put('vs-s0', `${code} − S0 ${signedWon(s.vs_s0)} (${percent(s.vs_s0_pct)})`);
    [['total-pnl', s.total_pnl], ['realized', s.realized_pnl], ['unrealized', s.unrealized_pnl],
      ['vs-s0', s.vs_s0]].forEach(([id, value]) => tone($(id), value));
    const m = packet.market;
    put('market-date', m?.date || 'NOT PROCESSED');
    ['open', 'high', 'low', 'close'].forEach(key => put(key, won(m?.[key])));
    put('volume', number(m?.volume));
    const previousPhase = packet.journal.length > 1 ? packet.journal.at(-2).journal.phase : null;
    put('phase', packet.phase ? `${packet.phase}${previousPhase && previousPhase !== packet.phase ? ` ← ${previousPhase}` : ''}` : 'NOT PROCESSED');
    put('signal', packet.signal || 'NOT PROCESSED');
    put('decision', packet.decision?.decision || 'NOT PROCESSED');
    put('reason', packet.decision?.reason || '—');
    put('pending', packet.pending_order ? `${packet.pending_order.side} · ${packet.pending_order.requested_price}` : 'NONE');
    put('execution', packet.execution ? `${packet.execution.side} · ${won(packet.execution.fill_price)} · ${number(packet.execution.quantity)}주` : 'NONE');
    const p = packet.position;
    const holdings = $('balance-holdings');
    holdings.replaceChildren();
    const holdingRow = document.createElement('tr');
    const holdingValues = p.status === 'OPEN'
      ? [`${packet.asset_name} · ${packet.symbol}`, won(p.average_entry), `${number(p.quantity)}주`,
        won(s.purchase_amount), won(s.market_value), signedWon(s.unrealized_pnl),
        percent(s.valuation_return_pct)]
      : ['보유 종목 없음 · 예수금 대기', '—', '0주', '—', '—', '—', '—'];
    for (const value of holdingValues) holdingRow.insertCell().textContent = value;
    holdings.append(holdingRow);
    put('position-status', p.status);
    put('qty', `${number(p.quantity)}주`);
    put('avg-entry', won(p.average_entry));
    put('entry-date', p.entry_date || '—');
    put('hold-days', p.hold_days ? `${number(p.hold_days)} 거래일` : '—');
    put('position-close', won(p.close));
    put('position-value', won(p.market_value));
    put('position-pnl', signedWon(p.unrealized_pnl));
    put('exit-rule-label', code === 'S7' ? 'Exit: 10일 저점' : 'Take Profit');
    put('take-profit-price', won(p.take_profit_price));
    put('stop-loss-price', won(p.stop_loss_price));
    put('equity-chart-title', `${code} vs S0 자산 차트`);
    put('strategy-legend', `${code} Paper`);
    put('equity-chart-note', code === 'S0'
      ? 'S0 Paper는 설정한 1회 매수 한도만 사용합니다. 기준선 S0는 첫 시가에 전체 가용 자금으로 매수합니다.'
      : 'S0 기준선은 첫 시가에 전체 가용 자금으로 매수합니다. Paper 전략은 사전 정의된 시점 규칙을 따릅니다.');
    tone($('position-pnl'), p.unrealized_pnl);
    put('next-hint', packet.viewing_history ? '최신 화면으로 돌아온 뒤 진행할 수 있습니다.' :
      packet.replay_complete ? 'REPLAY_COMPLETE · 더 진행할 데이터가 없습니다.' :
      `다음 실제 거래일: ${packet.next_session}`);
    $('next').disabled = packet.replay_complete || packet.viewing_history;
    $('previous').disabled = packet.journal.length < 2;
    $('latest').disabled = !packet.viewing_history;
    put('provenance', `Local-only ${packet.provenance.provider || 'UNVERIFIED'} · ${packet.provenance.adjustment || 'UNKNOWN'} · Historical Replay only · 투자 조언/실거래 아님`);
    renderHeaders(packet);
    renderJournal(packet);
    renderTransit(packet);
    renderCharts(packet);
    if ($('price-mode').value === 'research' &&
        (researchMarket?.symbol !== packet.symbol || researchMarket?.year !== Number($('price-year').value))) {
      loadResearchMarket(packet);
    }
  }

  async function loadState(viewDate = null) {
    if (!accountId) return;
    try {
      error('');
      const query = viewDate ? `?view_date=${encodeURIComponent(viewDate)}` : '';
      render(await request(`/api/replay/${encodeURIComponent(accountId)}/state${query}`));
    } catch (failure) { error(failure.message); }
  }

  async function refreshAccounts(selected = accountId) {
    const accounts = await request('/api/accounts');
    const select = $('account-select');
    select.replaceChildren();
    const blank = document.createElement('option');
    blank.value = '';
    blank.textContent = accounts.length ? '계좌 선택' : '저장된 계좌 없음';
    select.append(blank);
    for (const account of accounts) {
      const option = document.createElement('option');
      option.value = account.account_id;
      option.textContent = `${account.asset_name} ${account.symbol} · ${strategyCode(account.strategy_id)} · ${account.start_date} · ${won(account.capital, account.currency)} · ${account.days_processed}일${account.last_date ? ` · ${account.last_date}` : ''}`;
      select.append(option);
    }
    select.value = selected && accounts.some(a => a.account_id === selected) ? selected : '';
    $('hide-account').disabled = !select.value;
    const hidden = await request('/api/accounts/hidden');
    const hiddenSelect = $('hidden-account-select');
    hiddenSelect.replaceChildren();
    for (const account of hidden) {
      const option = document.createElement('option');
      option.value = account.account_id;
      option.textContent = `${account.asset_name} ${account.symbol} · ${strategyCode(account.strategy_id)} · ${account.start_date} · ${won(account.capital, account.currency)} · ${account.days_processed}일`;
      hiddenSelect.append(option);
    }
    $('hidden-restore').hidden = hidden.length === 0;
    put('hidden-count', `(${hidden.length})`);
    return accounts;
  }

  $('create-form').addEventListener('submit', async event => {
    event.preventDefault();
    const button = event.currentTarget.querySelector('button');
    button.disabled = true;
    try {
      error('');
      const strategy = $('strategy-select').value;
      const inputs = {symbol: $('asset-select').value, strategy, capital: $('capital').value,
        buy_budget: $('buy-budget').value, start_date: $('start-date').value};
      if (strategy === 'S1') {
        inputs.entry_offset_pct = $('entry-offset').value;
        inputs.take_profit_pct = $('take-profit').value;
      }
      const created = await request('/api/replay/create', {method: 'POST',
        headers: {'Content-Type': 'application/json'}, body: JSON.stringify(inputs)});
      render(created.state);
      await refreshAccounts(created.account_id);
    } catch (failure) { error(failure.message); }
    finally { button.disabled = false; }
  });

  $('account-select').addEventListener('change', async event => {
    $('hide-account').disabled = !event.target.value;
    if (!event.target.value) return;
    accountId = event.target.value;
    await loadState();
  });
  $('hide-account').addEventListener('click', async () => {
    const selected = $('account-select').value;
    if (!selected) return;
    const label = $('account-select').selectedOptions[0]?.textContent || selected;
    if (!window.confirm(`이 Replay 계좌를 목록에서 숨길까요?\n${label}\n\n원본 계좌와 매매 Journal은 삭제되지 않습니다.`)) return;
    const button = $('hide-account');
    button.disabled = true;
    try {
      error('');
      await request(`/api/replay/${encodeURIComponent(selected)}/hide`,
        {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'});
      accountId = null;
      state = null;
      const accounts = await refreshAccounts();
      if (accounts.length) {
        accountId = accounts[0].account_id;
        $('account-select').value = accountId;
        button.disabled = false;
        await loadState();
      } else {
        $('workspace').hidden = true;
        $('empty-state').hidden = false;
      }
    } catch (failure) { error(failure.message); button.disabled = !$('account-select').value; }
  });
  $('restore-account').addEventListener('click', async () => {
    const selected = $('hidden-account-select').value;
    if (!selected) return;
    const button = $('restore-account');
    button.disabled = true;
    try {
      error('');
      await request(`/api/replay/${encodeURIComponent(selected)}/restore`,
        {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'});
      const accounts = await refreshAccounts(selected);
      if (accounts.some(a => a.account_id === selected)) {
        accountId = selected;
        await loadState();
      }
    } catch (failure) { error(failure.message); }
    finally { button.disabled = false; }
  });
  $('next').addEventListener('click', async () => {
    if (!accountId || state?.viewing_history) return;
    $('next').disabled = true;
    try {
      error('');
      const result = await request(`/api/replay/${encodeURIComponent(accountId)}/next`,
        {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'});
      section('journal').open = true;
      section('today').open = true;
      highlightDate = result.journal_date || null;
      render(result.state);
      if (highlightDate) requestAnimationFrame(() => {
        const row = $('journal-body').querySelector('.new-row');
        section('journal').scrollIntoView({block: 'start'});
        row?.scrollIntoView({block: 'nearest'});
        row?.focus({preventScroll: true});
        setTimeout(() => row?.classList.remove('new-row'), 3600);
        highlightDate = null;
      });
      await refreshAccounts(accountId);
    } catch (failure) { error(failure.message); $('next').disabled = false; }
  });
  $('previous').addEventListener('click', () => {
    if (state?.journal.length > 1) loadState(state.journal.at(-2).journal.journal_date);
  });
  $('latest').addEventListener('click', () => loadState());

  function syncStrategy() {
    const code = $('strategy-select').value;
    $('s1-fields').hidden = code !== 'S1';
    $('entry-offset').required = code === 'S1';
    $('take-profit').required = code === 'S1';
    const notes = {S0: '첫 거래일 시가에 1회 매수 후 보유 · 매수 한도 밖의 현금 유지',
      S2: '고정 규칙: 시가 -1% 매수 · +5% 익절 · -3% 손절 (다음 거래일부터 브래킷 적용)',
      S7: '고정 규칙: 전일 20일 고가 돌파 시 다음 시가 매수 · 10일 저점 이탈 시 다음 시가 매도'};
    $('strategy-note').hidden = code === 'S1';
    put('strategy-note', notes[code] || '');
  }
  $('strategy-select').addEventListener('change', syncStrategy);
  $('capital').addEventListener('input', () => {
    const capital = Number($('capital').value);
    const budget = $('buy-budget');
    const previous = Number(budget.max);
    budget.max = String(capital);
    if (Number(budget.value) === Math.floor(previous / 5) || Number(budget.value) > capital) {
      budget.value = String(Math.max(1, Math.floor(capital / 5)));
    }
  });

  async function loadMeta(symbol, populateAssets = false) {
    const meta = await request(symbol ? `/api/meta?symbol=${encodeURIComponent(symbol)}` : '/api/meta');
    if (populateAssets) {
      const select = $('asset-select');
      select.replaceChildren();
      for (const asset of meta.available_assets) {
        const option = document.createElement('option');
        option.value = asset.symbol;
        option.textContent = `${asset.name} · ${asset.symbol} (${asset.currency})`;
        select.append(option);
      }
      const strategies = $('strategy-select');
      strategies.replaceChildren();
      for (const strategy of meta.available_strategies) {
        const option = document.createElement('option');
        option.value = strategy.code;
        option.textContent = strategy.name;
        strategies.append(option);
      }
      strategies.value = 'S1';
      syncStrategy();
    }
    $('asset-select').value = meta.symbol;
    $('start-date').min = meta.first_observation;
    $('start-date').max = meta.latest_observation;
    $('start-date').value = meta.suggested_start;
    $('capital').min = meta.currency === 'USD' ? '100' : '10000';
    $('capital').value = meta.default_capital;
    $('buy-budget').max = meta.default_capital;
    $('buy-budget').value = String(Math.floor(Number(meta.default_capital) / 5));
    put('capital-label', `초기 투자금 (${meta.currency})`);
    put('budget-label', `1회 매수 한도 (${meta.currency})`);
    put('data-range', `${meta.asset_name} · 시세 ${meta.first_observation} ~ ${meta.latest_observation} · ${meta.provider}`);
  }

  $('asset-select').addEventListener('change', async event => {
    try { error(''); await loadMeta(event.target.value); }
    catch (failure) { error(failure.message); }
  });

  (async () => {
    try {
      await loadMeta(null, true);
      const accounts = await refreshAccounts();
      if (accounts.length) {
        accountId = accounts[0].account_id;
        $('account-select').value = accountId;
        await loadState();
      }
    } catch (failure) { error(failure.message); }
  })();
})();
