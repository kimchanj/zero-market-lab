from datetime import date

import pandas as pd
import pytest

from zero_market_lab.asset_discovery.behavior import analyze_behavior
from zero_market_lab.asset_discovery.engine import ResearchRunConfig, filter_cells, run_discovery
from zero_market_lab.simulator.strategy_family import STRATEGIES
from zero_market_lab.simulator.strategy_family import FixedTakeProfitConfig
from decimal import Decimal


def frame(length=250, *, jump=1):
    days = pd.bdate_range('2025-01-01', periods=length)
    prices = [10000 + i * 10 for i in range(length)]
    prices[-1] *= jump
    return pd.DataFrame([{'date': d.date(), 'open': p, 'high': p + 5,
                          'low': p - 5, 'close': p, 'volume': 1000,
                          'trading_value': p * 1000} for d, p in zip(days, prices)])


def universe():
    return [{'symbol': code, 'name': code, 'market': 'KRX'} for code in ('000001', '000002')]


def test_profile_is_time_sliced_and_characterizes_price_behavior():
    market = frame()
    cutoff = market.iloc[-2].date
    before = analyze_behavior(market, as_of=cutoff, symbol='000001', name='Fixture')
    modified = market.copy()
    modified.loc[len(market)-1, ['open', 'high', 'low', 'close']] = [20000, 20005, 19995, 20000]
    after = analyze_behavior(modified, as_of=cutoff, symbol='000001', name='Fixture')
    assert before == after
    assert before['observation_count'] == 249
    assert before['annual_volatility'] >= 0
    assert before['atr_pct'] > 0
    assert before['max_up_streak'] > 0
    assert before['breakout_count'] > 0
    assert before['mdd'] == 0
    assert before['average_trading_value'] > 0


def test_profile_uses_prior_warmup_but_counts_only_evaluation_events():
    market = frame()
    market.loc[:119, ['open', 'high', 'low', 'close']] = [10000, 10005, 9995, 10000]
    market.loc[120, ['open', 'high', 'low', 'close']] = [11000, 11005, 10995, 11000]
    start = market.iloc[120].date
    profile = analyze_behavior(market, as_of=market.iloc[-1].date, start=start,
                               symbol='000001', name='Fixture')
    assert profile['period_start'] == start.isoformat()
    assert profile['observation_count'] == 130
    assert profile['breakout_count'] >= 1


def test_discovery_matrix_deterministic_filters_and_load_once():
    base = frame()
    cutoff = base.iloc[-1].date
    calls = []
    def loader(symbol):
        calls.append(symbol)
        return base, {'provider': 'synthetic test fixture', 'adjustment': 'UNADJUSTED'}
    run = run_discovery(universe(), loader, ResearchRunConfig(cutoff, '6M'))
    assert calls == ['000001', '000002']
    assert len(run['cells']) == 2 * len(STRATEGIES)
    assert {a['status'] for a in run['assets']} == {'OK'}
    selected = filter_cells(run, strategy_id=STRATEGIES[0])
    assert [c['symbol'] for c in selected] == ['000001', '000002']
    assert filter_cells(run, strategy_id=STRATEGIES[0], minimum_trades=1) == []
    assert filter_cells(run, strategy_id=STRATEGIES[0], minimum_profit_factor=1.2) == []
    assert len(filter_cells(run, strategy_id=STRATEGIES[0], maximum_drawdown=-1,
                            minimum_liquidity=1000)) == 2
    assert run['input_hash'] and run['strategy_config_hash']
    assert run['cells'][0]['metrics']['initial_capital'] == 500000


def test_s1_config_and_fee_model_change_research_identity():
    base = frame()
    cutoff = base.iloc[-1].date
    loader = lambda _: (base, {'provider': 'fixture'})
    five = run_discovery(universe()[:1], loader, ResearchRunConfig(cutoff, '6M'))
    three = run_discovery(universe()[:1], loader, ResearchRunConfig(
        cutoff, '6M', s1=FixedTakeProfitConfig(Decimal('-1'), Decimal('3'))))
    assert five['strategy_config_hash'] != three['strategy_config_hash']
    assert five['input_hash'] != three['input_hash']
    assert three['cells'][1]['strategy_config']['take_profit_pct'] == '3'


