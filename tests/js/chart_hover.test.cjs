const { test } = require('node:test');
const assert = require('node:assert/strict');
const { marketDate, model } = require('../../experiments/tiger_etf_v2/hover.js');

const row = changes => ({
  date: '2026-01-19', status: 'WAITING_ENTRY', action: 'NONE',
  entry_order_price: 25100, low: 25240, entry_gap: 140,
  cash_after: 523412, portfolio_value: 523412,
  position_qty_after: 0, ...changes,
});
const values = hover => Object.fromEntries(hover.items);

test('WAITING_ENTRY uses the ledger limit, low, gap and cash', () => {
  const hover = model(row());
  assert.equal(hover.title, '매수 대기');
  assert.equal(values(hover)['미체결 이유'], '140원 부족 · 미체결');
  assert.match(values(hover)['매수 지정가 · 오늘 저가'], /25,100원 · 25,240원/);
  assert.match(values(hover)['현금 · 총자산'], /523,412원/);
});

test('ENTRY_FILLED uses execution and accounting values', () => {
  const hover = model(row({status:'ENTRY_FILLED', action:'BUY', execution_price:24500,
    execution_qty:20, buy_amount:490000, buy_fee:98, take_profit_price:25725,
    cash_after:9902, portfolio_value:499902, position_qty_after:20}));
  assert.equal(hover.title, '매수 완료');
  assert.equal(values(hover)['매수가 · 수량'], '24,500원 × 20주');
  assert.equal(values(hover)['매수금액 · 수수료'], '490,000원 · 98원');
  assert.equal(values(hover)['익절 목표'], '25,725원');
});

test('HOLDING uses ledger target distance and holding days', () => {
  const hover = model(row({status:'WAITING_TAKE_PROFIT', action:'HOLD',
    position_qty_after:41, avg_entry_price_after:24500, take_profit_price:25725,
    high:25310, high_target_gap:415, trading_holding_days:12,
    cash_after:10000, portfolio_value:518230}));
  assert.equal(hover.title, '보유 중 · 12거래일');
  assert.equal(values(hover)['목표까지'], '415원');
  assert.match(values(hover)['현금 · 총자산'], /518,230원/);
});

test('EXIT_FILLED uses net profit, net return and duration from ledger', () => {
  const hover = model(row({status:'EXIT_FILLED', action:'SELL', execution_price:25725,
    execution_qty:41, net_profit:23412, net_return:0.0468,
    trading_holding_days:16, sell_fee:52, tax:0, portfolio_value:523412}));
  assert.equal(hover.title, '익절 완료');
  assert.equal(values(hover)['순이익 · 수익률'], '+23,412원 (+4.68%)');
  assert.equal(values(hover)['보유기간'], '16거래일');
});

test('final OPEN position uses close and unrealized profit without closing trade', () => {
  const hover = model(row({date:'2026-10-06', status:'WAITING_TAKE_PROFIT', action:'HOLD',
    position_qty_after:41, avg_entry_price_after:13070, close:13620,
    unrealized_profit:21922, target_gap:105, target_gap_rate:0.0077,
    trading_holding_days:24, portfolio_value:546779}), true);
  assert.equal(hover.title, '미청산 보유');
  assert.equal(values(hover)['현재 종가'], '13,620원');
  assert.equal(values(hover)['미실현손익'], '+21,922원');
  assert.match(values(hover)['익절 목표까지'], /105원/);
});

test('market dates never shift across timezones', () => {
  assert.equal(marketDate('2026-10-06'), '2026-10-06');
  assert.equal(marketDate({year:2026,month:1,day:2}), '2026-01-02');
  assert.equal(marketDate('2026-10-06T00:00:00Z'), null);
});

test('missing or out-of-period ledger fields do not crash', () => {
  assert.equal(model(null).title, '시뮬레이션 기간 밖');
  assert.equal(model({status:'WAITING_ENTRY'}).kind, 'waiting');
  assert.equal(values(model({status:'WAITING_ENTRY'}))['미체결 이유'], '체결 조건을 확인하세요');
});

test('insufficient cash is explained without exposing an internal code', () => {
  const hover = model(row({decision_code:'INSUFFICIENT_CASH', entry_gap:0}));
  assert.equal(values(hover)['미체결 이유'], '매수 가능 수량을 채울 현금이 부족합니다');
  assert.doesNotMatch(JSON.stringify(hover), /INSUFFICIENT_CASH/);
});

test('periodic contribution hover separates deposits from investment gain', () => {
  const hover = model(row({strategy:'PERIODIC_CONTRIBUTION', contribution_amount:500000,
    total_contributions:1000000, purchase_quantity:19, execution_price:25000,
    position_qty_after:39, avg_entry_price_after:24700, cash_after:37000,
    portfolio_value:1016000, cumulative_gain:16000}));
  assert.equal(hover.title, '정기 적립 매수');
  assert.equal(values(hover)['입금 · 누적납입금'], '500,000원 · 1,000,000원');
  assert.equal(values(hover)['누적 손익'], '+16,000원');
});
