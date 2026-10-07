from copy import deepcopy
from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal as D
import json
from pathlib import Path

import pytest

from zero_market_lab.simulator import Instrument, MarketBar, simulate, ExecutionConfig, CostConfig
from zero_market_lab.research.news import CatalogNewsProvider, NewsItem
from zero_market_lab.research.snapshot import build_snapshot, markdown

ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 10, 6, tzinfo=timezone.utc)


@pytest.fixture
def instrument():
    return Instrument("TEST:ETF", "ETF", "Test ETF", "ETF", "TEST", "USD", "Asia/Seoul",
                      currency_precision=2, market_hours="09:00-15:30",
                      related_macro_topics=("FOMC", "CPI"))


def item(instant="2023-02-01T14:00:00-05:00", **kwargs):
    return NewsItem(datetime.fromisoformat(instant), "Test release", "Official",
                    kwargs.pop("url", "https://example.org/release"), "Summary", ("FOMC",), **kwargs)


def test_replay_timezone_excludes_us_release_before_krx_close(instrument):
    provider = CatalogNewsProvider([item()])
    assert provider.search_news(instrument, date(2023,2,1), date(2023,2,1),
        cutoff=datetime.fromisoformat("2023-02-01T15:30:00+09:00")) == []
    result = provider.search_news(instrument, date(2023,2,2), date(2023,2,2),
        cutoff=datetime.fromisoformat("2023-02-02T15:30:00+09:00"))
    assert len(result) == 1
    assert result[0].url == "https://example.org/release"
    assert result[0].source == "Official"
    assert result[0].relevance_score > 0


def test_replay_exact_cutoff_and_future_exclusion(instrument):
    provider = CatalogNewsProvider([item("2023-02-02T15:30:00+09:00"),
                                   item("2023-02-02T15:30:01+09:00", url="https://example.org/later")])
    result=provider.search_news(instrument,date(2023,2,2),date(2023,2,2),
                               cutoff=datetime.fromisoformat("2023-02-02T15:30:00+09:00"))
    assert len(result) == 1


def test_post_analysis_includes_later_retrospective_only_with_event_match(instrument):
    late = item("2023-04-12T14:00:00-04:00", retrospective=True,event_date=date(2023,3,22))
    unrelated = replace(late,url="https://example.org/other",event_date=date(2023,5,1))
    provider=CatalogNewsProvider([late,unrelated])
    assert not provider.search_news(instrument,date(2023,3,1),date(2023,3,31),cutoff=NOW)
    result=provider.search_news(instrument,date(2023,3,1),date(2023,3,31),mode="POST_ANALYSIS_MODE",cutoff=NOW)
    assert result == [replace(late,relevance_score=.2)]


def test_relevance_and_duplicate_filter(instrument):
    irrelevant=replace(item(),keywords=("unrelated",),url="https://example.org/unrelated")
    result=CatalogNewsProvider([item(),item(),irrelevant]).search_news(
        instrument,date(2023,2,1),date(2023,2,3),cutoff=NOW)
    assert len(result) == 1


@pytest.mark.parametrize("instant,url",[("2023-01-01T00:00:00","https://example.org"),
                                        ("2023-01-01T00:00:00Z","javascript:alert(1)")])
def test_invalid_news_metadata_rejected(instant,url):
    with pytest.raises(ValueError):
        item(instant,url=url)


@pytest.fixture
def source(instrument):
    bars=[MarketBar(datetime(2023,2,day),D(o),D(h),D(l),D(c),D(10))
          for day,o,h,l,c in [(1,100,101,98,100),(2,100,102,99,101),(3,102,106,101,105)]]
    result=simulate(instrument=instrument,bars=bars,initial_capital=D(500))
    payload=result.to_dict()
    payload['scope']={'actual_period':['2023-02-01','2023-02-03']}
    market=[{'date':bar.timestamp.date().isoformat(),'open':float(bar.open),'high':float(bar.high),
             'low':float(bar.low),'close':float(bar.close),'volume':10} for bar in bars]
    return payload,market