def test_s2_config_changes_research_identity_and_filtered_cell_is_recorded():
    from zero_market_lab.simulator.strategy_family import FixedStopConfig
    base = frame(length=350)
    cutoff = base.iloc[-1].date
    loader = lambda _: (base, {'provider': 'fixture'})
    first = run_discovery(universe()[:1], loader, ResearchRunConfig(cutoff, '6M'))
    changed = run_discovery(universe()[:1], loader, ResearchRunConfig(
        cutoff, '6M', s2=FixedStopConfig(Decimal(5), Decimal(7))))
    assert first['strategy_config_hash'] != changed['strategy_config_hash']
    assert first['input_hash'] != changed['input_hash']
    filtered = next(cell for cell in changed['cells']
                    if cell['strategy_id'] == 'S2_TREND_FILTERED_TP_SL')
    assert filtered['status'] == 'OK'
    assert filtered['strategy_config']['stop_loss_pct'] == '7'


def test_current_affordability_is_separate_from_historical_trade_status():
    base = frame()
    cutoff = base.iloc[-1].date
    latest = base.copy()
    latest.loc[len(latest)-1, ['open', 'high', 'low', 'close']] = [600000, 601000, 590000, 600000]
    report = run_discovery(universe()[:1], lambda _: (latest, {'provider': 'fixture'}),
                           ResearchRunConfig(cutoff, '6M'))
    asset = report['assets'][0]
    assert asset['affordability']['current_price'] == 600000
    assert asset['affordability']['max_affordable_qty'] == 0
    assert asset['affordability']['required_cash_for_one_share'] > 500000
    s0 = next(cell for cell in report['cells'] if cell['strategy_id'] == 'S0_BUY_AND_HOLD')
    assert s0['status'] == 'OK' and s0['metrics']['open_trades'] == 1

    expensive = base.copy()
    for column in ('open', 'high', 'low', 'close'):
        expensive[column] *= 100
    unaffordable = run_discovery(universe()[:1], lambda _: (expensive, {'provider': 'fixture'}),
                                  ResearchRunConfig(cutoff, '6M'))
    no_buy = next(cell for cell in unaffordable['cells'] if cell['strategy_id'] == 'S0_BUY_AND_HOLD')
    assert no_buy['status'] == 'NOT_AFFORDABLE'
    assert no_buy['metrics']['net_return'] == 0


def test_isa_and_cost_reference_keep_historical_research_cost_separate():
    from zero_market_lab.asset_discovery.instrument_policy import current_cost_reference
    kospi = current_cost_reference('KRX_STOCK', 'KOSPI')
    kosdaq = current_cost_reference('KRX_STOCK', 'KOSDAQ')
    etf = current_cost_reference('KRX_ETF', 'KRX')
    assert sum(kospi.sell_tax_components[i][1] for i in range(2)) == Decimal('0.0020')
    assert kosdaq.sell_tax_components == (('securities_transaction_tax', Decimal('0.002')),)
    assert etf.sell_tax_components == ()
    assert kospi.as_dict()['applied_to_backtest'] is False
    assert current_cost_reference('US_STOCK', 'NASDAQ') is None
    base = frame()
    entry = {'symbol': '000001', 'name': 'Fixture', 'market': 'KRX',
             'instrument_type': 'KRX_STOCK', 'exchange_segment': 'KOSPI', 'isa_eligible': True}
    report = run_discovery([entry], lambda _: (base, {'provider': 'fixture'}),
                           ResearchRunConfig(base.iloc[-1].date, '6M'))
    assert report['assets'][0]['isa_eligible'] is True
    assert report['assets'][0]['cost_profile_reference']['sell_tax_components']['rural_special_tax'] == 0.0015
    assert report['fee_model_by_market']['KRX']['sell_tax_rate'] == '0'


