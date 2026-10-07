"""UI application adapter: validate inputs, invoke the existing engine, present results."""
from datetime import date
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import pandas as pd

from .engine import simulate
from .execution import required_exit_price
from .models import Instrument, StrategyParameters, ExecutionConfig, CostConfig
from .provider import FrameOHLCVProvider

STATUS = {"WAITING_ENTRY":"매수 대기", "ENTRY_FILLED":"매수 완료", "HOLDING":"보유 중",
          "WAITING_TAKE_PROFIT":"익절 대기", "EXIT_FILLED":"익절 완료", "WAITING_REENTRY":"재매수 대기",
          "NO_ACTION":"대기", "AMBIGUOUS":"확인 필요"}
ACTION = {"BUY":"매수", "SELL":"매도", "HOLD":"보유", "NONE":"대기"}


def number(params, key, default, minimum, maximum):
    try:
        value=Decimal(str(params.get(key,default)).replace(',',''))
    except (InvalidOperation, ValueError):
        raise ValueError(f"{key}: 숫자를 입력하세요.")
    if not value.is_finite() or not minimum <= value <= maximum:
        raise ValueError(f"{key}: {minimum}~{maximum} 범위로 입력하세요.")
    return value


def run_simulation(bundle: dict, params: dict) -> dict:
    start,end=date.fromisoformat(params['start']),date.fromisoformat(params['end'])
    if start > end:
        raise ValueError('투자 시작일은 종료일보다 늦을 수 없습니다.')
    seed=number(params,'initial_capital','500000',Decimal('1'),Decimal('1e12'))
    entry=number(params,'entry_percent','1',Decimal('0'),Decimal('50'))/100
    tp=number(params,'take_profit_percent','5',Decimal('.01'),Decimal('100'))/100
    minimum=number(params,'minimum_net_percent','1',Decimal('0'),Decimal('100'))/100
    meta=dict(bundle['simulation']['instrument'])
    for key in ('tick_size','lot_size'):
        meta[key]=Decimal(str(meta[key]))
    instrument=Instrument(**meta)
    raw_costs=bundle['simulation']['costs']
    costs=CostConfig(**{k: v if k=='label' else Decimal(str(v)) for k,v in raw_costs.items()})
    strategy=StrategyParameters(entry_offset_rate=entry,take_profit_rate=tp)
    try:
        bars=FrameOHLCVProvider(pd.DataFrame(bundle['market'])).load_ohlcv(instrument,start,end)
    except ValueError as error:
        if str(error) == 'No OHLCV bars in requested range':
            raise ValueError('선택한 투자기간에 실제 OHLCV 관측값이 없습니다.') from error
        raise
    result=simulate(instrument=instrument,bars=bars,initial_capital=seed,
                    strategy=strategy,execution=ExecutionConfig(),costs=costs)
    payload=result.to_dict()
    payload['scope']={
        'requested_period':[start.isoformat(),end.isoformat()],
        'actual_period':[result.summary.start_date.isoformat(),result.summary.end_date.isoformat()],
        'initial_capital':float(seed),'parameter_search':False,
        'fee_disclaimer': '매수·매도 각 0.015%, 세금 0% 연구 가정 · 분배금 제외 · 시가 확인 후 주문',
    }
    payload['minimum_net']={'rate':float(minimum),'mode':'EVALUATION_ONLY',
        'description':'최소 순수익은 완료 거래의 평가 기준입니다. 익절 체결가격을 변경하지 않습니다.'}
    payload['provenance']=bundle['simulation'].get('provenance',{})
    trades_by_id={trade.trade_id:trade for trade in result.trades}
    for trade_dict,trade in zip(payload['trades'],result.trades):
        trade_dict['minimum_net_met']=(trade.net_return >= minimum) if trade.status=='CLOSED' else None
        trade_dict['required_exit_price']=float(required_exit_price(
            entry_price=trade.entry_price,quantity=trade.entry_qty,buy_fee=trade.entry_fee,
            minimum_net_return=minimum,instrument=instrument,costs=costs))
    markers,average,targets=[],[],[]
    for row,raw in zip(payload['ledger'],result.ledger):
        row['status_label']=STATUS.get(row['status'],'대기')
        row['action_label']=ACTION.get(row['action'],'대기')
        row['target_gap']=None if raw.take_profit_price is None else float(raw.take_profit_price-raw.close)
        row['target_gap_rate']=None if raw.take_profit_price is None else float(raw.take_profit_price/raw.close-1)
        row['high_target_gap']=None if raw.take_profit_price is None else float(max(Decimal(0),raw.take_profit_price-raw.high))
        row['entry_gap']=None if raw.entry_order_price is None else float(max(Decimal(0),raw.low-raw.entry_order_price))
        if raw.action=='BUY':
            row['brief']=f"{raw.execution_price:,.0f}원에 {raw.execution_qty:,.0f}주 매수 완료"
        elif raw.action=='SELL':
            row['brief']=f"+{tp*100:g}% 익절 체결"
        elif raw.position_qty_after>0:
            row['brief']=f"익절가까지 {row['high_target_gap']:,.0f}원 · 보유 {raw.trading_holding_days}일차"
        else:
            row['brief']='최소 수량 매수자금 부족' if raw.decision_code=='INSUFFICIENT_CASH' else '매수가 미도달'
        if raw.ambiguous:
            row['brief']='당일 매수·익절 순서를 알 수 없어 보유'
        row['required_exit_price']=None
        if raw.trade_id:
            trade=trades_by_id[raw.trade_id]
            row['required_exit_price']=float(required_exit_price(
                entry_price=trade.entry_price,quantity=trade.entry_qty,buy_fee=trade.entry_fee,
                minimum_net_return=minimum,instrument=instrument,costs=costs))
        if raw.position_qty_after>0:
            average.append({'time':row['date'],'value':row['avg_entry_price_after']})
            targets.append({'time':row['date'],'value':row['take_profit_price']})
        else:
            average.append({'time':row['date']}); targets.append({'time':row['date']})
        if raw.action in {'BUY','SELL'}:
            markers.append({'time':row['date'],'action':row['action'],'tradeId':raw.trade_id,
                'price':row['execution_price'],'quantity':row['execution_qty'],'fee':row['total_cost'],
                'cashAfter':row['cash_after'],'grossProfit':row['gross_profit'],'tax':row['tax'],
                'netProfit':row['net_profit'],'netReturn':row['net_return'],'holdingDays':raw.trading_holding_days,
                'explanation':row['explanation']})
    payload['chart']={'markers':markers,'averageCost':average,'takeProfit':targets}
    open_trade=next((trade for trade in payload['trades'] if trade['status']=='OPEN'),None)
    last=payload['ledger'][-1]
    if open_trade is not None:
        last['brief']=f"기간 종료 시 미청산 · 익절가까지 {last['high_target_gap']:,.0f}원"
    payload['open_position']=None if open_trade is None else {
        **open_trade,'current_close':last['close'],'current_value':last['position_value'],
        'target_price':last['take_profit_price'],'target_gap':last['target_gap'],
        'target_gap_rate':last['target_gap_rate']}
    payload['run_id']=sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:20]
    return payload
