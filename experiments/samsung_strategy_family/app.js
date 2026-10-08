(() => {
  const number = value => value == null ? '—' : Number(value).toLocaleString('ko-KR',{maximumFractionDigits:2});
  const percent = value => value == null ? '—' : `${(value*100).toFixed(2)}%`;
  const labels = {
    S0_BUY_AND_HOLD:'S0 · 일시금 보유',S1_FIXED_TAKE_PROFIT:'S1 · 익절 5%',
    S2_FIXED_TP_SL:'S2 · 익절/손절',S3_FIXED_TP_SL_TIME:'S3 · 익절/손절/20일',
    S4_TREND_FILTERED_TP_SL_TIME:'S4 · MA100 추세 필터',
    S5_ATR_ADAPTIVE_EXIT:'S5 · ATR 적응형',S6A_PURE_MEAN_REVERSION:'S6-A · 평균회귀',
    S6B_CONFIRMED_REVERSAL:'S6-B · 반전 확인',S7_BREAKOUT_TREND_FOLLOWING:'S7 · 돌파 추세',
  };
  const cell=(row,value,kind='')=>{const item=row.insertCell();item.textContent=value;item.className=kind;};
  const fact=(parent,label,value,kind='fact')=>{const item=document.createElement('div');item.className=kind;
    const small=document.createElement('small');small.textContent=label;const strong=document.createElement('strong');strong.textContent=value;
    item.append(small,strong);parent.append(item);};
  async function main(){
    try {
      const response=await fetch('/api/samsung-family');
      const report=await response.json();
      if(!response.ok) throw new Error(report.error||'결과를 불러오지 못했습니다.');
      document.getElementById('status').textContent=`계산 완료 · ${report.actual_period.join(' ~ ')} · ${Object.keys(report.results).length}개 전략`;
      const scope=document.getElementById('scope');
      [['자산',`${report.instrument.name} ${report.instrument.symbol}`],['평가기간',report.actual_period.join(' ~ ')],
       ['Data Load',report.data_load_period.join(' ~ ')],['Warm-up',`${report.warmup_observations}거래일`],
       ['초기금액',`${number(report.capital)}원`],['자료',report.source]].forEach(([a,b])=>fact(scope,a,b));
      const matrix=document.getElementById('matrix');
      for(const [key,result] of Object.entries(report.results)){
        const m=result.metrics,row=matrix.insertRow();cell(row,labels[key]||key);
        cell(row,`${number(m.final_portfolio)}원`);cell(row,percent(m.net_return),m.net_return>=0?'positive':'negative');
        cell(row,percent(m.mdd));cell(row,`${m.completed_trades}건`);cell(row,percent(m.win_rate));
        cell(row,m.average_holding_days==null?'—':`${number(m.average_holding_days)}일`);
        cell(row,`${m.max_holding_days}일`);cell(row,number(m.profit_factor));
        cell(row,percent(m.market_exposure_ratio));cell(row,`${result.ambiguity_count}건`);
      }
      const regimes=document.getElementById('regimes');
      for(const period of report.regimes){
        fact(regimes,`${period.month} · ${period.label}`,
          `가격 ${percent(period.price_return)} · 상대 상위 ${labels[period.sample_best]||'—'} · 하위 ${labels[period.sample_worst]||'—'}`,'regime');
      }
      const details=document.getElementById('details');
      for(const [key,result] of Object.entries(report.results)){
        const box=document.createElement('details'),title=document.createElement('summary');
        title.textContent=`${labels[key]} · ${result.trades.length}건 완료 · 총비용 ${number(result.metrics.total_trading_cost)}원`;
        box.append(title);
        const metrics=document.createElement('div');metrics.className='detail-row';
        for(const [label,value] of [['손절',result.metrics.stop_loss_count],['시간청산',result.metrics.time_stop_count],
          ['신호',result.metrics.signal_count],['필터 미통과',result.metrics.filtered_entry_count],
          ['최대 낙폭 지속',result.metrics.max_drawdown_duration]]){
          const item=document.createElement('span');item.textContent=`${label} ${value}`;metrics.append(item);
        }
        box.append(metrics);
        const trades=document.createElement('p');trades.textContent=result.trades.length
          ? result.trades.map(t=>`${t.entry_date} 매수 ${number(t.entry_price)}원 → ${t.exit_date} ${t.exit_reason} ${number(t.exit_price)}원 · 손익 ${number(t.net_profit)}원`).join(' | ')
          : '완료 거래 없음. 기간 말 보유는 최종 종가로 평가합니다.';
        box.append(trades);
        const ledger=document.createElement('details'),ledgerTitle=document.createElement('summary');ledgerTitle.textContent='일별 Ledger';ledger.append(ledgerTitle);
        const table=document.createElement('table'),body=document.createElement('tbody');
        for(const day of result.ledger){const row=body.insertRow();
          [day.date,day.action,day.reason||'—',`${number(day.cash)}원`,`${number(day.quantity)}주`,`${number(day.portfolio_value)}원`].forEach(value=>cell(row,value));}
        table.append(body);ledger.append(table);box.append(ledger);details.append(box);
      }
    }catch(error){document.getElementById('status').textContent=`비교 결과를 불러오지 못했습니다: ${error.message}`;}
  }
  main();
})();
