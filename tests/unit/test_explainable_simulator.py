from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from zero_market_lab.simulator import (
    CostConfig,
    FrameOHLCVProvider,
    Instrument,
    MarketBar,
    StrategyParameters,
    required_exit_price,
    simulate,
    compare_results,
)


D = Decimal


@pytest.fixture
def instrument() -> Instrument:
    return Instrument(
        instrument_id="KRX:TEST", symbol="TEST", display_name="Generic ETF",
        asset_class="ETF", market="KRX", currency="KRW", timezone="Asia/Seoul",
        lot_size=D("1"), tick_size=D("1"), fractional_allowed=False,
        trading_calendar="KRX", provider="TEST",
    )


def bar(day: str, *, open: str = "100", high: str = "101", low: str = "98", close: str = "100") -> MarketBar:
    return MarketBar(
        timestamp=datetime.fromisoformat(day), open=D(open), high=D(high), low=D(low),
        close=D(close), volume=D("1000"),
    )


STRATEGY = StrategyParameters(entry_offset_rate=D("0.01"), take_profit_rate=D("0.05"))


def test_entry_filled_and_integer_cash_remainder(instrument: Instrument) -> None:
    result = simulate(
        instrument=instrument, bars=[bar("2024-01-02")],
        initial_capital=D("500"), strategy=STRATEGY,
    )
    row = result.ledger[0]
    assert row.status == "ENTRY_FILLED"
    assert row.execution_price == D("99")
    assert row.position_qty_after == D("5")
    assert row.cash_after == D("5")
    assert row.decision_code == "ENTRY_FILLED"
    assert "당일 저가" in row.explanation


def test_entry_not_filled_is_explained(instrument: Instrument) -> None:
    result = simulate(
        instrument=instrument, bars=[bar("2024-01-02", low="99.5")],
        initial_capital=D("500"), strategy=STRATEGY,
    )
    row = result.ledger[0]
    assert row.status == "WAITING_ENTRY"
    assert row.action == "NONE"
    assert row.position_qty_after == 0
    assert "체결되지 않았습니다" in row.explanation


def test_same_day_entry_exit_is_ambiguous_and_held(instrument: Instrument) -> None:
    result = simulate(
        instrument=instrument,
        bars=[bar("2024-01-02", high="105", low="98", close="100")],
        initial_capital=D("500"), strategy=STRATEGY,
    )
    row = result.ledger[0]
    assert row.status == "AMBIGUOUS"
    assert row.action == "BUY"
    assert row.position_qty_after == D("5")
    assert row.ambiguous is True
    assert row.decisions[-1].result is None
    assert "발생 순서" in row.explanation


def test_take_profit_after_one_day_and_holding_days(instrument: Instrument) -> None:
    result = simulate(
        instrument=instrument,
        bars=[
                bar("2024-01-05"),
                bar("2024-01-08", open="102", high="104", low="101", close="103"),
        ],
        initial_capital=D("500"), strategy=STRATEGY,
    )
    trade = result.trades[0]
    assert trade.status == "CLOSED"
    assert trade.exit_price == D("104")
    assert trade.trading_holding_days == 2
    assert trade.calendar_holding_days == 4
    assert result.ledger[-1].status == "EXIT_FILLED"
    assert result.ledger[-1].trading_holding_days == 2


def test_take_profit_after_multiple_holding_days(instrument: Instrument) -> None:
    result = simulate(
        instrument=instrument,
        bars=[
            bar("2024-01-02"),
            bar("2024-01-03", open="101", high="102", low="100", close="101"),
            bar("2024-01-04", open="102", high="103", low="101", close="102"),
            bar("2024-01-05", open="103", high="104", low="102", close="103"),
        ],
        initial_capital=D("500"), strategy=STRATEGY,
    )
    assert [row.status for row in result.ledger] == [
        "ENTRY_FILLED", "WAITING_TAKE_PROFIT", "WAITING_TAKE_PROFIT", "EXIT_FILLED"
    ]
    assert result.trades[0].trading_holding_days == 4
    assert "목표보다" in result.ledger[1].explanation


def test_take_profit_never_reached_leaves_open_position(instrument: Instrument) -> None:
    result = simulate(
        instrument=instrument,
        bars=[bar("2024-01-02"), bar("2024-01-03", high="103", low="99")],
        initial_capital=D("500"), strategy=STRATEGY,
    )
    assert result.summary.completed_trades == 0
    assert result.summary.open_trades == 1
    assert result.trades[0].status == "OPEN"
    assert result.trades[0].exit_reason == "PERIOD_END_OPEN"
    assert result.ledger[-1].position_qty_after == D("5")


def test_fee_tax_net_profit_and_accounting(instrument: Instrument) -> None:
    costs = CostConfig(
        buy_fee_rate=D("0.01"), sell_fee_rate=D("0.01"), sell_tax_rate=D("0.02")
    )
    result = simulate(
        instrument=instrument,
        bars=[bar("2024-01-02"), bar("2024-01-03", open="102", high="104", low="101", close="103")],
        initial_capital=D("1000"), strategy=STRATEGY, costs=costs,
    )
    trade = result.trades[0]
    assert trade.entry_qty == D("10")
    assert trade.entry_fee == D("10")
    assert trade.exit_fee == D("10")
    assert trade.tax == D("21")
    assert trade.gross_profit == D("50")
    assert trade.net_profit == D("9")
    assert trade.gross_profit - trade.entry_fee - trade.exit_fee - trade.tax == trade.net_profit
    assert result.summary.final_portfolio_value == D("1009")


