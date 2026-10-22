(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  let accountId = null;
  let state = null;
  let assets = [];
  const money = (value, currency) => currency === 'USD'
    ? `$${Number(value).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`
    : `₩${Number(value).toLocaleString('ko-KR', {maximumFractionDigits: 0})}`;
  const signed = (value, currency) => `${Number(value) > 0 ? '+' : Number(value) < 0 ? '-' : ''}${money(Math.abs(Number(value)), currency)}`;
  const ratio = value => value == null ? '—' : `${Number(value) > 0 ? '+' : ''}${Number(value).toFixed(2)}%`;
  const set = (id, value) => { $(id).textContent = value; };
  async function request(path, options = {}) {
    const response = await fetch(path, {cache: 'no-store', ...options});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `요청 실패 ${response.status}`);
    return data;
  }
  const post = (path, body) => request(path, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  function error(message) { set('error', message); $('error').hidden = !message; }
  function metric(container, label, value, tone = '') {
    const box = document.createElement('div');
    const caption = document.createElement('span'); caption.textContent = label;
    const amount = document.createElement('strong'); amount.textContent = value;
    if (tone) amount.className = tone;
    box.append(caption, amount); container.append(box);
  }
  function render(packet) {
    state = packet; accountId = packet.account_id; $('workspace').hidden = false;
    set('replay-date', packet.date ? `현재 Replay · ${packet.date}` : '거래일 진행 전');
    set('next-date', packet.next_date ? `다음 관측일 ${packet.next_date}` : '마지막 관측일');
    $('next-day').disabled = !packet.next_date;
    const journal = $('journal-body'); journal.replaceChildren();
    for (const day of [...(packet.journal || [])].reverse().slice(0, 120)) {
      const row = journal.insertRow();
      if (day.date === packet.date) row.className = 'journal-latest';
      const fills = day.fills.map(fill => `${fill.symbol} ${fill.side} ${fill.quantity}주`).join(', ') || 'HOLD';
      for (const value of [day.date, fills, `${day.positions}종목`,
        money(day.wallets.KRW.cash, 'KRW'), money(day.wallets.KRW.equity, 'KRW'),
        money(day.wallets.USD.cash, 'USD'), money(day.wallets.USD.equity, 'USD')]) {
        row.insertCell().textContent = value;
      }
    }
    set('journal-head', `${packet.days_processed} sessions · ${packet.date || '거래일 진행 전'} · ${packet.journal?.at(-1)?.fills?.length || 0}건 체결`);
    set('summary-head', `KRW ${money(packet.wallets.KRW.equity, 'KRW')} · 현금 ${money(packet.wallets.KRW.cash, 'KRW')} / USD ${money(packet.wallets.USD.equity, 'USD')}`);
    set('today-head', `${packet.date || '진행 전'} · 다음 ${packet.next_date || '없음'} · 사용자 주문`);
    set('position-head', `${packet.holdings.length}종목 · ${packet.holdings.reduce((count, item) => count + Number(item.quantity), 0)}주`);
    set('orders-head', `대기 ${packet.pending_orders.length}건 · 최근 기록 ${packet.recent_events.length}건`);
    set('technical-detail', `계좌 ${packet.account_id} · ${packet.mode} · 설정 ${packet.config_hash} · 비용 ${packet.fee_model_version} · 체결 ${packet.fill_rule_version}`);
    if (packet.date) {
      const asset = assets.find(item => item.symbol === $('symbol').value) || assets[0];
      const currency = asset?.currency || 'KRW';
      request(`/api/transit/current?date=${encodeURIComponent(packet.date)}&currency=${currency}`).then(transit => {
        if (state !== packet) return;
        set('transit-head', `${transit.gate}.${transit.line} · ${transit.center} · ${transit.keynote}`);
        set('transit-detail', `Gate ${transit.gate}.${transit.line} · ${transit.center} · ${transit.keynote} · ${transit.start_kst.slice(0, 16).replace('T', ' ')} ~ ${transit.end_kst.slice(0, 16).replace('T', ' ')} KST · USNO 근사 모델, 인과관계/매매 신호 아님`);
      }).catch(() => set('transit-head', 'Transit 조회 불가'));
    } else {
      set('transit-head', '거래일 진행 전');
    }
    const wallets = $('wallets'); wallets.replaceChildren();
    for (const currency of ['KRW', 'USD']) {
      const w = packet.wallets[currency];
      const card = document.createElement('div'); card.className = 'wallet';
      const title = document.createElement('h3'); title.textContent = `${currency} 잔고`;
      const grid = document.createElement('div'); grid.className = 'wallet-grid';
      metric(grid, '총자산', money(w.equity, currency));
      metric(grid, '예수금', money(w.cash, currency));
      metric(grid, '매입금액', money(w.purchase, currency));
      metric(grid, '평가금액', money(w.valuation, currency));
      metric(grid, '평가손익', signed(w.unrealized_pnl, currency), Number(w.unrealized_pnl) < 0 ? 'negative' : 'positive');
      metric(grid, '총손익 / 수익률', `${signed(w.total_pnl, currency)} · ${ratio(w.return_pct)}`, Number(w.total_pnl) < 0 ? 'negative' : 'positive');
      card.append(title, grid); wallets.append(card);
    }
    const tbody = $('holdings'); tbody.replaceChildren();
    if (!packet.holdings.length) {
      const row = tbody.insertRow(); const cell = row.insertCell(); cell.colSpan = 8;
      cell.textContent = '보유 종목이 없습니다. 현금으로 대기 중입니다.';
    }
    for (const holding of packet.holdings) {
      const row = tbody.insertRow();
      const values = [`${holding.name} · ${holding.symbol}`, money(holding.average_cost, holding.currency),
        `${holding.quantity}주`, money(holding.close, holding.currency),
        money(holding.purchase, holding.currency), money(holding.valuation, holding.currency),
        signed(holding.unrealized_pnl, holding.currency), ratio(holding.return_pct)];
      for (const value of values) row.insertCell().textContent = value;
      row.addEventListener('click', () => { $('symbol').value = holding.symbol; $('side').value = 'SELL'; syncOrder(); });
    }
    const pending = $('pending'); pending.replaceChildren();
    if (!packet.pending_orders.length) pending.textContent = '없음';
    for (const order of packet.pending_orders) {
      const line = document.createElement('div');
      line.textContent = `${order.date} 주문 · ${order.symbol} ${order.side === 'BUY' ? '매수 한도 ' + money(order.budget, order.currency) : '매도 ' + order.quantity + '주'} · 다음 해당 종목 거래일 시가 대기`;
      pending.append(line);
    }
    const history = $('events'); history.replaceChildren();
    if (!packet.recent_events.length) history.textContent = '없음';
    for (const event of packet.recent_events) {
      const line = document.createElement('div');
      line.textContent = event.kind === 'FILL'
        ? `${event.date} · ${event.symbol} ${event.side === 'BUY' ? '매수' : '매도'} ${event.quantity}주 × ${money(event.price, event.currency)} · 체결 후 예수금 ${money(event.cash_after, event.currency)}`
        : `${event.date} · 주문 #${event.order_id} 거부 · ${event.reason}`;
      history.append(line);
    }
    syncOrder();
  }
  function syncOrder() {
    const asset = assets.find(item => item.symbol === $('symbol').value);
    const selling = $('side').value === 'SELL';
    $('budget-field').hidden = selling; $('quantity-field').hidden = !selling;
    $('budget').required = !selling; $('quantity').required = selling;
    set('submit-order', selling ? '매도 주문' : '매수 주문');
    if (!asset || !state) return;
    const cash = state.wallets[asset.currency].cash;
    const holding = state.holdings.find(item => item.symbol === asset.symbol);
    const market = state.market_snapshot?.[asset.symbol];
    set('market-board', market
      ? `${asset.name} · ${market.date} 관측 · 시가 ${money(market.open, asset.currency)} · 고가 ${money(market.high, asset.currency)} · 저가 ${money(market.low, asset.currency)} · 종가 ${money(market.close, asset.currency)} · 거래량 ${Number(market.volume).toLocaleString('ko-KR')} · 판단/주문은 사용자 선택`
      : '선택 종목에 현재 Replay 날짜까지의 관측 시세가 없습니다.');
    set('order-hint', `${asset.name} · ${asset.currency} 예수금 ${money(cash, asset.currency)} · 보유 ${holding?.quantity || 0}주 · 현재 주문은 다음 해당 종목 거래일 시가에 체결`);
    $('budget').step = asset.currency === 'KRW' ? '1' : '0.01';
    $('budget').min = asset.currency === 'KRW' ? '1' : '0.01';
  }
  async function refreshAccounts(selected) {
    const accounts = await request('/api/manual/accounts');
    const select = $('account-select'); select.replaceChildren();
    const blank = document.createElement('option'); blank.value = ''; blank.textContent = '계좌 선택'; select.append(blank);
    for (const account of accounts) {
      const option = document.createElement('option'); option.value = account.account_id;
      option.textContent = `${account.start_date} · KRW ${money(account.initial_cash.KRW, 'KRW')} · USD ${money(account.initial_cash.USD, 'USD')} · ${account.days_processed}일`;
      select.append(option);
    }
    if (selected && accounts.some(item => item.account_id === selected)) select.value = selected;
  }
  $('create-form').addEventListener('submit', async event => {
    event.preventDefault();
    try { error(''); const packet = await post('/api/manual/create', {
      start_date: $('start-date').value, initial_krw: $('initial-krw').value,
      initial_usd: $('initial-usd').value}); render(packet); await refreshAccounts(packet.account_id); }
    catch (failure) { error(failure.message); }
  });
  $('next-day').addEventListener('click', async () => {
    if (!accountId) return;
    try { error(''); render(await post(`/api/manual/${encodeURIComponent(accountId)}/next`, {}));
      $('manual-journal').open = true;
      $('manual-journal').scrollIntoView({block: 'start'});
    }
    catch (failure) { error(failure.message); }
  });
  $('order-form').addEventListener('submit', async event => {
    event.preventDefault(); if (!accountId) return;
    try { error(''); render(await post(`/api/manual/${encodeURIComponent(accountId)}/order`, {
      symbol: $('symbol').value, side: $('side').value,
      budget: $('side').value === 'BUY' ? $('budget').value : null,
      quantity: $('side').value === 'SELL' ? $('quantity').value : null})); }
    catch (failure) { error(failure.message); }
  });
  $('account-select').addEventListener('change', async () => {
    if (!$('account-select').value) return;
    try { error(''); render(await request(`/api/manual/${encodeURIComponent($('account-select').value)}/state`)); }
    catch (failure) { error(failure.message); }
  });
  $('symbol').addEventListener('change', syncOrder); $('side').addEventListener('change', syncOrder);
  (async () => {
    try {
      const meta = await request('/api/manual/meta'); assets = meta.assets;
      const select = $('symbol'); select.replaceChildren();
      for (const asset of assets) { const option = document.createElement('option');
        option.value = asset.symbol; option.textContent = `${asset.name} · ${asset.symbol} (${asset.currency})`; select.append(option); }
      const dates = assets.map(item => item.last_date).sort();
      $('start-date').value = dates[Math.floor(dates.length / 2)];
      await refreshAccounts();
    } catch (failure) { error(failure.message); }
  })();
})();
