(() => {
  const ids=['S0_BUY_AND_HOLD','S1_FIXED_TAKE_PROFIT','S1_TREND_FILTERED_TAKE_PROFIT','S2_FIXED_TP_SL','S2_TREND_FILTERED_TP_SL','S3_FIXED_TP_SL_TIME','S4_TREND_FILTERED_TP_SL_TIME','S5_ATR_ADAPTIVE_EXIT','S6A_PURE_MEAN_REVERSION','S6B_CONFIRMED_REVERSAL','S7_BREAKOUT_TREND_FOLLOWING'];
  const short=id=>id==='S1_TREND_FILTERED_TAKE_PROFIT'?'S1-TF':
    id==='S2_TREND_FILTERED_TP_SL'?'S2-TF':id.replace(/^S(\d)([AB])?_.*$/,'S$1$2');
  const $=id=>document.getElementById(id);
  const pct=v=>v==null?'—':`${(v*100).toFixed(2)}%`;
  const num=v=>v==null?'—':Number(v).toLocaleString('ko-KR',{maximumFractionDigits:2});
  const money=(v,currency,sign=false)=>v==null?'—':`${sign&&v>0?'+':''}${num(v)}${currency==='KRW'?'원':' USD'}`;
  const td=(row,value)=>{const c=row.insertCell();c.textContent=value;return c;};
  let report=null, yearlyReport=null, selectedSymbol=null, executedConfig=null, executedStrategy=null;
  const strategy=$('strategy');ids.forEach(id=>{const o=document.createElement('option');o.value=id;o.textContent=`${short(id)} · ${id.slice(id.indexOf('_')+1).replaceAll('_',' ')}`;strategy.append(o);});
  strategy.value='S1_FIXED_TAKE_PROFIT';
  function syncS1Panel(){ $('s1-panel').hidden=!['S1_FIXED_TAKE_PROFIT',
    'S1_TREND_FILTERED_TAKE_PROFIT'].includes(strategy.value);
    $('s2-panel').hidden=!['S2_FIXED_TP_SL','S2_TREND_FILTERED_TP_SL'].includes(strategy.value); }
  syncS1Panel();
  strategy.addEventListener('input',syncS1Panel);
  const condition=c=>['S1_FIXED_TAKE_PROFIT','S1_TREND_FILTERED_TAKE_PROFIT'].includes(c.strategy_id)?
    `진입 ${c.strategy_config?.entry_offset_pct??'-1'}% · TP ${c.strategy_config?.take_profit_pct??'5'}%`:
    ['S2_FIXED_TP_SL','S2_TREND_FILTERED_TP_SL'].includes(c.strategy_id)?
    `TP ${c.strategy_config?.take_profit_pct??'5'}% · SL ${c.strategy_config?.stop_loss_pct??'3'}%`:'기본값';
  $('asof').value=new Date().toLocaleDateString('sv-SE',{timeZone:'Asia/Seoul'});
  function currentRunConfig(){return {query:queryFromInputs().toString(),strategy:strategy.value,market:$('market').value};}
  function executedQuery(){return new URLSearchParams(executedConfig?.query||queryFromInputs().toString());}
  function markStale(){const stale=!!executedConfig&&JSON.stringify(currentRunConfig())!==JSON.stringify(executedConfig);
    $('stale-banner').hidden=!stale;
    for(const id of ['investment-results','asset-comparison','trade-records','period-panel','survival-panel','robustness-panel','year-panel','regime-panel'])
      $(id).classList.toggle('stale-results',stale);
    return stale;}
  function syncLiquidityFilter(){
    const market=$('market').value, all=market==='ALL';
    $('liquidity').disabled=all;
    $('liquidity').placeholder=all?'시장 선택 후 입력':'전체';
    $('liquidity-help').textContent=all?'KRW와 USD를 섞어 비교하지 않습니다. 한국 또는 미국을 선택하세요.':
      `유동성이 낮은 종목 제외 · ${market==='KRX'?'KRW':'USD'} 기준`;
  }
  syncLiquidityFilter();
  function sortedCandidates(){
    if(!report)return [];
    const selected=executedStrategy, sort=$('sort').value,market=executedConfig?.market||$('market').value;
    const minTrades=Number($('mintrades').value||0), mdd=$('mdd').value===''?null:Number($('mdd').value)/100;
    const pf=$('pf').value===''?null:Number($('pf').value),
      liq=market==='ALL'?0:Number($('liquidity').value||0);
    const rows=report.cells.filter(c=>c.status==='OK'&&c.strategy_id===selected&&
      (market==='ALL'||c.market===market)&&(!$('isa-only').checked||report.assets.find(a=>a.symbol===c.symbol)?.isa_eligible)).filter(c=>
      c.metrics.completed_trades>=minTrades&&(mdd==null||c.metrics.mdd>=mdd)&&
      (pf==null||(c.metrics.profit_factor!=null&&c.metrics.profit_factor>=pf))&&c.profile.average_trading_value>=liq);
    rows.sort((a,b)=>{const get=c=>['atr_pct','annual_volatility'].includes(sort)?c.profile[sort]:c.metrics[sort];
      const marketOrder=a.market.localeCompare(b.market);if(marketOrder)return marketOrder;
      const av=get(a),bv=get(b);if(av==null&&bv==null)return a.symbol.localeCompare(b.symbol);
      if(av==null)return 1;if(bv==null)return -1;
      return bv-av||a.symbol.localeCompare(b.symbol);});
    return rows;
  }
  function showMatrix(symbol){
    if(selectedSymbol!==symbol){$('period-matrix').replaceChildren();$('period-status').textContent='';
      $('robustness-summary').replaceChildren();$('filter-rolling-body').replaceChildren();$('robustness-status').textContent='';
      $('daily-ledger').replaceChildren();$('journal-status').textContent='';}
    selectedSymbol=symbol;
    $('asset').value=symbol;
    const asset=report.assets.find(a=>a.symbol===symbol), body=$('matrix');body.replaceChildren();
    $('matrix-title').textContent=`${asset.name} ${symbol} · ${asset.market} · ${asset.currency} 자산별 전략 매트릭스`;
    const profile=asset.profile,selected=report.cells.find(c=>c.symbol===symbol&&c.strategy_id===executedStrategy);
    let behavior=`최근 구간 연변동성 ${pct(profile.annual_volatility)}, ATR ${pct(profile.atr_pct)}.`;
    if(!selected?.metrics)behavior+=' 선택 전략 셀은 계산 오류로 제외됐습니다.';
    else if(executedStrategy==='S7_BREAKOUT_TREND_FOLLOWING')behavior+=` 20일 고가 돌파 ${profile.breakout_count}회, 5거래일 후 평가 가능한 ${profile.breakout_5d_evaluated}회 중 양수 비율 ${pct(profile.breakout_success_rate)}. S7 손실 청산 ${selected.metrics.whipsaw_count}회.`;
    else if(['S1_FIXED_TAKE_PROFIT','S1_TREND_FILTERED_TAKE_PROFIT'].includes(executedStrategy))behavior+=` ${short(executedStrategy)} 완료 거래 ${selected.metrics.completed_trades}건, 평균 보유 ${num(selected.metrics.average_holding_days)}거래일. 신규진입 차단 ${selected.metrics.blocked_entry_opportunity_count}건.`;
    else if(executedStrategy.startsWith('S6'))behavior+=` 3% 이상 하락 ${profile.drop_3pct_count}회, 이후 5거래일 양수 반등 비율 ${pct(profile.rebound_rate_5d)}.`;
    else behavior+=` 최대 낙폭 ${pct(selected.metrics.mdd)}, 완료 거래 ${selected.metrics.completed_trades}건.`;
    const buyHold=report.cells.find(c=>c.symbol===symbol&&c.strategy_id==='S0_BUY_AND_HOLD');
    if(buyHold?.metrics?.market_exposure_ratio===0)
      behavior+=` S0는 초기자금 ${num(buyHold.metrics.initial_capital)} ${asset.currency}로 첫 거래일 정수 1주를 매수하지 못해 현금만 보유했습니다.`;
    const s2=report.cells.find(c=>c.symbol===symbol&&c.strategy_id==='S2_FIXED_TP_SL');
    const s3=report.cells.find(c=>c.symbol===symbol&&c.strategy_id==='S3_FIXED_TP_SL_TIME');
    if(s2?.metrics&&s3?.metrics&&s3.metrics.time_stop_count===0&&
       s2.metrics.final_portfolio===s3.metrics.final_portfolio&&
       s2.metrics.completed_trades===s3.metrics.completed_trades)
      behavior+=' S3의 20거래일 시간 청산이 이 기간에는 발생하지 않아 S2와 결과가 동일합니다.';
    $('why').textContent=`가격행동 관찰: ${behavior} 선택 기간의 기술적 기록이며 전략 효과의 원인 또는 미래 적합성을 증명하지 않습니다.`;
    for(const c of report.cells.filter(c=>c.symbol===symbol)){
      const row=body.insertRow(),m=c.metrics;
      [short(c.strategy_id),condition(c),m?`${num(m.final_portfolio)} ${c.currency}`:c.status,
        pct(m?.net_return),pct(m?.gross_return_cost_addback),pct(m?.mdd),num(m?.profit_factor),
        m?.completed_trades??'—',pct(m?.win_rate),m?.average_holding_days==null?'—':`${num(m.average_holding_days)}일`,
        m?`${num(m.total_trading_cost)} ${c.currency}`:'—'].forEach(v=>td(row,v));
    }
    renderMoneyAndTrades(selected,asset);
  }
  function renderMoneyAndTrades(cell,asset){
    const m=cell?.metrics,currency=asset.currency;
    $('s1-risk-warning').hidden=!['S1_FIXED_TAKE_PROFIT','S1_TREND_FILTERED_TAKE_PROFIT'].includes(cell?.strategy_id);
    const s0=report.cells.find(c=>c.symbol===asset.symbol&&c.strategy_id==='S0_BUY_AND_HOLD');
    const benchmark=s0?.metrics?.final_portfolio;
    $('benchmark-note').textContent=m&&cell.strategy_id!=='S0_BUY_AND_HOLD'?
      `같은 기간 단순보유(S0) 최종자산 ${money(benchmark,currency)} · ${short(cell.strategy_id)} − S0 ${benchmark==null?'—':money(m.final_portfolio-benchmark,currency,true)}. 가격 데이터에는 배당이 반영되지 않아 S0 실제 총수익과 다를 수 있습니다.`:'';
    const open=cell?.open_position;
    $('open-risk-note').textContent=m?(open?
      `미청산 ${num(open.quantity)}주 · 진입가 ${money(open.entry_price,currency)} · 현재가 ${money(open.mark_close,currency)} · 익절 목표 ${money(open.target,currency)} · 현재 평가손익 ${money(open.unrealized_pnl,currency,true)} (${pct(open.unrealized_return)}) · 보유 중 종가 기준 최대 평가손실 ${money(open.worst_marked_pnl,currency,true)} (${pct(open.worst_marked_return)}) · 현재 ${open.holding_days}거래일 보유. 미래 매도비용은 미차감.`:
      '기간 종료 시 미청산 포지션 없음. 실현 거래 수익만으로 과거 위험을 판단하지 마세요.'):'';
    $('accounting-note').textContent=m?
      `현금 ${money(m.cash,currency)} + 보유주식 평가액 ${money(m.market_value,currency)} = 현재/최종 총자산 ${money(m.final_portfolio,currency)}. 실현손익과 미실현손익을 함께 확인하세요.`:'';
    $('cash-state-note').textContent=m&&['S1_TREND_FILTERED_TAKE_PROFIT','S2_TREND_FILTERED_TP_SL'].includes(cell.strategy_id)?
      `${open?'보유 중 · 필터 변화만으로 자동 청산하지 않음':
        m.cash<(asset.affordability?.required_cash_for_one_share??Infinity)?'현금 보유 · 현재 자금으로 1주 매수 불가':
        cell.last_entry_filter_allowed?'현금 보유 · 진입 허용 환경이지만 매수 조건 미충족':
        '의도적 현금 대기 · 장기 추세 필터 조건 미충족'} · 차단된 진입 기회 ${cell.blocked_entries.length}건. 사후 수익률은 실행 판단에 사용하지 않았습니다.`:'';
    const available=asset.affordability,blocked=(cell?.affordability_events||[]).find(e=>e.reason==='REENTRY_BLOCKED_BY_CAPITAL');
    $('affordability-note').textContent=available?
      `마지막 종가 ${money(available.current_price,currency)} (${available.price_date}) · 현재 새 시드 ${money(available.available_cash,currency)}로 ${available.max_affordable_qty}주 매수 가능${available.max_affordable_qty===0?' · 시드 부족 · 1주 매수 불가':''}. 1주 필요금액 ${money(available.required_cash_for_one_share,currency)}.${blocked?` ${blocked.event_date} 매수 조건 충족 시 가용현금 ${money(blocked.available_cash,currency)}으로 1주 필요금액 ${money(blocked.required_cash,currency)}을 충당하지 못해 재진입하지 못했습니다.`:''}`:'';
    const values={initial:money(m?.initial_capital,currency),final:money(m?.final_portfolio,currency),
      profit:money(m?.net_gain,currency,true),return:pct(m?.net_return),
      trades:m?`${m.completed_trades}회`:'—',realized:money(m?.realized_gain,currency,true),
      unrealized:money(m?.unrealized_gain,currency,true),mdd:pct(m?.mdd),
      'drawdown-money':money(m?.max_drawdown_amount,currency),
      cost:money(m?.total_trading_cost,currency),
      holding:m?.average_holding_days==null?'—':`${num(m.average_holding_days)} 거래일`,
      lock:m?`${Math.max(m.max_holding_days||0,cell?.open_position?.holding_days||0)} 거래일`:'—'};
    for(const [key,value] of Object.entries(values)){$(`summary-${key}`).textContent=value;
      $(`summary-${key}`).classList.toggle('positive',['profit','realized','unrealized','return'].includes(key)&&
        Number(key==='return'?m?.net_return:m?.[key==='profit'?'net_gain':key==='realized'?'realized_gain':'unrealized_gain'])>0);
      $(`summary-${key}`).classList.toggle('negative',['profit','realized','unrealized','return'].includes(key)&&
        Number(key==='return'?m?.net_return:m?.[key==='profit'?'net_gain':key==='realized'?'realized_gain':'unrealized_gain'])<0);}
    $('money-explanation').textContent=m?
      `${asset.name} ${asset.symbol} · ${short(cell.strategy_id)}: ${money(m.initial_capital,currency)}으로 시작해 완료 거래 ${m.completed_trades}회 후 최종자산은 ${money(m.final_portfolio,currency)}입니다. 순수익금 ${money(m.net_gain,currency,true)}, 거래비용 ${money(m.total_trading_cost,currency)}입니다. 미청산 손익은 최종자산에 포함됩니다.`:
      `${asset.name}의 선택 전략 결과를 계산할 수 없습니다.`;
    if(cell?.status==='NOT_AFFORDABLE')$('money-explanation').textContent+=
      ' 과거 평가기간에 매수 조건이 발생했지만 정수 1주를 살 자금이 없어 거래하지 못했습니다. 0%를 전략 성과로 해석하지 마세요.';
    const body=$('trade-body');body.replaceChildren();
    for(const trade of cell?.trades||[]){const row=body.insertRow();
      [trade.entry_date,trade.exit_date,num(trade.entry_price),num(trade.exit_price),
        num(trade.quantity),money(trade.net_profit,currency,true),`${trade.holding_days}일`,
        money(trade.cost,currency)].forEach(value=>td(row,value));}
    if(cell?.open_position){const item=cell.open_position,row=body.insertRow();
      [item.entry_date,'미청산 · 종가 평가',num(item.entry_price),num(item.mark_close),
        num(item.quantity),money(item.unrealized_pnl,currency,true),`${item.holding_days}일`,'미래 매도비용 미차감'].forEach(value=>td(row,value));}
    if(!body.rows.length){const row=body.insertRow(),message=td(row,'완료 거래와 미청산 포지션이 없습니다.');message.colSpan=8;}
  }
  function renderComparison(){
    const body=$('asset-comparison-body');body.replaceChildren();
    const market=executedConfig?.market||$('market').value;
    for(const asset of report.assets.filter(a=>(market==='ALL'||a.market===market)&&
      (!$('isa-only').checked||a.isa_eligible))){
      const cell=report.cells.find(c=>c.symbol===asset.symbol&&c.strategy_id===executedStrategy);
      const s0=report.cells.find(c=>c.symbol===asset.symbol&&c.strategy_id==='S0_BUY_AND_HOLD');
      const m=cell?.metrics,currency=asset.currency,a=asset.affordability,row=body.insertRow();
      row.dataset.symbol=asset.symbol;
      [asset.name+' '+asset.symbol,asset.isa_eligible?'ISA 가능':'연구용 · ISA 직접매수 불가',
        money(a?.current_price,currency),a?`${a.max_affordable_qty}주`:'—',
        money(m?.final_portfolio,currency),money(m?.net_gain,currency,true),pct(m?.net_return),
        money(s0?.metrics?.final_portfolio,currency),
        m&&s0?.metrics?money(m.final_portfolio-s0.metrics.final_portfolio,currency,true):'—',
        m?.completed_trades??'—',pct(m?.mdd),
        m?`${m.max_capital_lock_days_observed}일`:'—',
        cell?.status==='NOT_AFFORDABLE'?'과거 1주 매수 불가':
        a?.affordability_status==='NOT_AFFORDABLE'?'현재 시드 부족':
        m?.reentry_blocked_by_capital?'재진입 자금 부족':cell?.status||asset.status].forEach(value=>td(row,value));
      if(asset.status==='OK')row.addEventListener('click',()=>{showMatrix(asset.symbol);comparePeriods();loadJournal();if($('survival-panel').open)loadSurvival();});
    }
    if(!body.rows.length){const row=body.insertRow(),cell=td(row,'조건에 맞는 종목이 없습니다.');cell.colSpan=13;}
  }
  function render(){
    const runMarket=executedConfig?.market||$('market').value;
    const body=$('candidates');body.replaceChildren();
    const candidates=sortedCandidates();
    let lastMarket='';
    for(const c of candidates){const m=c.metrics,p=c.profile;
      if(c.market!==lastMarket){const separator=body.insertRow(),heading=td(separator,c.market==='KRX'?'한국 · KRW':'미국 · USD');heading.colSpan=14;separator.className='market-divider';lastMarket=c.market;}
      const row=body.insertRow();row.dataset.symbol=c.symbol;
      [c.market,c.name+' '+c.symbol,short(c.strategy_id),condition(c),pct(m.net_return),pct(m.mdd),num(m.profit_factor),String(m.completed_trades),`${num(m.total_trading_cost)} ${c.currency}`,pct(m.win_rate),num(m.average_holding_days),pct(m.market_exposure_ratio),pct(p.atr_pct),pct(p.annual_volatility)].forEach(v=>td(row,v));
      row.addEventListener('click',()=>{showMatrix(c.symbol);comparePeriods();loadJournal();if($('survival-panel').open)loadSurvival();});}
    if(!candidates.length){const row=body.insertRow();td(row,'조건에 맞는 실제 데이터 결과가 없습니다.');}
    const availability=$('availability');availability.replaceChildren();
    renderComparison();
    const ready=report.assets.filter(a=>a.status==='OK');
    const last=ready.map(a=>a.data_quality?.data_end).filter(Boolean).sort().at(-1);
    $('data-quality-line').textContent=`데이터 ${ready.length}/${report.assets.length}종목 사용 · 최종 관측 ${last||'—'} · 배당 미반영 · 원본 가격 보정 상태는 데이터 상세 참조`;
    for(const asset of report.assets.filter(a=>runMarket==='ALL'||a.market===runMarket)){
      const row=availability.insertRow();row.className=asset.status==='OK'?'':'skipped';
      [asset.market,asset.name+' '+asset.symbol,asset.status==='OK'?'REAL':asset.status,
        asset.data_quality?`${asset.data_quality.data_start} ~ ${asset.data_quality.data_end}`:'—',
        asset.actual_period?.join(' ~ ')||'—',asset.warmup_observations??'—',
        asset.data_quality?.period_support?Object.entries(asset.data_quality.period_support).filter(([,ok])=>ok).map(([period])=>period).join(' · '):'—',
        asset.data_quality?.row_count??'—',
        asset.data_quality?.provider||'—',asset.data_quality?.adjustment||'—',
        [asset.reason,asset.expected_import_file].filter(Boolean).join(' · ')||'—'].forEach(v=>td(row,v));}
    const preferred=report.assets.find(a=>a.symbol===$('asset').value&&a.status==='OK'&&
      (runMarket==='ALL'||a.market===runMarket)&&(!$('isa-only').checked||a.isa_eligible));
    const first=preferred||report.assets.find(a=>a.status==='OK'&&
      (runMarket==='ALL'||a.market===runMarket)&&(!$('isa-only').checked||a.isa_eligible));
    if(first)showMatrix(first.symbol);
    else{selectedSymbol=null;$('matrix').replaceChildren();$('trade-body').replaceChildren();
      $('why').textContent='';$('matrix-title').textContent='자산별 전략 매트릭스 · 계산 가능한 종목 없음';}
  }
  function queryFromInputs(){return new URLSearchParams({as_of:$('asof').value,lookback:$('lookback').value,
      capital:$('capital').value,us_capital:$('us-capital').value,
      s1_entry:$('s1-entry').value,s1_tp:$('s1-tp').value,
      s2_tp:$('s2-tp').value,s2_sl:$('s2-sl').value,
      kr_buy:$('kr-buy').value,kr_sell:$('kr-sell').value,kr_tax:$('kr-tax').value,kr_slip:$('kr-slip').value,
      us_buy:$('us-buy').value,us_sell:$('us-sell').value,us_tax:$('us-tax').value,us_slip:$('us-slip').value});}
  async function run(){
    $('status').textContent=`로컬 시세와 ${ids.length}개 전략을 계산 중…`;$('run').disabled=true;
    const submitted=currentRunConfig();
    try{const response=await fetch('/api/asset-discovery?'+submitted.query);const data=await response.json();
      if(!response.ok)throw new Error(data.error||'분석 실패');report=data;selectedSymbol=null;
      executedConfig=submitted;executedStrategy=submitted.strategy;
      const fields=new URLSearchParams(submitted.query);
      $('executed-config').textContent=`마지막 실행조건: ${short(executedStrategy)}${['S1_FIXED_TAKE_PROFIT','S1_TREND_FILTERED_TAKE_PROFIT'].includes(executedStrategy)?` · 진입 ${fields.get('s1_entry')}% · 익절 ${fields.get('s1_tp')}%`:['S2_FIXED_TP_SL','S2_TREND_FILTERED_TP_SL'].includes(executedStrategy)?` · 익절 ${fields.get('s2_tp')}% · 손절 ${fields.get('s2_sl')}%`:''} · ${fields.get('lookback')} · 기준일 ${fields.get('as_of')} · 한국 ${money(Number(fields.get('capital')),'KRW')} / 미국 ${money(Number(fields.get('us_capital')),'USD')}`;
      $('period-matrix').replaceChildren();$('period-status').textContent='';
      $('robustness-summary').replaceChildren();$('filter-rolling-body').replaceChildren();$('robustness-status').textContent='';
      yearlyReport=null;$('yearly').replaceChildren();$('regime-summary').replaceChildren();
      $('year-status').textContent='투자 조건이 바뀌었습니다. 연도별 분석을 다시 실행하세요.';
      render();markStale();comparePeriods();loadJournal();if($('survival-panel').open)loadSurvival();
      const ok=data.assets.filter(a=>a.status==='OK').length;
      $('status').textContent=`${data.requested_period.join(' ~ ')} · ${ok}/${data.assets.length}종목 데이터 사용 · ${data.cells.filter(c=>c.status==='OK').length}개 전략 셀 · ${short(executedStrategy)}${['S1_FIXED_TAKE_PROFIT','S1_TREND_FILTERED_TAKE_PROFIT'].includes(executedStrategy)?` TP ${data.strategy_config.S1_FIXED_TAKE_PROFIT.take_profit_pct}%`:''} · ${data.run_id}`;
    }catch(error){$('status').textContent=`분석 실패: ${error.message}`;}finally{$('run').disabled=false;}
  }
  async function comparePeriods(){
    if(!selectedSymbol)return;
    const requestedSymbol=selectedSymbol,requestedConfig=executedConfig;
    $('period-status').textContent='선택 종목의 6개 기간을 계산 중…';
    try{
      const query=executedQuery();query.set('symbol',selectedSymbol);query.set('strategy',executedStrategy);
      const response=await fetch('/api/asset-discovery/periods?'+query),data=await response.json();
      if(!response.ok)throw new Error(data.error||'기간 비교 실패');
      if(requestedSymbol!==selectedSymbol||requestedConfig!==executedConfig)return;
      const body=$('period-matrix');body.replaceChildren();
      for(const item of data.periods){const row=body.insertRow(),m=item.metrics;
        const currency=report.assets.find(a=>a.symbol===selectedSymbol)?.currency||'KRW';
        [item.period,money(m?.initial_capital,currency),
          money(m?.final_portfolio,currency),money(m?.net_gain,currency,true),
          pct(m?.net_return),money(item.s0_metrics?.final_portfolio,currency),
          money(item.difference_vs_s0,currency,true),m?.completed_trades??'—',
          money(m?.total_trading_cost,currency),pct(m?.mdd),
          m?`${m.max_capital_lock_days_observed}일`:'—',item.status].forEach(value=>td(row,value));}
      $('period-status').textContent=`${data.symbol} · ${short(data.strategy_id)} · 6개 기간 · 원본 데이터 ${data.load_count}회 로드`;
    }catch(error){$('period-status').textContent=`기간 비교 실패: ${error.message}`;}
  }
  async function loadJournal(){
    if(!selectedSymbol||!executedConfig)return;
    const requestedSymbol=selectedSymbol,requestedConfig=executedConfig;
    $('journal-status').textContent='일별 매매 기록 계산 중…';
    try{const query=executedQuery();query.set('symbol',requestedSymbol);query.set('strategy',executedStrategy);
      const response=await fetch('/api/asset-discovery/journal?'+query),data=await response.json();
      if(!response.ok)throw new Error(data.error||'매매 기록 계산 실패');
      if(requestedSymbol!==selectedSymbol||requestedConfig!==executedConfig)return;
      const asset=report.assets.find(a=>a.symbol===requestedSymbol),currency=asset.currency;
      const realized=new Map(data.trades.map(t=>[t.exit_date,t.net_profit]));
      const body=$('daily-ledger');body.replaceChildren();
      for(const item of data.ledger){const row=body.insertRow();
        [item.date,item.action==='BUY'?'매수':item.action==='SELL'?'매도':item.action==='BUY+SELL'?'매수·매도':item.strategy_state==='CASH'?'현금 대기':'보유 중',
          money(item.execution_price,currency),num(item.quantity),money(item.cash,currency),
          money(item.portfolio_value,currency),money(realized.get(item.date),currency,true),
          item.reason|| (item.quantity>0?'보유 중':'매수 대기')].forEach(value=>td(row,value));}
      if(data.open_position){const row=body.insertRow(),p=data.open_position;
        [data.ledger.at(-1)?.date||'—','OPEN POSITION',money(p.entry_price,currency),num(p.quantity),
          '—',money(data.ledger.at(-1)?.portfolio_value,currency),
          '—',`진입 ${p.entry_date} · ${p.holding_days}거래일 보유 · 현재 종가 ${money(p.mark_close,currency)} · 미실현손익 ${money(p.unrealized_pnl,currency,true)}`].forEach(value=>td(row,value));}
      $('journal-status').textContent=`${asset.name} · ${short(data.strategy_id)} · ${data.ledger.length}거래일 · 실제 실행조건 기준 · 미청산 손익은 실현손익에 포함하지 않음`;
    }catch(error){$('journal-status').textContent=`매매 기록 실패: ${error.message}`;}
  }
  async function loadSurvival(){
    if(!selectedSymbol||!executedConfig)return;
    const symbol=selectedSymbol,config=executedConfig;
    $('survival-status').textContent='고정된 S0/S1/S2/S7 및 진입필터 전략을 비교 중…';
    try{const query=executedQuery();query.set('symbol',symbol);
      const response=await fetch('/api/asset-discovery/survival?'+query),data=await response.json();
      if(!response.ok)throw new Error(data.error||'전략 비교 실패');
      if(symbol!==selectedSymbol||config!==executedConfig)return;
      const body=$('survival-body');body.replaceChildren();
      for(const item of data.rows){const m=item.metrics,row=body.insertRow();
        const label=short(item.strategy_id)+(item.tp_pct!=null?` TP${item.tp_pct}%`:'')+
          (item.sl_pct!=null?` SL${item.sl_pct}%`:'');
        const recovery=m?(m.recovered_from_max_drawdown?`${m.recovery_days}일`:
          `미회복 · ${m.unrecovered_days}거래일째`):'—';
        [label,money(m?.final_portfolio,data.currency),money(item.difference_vs_s0,data.currency,true),
          money(m?.net_gain,data.currency,true),pct(m?.mdd),recovery,
          m?`${m.max_capital_lock_days_observed}일`:'—',
          money(m?.closed_trade_expectancy_krw,data.currency,true),num(m?.payoff_ratio),
          pct(m?.cash_ratio),m?.blocked_entry_opportunity_count??'—'].forEach(value=>td(row,value));
        if(m){const detail=body.insertRow();detail.hidden=true;
          const cell=td(detail,`청산거래 승률 ${pct(m.win_rate)} · 평균 이익 ${money(m.average_win,data.currency)} · 평균 손실 ${money(m.average_loss,data.currency)} · PF ${num(m.profit_factor)} · 최대 단일 손실 ${money(m.max_single_loss,data.currency)} · 연속 손실 ${m.max_consecutive_losses}회 · 평균 보유 ${num(m.average_holding_days)}일 · 연간 실현수익 거래 ${num(m.realized_profit_events_per_year)}회 · 100거래일당 순손익 ${money(m.net_profit_per_100_trading_days,data.currency,true)} · 시장 노출 ${pct(m.market_exposure_ratio)} · 미실현손익 ${money(m.unrealized_gain,data.currency,true)} · 총비용 ${money(m.total_trading_cost,data.currency)} · MDD 회복 필요수익 ${pct(m.required_gain_to_recover_pct)}. 미청산 손익은 청산거래 기대값에 포함하지 않습니다.`);
          cell.colSpan=11;row.addEventListener('click',()=>{detail.hidden=!detail.hidden;});row.style.cursor='pointer';}
      }
      $('survival-status').textContent=`${data.name} · ${data.actual_period.join(' ~ ')} · 원본 데이터 ${data.load_count}회 로드 · 같은 비용 가정 · 결과는 과거 연구`;
    }catch(error){$('survival-status').textContent=`전략 비교 실패: ${error.message}`;}
  }
  async function runRobustness(){
    if(!selectedSymbol)return;
    const button=$('run-robustness');button.disabled=true;
    $('robustness-status').textContent='동일한 월별 시작점에서 S1 TP 3%와 5%를 계산 중…';
    try{const query=executedQuery();query.set('symbol',selectedSymbol);
      const response=await fetch('/api/asset-discovery/robustness?'+query),data=await response.json();
      if(!response.ok)throw new Error(data.error||'안정성 계산 실패');
      const asset=data.assets[0],body=$('robustness-summary');body.replaceChildren();
      if(asset.status!=='OK')throw new Error(asset.reason||asset.status);
      for(const group of asset.groups){const row=body.insertRow();
        const worst=group.worst_window;
        [asset.name,`${group.tp_pct}%`,group.period,
          `${group.affordable_window_count}/${group.windows} · 불가 ${group.not_affordable_window_count}`,
          `${group.positive_windows}건 · ${pct(group.positive_window_ratio)}`,
          `${group.s1_beats_s0_count}건 · ${pct(group.s1_beats_s0_ratio)}`,
          pct(group.median_return),worst?`${worst.window_start} ~ ${worst.window_end} · ${money(worst.initial_capital,asset.currency)} → ${money(worst.final_capital,asset.currency)} (${money(worst.net_profit,asset.currency,true)})`:'—',
          pct(group.open_at_end_ratio),`${group.down_market_s1_beats_s0_count}/${group.down_market_window_count} · ${pct(group.down_market_average_excess_return)}`,
          pct(group.median_missed_upside),`${group.max_capital_lock_days_observed}일`,
          `${group.max_recovery_days}일`,
          group.average_days_between_profit_events==null?'—':`${num(group.average_days_between_profit_events)}거래일`,
          money(group.total_trading_cost_across_windows,asset.currency)].forEach(value=>td(row,value));}
      const paired=$('filter-rolling-body');paired.replaceChildren();
      for(const group of asset.filter_comparison||[]){const row=paired.insertRow();
        [short(group.strategy_id),group.period,
          `${group.affordable_window_count}/${group.windows}`,
          pct(group.positive_window_ratio),pct(group.s1_beats_s0_ratio),
          pct(group.median_return),pct(group.worst_return),pct(group.average_mdd),
          `${group.max_capital_lock_days_observed}일`,pct(group.open_at_end_ratio),
          pct(group.average_cash_ratio),pct(group.down_market_average_excess_return),
          pct(group.median_missed_upside)].forEach(value=>td(row,value));}
      $('robustness-status').textContent=`${asset.name} · 원본 데이터 ${data.load_counts[asset.symbol]}회 로드 · TP 3%/5% 동일 시작점 비교 · 구간별 초기자금 독립 · 겹치는 표본`;
    }catch(error){$('robustness-status').textContent=`안정성 계산 실패: ${error.message}`;}
    finally{button.disabled=false;}
  }
  function renderYearly(){
    if(!yearlyReport)return;
    const assetFilter=$('year-asset').value,yearFilter=$('year-filter').value;
    const rows=yearlyReport.years.filter(item=>['OK','NO_POSITION_CAPITAL'].includes(item.status)&&
      (assetFilter==='ALL'||item.symbol===assetFilter)&&
      (yearFilter==='ALL'||String(item.year)===yearFilter));
    const body=$('yearly');body.replaceChildren();
    for(const item of rows){
      const s=item.strategies, row=body.insertRow();
      const period=item.actual_period.join(' ~ ')+(item.partial_start?' · 준비기간으로 시작 조정':'')+
        (item.partial_end?' · YTD':'');
      [item.name+' '+item.symbol,String(item.year),period,
        item.capital_constraint?item.regime.label+' · 자금 부족으로 미매수':item.regime.label,
        pct(item.regime.period_price_return),pct(s.S0_BUY_AND_HOLD?.net_return),
        pct(s.S1_FIXED_TAKE_PROFIT?.net_return),
        pct(s.S1_FIXED_TAKE_PROFIT?.gross_return_cost_addback),
        pct(s.S7_BREAKOUT_TREND_FOLLOWING?.net_return),
        item.excess_return_vs_s0.S1_FIXED_TAKE_PROFIT==null?'—':`${(item.excess_return_vs_s0.S1_FIXED_TAKE_PROFIT*100).toFixed(2)}`,
        item.excess_return_vs_s0.S7_BREAKOUT_TREND_FOLLOWING==null?'—':`${(item.excess_return_vs_s0.S7_BREAKOUT_TREND_FOLLOWING*100).toFixed(2)}`,
        `${num(s.S1_FIXED_TAKE_PROFIT?.total_trading_cost)} ${item.currency}`].forEach(v=>td(row,v));
    }
    if(!rows.length){const row=body.insertRow(),cell=td(row,'조건에 맞는 연도별 결과가 없습니다.');cell.colSpan=12;}
    if(rows.length===1){const item=rows[0],excess=item.excess_return_vs_s0.S1_FIXED_TAKE_PROFIT;
      $('year-interpretation').textContent=item.capital_constraint?
        `${item.name} ${item.year}년은 초기자금으로 정수 1주를 매수하지 못해 세 전략 모두 현금만 보유했습니다. 전략 성과 비교 표본에서 제외합니다.`:
        `${item.name} ${item.year}년은 ${item.regime.label}로 사후 분류됐고, S1의 S0 대비 초과수익은 ${excess==null?'계산 불가':(excess*100).toFixed(2)+'%p'}였습니다. 이 분류는 해당 연도 말에만 알 수 있어 미래 전략 선택 근거가 아닙니다.`;
    }else $('year-interpretation').textContent='Regime은 자산별·연도별 사후 분류입니다. 수익률은 각 연도 독립 실행의 비용 차감 결과입니다.';
  }
  async function runYearly(){
    const button=$('run-yearly');button.disabled=true;
    $('year-status').textContent='연도별 S0/S1/S7과 Regime을 계산 중…';
    try{const response=await fetch('/api/asset-discovery/yearly?'+executedQuery()),data=await response.json();
      if(!response.ok)throw new Error(data.error||'연도별 분석 실패');yearlyReport=data;
      const assetSelect=$('year-asset'),yearSelect=$('year-filter');
      assetSelect.replaceChildren(new Option('전체','ALL'));
      for(const asset of data.assets)assetSelect.append(new Option(`${asset.name} ${asset.symbol}`,asset.symbol));
      yearSelect.replaceChildren(new Option('전체','ALL'));
      for(const year of [...new Set(data.years.map(item=>item.year))].sort())yearSelect.append(new Option(String(year),String(year)));
      renderYearly();
      const summary=$('regime-summary');summary.replaceChildren();
      for(const item of data.regime_summary){const row=summary.insertRow();
        [item.regime,short(item.strategy_id),String(item.sample_count),pct(item.mean_net_return),
          pct(item.median_net_return),pct(item.positive_period_ratio),pct(item.mean_mdd),
          num(item.mean_completed_trades),item.mean_excess_vs_s0==null?'—':`${(item.mean_excess_vs_s0*100).toFixed(2)}`].forEach(v=>td(row,v));}
      $('year-status').textContent=`${data.years.filter(item=>item.status==='OK').length}개 자산·연도 · 데이터 종목별 1회 로드 · ${data.run_id}`;
    }catch(error){$('year-status').textContent=`연도별 분석 실패: ${error.message}`;}
    finally{button.disabled=false;}
  }
  $('run').addEventListener('click',run);
  $('run-robustness').addEventListener('click',runRobustness);
  $('run-yearly').addEventListener('click',runYearly);
  $('survival-panel').addEventListener('toggle',()=>{if($('survival-panel').open)loadSurvival();});
  for(const id of ['year-asset','year-filter'])$(id).addEventListener('input',renderYearly);
  $('market').addEventListener('input',syncLiquidityFilter);
  for(const id of ['market','lookback','asof','capital','us-capital','strategy','s1-entry','s1-tp','s2-tp','s2-sl',
    'kr-buy','kr-sell','kr-tax','kr-slip','us-buy','us-sell','us-tax','us-slip'])
    $(id).addEventListener('input',markStale);
  $('asset').addEventListener('input',()=>{if(report){render();comparePeriods();loadJournal();if($('survival-panel').open)loadSurvival();}});
  $('isa-only').addEventListener('input',()=>{if(report){render();comparePeriods();loadJournal();if($('survival-panel').open)loadSurvival();}});
  for(const id of ['mintrades','mdd','pf','liquidity','sort'])$(id).addEventListener('input',()=>report&&render());
})();
