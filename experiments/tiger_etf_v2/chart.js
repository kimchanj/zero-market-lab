(() => {
  const started = performance.now();
  const data = window.TIGER_V2_DATA;
  let simulation = window.TIGER_SIMULATION_DATA;
  const statusLabels = {WAITING_ENTRY:"매수 대기", ENTRY_FILLED:"매수 완료", WAITING_TAKE_PROFIT:"익절 대기", EXIT_FILLED:"익절 완료", HOLDING:"보유 중", WAITING_REENTRY:"재매수 대기", AMBIGUOUS:"당일 순서 불확실", NO_ACTION:"대기"};
  const actionLabels = {BUY:"매수",SELL:"매도",HOLD:"보유",NONE:"대기"};
  if (!data || !data.candles?.length) {
    document.getElementById('loading').textContent = '검증된 OHLCV payload가 없습니다.';
    return;
  }

  const { CandlestickSeries, ColorType, CrosshairMode, HistogramSeries, LineSeries, LineStyle, createChart, createSeriesMarkers } = window.LightweightCharts;
  const chart = createChart(document.getElementById('chart'), {
    autoSize: true,
    layout: {
      background: { type: ColorType.Solid, color: '#0a1422' }, textColor: '#8297ad',
      fontFamily: 'Inter, Noto Sans KR, Segoe UI, sans-serif', fontSize: 11,
      panes: { enableResize: true, separatorColor: '#1a3046', separatorHoverColor: '#3c668f' },
    },
    grid: { vertLines: { color: '#112237' }, horzLines: { color: '#112237' } },
    crosshair: {
      mode: CrosshairMode.Normal,
      vertLine: { color: '#668099', width: 1, style: LineStyle.Dashed, labelVisible: true },
      horzLine: { color: '#668099', width: 1, style: LineStyle.Dashed, labelVisible: true },
    },
    rightPriceScale: { borderColor: '#253b51', autoScale: true, scaleMargins: { top: 0.08, bottom: 0.08 } },
    timeScale: { borderColor: '#253b51', timeVisible: false, rightOffset: 3, barSpacing: 6, minBarSpacing: 0.4 },
    handleScroll: { mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: false },
    handleScale: { axisPressedMouseMove: true, mouseWheel: true, pinch: true },
  });

  const candles = chart.addSeries(CandlestickSeries, {
    title: '360750', upColor: '#26a69a', downColor: '#ef5350',
    wickUpColor: '#26a69a', wickDownColor: '#ef5350', borderVisible: false,
    priceFormat: { type: 'price', precision: 0, minMove: 5 },
  }, 0);
  const volume = chart.addSeries(HistogramSeries, {
    title: '거래량', priceFormat: { type: 'volume' }, priceLineVisible: false,
    lastValueVisible: false, base: 0,
  }, 1);
  candles.setData(data.candles);
  volume.setData(data.volume);

  let averageCost = null;
  let takeProfit = null;
  let markerApi = null;
  const markerById = new Map();
  if (simulation) {
    averageCost = chart.addSeries(LineSeries, {
      title: '평균매입가', color: '#62a5ff', lineWidth: 1,
      lineStyle: LineStyle.Dashed, priceLineVisible: false, lastValueVisible: false,
    }, 0);
    takeProfit = chart.addSeries(LineSeries, {
      title: '+5% 익절선', color: '#f0b84b', lineWidth: 1,
      lineStyle: LineStyle.Dotted, priceLineVisible: false, lastValueVisible: false,
    }, 0);
    averageCost.setData(simulation.chart.averageCost);
    takeProfit.setData(simulation.chart.takeProfit);
    const markerData = simulation.chart.markers.map((marker, index) => {
      const id = `${marker.action}-${marker.tradeId}-${index}`;
      markerById.set(id, marker);
      return {
        id, time: marker.time,
        position: marker.action === 'BUY' ? 'belowBar' : 'aboveBar',
        color: marker.action === 'BUY' ? '#4c9cff' : '#f0b84b',
        shape: marker.action === 'BUY' ? 'arrowUp' : 'arrowDown',
        text: marker.action === 'BUY' ? '매수' : '익절',
      };
    });
    markerApi = createSeriesMarkers(candles, markerData);
  }

  const panes = chart.panes();
  if (panes.length >= 2) { panes[0].setStretchFactor(4); panes[1].setStretchFactor(1); }
  document.getElementById('loading').style.display = 'none';

  const byTime = new Map(data.candles.map((bar, index) => [bar.time, { ...bar, volume: data.volume[index].value }]));
  const ledgerByTime = new Map((simulation?.ledger || []).map(row => [row.date, row]));
  const number = value => value == null
    ? '—'
    : Number(value).toLocaleString('ko-KR', { maximumFractionDigits: 2 });
  const decisionValue = value => value == null || value === ''
    ? '—'
    : Number.isFinite(Number(value)) ? number(value) : String(value);
  const weekday = new Intl.DateTimeFormat('ko-KR', { dateStyle: 'full', timeZone: 'Asia/Seoul' });
  let shownHoverDate = null;
  function showStrategyHover(date, state) {
    if (date === shownHoverDate) return;
    shownHoverDate = date;
    const isFinalOpen = state?.date === simulation?.scope.actual_period[1] && Number(state.position_qty_after) > 0;
    const hover = window.ZML_HOVER.model(state, isFinalOpen);
    const panel = document.getElementById('strategy-hover');
    panel.dataset.kind = hover.kind;
    document.getElementById('hover-date').textContent = date;
    document.getElementById('hover-title').textContent = hover.title;
    document.getElementById('strategy-state').textContent = hover.title;
    const lines = document.getElementById('hover-lines');
    lines.replaceChildren(...hover.items.map(([label, value]) => {
      const item = document.createElement('span'); item.className = 'strategy-hover-item';
      const caption = document.createElement('small'), content = document.createElement('b');
      caption.textContent = label; content.textContent = value; item.append(caption, content);
      return item;
    }));
  }
  function showQuote(bar) {
    if (!bar) return;
    document.getElementById('quote-date').textContent = weekday.format(new Date(`${bar.time}T00:00:00+09:00`));
    ['open', 'high', 'low', 'close'].forEach(key => {
      document.getElementById(`quote-${key}`).textContent = `${number(bar[key])}원`;
    });
    const change = bar.changePercent;
    const changeElement = document.getElementById('quote-change');
    changeElement.textContent = change == null ? '등락률 —' : `등락률 ${change >= 0 ? '+' : ''}${change.toFixed(2)}%`;
    changeElement.style.color = change == null ? '#8ea3ba' : change >= 0 ? '#26a69a' : '#ef5350';
    document.getElementById('quote-volume').textContent = number(bar.volume);
    const state = ledgerByTime.get(bar.time);
    showStrategyHover(bar.time, state);
  }
  const initialTime = simulation?.scope.actual_period[1] || data.period[1];
  showQuote(byTime.get(initialTime));
  chart.subscribeCrosshairMove(param => {
    const hoveredMarker = markerById.get(param.hoveredObjectId);
    const date = window.ZML_HOVER.marketDate(param.time) || hoveredMarker?.time;
    if (date) showQuote(byTime.get(date));
  });

  chart.subscribeClick(param => {
    const marker = markerById.get(param.hoveredObjectId);
    if (!marker) return;
    const element = document.getElementById('marker-detail');
    element.hidden = false;
    element.textContent = `${marker.time} · ${marker.action === 'BUY' ? '매수' : '익절 매도'} ${number(marker.quantity)}주 @ ${number(marker.price)}원 · 비용 ${number(marker.fee)}원 · 잔여현금 ${number(marker.cashAfter)}원 · Gross ${number(marker.grossProfit)}원 · 세금 ${number(marker.tax)}원 · Net ${number(marker.netProfit)}원 (${number(marker.netReturn == null ? null : marker.netReturn * 100)}%) · ${marker.holdingDays}거래일 · ${marker.explanation}`;
    document.getElementById(`ledger-${marker.time}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  });

  const series = { candles, volume, averageCost, takeProfit };
  document.querySelectorAll('.layers input').forEach(input => {
    input.addEventListener('change', () => {
      if (input.value === 'markers') {
        markerApi?.setMarkers(input.checked ? [...markerById.entries()].map(([id, marker]) => ({
          id, time: marker.time, position: marker.action === 'BUY' ? 'belowBar' : 'aboveBar',
          color: marker.action === 'BUY' ? '#4c9cff' : '#f0b84b',
          shape: marker.action === 'BUY' ? 'arrowUp' : 'arrowDown',
          text: marker.action === 'BUY' ? '매수' : '익절',
        })) : []);
      } else series[input.value]?.applyOptions({ visible: input.checked });
    });
  });

  const last = new Date(`${data.period[1]}T00:00:00Z`);
  function rangeStart(range) {
    const from = new Date(last);
    if (range === '1M') from.setUTCMonth(from.getUTCMonth() - 1);
    if (range === '3M') from.setUTCMonth(from.getUTCMonth() - 3);
    if (range === '6M') from.setUTCMonth(from.getUTCMonth() - 6);
    if (range === '1Y') from.setUTCFullYear(from.getUTCFullYear() - 1);
    if (range === '3Y') from.setUTCFullYear(from.getUTCFullYear() - 3);
    return from.toISOString().slice(0, 10);
  }
  document.querySelectorAll('[data-range]').forEach(button => {
    button.addEventListener('click', () => {
      document.querySelectorAll('[data-range]').forEach(item => item.classList.remove('active'));
      button.classList.add('active');
      const range = button.dataset.range;
      if (range === 'SIM' && simulation) chart.timeScale().setVisibleRange({ from: simulation.scope.actual_period[0], to: simulation.scope.actual_period[1] });
      else if (range === 'ALL') chart.timeScale().fitContent();
      else chart.timeScale().setVisibleRange({ from: rangeStart(range), to: data.period[1] });
    });
  });

  if (simulation) chart.timeScale().setVisibleRange({ from: simulation.scope.actual_period[0], to: simulation.scope.actual_period[1] });
  else chart.timeScale().fitContent();

  function signed(value, percent = false) {
    const numeric = Number(value);
    return `${numeric >= 0 ? '+' : ''}${number(percent ? numeric * 100 : numeric)}${percent ? '%' : '원'}`;
  }
  function renderSimulation() {
    if (!simulation) return;
    const summary=simulation.summary;
    document.getElementById('simulation-period').textContent=`${summary.start_date} ~ ${summary.end_date} · ${simulation.ledger.length}거래일`;
    document.getElementById('fee-assumption').textContent=simulation.scope.fee_disclaimer;
    const metrics=[['초기 투자금',`${number(summary.initial_capital)}원`],['최종 자산',`${number(summary.final_portfolio_value)}원`],
      ['순수익',signed(summary.net_profit),summary.net_profit>=0],['순수익률',signed(summary.net_return,true),summary.net_return>=0],
      ['완료 거래수',`${summary.completed_trades}건`],['평균 보유기간',summary.average_holding_days==null?'완료 거래 없음':`${number(summary.average_holding_days)}거래일`]];
    document.getElementById('summary-cards').innerHTML=metrics.map(([label,value,positive])=>`<div class="metric"><span>${label}</span><strong class="${positive===undefined?'':positive?'positive':'negative'}">${value}</strong></div>`).join('');
    document.getElementById('secondary-summary').textContent=`총 거래비용 ${number(summary.total_trading_cost)}원 · 최대 낙폭 ${number(summary.mdd*100)}% · 미청산 ${summary.open_trades}건 · 순수익에 미실현손익 포함`;
    const open=simulation.open_position;
    document.getElementById('open-position').textContent=open
      ? `보유 중 ${number(open.entry_qty)}주 · 매수가 ${number(open.entry_price)}원 · 현재 ${number(open.current_close)}원 · 미실현 ${signed(open.net_profit)} · 익절까지 ${number(open.target_gap)}원 · ${open.trading_holding_days}거래일`
      : '기간 종료 시 보유 중인 포지션이 없습니다.';
    document.querySelector('#trade-table tbody').innerHTML=simulation.trades.map(trade=>
      `<tr><td>${trade.entry_date}<br>${number(trade.entry_price)}원</td><td>${trade.exit_date||'보유 중'}<br>${number(trade.exit_price)}${trade.exit_price==null?'':'원'}</td><td>${number(trade.entry_qty)}</td><td>${signed(trade.net_profit)}</td><td>${signed(trade.net_return,true)}</td><td>${trade.trading_holding_days}거래일 / ${trade.calendar_holding_days}일</td><td>${trade.minimum_net_met===true?'충족':trade.minimum_net_met===false?'미충족':'청산 전'}<br>필요 매도가 ${number(trade.required_exit_price)}원</td></tr>`).join('');
    document.querySelector('#ledger-table tbody').innerHTML=simulation.ledger.map(row=>{
      const actionClass=row.action==='BUY'?'status-buy':row.action==='SELL'?'status-sell':'status-hold';
      const details=row.decisions.map(d=>`<div class="decision">${d.rule_name} · 관측 ${decisionValue(d.observed_value)} · 기준 ${decisionValue(d.rule_value)} · ${d.comparison} → ${d.reason_code}</div>`).join('');
      const brief=row.brief||(row.action==='BUY'?`${number(row.execution_price)}원 매수`:row.action==='SELL'?`${number(row.execution_price)}원 익절`:row.action==='HOLD'?`보유 ${row.trading_holding_days}일차`:'매수가 미도달');
      return `<tr id="ledger-${row.date}"><td>${row.date}</td><td>시 ${number(row.open)} · 고 ${number(row.high)}<br>저 ${number(row.low)} · 종 ${number(row.close)}</td><td class="${actionClass}">${row.status_label||statusLabels[row.status]}</td><td class="${actionClass}">${row.action_label||actionLabels[row.action]}</td><td>${number(row.execution_price)}${row.execution_price==null?'':'원'}</td><td>${number(row.position_qty_after)}주</td><td>${number(row.cash_after)}원</td><td>${number(row.portfolio_value)}원</td><td>${number(row.take_profit_price)}${row.take_profit_price==null?'':'원'}</td><td>${row.trading_holding_days}거래일</td><td><div class="brief">${brief}</div><details><summary>상세보기</summary><div class="detail-grid"><span>시가 / 고가 / 저가 / 종가 <b>${number(row.open)} / ${number(row.high)} / ${number(row.low)} / ${number(row.close)}원</b></span><span>매수가 / 평균매입가 <b>${number(row.execution_price)} / ${number(row.avg_entry_price_after)}원</b></span><span>수량 / 보유기간 <b>${number(row.position_qty_after)}주 / ${row.trading_holding_days}거래일 (${row.calendar_holding_days}일)</b></span><span>Entry Limit / Take Profit <b>${number(row.entry_order_price)} / ${number(row.take_profit_price)}원</b></span><span>최소 순수익 필요 매도가 <b>${number(row.required_exit_price)}원</b></span><span>오늘 고가와 목표 차이 <b>${number(row.high_target_gap)}원</b></span><span>현금 / 평가액 <b>${number(row.cash_after)} / ${number(row.position_value)}원</b></span><span>실현 / 미실현손익 <b>${signed(row.net_profit)} / ${signed(row.unrealized_profit)}</b></span><span>오늘 비용 / 누적 비용 <b>${number(row.total_cost)} / ${number(row.cumulative_cost)}원</b></span><span>매수수수료 / 매도수수료 / 세금 <b>${number(row.buy_fee)} / ${number(row.sell_fee)} / ${number(row.tax)}원</b></span></div><p>${row.explanation}</p><button data-news-date="${row.date}">관련 뉴스 보기</button><details class="raw-detail"><summary>개발자용 판단 기록</summary><p>${row.trade_id||'거래 없음'} · ${row.decision_code}</p>${details}</details></details></td></tr>`;
    }).join('');
    document.querySelectorAll('[data-news-date]').forEach(button=>button.addEventListener('click',()=>window.dispatchEvent(new CustomEvent('zml:research-day',{detail:{date:button.dataset.newsDate}}))));
  }
  function updateResult(payload) {
    simulation=payload;
    window.TIGER_SIMULATION_DATA=payload;
    shownHoverDate=null;
    $('technical-run').textContent=`실행 ID ${payload.run_id} · 요청 기간 ${payload.scope.requested_period.join(' ~ ')} · 실제 관측 ${payload.scope.actual_period.join(' ~ ')} · ${payload.provenance?.source || 'TIGER OHLCV'}`;
    ledgerByTime.clear(); payload.ledger.forEach(row=>ledgerByTime.set(row.date,row));
    markerById.clear();
    const markers=payload.chart.markers.map((marker,index)=>{
      const id=`${marker.action}-${index}`; markerById.set(id,marker);
      return {id,time:marker.time,position:marker.action==='BUY'?'belowBar':'aboveBar',color:marker.action==='BUY'?'#4c9cff':'#f0b84b',shape:marker.action==='BUY'?'arrowUp':'arrowDown',text:marker.action==='BUY'?'매수':'익절'};
    });
    averageCost.setData(payload.chart.averageCost); takeProfit.setData(payload.chart.takeProfit);
    takeProfit.applyOptions({title:`+${number(payload.strategy.take_profit_rate*100)}% 익절선`});
    markerApi.setMarkers(document.querySelector('input[value="markers"]').checked?markers:[]);
    document.getElementById('marker-detail').hidden=true;
    renderSimulation();
    chart.timeScale().setVisibleRange({from:payload.scope.actual_period[0],to:payload.scope.actual_period[1]});
    document.querySelectorAll('[data-range]').forEach(button=>button.classList.toggle('active',button.dataset.range==='SIM'));
    showQuote(byTime.get(payload.scope.actual_period[1]));
    window.dispatchEvent(new CustomEvent('zml:simulation-updated',{detail:payload}));
  }
  renderSimulation();
  const dateText=value=>typeof value==='string'?value:`${value.year}-${String(value.month).padStart(2,'0')}-${String(value.day).padStart(2,'0')}`;
  function rememberResearchRange(range) { if(range) window.ZML_RESEARCH_RANGE={start:dateText(range.from),end:dateText(range.to)}; }
  chart.timeScale().subscribeVisibleTimeRangeChange(rememberResearchRange);
  rememberResearchRange(chart.timeScale().getVisibleRange());

  const $=id=>document.getElementById(id);
  let inputRevision=0, requestId=0;
  const todaySeoul=()=>{
    const parts=Object.fromEntries(new Intl.DateTimeFormat('en-US',{
      timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit',
    }).formatToParts(new Date()).filter(part=>part.type!=='literal').map(part=>[part.type,part.value]));
    return `${parts.year}-${parts.month}-${parts.day}`;
  };
  const monthsBefore=(iso,months)=>{
    const [year,month,day]=iso.split('-').map(Number);
    const target=new Date(Date.UTC(year,month-1-months,1));
    const lastDay=new Date(Date.UTC(target.getUTCFullYear(),target.getUTCMonth()+1,0)).getUTCDate();
    target.setUTCDate(Math.min(day,lastDay));
    return target.toISOString().slice(0,10);
  };
  const initialToday=todaySeoul();
  $('invest-start').value=`${initialToday.slice(0,4)}-01-01`;
  $('invest-end').value=initialToday;
  const inputIds=['invest-start','invest-end','invest-capital','invest-entry','invest-tp','invest-minimum'];
  const dirty=()=>{inputRevision++; $('run-status').textContent='입력이 변경됐습니다. 아래는 이전 실행 결과입니다. 시뮬레이션을 실행하세요.';};
  inputIds.forEach(id=>$(id).addEventListener('input',()=>{
    dirty();
    if(id==='invest-start'||id==='invest-end') {
      document.querySelectorAll('[data-invest-months]').forEach(b=>b.classList.remove('active'));
      $('custom-period').classList.add('active');
    }
  }));
  document.querySelectorAll('[data-invest-months]').forEach(button=>button.addEventListener('click',()=>{
    const today=todaySeoul();
    $('invest-start').value=monthsBefore(today,Number(button.dataset.investMonths));
    $('invest-end').value=today;
    document.querySelectorAll('[data-invest-months]').forEach(b=>b.classList.toggle('active',b===button));
    $('custom-period').classList.remove('active'); dirty();
  }));
  $('custom-period').addEventListener('click',()=>{
    document.querySelectorAll('[data-invest-months]').forEach(b=>b.classList.remove('active'));
    $('custom-period').classList.add('active'); $('invest-end').focus();
  });
  $('all-invest-period').addEventListener('click',()=>{
    $('invest-start').value=data.period[0]; $('invest-end').value=todaySeoul();
    document.querySelectorAll('[data-invest-months]').forEach(b=>b.classList.remove('active'));
    $('custom-period').classList.remove('active'); $('all-invest-period').classList.add('active'); dirty();
  });
  async function runSimulation() {
    const version=inputRevision, id=++requestId;
    const params={start:$('invest-start').value,end:$('invest-end').value,initial_capital:$('invest-capital').value,
      entry_percent:$('invest-entry').value,take_profit_percent:$('invest-tp').value,minimum_net_percent:$('invest-minimum').value};
    $('run-status').textContent='선택한 투자기간으로 계산 중…'; $('run-simulation').disabled=true;
    try {
      const request=await fetch('/api/simulate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(params)});
      if(request.status===404) throw new Error('재계산 API가 없습니다. scripts/run_research_ui.py로 실행한 8062 화면을 열어주세요.');
      const payload=await request.json().catch(()=>{throw new Error('서버 응답 형식을 읽을 수 없습니다. 이전 결과를 유지합니다.');});
      if(id!==requestId||version!==inputRevision) return;
      if(!request.ok) throw new Error(payload.error);
      updateResult(payload);
      $('run-status').textContent=`계산 완료 · 요청 ${params.start} ~ ${params.end} · 실제 관측 ${payload.scope.actual_period.join(' ~ ')} · ${payload.ledger.length}거래일`;
    } catch(error) { if(id===requestId&&version===inputRevision) $('run-status').textContent=`실행 실패: ${error.message} · 이전 결과를 유지합니다.`; }
    finally {if(id===requestId) $('run-simulation').disabled=false;}
  }
  $('simulation-form').addEventListener('submit',event=>{event.preventDefault();runSimulation();});
  runSimulation();
  document.getElementById('performance').textContent=`${data.candles.length.toLocaleString('ko-KR')} bars · 2 panes · setup ${(performance.now()-started).toFixed(1)} ms`;
})();