def test_price_summary_and_full_strategy_consistent(source):
    sim,market=source
    snapshot=build_snapshot(sim,market,CatalogNewsProvider([]),date(2023,2,1),date(2023,2,3),now=NOW)
    assert snapshot['price_context']['period_return'] == pytest.approx(.05)
    assert snapshot['price_context']['start_price'] == 100
    assert snapshot['price_context']['high'] == 106
    assert snapshot['strategy_window']['closing_equity'] == sim['summary']['final_portfolio_value']
    assert snapshot['strategy_window']['net_profit'] == sim['summary']['net_profit']


def test_early_snapshot_redacts_future_exit_and_preserves_carry_in(source):
    sim,market=source
    snapshot=build_snapshot(sim,market,CatalogNewsProvider([]),date(2023,2,2),date(2023,2,2),now=NOW)
    trade=snapshot['trades'][0]
    assert trade['status'] == 'OPEN'
    assert trade['exit_date'] is None
    assert trade['exit_price'] is None
    assert trade['trading_holding_days'] == 2
    assert trade['capital_after'] == sim['ledger'][1]['portfolio_value']
    assert snapshot['strategy_window']['opening_equity'] == sim['ledger'][0]['portfolio_value']
    assert snapshot['ledger'][0]['position_qty_before'] > 0


def test_context_never_changes_simulation_and_export_is_detached(source):
    sim,market=source
    baseline=deepcopy(sim)
    result=build_snapshot(sim,market,CatalogNewsProvider([item()]),date(2023,2,1),date(2023,2,3),now=NOW)
    result['ledger'][0]['cash_after']=-123
    assert sim == baseline


@pytest.mark.parametrize('prompt_type',['snapshot','validation','concept'])
def test_markdown_required_sections_and_hypothesis(source,prompt_type):
    sim,market=source
    packet=build_snapshot(sim,market,CatalogNewsProvider([item()]),date(2023,2,1),date(2023,2,3),now=NOW,hypothesis='반증 가능한 가설')
    text=markdown(packet,prompt_type)
    for expected in ['Test ETF','2023-02-01','가격 데이터 요약','전략 조건','매매 결과','주요 관련 뉴스',
                     'https://example.org/release','반증 가능한 가설','Daily Ledger']:
        assert expected in text
    if prompt_type=='concept':
        assert '개념 학습 요청' in text
        assert 'Macro → Market → Asset' in text
    else:
        assert '확정 / 유력 / 불확실 / 반증' in text


def test_range_errors_and_price_only_window(source):
    sim,market=source
    with pytest.raises(ValueError,match='시작일'):
        build_snapshot(sim,market,CatalogNewsProvider([]),date(2023,3,1),date(2023,2,1),now=NOW)
    with pytest.raises(ValueError,match='관측값'):
        build_snapshot(sim,market,CatalogNewsProvider([]),date(2022,1,1),date(2022,1,2),now=NOW)
    market.append({**market[-1],'date':'2023-02-06'})
    packet=build_snapshot(sim,market,CatalogNewsProvider([]),date(2023,2,6),date(2023,2,6),now=NOW)
    assert packet['strategy_window'] is None
    assert packet['ledger'] == []
    assert packet['trades'] == []


def test_official_catalog_replay_vs_post(instrument):
    provider=CatalogNewsProvider.from_file(ROOT/'data/news/official_context_catalog.json')
    replay=provider.search_news(instrument,date(2023,1,4),date(2023,4,4),cutoff=NOW)
    post=provider.search_news(instrument,date(2023,1,4),date(2023,4,4),mode='POST_ANALYSIS_MODE',cutoff=NOW)
    assert len(replay)==3
    assert len(post)==4
    assert all(not item.retrospective for item in replay)


def test_currency_explanation_and_initial_fee_drawdown(instrument):
    bar=MarketBar(datetime(2023,2,1),D(100),D(101),D(98),D(99),D(10))
    result=simulate(instrument=instrument,bars=[bar],initial_capital=D(500),costs=CostConfig(fixed_buy_fee=D(1)))
    assert 'USD' in result.ledger[0].explanation
    assert '원' not in result.ledger[0].explanation
    assert result.summary.mdd == D('-0.002')


def test_preopen_current_open_order_is_rejected(instrument):
    bar=MarketBar(datetime(2023,2,1),D(100),D(101),D(98),D(99),D(10))
    with pytest.raises(ValueError,match='AFTER_OPEN_OBSERVED'):
        simulate(instrument=instrument,bars=[bar],initial_capital=D(500),
                 execution=ExecutionConfig(entry_order_timing='PREOPEN'))
