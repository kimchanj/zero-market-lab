/* Presentation-only mapping from engine Daily Ledger rows to chart hover text. */
((root) => {
  const format = value => value == null || !Number.isFinite(Number(value))
    ? '—' : Number(value).toLocaleString('ko-KR', { maximumFractionDigits: 2 });
  const won = value => value == null ? '—' : `${format(value)}원`;
  const signedWon = value => value == null ? '—' : `${Number(value) >= 0 ? '+' : ''}${format(value)}원`;
  const signedPercent = value => value == null ? '—'
    : `${Number(value) >= 0 ? '+' : ''}${format(Number(value) * 100)}%`;

  function marketDate(value) {
    if (typeof value === 'string') return /^\d{4}-\d{2}-\d{2}$/.test(value) ? value : null;
    if (value && Number.isInteger(value.year) && Number.isInteger(value.month) && Number.isInteger(value.day)) {
      return `${value.year}-${String(value.month).padStart(2, '0')}-${String(value.day).padStart(2, '0')}`;
    }
    return null;
  }

  function model(row, isFinalOpen = false) {
    if (!row) return { kind: 'outside', title: '시뮬레이션 기간 밖', items: [] };
    if (isFinalOpen && Number(row.position_qty_after) > 0) {
      return { kind: 'open', title: '미청산 보유', items: [
        ['수량 · 평균매입', `${format(row.position_qty_after)}주 · ${won(row.avg_entry_price_after)}`],
        ['현재 종가', won(row.close)],
        ['미실현손익', signedWon(row.unrealized_profit)],
        ['익절 목표까지', `${won(row.target_gap)} (${signedPercent(row.target_gap_rate)})`],
        ['보유기간 · 총자산', `${format(row.trading_holding_days)}거래일 · ${won(row.portfolio_value)}`],
      ] };
    }
    if (row.status === 'AMBIGUOUS' || row.ambiguous) {
      return { kind: 'ambiguous', title: '당일 순서 확인 필요', items: [
        ['체결', `${won(row.execution_price)} × ${format(row.execution_qty)}주`],
        ['판정', '매수·익절 순서 불명 · 당일 보유'],
        ['총자산', won(row.portfolio_value)],
      ] };
    }
    if (row.action === 'SELL' || row.status === 'EXIT_FILLED') {
      return { kind: 'exit', title: '익절 완료', items: [
        ['매도가 · 수량', `${won(row.execution_price)} × ${format(row.execution_qty)}주`],
        ['보유기간', `${format(row.trading_holding_days)}거래일`],
        ['순이익 · 수익률', `${signedWon(row.net_profit)} (${signedPercent(row.net_return)})`],
        ['매도비용 · 세금', `${won(row.sell_fee)} · ${won(row.tax)}`],
        ['총자산', won(row.portfolio_value)],
      ] };
    }
    if (row.action === 'BUY' || row.status === 'ENTRY_FILLED') {
      return { kind: 'entry', title: '매수 완료', items: [
        ['매수가 · 수량', `${won(row.execution_price)} × ${format(row.execution_qty)}주`],
        ['매수금액 · 수수료', `${won(row.buy_amount)} · ${won(row.buy_fee)}`],
        ['익절 목표', won(row.take_profit_price)],
        ['잔여현금 · 총자산', `${won(row.cash_after)} · ${won(row.portfolio_value)}`],
      ] };
    }
    if (Number(row.position_qty_after) > 0) {
      return { kind: 'holding', title: `보유 중 · ${format(row.trading_holding_days)}거래일`, items: [
        ['수량 · 평균매입', `${format(row.position_qty_after)}주 · ${won(row.avg_entry_price_after)}`],
        ['익절 목표 · 오늘 고가', `${won(row.take_profit_price)} · ${won(row.high)}`],
        ['목표까지', won(row.high_target_gap)],
        ['현금 · 총자산', `${won(row.cash_after)} · ${won(row.portfolio_value)}`],
      ] };
    }
    if (row.status === 'WAITING_ENTRY') {
      const waitingReason = row.decision_code === 'INSUFFICIENT_CASH'
        ? '매수 가능 수량을 채울 현금이 부족합니다'
        : row.entry_gap == null ? '체결 조건을 확인하세요' : `${won(row.entry_gap)} 부족 · 미체결`;
      return { kind: 'waiting', title: '매수 대기', items: [
        ['매수 지정가 · 오늘 저가', `${won(row.entry_order_price)} · ${won(row.low)}`],
        ['미체결 이유', waitingReason],
        ['현금 · 총자산', `${won(row.cash_after)} · ${won(row.portfolio_value)}`],
      ] };
    }
    return { kind: 'other', title: row.status_label || '대기', items: [
      ['행동', row.action_label || '대기'], ['총자산', won(row.portfolio_value)],
    ] };
  }

  const api = { marketDate, model };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (root) root.ZML_HOVER = api;
})(typeof window === 'undefined' ? null : window);