def test_required_exit_price_meets_minimum_net_return(instrument: Instrument) -> None:
    costs = CostConfig(buy_fee_rate=D("0.001"), sell_fee_rate=D("0.001"))
    price = required_exit_price(
        entry_price=D("100"), quantity=D("10"), buy_fee=D("1"),
        minimum_net_return=D("0.01"), instrument=instrument, costs=costs,
    )
    sell_notional = price * D("10")
    sell_fee = (sell_notional * costs.sell_fee_rate).quantize(D("1"))
    assert (sell_notional - sell_fee - D("1001")) / D("1001") >= D("0.01")


def test_capital_compounds_into_next_trade(instrument: Instrument) -> None:
    compound_strategy = StrategyParameters(entry_offset_rate=D("0.10"), take_profit_rate=D("0.20"))
    bars = [
        bar("2024-01-02", high="101", low="89"),
        bar("2024-01-03", open="105", high="108", low="104", close="107"),
        bar("2024-01-04", high="101", low="89"),
        bar("2024-01-05", open="105", high="108", low="104", close="107"),
    ]
    result = simulate(
        instrument=instrument, bars=bars, initial_capital=D("500"), strategy=compound_strategy,
    )
    assert result.trades[0].capital_after == D("590")
    assert result.trades[1].capital_before == D("590")
    assert result.trades[1].entry_qty == D("6")
    assert result.summary.final_portfolio_value == D("698")


def test_daily_ledger_invariants_and_decision_consistency(instrument: Instrument) -> None:
    result = simulate(
        instrument=instrument,
        bars=[bar("2024-01-02"), bar("2024-01-03", high="103", low="99")],
        initial_capital=D("500"), strategy=STRATEGY,
    )
    for row in result.ledger:
        assert row.cash_after >= 0
        assert row.position_qty_after >= 0
        assert row.portfolio_value == row.cash_after + row.position_qty_after * row.close
        assert row.decision_code == row.decisions[-1].reason_code
        assert row.explanation


def test_frame_provider_and_cross_asset_fractional_smoke() -> None:
    frame = pd.DataFrame({
        "date": ["2024-01-01", "2024-01-02"], "open": [100, 102],
        "high": [101, 104], "low": [98, 101], "close": [100, 103], "volume": [10, 12],
    })
    crypto = Instrument(
        instrument_id="CRYPTO:BTC-KRW", symbol="BTC-KRW", display_name="BTC/KRW",
        asset_class="CRYPTO", market="TEST", currency="KRW", timezone="Asia/Seoul",
        lot_size=D("0.0001"), tick_size=D("1"), fractional_allowed=True,
        quantity_precision=4, trading_calendar="24/7", provider="TEST",
    )
    bars = FrameOHLCVProvider(frame).load_ohlcv(
        crypto, date(2024, 1, 1), date(2024, 1, 2)
    )
    result = simulate(
        instrument=crypto, bars=bars, initial_capital=D("1000"), strategy=STRATEGY,
    )
    assert result.ledger[0].position_qty_after == D("10.1010")
    assert result.summary.completed_trades == 1
    assert result.instrument.symbol == "BTC-KRW"
    assert all("360750" not in row.strategy for row in result.ledger)

    etf = Instrument(
        instrument_id="KRX:TEST-ETF", symbol="TEST-ETF", display_name="Synthetic ETF",
        asset_class="ETF", market="KRX", currency="KRW", timezone="Asia/Seoul",
        lot_size=D("1"), tick_size=D("1"), fractional_allowed=False,
        quantity_precision=0, trading_calendar="KRX", provider="TEST",
    )
    etf_result = simulate(
        instrument=etf, bars=bars, initial_capital=D("1000"), strategy=STRATEGY,
    )
    comparison = compare_results([result, etf_result])
    assert [row.instrument_id for row in comparison] == ["CRYPTO:BTC-KRW", "KRX:TEST-ETF"]
    assert comparison[0].final_portfolio_value == result.summary.final_portfolio_value
    assert comparison[1].open_trades == etf_result.summary.open_trades


def test_invalid_bar_fails_fast(instrument: Instrument) -> None:
    bad = bar("2024-01-02", high="90", low="89", close="100")
    with pytest.raises(ValueError, match="High"):
        simulate(instrument=instrument, bars=[bad], initial_capital=D("500"))


def test_existing_financial_chart_integrates_engine_outputs() -> None:
    root = Path(__file__).resolve().parents[2]
    chart_dir = root / "experiments" / "tiger_etf_v2"
    html = (chart_dir / "index.html").read_text(encoding="utf-8")
    script = (chart_dir / "chart.js").read_text(encoding="utf-8")
    builder = (chart_dir / "build_simulation.py").read_text(encoding="utf-8")
    assert 'id="ledger-table"' in html
    assert 'id="trade-table"' in html
    assert "simulation_data.js" in html
    assert "createSeriesMarkers" in script
    assert "simulation.ledger" in script
    assert "simulation.trades" in script
    assert "zero_market_lab.simulator" in builder
    assert "parameter_search" in builder