def test_missing_and_stale_asset_isolation():
    base = frame()
    cutoff = base.iloc[-1].date
    def loader(symbol):
        if symbol == '000002':
            raise FileNotFoundError(symbol)
        return base, {'provider': 'synthetic test fixture'}
    run = run_discovery(universe(), loader, ResearchRunConfig(cutoff, '6M'))
    assert run['assets'][0]['status'] == 'OK'
    assert run['assets'][1]['status'] == 'DATA_UNAVAILABLE'
    assert run['assets'][1]['expected_import_file'].endswith('korea_000002/<snapshot>/ohlcv.csv')
    assert len(run['cells']) == len(STRATEGIES)
    stale = run_discovery(universe()[:1], lambda _: (base, {}),
                          ResearchRunConfig(date(2026, 1, 1), '6M'))
    assert stale['assets'][0]['reason'] == 'STALE_DATA'


def test_strategy_failure_only_marks_one_cell(monkeypatch):
    import zero_market_lab.simulator.strategy_family as family
    original = family._run_one
    def fail_one(*args):
        if args[-1] == STRATEGIES[1]:
            raise RuntimeError('test failure')
        return original(*args)
    monkeypatch.setattr(family, '_run_one', fail_one)
    base = frame()
    run = run_discovery(universe()[:1], lambda _: (base, {}),
                        ResearchRunConfig(base.iloc[-1].date, '6M'))
    assert len(run['cells']) == len(STRATEGIES)
    assert sum(c['status'] == 'ERROR' for c in run['cells']) == 1
    assert run['cells'][1]['reason'] == 'RuntimeError'


def test_insufficient_history_skips_without_future_fill():
    base = frame(90)
    run = run_discovery(universe()[:1], lambda _: (base, {}),
                        ResearchRunConfig(base.iloc[-1].date, '6M'))
    assert run['assets'][0]['reason'] == 'INSUFFICIENT_DATA'
    assert not run['cells']


def test_us_native_currency_price_rules_and_market_filter():
    kr = frame()
    us = frame()
    for column in ('open', 'high', 'low', 'close'):
        us[column] = us[column] / 100
    assets = [universe()[0], {'symbol': 'NVDA', 'name': 'NVIDIA', 'market': 'US',
                               'currency': 'USD', 'timezone': 'America/New_York'}]
    def loader(symbol):
        return (us if symbol == 'NVDA' else kr), {'provider': 'synthetic test fixture'}
    run = run_discovery(assets, loader, ResearchRunConfig(kr.iloc[-1].date, '6M'))
    assert len(run['cells']) == 2 * len(STRATEGIES)
    assert {c['currency'] for c in run['cells']} == {'KRW', 'USD'}
    us_cells = filter_cells(run, strategy_id=STRATEGIES[0], market='US')
    assert len(us_cells) == 1 and us_cells[0]['symbol'] == 'NVDA'
    assert us_cells[0]['metrics']['initial_capital'] == 500
    assert filter_cells(run, strategy_id=STRATEGIES[0], market='KRX')[0]['symbol'] == '000001'


def test_us_provider_uses_exchange_dates_and_keeps_adjusted_close_separate():
    from scripts.fetch_us_seed import normalize
    timestamps = [int(pd.Timestamp(value, tz='UTC').timestamp()) for value in
                  ('2025-01-02 14:30', '2025-01-03 14:30')]
    document = {'chart': {'error': None, 'result': [{'meta': {
        'symbol': 'NVDA', 'exchangeTimezoneName': 'America/New_York', 'currency': 'USD'},
        'timestamp': timestamps, 'indicators': {
            'quote': [{'open': [100, 101], 'high': [102, 103], 'low': [99, 100],
                       'close': [101, 102], 'volume': [1000, 1100]}],
            'adjclose': [{'adjclose': [100.5, 101.5]}]}}]}}
    market, metadata = normalize(document, 'NVDA')
    assert market.date.tolist() == [date(2025, 1, 2), date(2025, 1, 3)]
    assert market.close.tolist() == [101, 102]
    assert market.adjusted_close.tolist() == [100.5, 101.5]
    assert metadata['exchange_timezone'] == 'America/New_York'


