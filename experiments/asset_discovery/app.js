(() => {
  const ids=['S0_BUY_AND_HOLD','S1_FIXED_TAKE_PROFIT','S2_FIXED_TP_SL','S3_FIXED_TP_SL_TIME','S4_TREND_FILTERED_TP_SL_TIME','S5_ATR_ADAPTIVE_EXIT','S6A_PURE_MEAN_REVERSION','S6B_CONFIRMED_REVERSAL','S7_BREAKOUT_TREND_FOLLOWING'];
  const short=id=>id.replace(/^S(\d)([AB])?_.*$/,'S$1$2');
  const $=id=>document.getElementById(id);
  const pct=v=>v==null?'—':`${(v*100).toFixed(2)}%`;
  const num=v=>v==null?'—':Number(v).toLocaleString('ko-KR',{maximumFractionDigits:2});
  const td=(row,value)=>{const c=row.insertCell();c.textContent=value;return c;};
  let report=null;
  const strategy=$('strategy');ids.forEach(id=>{const o=document.createElement('option');o.value=id;o.textContent=`${short(id)} · ${id.slice(id.indexOf('_')+1).replaceAll('_',' ')}`;strategy.append(o);});
  strategy.value='S7_BREAKOUT_TREND_FOLLOWING';
  $('asof').value=new Date().toLocaleDateString('sv-SE',{timeZone:'Asia/Seoul'});
  function sortedCandidates(){
    if(!report)return [];
    const selected=strategy.value, sort=$('sort').value,market=$('market').value;
    const minTrades=Number($('mintrades').value||0), mdd=$('mdd').value===''?null:Number($('mdd').value)/100;
    const pf=$('pf').value===''?null:Number($('pf').value), liq=Number($('liquidity').value||0);
    const rows=report.cells.filter(c=>c.status==='OK'&&c.strategy_id===selected&&
      (market==='ALL'||c.market===market)).filter(c=>
      c.metrics.completed_trades>=minTrades&&(mdd==null||c.metrics.mdd>=mdd)&&
      (pf==null||(c.metrics.profit_factor!=null&&c.metrics.profit_factor>=pf))&&c.profile.average_trading_value>=liq);
    rows.sort((a,b)=>{const get=c=>sort==='atr_pct'?c.profile.atr_pct:c.metrics[sort];
      const marketOrder=a.market.localeCompare(b.market);if(marketOrder)return marketOrder;
      const av=get(a),bv=get(b);if(av==null&&bv==null)return a.symbol.localeCompare(b.symbol);
      if(av==null)return 1;if(bv==null)return -1;
      return bv-av||a.symbol.localeCompare(b.symbol);});
    return rows;
  }
  function showMatrix(symbol){
    const asset=report.assets.find(a=>a.symbol===symbol), body=$('matrix');body.replaceChildren();
    $('matrix-title').textContent=`${asset.name} ${symbol} · ${asset.market} · ${asset.currency} 자산별 전략 매트릭스`;
    const profile=asset.profile,selected=report.cells.find(c=>c.symbol===symbol&&c.strategy_id===strategy.value);
    let behavior=`최근 구간 연변동성 ${pct(profile.annual_volatility)}, ATR ${pct(profile.atr_pct)}.`;
    if(!selected?.metrics)behavior+=' 선택 전략 셀은 계산 오류로 제외됐습니다.';
    else if(strategy.value==='S7_BREAKOUT_TREND_FOLLOWING')behavior+=` 20일 고가 돌파 ${profile.breakout_count}회, 5거래일 후 평가 가능한 ${profile.breakout_5d_evaluated}회 중 양수 비율 ${pct(profile.breakout_success_rate)}. S7 손실 청산 ${selected.metrics.whipsaw_count}회.`;
    else if(strategy.value==='S1_FIXED_TAKE_PROFIT')behavior+=` S1 완료 거래 ${selected.metrics.completed_trades}건, 평균 보유 ${num(selected.metrics.average_holding_days)}거래일.`;
    else if(strategy.value.startsWith('S6'))behavior+=` 3% 이상 하락 ${profile.drop_3pct_count}회, 이후 5거래일 양수 반등 비율 ${pct(profile.rebound_rate_5d)}.`;
    else behavior+=` 최대 낙폭 ${pct(selected.metrics.mdd)}, 완료 거래 ${selected.metrics.completed_trades}건.`;
    const buyHold=report.cells.find(c=>c.symbol===symbol&&c.strategy_id==='S0_BUY_AND_HOLD');
    if(buyHold?.metrics?.market_exposure_ratio===0)
      behavior+=` S0는 초기자금 ${num(buyHold.metrics.initial_capital)} ${asset.currency}로 첫 거래일 정수 1주를 매수하지 못해 현금만 보유했습니다.`;
    $('why').textContent=`가격행동 관찰: ${behavior} 선택 기간의 기술적 기록이며 전략 효과의 원인 또는 미래 적합성을 증명하지 않습니다.`;
    for(const c of report.cells.filter(c=>c.symbol===symbol)){
      const row=body.insertRow(),m=c.metrics;
      [short(c.strategy_id),m?`${num(m.final_portfolio)} ${c.currency}`:c.status,pct(m?.net_return),pct(m?.mdd),num(m?.profit_factor),m?.completed_trades??'—',pct(m?.win_rate),m?.average_holding_days==null?'—':`${num(m.average_holding_days)}일`,m?`${num(m.total_trading_cost)} ${c.currency}`:'—'].forEach(v=>td(row,v));
    }
  }
  function render(){
    const body=$('candidates');body.replaceChildren();
    const candidates=sortedCandidates();
    let lastMarket='';
    for(const c of candidates){const m=c.metrics,p=c.profile;
      if(c.market!==lastMarket){const separator=body.insertRow(),heading=td(separator,c.market==='KRX'?'한국 · KRW':'미국 · USD');heading.colSpan=12;separator.className='market-divider';lastMarket=c.market;}
      const row=body.insertRow();row.dataset.symbol=c.symbol;
      [c.market,c.name+' '+c.symbol,short(c.strategy_id),pct(m.net_return),pct(m.mdd),num(m.profit_factor),String(m.completed_trades),pct(m.win_rate),num(m.average_holding_days),pct(m.market_exposure_ratio),pct(p.atr_pct),pct(p.annual_volatility)].forEach(v=>td(row,v));
      row.addEventListener('click',()=>showMatrix(c.symbol));}
    if(!candidates.length){const row=body.insertRow();td(row,'조건에 맞는 실제 데이터 결과가 없습니다.');}
    const availability=$('availability');availability.replaceChildren();
    for(const asset of report.assets.filter(a=>$('market').value==='ALL'||a.market===$('market').value)){
      const row=availability.insertRow();row.className=asset.status==='OK'?'':'skipped';
      [asset.market,asset.name+' '+asset.symbol,asset.status==='OK'?'REAL':asset.status,
        asset.data_quality?.row_count??'—',asset.data_quality?.data_end||'—',
        asset.data_quality?.provider||'—',asset.data_quality?.adjustment||'—',
        [asset.reason,asset.expected_import_file].filter(Boolean).join(' · ')||'—'].forEach(v=>td(row,v));}
    const first=candidates[0]||report.cells.find(c=>c.status==='OK'&&($('market').value==='ALL'||c.market===$('market').value));
    if(first)showMatrix(first.symbol);
    else{$('matrix').replaceChildren();$('why').textContent='';$('matrix-title').textContent='자산별 전략 매트릭스 · 계산 가능한 종목 없음';}
  }
  async function run(){
    $('status').textContent='로컬 시세와 9개 전략을 계산 중…';$('run').disabled=true;
    try{const query=new URLSearchParams({as_of:$('asof').value,lookback:$('lookback').value,
      capital:$('capital').value,us_capital:$('us-capital').value});
      const response=await fetch('/api/asset-discovery?'+query);const data=await response.json();
      if(!response.ok)throw new Error(data.error||'분석 실패');report=data;render();
      const ok=data.assets.filter(a=>a.status==='OK').length;
      $('status').textContent=`${data.requested_period.join(' ~ ')} · ${ok}/${data.assets.length}종목 데이터 사용 · ${data.cells.filter(c=>c.status==='OK').length}개 전략 셀 · ${data.run_id}`;
    }catch(error){$('status').textContent=`분석 실패: ${error.message}`;}finally{$('run').disabled=false;}
  }
  $('run').addEventListener('click',run);
  for(const id of ['strategy','market','mintrades','mdd','pf','liquidity','sort'])$(id).addEventListener('input',()=>report&&render());
})();
