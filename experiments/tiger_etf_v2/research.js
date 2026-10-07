(() => {
  const $ = id => document.getElementById(id);
  const initial = window.TIGER_SIMULATION_DATA?.scope.actual_period || window.TIGER_V2_DATA.period;
  const publicDemo = window.TIGER_V2_DATA?.provenance?.data_mode === 'PUBLIC_DEMO';
  if (publicDemo) {
    $('news-assumption').textContent = 'Public Demo는 합성 시세를 사용하며 실제 뉴스 카탈로그를 연결하지 않습니다. 가격·전략 Snapshot과 검증 프롬프트는 사용할 수 있습니다.';
  }
  $('research-start').value = initial[0];
  $('research-end').value = initial[1];
  let response = null, revision = 0, selectedType = 'markdown', mdUrl = null, jsonUrl = null;
  let periodSource = '현재 시뮬레이션 기간';
  function invalidate() {
    revision += 1;
    response = null;
    document.querySelectorAll('[data-export]').forEach(button => button.disabled = true);
    $('copy-research').disabled = true;
    $('download-markdown').hidden = $('download-json').hidden = true;
    $('research-output').value = '';
    $('news-list').replaceChildren();
    $('price-context').replaceChildren();
    $('research-status').textContent = '조건이 변경됐습니다. 다시 생성하세요.';
    $('research-period-source').textContent = `조회 기준: ${periodSource}`;
  }
  ['research-start', 'research-end'].forEach(id => $(id).addEventListener('input', () => {periodSource='직접 선택 연구기간';invalidate();}));
  ['research-mode', 'research-hypothesis'].forEach(id => $(id).addEventListener('input', invalidate));
  $('use-simulation-period').addEventListener('click', () => {
    const period=window.TIGER_SIMULATION_DATA?.scope.actual_period;
    if (!period) return;
    $('research-start').value=period[0]; $('research-end').value=period[1];
    periodSource='현재 시뮬레이션 기간'; invalidate();
  });
  $('use-chart-range').addEventListener('click', () => {
    const range = window.ZML_RESEARCH_RANGE;
    if (!range) return;
    $('research-start').value = range.start;
    $('research-end').value = range.end;
    periodSource='현재 차트 조회 범위';
    invalidate();
  });
  window.addEventListener('zml:research-day', event => {
    document.querySelector('.research-fold').open = true;
    $('research-start').value = $('research-end').value = event.detail.date;
    periodSource='선택한 매매복기 날짜';
    invalidate();
    $('research-status').textContent = `${event.detail.date} 선택 · 버튼을 눌러 해당 날짜 공개 자료를 확인하세요.`;
    $('research-start').scrollIntoView({behavior:'smooth', block:'center'});
  });
  window.addEventListener('zml:simulation-updated', event => {
    $('research-start').value=event.detail.scope.actual_period[0];
    $('research-end').value=event.detail.scope.actual_period[1];
    periodSource='현재 시뮬레이션 기간';
    invalidate();
  });
  function linkBlob(id, text, type, filename, previous) {
    if (previous) URL.revokeObjectURL(previous);
    const url = URL.createObjectURL(new Blob([text], {type}));
    $(id).href = url; $(id).download = filename; $(id).hidden = false;
    return url;
  }
  function showExport(type) {
    if (!response) return;
    selectedType = type;
    $('research-output').value = response[type];
    mdUrl = linkBlob('download-markdown', response[type], 'text/markdown;charset=utf-8', `${response.snapshot.snapshot_id}-${type}.md`, mdUrl);
  }
  function render(result) {
    const packet = result.snapshot, price = packet.price_context;
    const fmt = n => Number(n).toLocaleString('ko-KR', {maximumFractionDigits:2});
    const metrics = [['시작 종가', fmt(price.start_price)], ['종료 종가', fmt(price.end_price)],
      ['가격 수익률', `${fmt(price.period_return * 100)}%`], ['고가 / 저가', `${fmt(price.high)} / ${fmt(price.low)}`],
      ['종가 MDD', `${fmt(price.mdd * 100)}%`], ['관측 수', price.observations]];
    $('price-context').replaceChildren(...metrics.map(([label, value]) => {
      const box = document.createElement('div'); box.className='metric';
      const title=document.createElement('span'), text=document.createElement('strong');
      title.textContent=label; text.textContent=value; box.append(title,text); return box;
    }));
    $('news-list').replaceChildren();
    if (!packet.news.length) {
      const empty=document.createElement('p'); empty.textContent=publicDemo
        ? 'Public Demo에는 실제 뉴스가 연결되지 않습니다. 합성 가격을 실제 사건과 연결하지 않습니다.'
        : '이 기간에 일치하는 카탈로그 자료가 없습니다. 전체 뉴스 부재를 뜻하지 않습니다.';
      $('news-list').append(empty);
    }
    packet.news.forEach(item => {
      const card=document.createElement('article'); card.className='news-item';
      const date=document.createElement('small'), link=document.createElement('a'), summary=document.createElement('p');
      date.textContent=`${item.published_local} · ${item.source}${item.retrospective || item.after_selected_period ? ' · 사후 공개 / 회고' : ''}`;
      link.textContent=item.headline; link.href=item.url; link.target='_blank'; link.rel='noopener noreferrer';
      summary.textContent=item.summary; card.append(date,link,summary); $('news-list').append(card);
    });
    $('research-status').textContent=`${packet.mode === 'REPLAY_MODE' ? '복기 모드' : '사후 분석'} · ${packet.selected_period.start}~${packet.selected_period.end} · ${packet.news.length}건 · 공개 cutoff ${packet.news_cutoff} · ${packet.strategy_window ? '현재 실행 전략 결과' : '전략 결과 없는 기간'}`;
    document.querySelectorAll('[data-export]').forEach(button => button.disabled=false);
    $('copy-research').disabled=false;
    showExport(selectedType);
    jsonUrl=linkBlob('download-json', JSON.stringify(packet,null,2), 'application/json', `${packet.snapshot_id}.json`, jsonUrl);
  }
  async function buildResearch() {
    invalidate();
    const version=revision;
    const params={start:$('research-start').value,end:$('research-end').value,mode:$('research-mode').value,hypothesis:$('research-hypothesis').value,run_id:window.TIGER_SIMULATION_DATA?.run_id};
    $('research-status').textContent='선택 구간과 공개시각을 확인하는 중…';
    try {
      const request=await fetch('/api/research',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(params)});
      if (!request.ok && request.status !== 400) throw new Error('뉴스 공급자 응답에 실패했습니다. 가격/매매 시뮬레이션에는 영향이 없습니다.');
      const result=await request.json();
      if (version !== revision) return;
      if (!request.ok) throw new Error(result.error || '입력 날짜와 실행 결과를 확인하세요.');
      response=result; render(result);
    } catch(error) {
      if (version === revision) $('research-status').textContent=`뉴스 조회 실패: ${error instanceof SyntaxError ? '응답 형식을 읽을 수 없습니다. 가격/매매 시뮬레이션에는 영향이 없습니다.' : error instanceof TypeError ? '뉴스 공급자 응답에 실패했습니다. 가격/매매 시뮬레이션에는 영향이 없습니다.' : error.message}`;
    }
  }
  $('build-research').addEventListener('click', buildResearch);
  $('build-validation').addEventListener('click', async () => {
    if (!response) await buildResearch();
    if(response) showExport('validation');
  });
  document.querySelectorAll('[data-export]').forEach(button => button.addEventListener('click',()=>showExport(button.dataset.export)));
  $('copy-research').addEventListener('click',async()=>{
    if (!response) return;
    try { await navigator.clipboard.writeText($('research-output').value); $('research-status').textContent='본문을 복사했습니다. 연구방에서 직접 붙여넣으세요.'; }
    catch { $('research-output').focus(); $('research-output').select(); $('research-status').textContent='본문을 선택했습니다. Ctrl+C로 복사하세요.'; }
  });
})();
