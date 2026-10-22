/* Read-only comparison workspace inside the existing Asset Discovery page. */
(() => {
  const $ = id => document.getElementById(id);
  const selected = new Map([['HD_TRANSIT', true], ['PRICE_PHASE_V1', true]]);
  const colors = ['#6baaff', '#ffbb6b', '#7bdcba', '#e59ae8', '#ffe08a', '#ff8f9a'];
  let catalog = new Map(), packet = null, chart = null, chartSeries = [], lockedDate = null;
  let previewDate = null, generation = 0, investmentPeriod = null;
  let quarters = new Map(), quarterByGate = new Map();
  let bandRenderId = 0;
  const calendarCache = new Map();
  const text = (id, value) => { $(id).textContent = value; };
  const value = number => Number(number).toLocaleString('ko-KR', {maximumFractionDigits: 2});
  const pct = number => number == null ? '전일 관측 없음' : `${number >= 0 ? '+' : ''}${number.toFixed(2)}%`;
  const params = object => new URLSearchParams(object).toString();
  const fetchJson = async url => {
    const response = await fetch(url);
    const body = await response.json();
    if (!response.ok) throw Error(body.error || `HTTP ${response.status}`);
    return body;
  };
  const kstToday = () => {
    const parts = new Intl.DateTimeFormat('en-CA', {timeZone: 'Asia/Seoul', year: 'numeric',
      month: '2-digit', day: '2-digit'}).formatToParts(new Date());
    const byType = Object.fromEntries(parts.map(part => [part.type, part.value]));
    return `${byType.year}-${byType.month}-${byType.day}`;
  };
  function subtractMonths(iso, months) {
    const [year, month, day] = iso.split('-').map(Number);
    const first = new Date(Date.UTC(year, month - 1 - months, 1));
    const lastDay = new Date(Date.UTC(first.getUTCFullYear(), first.getUTCMonth() + 1, 0)).getUTCDate();
    first.setUTCDate(Math.min(day, lastDay));
    return first.toISOString().slice(0, 10);
  }
  function applyShortcut(kind) {
    const base = catalog.get($('cmp-base').value);
    if (kind === 'SIM' && !investmentPeriod) {
      const {investmentStart, investmentEnd} = $('comparison-workspace').dataset;
      if (investmentStart && investmentEnd) investmentPeriod = [investmentStart, investmentEnd];
    }
    const end = kind === 'SIM' ? investmentPeriod?.[1] : base?.available_to;
    if (!end || (kind === 'SIM' && !investmentPeriod?.[0])) {
      text('cmp-range-note', kind === 'SIM' ? '투자조건을 실행한 뒤 SIM 기간을 선택할 수 있습니다.' : '기준 자산의 관측기간이 없습니다.');
      return;
    }
    const months = {"1M": 1, "3M": 3, "6M": 6, "1Y": 12, "3Y": 36};
    const start = kind === 'SIM' ? investmentPeriod[0] : kind === 'ALL' ? base.available_from : subtractMonths(end, months[kind]);
    $('cmp-start').value = start < base.available_from ? base.available_from : start;
    $('cmp-end').value = end > base.available_to ? base.available_to : end;
    $('cmp-year').value = '';
    document.querySelectorAll('[data-cmp-range]').forEach(button => button.classList.toggle('active', button.dataset.cmpRange === kind));
    text('cmp-range-note', `${kind} · 기준 자산 실제 관측기간 안에서 비교합니다. 전략 재계산 없음.`);
    run();
  }
  function renderLayers() {
    const target = $('cmp-layers'); target.replaceChildren();
    const baseChip = document.createElement('span'); baseChip.className = 'comparison-chip';
    baseChip.textContent = `기준 ${catalog.get($('cmp-base').value)?.display_name || '—'}`;
    target.append(baseChip);
    for (const [id] of selected) {
      const descriptor = catalog.get(id);
      if (!descriptor) continue;
      const chip = document.createElement('span'); chip.className = 'comparison-chip';
      const name = document.createElement('span');
      name.textContent = descriptor.display_name;
      const remove = document.createElement('button'); remove.type = 'button'; remove.textContent = '×';
      remove.title = 'Workspace에서 제거';
      remove.addEventListener('click', () => { selected.delete(id); renderLayers(); renderPicker(); run(); });
      chip.append(name, remove); target.append(chip);
    }
  }
  function renderPicker() {
    const target = $('cmp-catalog'); target.replaceChildren();
    const groups = [
      ['금융상품', ['ASSET', 'INDEX', 'COMMODITY']],
      ['거시 · 금리 · 환율', ['MACRO', 'RATE', 'FX']],
      ['심리 · 변동성', ['SENTIMENT', 'VOLATILITY']],
      ['시장 수급', ['FLOW', 'BREADTH']],
      ['연구 맥락', ['PHASE', 'TRANSIT']]];
    const query = $('cmp-search').value.trim().toLocaleLowerCase();
    for (const [label, types] of groups) {
      const items = [...catalog.values()].filter(item => types.includes(item.layer_type) &&
        ['AVAILABLE', 'RESEARCH_ONLY'].includes(item.availability) &&
        item.layer_id !== $('cmp-base').value && !selected.has(item.layer_id) &&
        `${item.display_name} ${item.layer_id}`.toLocaleLowerCase().includes(query));
      if (!items.length) continue;
      const title = document.createElement('h4'); title.textContent = label; target.append(title);
      for (const item of items) {
        const button = document.createElement('button'); button.type = 'button';
        button.textContent = item.display_name;
        button.title = `${item.source || 'Research context'} · ${item.frequency}`;
        button.addEventListener('click', () => {
          if (selected.size >= 10) { text('cmp-status', '비교 Layer는 최대 10개까지 선택할 수 있습니다.'); return; }
          selected.set(item.layer_id, true);
          $('cmp-picker').hidden = true;
          $('cmp-add').setAttribute('aria-expanded', 'false');
          renderLayers(); renderPicker(); run();
        });
        target.append(button);
      }
    }
    if (!target.childElementCount) {
      const empty = document.createElement('p'); empty.textContent = '추가할 수 있는 연결 항목이 없습니다.'; target.append(empty);
    }
  }
  function contextSection(title, main, details = [], unavailable = false, group = '') {
    const section = document.createElement('section');
    section.className = [group, unavailable ? 'unavailable' : ''].filter(Boolean).join(' ');
    const label = document.createElement('small'); label.textContent = title;
    const body = document.createElement('strong'); body.textContent = main;
    section.append(label, body);
    for (const detail of details) { const note = document.createElement('small'); note.textContent = detail; section.append(note); }
    return section;
  }
  function renderContext(day) {
    const panel = $('cmp-context-body'); panel.replaceChildren();
    text('cmp-date', day ? new Intl.DateTimeFormat('ko-KR', {timeZone:'UTC', year:'numeric', month:'long',
      day:'numeric', weekday:'long'}).format(new Date(`${day}T00:00:00Z`)) : '—');
    $('cmp-unlock').hidden = !lockedDate;
    $('cmp-context').classList.toggle('is-pinned', !!lockedDate);
    text('cmp-hover-mode', lockedDate ? '고정' : '호버');
    if (!packet || !day || !packet.context_by_date[day]) {
      panel.append(contextSection('관측 상태', '기준 자산 관측 없음', [], true));
      return;
    }
    const snapshot = packet.context_by_date[day];
    const baseName = catalog.get(packet.base)?.display_name || packet.base;
    const base = snapshot.base;
    const price = number => number == null ? 'N/A' : `${value(number)} ${base.unit}`;
    const baseCard = contextSection(baseName, `종 ${price(base.close)} · ${pct(base.daily_change_pct)}`,
      [`시 ${price(base.open)} · 고 ${price(base.high)}`,
        `저 ${price(base.low)} · 거래량 ${base.volume == null ? '—' : value(base.volume)}`], false, 'group-price');
    baseCard.classList.add(base.daily_change_pct > 0 ? 'up' : base.daily_change_pct < 0 ? 'down' : 'flat');
    panel.append(baseCard);
    const indicatorDetails = [];
    const pane = $('cmp-indicator-pane'); pane.replaceChildren();
    for (const [id, visible] of selected) {
      if (!visible || id === 'PRICE_PHASE_V1' || id === 'HD_TRANSIT') continue;
      const descriptor = catalog.get(id), result = snapshot.layers?.[id];
      const actual = result?.value != null;
      const detail = actual && result.observation_date !== day ? [`관측 ${result.observation_date}`] : [];
      const asset = ['ASSET', 'INDEX', 'COMMODITY'].includes(descriptor.layer_type);
      const state = id === 'VIX' ? {Lower: '낮음', Moderate: '보통', Elevated: '높음'}[result?.state] : null;
      panel.append(contextSection(descriptor.display_name,
        actual ? `${value(result.value)} ${result.unit}${asset ? ` · ${pct(result.change_1d_pct)}` : state ? ` · ${state}` : ''}` : '관측 없음',
        detail, !actual, 'group-market'));
      indicatorDetails.push(`${descriptor.display_name}: ${actual ? `${value(result.value)} ${result.unit} · ${result.reference} · ${result.state || result.status} · ${pct(result.change_1d_pct)} · ${result.meaning} · 관측 ${result.observation_date} · 적용 지연 ${result.lag_days ?? 0}일` : 'N/A · 해당 날짜 이용 가능 관측값 없음'} · 출처 ${descriptor.source || '미연결'}`);
      if (!['ASSET', 'INDEX'].includes(descriptor.layer_type)) {
        const item = document.createElement('span');
        item.textContent = `${descriptor.display_name} ${actual ? `${value(result.value)} ${result.unit}` : descriptor.availability === 'NOT_CONNECTED' ? 'N/A · 미연결' : 'N/A · 결측'}`;
        pane.append(item);
      }
    }
    pane.hidden = true;
    text('cmp-indicator-detail-body', indicatorDetails.length ? indicatorDetails.join('\n') : '선택된 비교 지표가 없습니다.');
    if (selected.get('PRICE_PHASE_V1')) panel.append(contextSection('가격 Phase',
      snapshot.phase || '미산출', [], !snapshot.phase, 'group-research'));
    if (selected.get('HD_TRANSIT')) {
      const gate = snapshot.transit;
      panel.append(contextSection('☉ 트랜짓 · 연구 맥락', gate ? `관문 ${gate.gate}.${gate.line} · ${gate.center_ko}` : '미산출',
        gate ? [`${gate.keynote_ko} · ${gate.quarter.name_ko}`] : [], !gate, 'group-research'));
      if (gate) {
        text('cmp-gate-head', `관문 ${gate.gate}.${gate.line} · ${gate.quarter.name_ko}`);
        text('cmp-gate-detail', `휴먼디자인 해석: ${gate.gate_name_ko} (${gate.gate_name}), ${gate.center_ko} (${gate.center}), 키노트 ${gate.keynote_ko} (${gate.keynote}). ${gate.short_description_ko} Theme: ${gate.theme_ko} (${gate.theme}). Fear Theme: ${gate.fear_theme_ko || '해당 자료에서 미분류'}. ${gate.quarter.name_ko} (${gate.quarter.name}), ${gate.quarter.theme_ko} (${gate.quarter.theme}). 시작 관문 ${gate.quarter.start_gate}, 전환 관문 ${gate.quarter.turning_gate}, 마지막 관문 ${gate.quarter.end_gate}. 트랜짓 ${gate.start_utc} ~ ${gate.end_utc} (UTC, 근사). 출처: ${gate.source}.\n금융시장 관측: ${baseName} ${day} 종가 ${value(base.close)} ${base.unit}, 등락 ${pct(base.daily_change_pct)}. 이 관측과 상징적 해석 사이의 인과관계는 검증되지 않았습니다.`);
      }
    } else { text('cmp-gate-head', '미선택'); text('cmp-gate-detail', '☉ 트랜짓 Layer를 추가하면 상세를 볼 수 있습니다.'); }
    document.querySelectorAll('#cmp-transit-band button').forEach(tile =>
      tile.classList.toggle('selected', day >= tile.dataset.start && day <= tile.dataset.end));
  }
  function resetChart() {
    if (!chart) return;
    for (const series of chartSeries) chart.removeSeries(series);
    chartSeries = [];
  }
  function initChart() {
    if (chart || !window.LightweightCharts) return;
    const lib = window.LightweightCharts;
    chart = lib.createChart($('cmp-chart'), {width: $('cmp-chart').clientWidth, height: $('cmp-chart').clientHeight,
      layout: {background: {color: '#0b1827'}, textColor: '#b6cce2', fontFamily: 'system-ui'},
      grid: {vertLines: {color: '#1d344a'}, horzLines: {color: '#1d344a'}},
      timeScale: {timeVisible: false, borderColor: '#40607d', rightOffset: 2},
      crosshair: {vertLine: {color: '#f0d384', width: 1}, horzLine: {color: '#6987a5'}}});
    chart.subscribeCrosshairMove(event => {
      if (lockedDate) return;
      const day = typeof event.time === 'string' ? event.time : event.time?.year ?
        `${event.time.year}-${String(event.time.month).padStart(2, '0')}-${String(event.time.day).padStart(2, '0')}` : null;
      if (day && packet?.context_by_date[day]) {
        if (day !== previewDate) { previewDate = day; renderContext(day); }
        $('cmp-context').hidden = false;
        $('cmp-context').classList.toggle('on-right', (event.point?.x ?? 0) < $('cmp-chart').clientWidth / 2);
      } else $('cmp-context').hidden = true;
    });
    chart.subscribeClick(event => {
      const day = typeof event.time === 'string' ? event.time : event.time?.year ?
        `${event.time.year}-${String(event.time.month).padStart(2, '0')}-${String(event.time.day).padStart(2, '0')}` : null;
      if (day && packet?.context_by_date[day]) {
        lockedDate = lockedDate === day ? null : day;
        previewDate = day; renderContext(day);
        $('cmp-context').hidden = false;
      }
    });
    $('cmp-chart').addEventListener('mouseleave', () => {
      if (!lockedDate) { previewDate = null; $('cmp-context').hidden = true; }
    });
    chart.timeScale().subscribeVisibleTimeRangeChange(() => renderBand());
    new ResizeObserver(() => { chart.applyOptions({width: $('cmp-chart').clientWidth, height: $('cmp-chart').clientHeight}); renderBand(); }).observe($('cmp-chart'));
  }
  function chartPointCoordinate(dayTime) {
    if (!packet || !chart) return null;
    const points = packet.series[0].points;
    if (!points.length) return null;
    const instant = Date.parse(dayTime);
    const first = Date.parse(`${points[0].date}T00:00:00Z`), last = Date.parse(`${points.at(-1).date}T00:00:00Z`);
    if (instant <= first) return chart.timeScale().timeToCoordinate(points[0].date);
    if (instant >= last) return chart.timeScale().timeToCoordinate(points.at(-1).date);
    let low = 0, high = points.length - 1;
    while (high - low > 1) {
      const mid = (low + high) >> 1;
      if (Date.parse(`${points[mid].date}T00:00:00Z`) <= instant) low = mid;
      else high = mid;
    }
    const a = chart.timeScale().timeToCoordinate(points[low].date);
    const b = chart.timeScale().timeToCoordinate(points[high].date);
    const left = Date.parse(`${points[low].date}T00:00:00Z`);
    const right = Date.parse(`${points[high].date}T00:00:00Z`);
    return a == null || b == null ? null : a + (b - a) * (instant - left) / (right - left);
  }
  async function renderBand() {
    const renderId = ++bandRenderId;
    const band = $('cmp-transit-band'); band.replaceChildren();
    const quarterBand = $('cmp-quarter-band'); quarterBand.replaceChildren();
    const markers = $('cmp-quarter-markers'); markers.replaceChildren();
    band.hidden = quarterBand.hidden = !selected.get('HD_TRANSIT');
    if (band.hidden || !packet?.series[0]?.points.length || !chart) return;
    const token = generation;
    const first = packet.series[0].points[0].date, last = packet.series[0].points.at(-1).date;
    try {
      const years = Array.from({length: Number(last.slice(0, 4)) - Number(first.slice(0, 4)) + 1},
        (_, index) => Number(first.slice(0, 4)) + index);
      const calendars = await Promise.all(years.map(year => {
        if (!calendarCache.has(year)) calendarCache.set(year,
          fetchJson(`/api/comparison/calendar?year=${year}`).catch(error => { calendarCache.delete(year); throw error; }));
        return calendarCache.get(year);
      }));
      if (generation !== token || renderId !== bandRenderId || !selected.get('HD_TRANSIT')) return;
      const isKrx = catalog.get(packet.base)?.metadata?.market === 'KRX';
      const localTime = segment => isKrx ? segment.start_kst : segment.start_ny;
      const localEnd = segment => isKrx ? segment.end_kst : segment.end_ny;
      const coordinate = stamp => chartPointCoordinate(`${stamp.slice(0, 10)}T${stamp.slice(11, 19)}Z`);
      const gates = calendars.flatMap(item => item.gates);
      const lines = calendars.flatMap(item => item.lines);
      const quarterRuns = [];
      for (const [index, gate] of gates.entries()) {
        const from = isKrx ? gate.start_kst : gate.start_ny;
        const to = isKrx ? gate.end_kst : gate.end_ny;
        const start = coordinate(from), end = coordinate(to);
        if (start == null || end == null || end <= start) continue;
        const quarter = quarters.get(quarterByGate.get(gate.gate));
        const prior = quarterRuns.at(-1);
        if (prior?.quarter.id === quarter.id && Math.abs(prior.end - start) < 2) prior.end = end;
        else quarterRuns.push({quarter, start, end});
        if (index && gates[index - 1].gate !== gate.gate && from.slice(0, 10) >= first && from.slice(0, 10) <= last &&
            gate.gate === quarter.start_gate) {
          const marker = document.createElement('span');
          marker.className = 'start';
          marker.style.left = `${start}px`;
          marker.title = `${quarter.name_ko} · ${marker.className === 'start' ? '시작' : '전환'} 관문 ${gate.gate}`;
          markers.append(marker);
        }
        if (gate.gate === quarter.turning_gate && from.slice(0, 10) >= first && from.slice(0, 10) <= last) {
          const marker = document.createElement('span');
          marker.className = 'turning';
          marker.style.left = `${Math.max(0, start)}px`;
          const label = document.createElement('em');
          label.textContent = `${gate.gate} · 전환`;
          label.className = start > $('cmp-chart').clientWidth - 120 ? 'align-end' : '';
          marker.append(label);
          marker.title = `${quarter.name_ko} · 전환 관문 ${gate.gate} 시작`;
          markers.append(marker);
        }
        const draw = (part, label) => {
          const left = coordinate(localTime(part)), right = coordinate(localEnd(part));
          if (left == null || right == null || right <= left) return;
          const tile = document.createElement('button'); tile.type = 'button';
          tile.style.left = `${Math.max(0, left)}px`;
          tile.style.width = `${Math.max(1, right - Math.max(0, left))}px`;
          tile.style.background = quarter.color;
          tile.textContent = right - Math.max(0, left) >= (part.line ? 30 : 24) ? label : '';
          tile.setAttribute('aria-label', `트랜짓 관문 ${label}`);
          tile.title = `관문 ${label} · ${quarter.name_ko} (${quarter.name})\n${localTime(part).slice(0, 16)} – ${localEnd(part).slice(0, 16)}`;
          tile.dataset.start = localTime(part).slice(0, 10);
          tile.dataset.end = localEnd(part).slice(0, 10);
          tile.addEventListener('click', () => {
            const date = packet.series[0].points.find(point => point.date >= tile.dataset.start && point.date <= tile.dataset.end)?.date;
            if (date) { lockedDate = date; renderContext(date); $('cmp-context').hidden = false; }
          });
          band.append(tile);
        };
        if (end - start >= 180) {
          lines.filter(line => line.gate === gate.gate && line.start_utc >= gate.start_utc && line.start_utc < gate.end_utc)
            .forEach(line => draw(line, `${gate.gate}.${line.line}`));
        } else draw(gate, String(gate.gate));
      }
      for (const run of quarterRuns) {
        const tile = document.createElement('span');
        tile.style.left = `${Math.max(0, run.start)}px`;
        tile.style.width = `${Math.max(1, run.end - Math.max(0, run.start))}px`;
        tile.style.background = run.quarter.color;
        tile.textContent = run.end - Math.max(0, run.start) >= 72 ? run.quarter.name_ko : '';
        tile.title = `${run.quarter.name_ko} (${run.quarter.name}) · ${run.quarter.theme_ko}`;
        quarterBand.append(tile);
      }
      renderContext(lockedDate || previewDate || packet.series[0].points.at(-1).date);
    } catch (error) { text('cmp-chart-note', `Transit Band를 표시하지 못했습니다: ${error.message}`); }
  }
  function renderChart() {
    initChart(); if (!chart || !packet) return;
    resetChart();
    const lib = window.LightweightCharts;
    let actualComparators = 0;
    packet.series.forEach((item, index) => {
      if (!item.points.length) return;
      if (index && !selected.get(item.layer_id)) return;
      const actual = packet.display === 'ACTUAL';
      const scale = actual && index ? (actualComparators++ === 0 ? 'left' : `unit-${item.layer_id}`) : 'right';
      const series = chart.addSeries(lib.LineSeries, {color: colors[index % colors.length], lineWidth: index ? 2 : 3,
        title: catalog.get(item.layer_id)?.display_name || item.layer_id,
        priceScaleId: scale}, 0);
      series.setData(item.points.map(point => ({time: point.date, value: point.display_value})));
      chartSeries.push(series);
    });
    chart.priceScale('left').applyOptions({visible: actualComparators > 0});
    chart.timeScale().fitContent();
    text('cmp-chart-note', `${packet.series[0].points.length}개 기준 자산 관측 · 금융상품은 한 Plot, 실제값은 각각 원단위, 상대 변화는 선택기간 첫 관측=100 · 환율 환산·결측 보간 없음`);
    renderBand();
  }
  async function run() {
    const token = ++generation;
    const base = $('cmp-base').value, start = $('cmp-start').value, end = $('cmp-end').value;
    if (!base || !start || !end) return;
    if (start > end) { text('cmp-status', '시작일이 종료일보다 늦습니다.'); return; }
    const ids = Array.from(selected.keys());
    text('cmp-status', '같은 날짜의 관측값과 맥락을 불러오는 중…');
    try {
      const payload = await fetchJson(`/api/comparison/series?${params({base, start, end,
        layers: ids.join(','), display: $('cmp-display').value})}`);
      if (generation !== token) return;
      packet = payload; lockedDate = previewDate = null;
      $('cmp-context').hidden = true;
      renderChart();
      renderContext(packet.series[0].points.at(-1).date);
      const lastObserved = packet.series[0].points.at(-1).date;
      text('cmp-status', `${base} · 실제 관측 ${packet.series[0].points[0].date} ~ ${lastObserved} (${packet.series[0].points.length}일)`);
      text('cmp-provenance', `기준 시세: ${payload.provenance.base.provider || '로컬 원천'} · 보정: ${payload.provenance.base.adjustment || '미확인'} · 다운로드: ${payload.provenance.base.retrieved_at || '메타데이터 없음'} · 동일 날짜만 비교, 결측 보간 없음. Transit은 USNO 근사 계산이며 시장 인과관계 미검증.`);
      const dataStatus = $('cmp-data-status');
      if (dataStatus) dataStatus.textContent = [...catalog.values()]
        .filter(item => item.availability === 'NOT_CONNECTED')
        .map(item => item.display_name).join(' · ') || '미연결 항목 없음';
    } catch (error) { text('cmp-status', `비교 실행 실패: ${error.message}`); }
  }
  async function init() {
    try {
      const response = await fetchJson('/api/comparison/catalog');
      catalog = new Map(response.layers.map(item => [item.layer_id, item]));
      quarters = new Map(response.quarters.map(item => [item.id, item]));
      quarterByGate = new Map(Object.entries(response.gate_to_quarter).map(([gate, id]) => [Number(gate), id]));
      const base = $('cmp-base');
      for (const item of response.layers.filter(row => ['ASSET', 'INDEX'].includes(row.layer_type) && row.availability !== 'NOT_CONNECTED')) {
        const option = document.createElement('option'); option.value = item.layer_id;
        option.textContent = item.display_name; base.append(option);
      }
      base.value = '005930';
      const today = kstToday(); $('cmp-end').value = today; $('cmp-start').value = `${today.slice(0, 4)}-01-01`;
      for (let year = 2020; year <= Number(today.slice(0, 4)); year++) {
        const option = document.createElement('option'); option.value = year;
        option.textContent = year; $('cmp-year').append(option);
      }
      $('cmp-year').value = today.slice(0, 4);
      base.addEventListener('change', () => { selected.delete(base.value); renderLayers(); renderPicker(); run(); });
      $('cmp-year').addEventListener('change', () => {
        const year = $('cmp-year').value;
        $('cmp-start').value = `${year}-01-01`;
        $('cmp-end').value = year === today.slice(0, 4) ? today : `${year}-12-31`;
        run();
      });
      $('cmp-run').addEventListener('click', run);
      $('cmp-display').addEventListener('change', run);
      document.querySelectorAll('[data-cmp-range]').forEach(button =>
        button.addEventListener('click', () => applyShortcut(button.dataset.cmpRange)));
      for (const id of ['cmp-start', 'cmp-end']) $(id).addEventListener('change', () => {
        $('cmp-year').value = '';
        document.querySelectorAll('[data-cmp-range]').forEach(button => button.classList.remove('active'));
      });
      window.addEventListener('zml:investment-period', event => {
        const period = event.detail;
        if (Array.isArray(period) && period.length === 2 && period.every(day => /^\d{4}-\d{2}-\d{2}$/.test(day))) {
          investmentPeriod = period;
          text('cmp-range-note', `마지막 투자조건 ${period[0]} ~ ${period[1]} · SIM 선택 가능`);
        }
      });
      document.addEventListener('keydown', event => {
        if (event.key === 'Escape') {
          $('cmp-picker').hidden = true;
          $('cmp-add').setAttribute('aria-expanded', 'false');
          lockedDate = previewDate = null;
          $('cmp-context').hidden = true;
        }
      });
      document.addEventListener('pointerdown', event => {
        if (!event.target.closest('.comparison-add-wrap')) {
          $('cmp-picker').hidden = true;
          $('cmp-add').setAttribute('aria-expanded', 'false');
        }
      });
      $('cmp-search').addEventListener('input', renderPicker);
      $('cmp-add').addEventListener('click', () => {
        $('cmp-picker').hidden = !$('cmp-picker').hidden;
        $('cmp-add').setAttribute('aria-expanded', String(!$('cmp-picker').hidden));
        renderPicker();
      });
      $('cmp-unlock').addEventListener('click', event => {
        event.stopPropagation(); lockedDate = previewDate = null; $('cmp-context').hidden = true;
      });
      renderLayers(); renderPicker(); await run();
    } catch (error) { text('cmp-status', `Research Workspace 초기화 실패: ${error.message}`); }
  }
  init();
})();