def test_us_current_exchange_day_is_not_used_as_a_completed_daily_bar():
    from scripts.fetch_us_seed import completed_daily_bars
    market = pd.DataFrame({'date': [date(2026, 10, 7), date(2026, 10, 8)],
                           'close': [100, 110]})
    completed = completed_daily_bars(market, date(2026, 10, 8))
    assert completed.date.tolist() == [date(2026, 10, 7)]
    with pytest.raises(ValueError, match='No completed'):
        completed_daily_bars(market.tail(1), date(2026, 10, 8))


def test_us_split_event_continuity_rejects_raw_split_discontinuity():
    from scripts.fetch_us_seed import audit_split_continuity
    timestamp = int(pd.Timestamp('2024-06-10 13:30', tz='UTC').timestamp())
    document = {'chart': {'result': [{'events': {'splits': {str(timestamp): {
        'date': timestamp, 'splitRatio': '10:1'}}}}]}}
    market = pd.DataFrame({'date': [date(2024, 6, 7), date(2024, 6, 10)],
                           'close': [120, 121]})
    assert audit_split_continuity(market, document)[0]['close_ratio'] == pytest.approx(121 / 120)
    market.loc[1, 'close'] = 12
    with pytest.raises(ValueError, match='Split-sized'):
        audit_split_continuity(market, document)


def test_five_year_run_has_warmup_and_period_coverage():
    days = pd.bdate_range('2020-01-01', periods=1700)
    prices = [10000 + i for i in range(len(days))]
    market = pd.DataFrame({'date': [day.date() for day in days],
                           'open': prices, 'high': [value + 5 for value in prices],
                           'low': [value - 5 for value in prices], 'close': prices,
                           'volume': 1000})
    cutoff = days[-1].date()
    result = run_discovery(universe()[:1], lambda _: (market, {'provider': 'fixture'}),
                           ResearchRunConfig(cutoff, '5Y'))
    asset = result['assets'][0]
    assert asset['status'] == 'OK'
    assert asset['warmup_observations'] >= 100
    assert all(asset['data_quality']['period_support'].values())
    assert len(result['cells']) == len(STRATEGIES)


@pytest.mark.parametrize('period', ('6M', '1Y', '2Y', '3Y', '4Y', '5Y'))
def test_each_supported_period_runs_with_the_same_historical_frame(period):
    days = pd.bdate_range('2020-01-01', periods=1700)
    prices = [10000 + i for i in range(len(days))]
    market = pd.DataFrame({'date': [day.date() for day in days],
                           'open': prices, 'high': [value + 5 for value in prices],
                           'low': [value - 5 for value in prices], 'close': prices,
                           'volume': 1000})
    run = run_discovery(universe()[:1], lambda _: (market, {'provider': 'fixture'}),
                        ResearchRunConfig(days[-1].date(), period))
    assert run['assets'][0]['status'] == 'OK'
    assert run['assets'][0]['warmup_observations'] >= 100
    assert len(run['cells']) == len(STRATEGIES)


@pytest.mark.parametrize('extension', ['csv', 'json', 'parquet'])
def test_local_seed_import_formats_and_manifest(tmp_path, extension):
    import json
    from zero_market_lab.asset_discovery.catalog import LocalOHLCVCatalog
    folder = tmp_path / 'data/processed/us_NVDA/fixture'
    folder.mkdir(parents=True)
    market = frame(30)
    output = folder / f'ohlcv.{extension}'
    if extension == 'csv':
        market.to_csv(output, index=False)
    elif extension == 'json':
        market.assign(date=market.date.astype(str)).to_json(output, orient='records')
    else:
        market.to_parquet(output, index=False)
    (folder / 'metadata.json').write_text(json.dumps({'provider': 'fixture',
                                                       'adjustment': 'UNKNOWN'}), encoding='utf-8')
    catalog = LocalOHLCVCatalog(tmp_path)
    loaded, metadata = catalog.load('NVDA')
    assert len(loaded) == 30 and metadata['provider'] == 'fixture'
    catalog.load('NVDA')
    assert catalog.read_count == {'NVDA': 1}
