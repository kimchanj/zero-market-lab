from datetime import date

import pandas as pd
import pytest

from zero_market_lab.asset_discovery.behavior import analyze_behavior
from zero_market_lab.asset_discovery.engine import ResearchRunConfig, filter_cells, run_discovery
from zero_market_lab.simulator.strategy_family import STRATEGIES


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
    assert len(run['cells']) == 9
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
    assert len(run['cells']) == 9
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
    assert len(run['cells']) == 18
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
