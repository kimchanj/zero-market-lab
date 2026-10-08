from datetime import date
from decimal import Decimal

import pandas as pd
import pytest

from zero_market_lab.simulator.models import Instrument
from zero_market_lab.simulator.strategy_family import STRATEGIES, krx_stock_tick, run_family


def instrument():
    return Instrument("KRX:TEST", "TEST", "Fixture", "KOREAN_EQUITY", "KRX", "KRW",
                      "Asia/Seoul", lot_size=Decimal(1), tick_size=Decimal(100))


def market(changes=None, length=140):
    changes = changes or {}
    days = pd.bdate_range("2025-01-01", periods=length)
    rows = []
    for index, day in enumerate(days):
        opn, high, low, close = changes.get(index, (10000, 10100, 9900, 10000))
        rows.append({"date": day.date(), "open": opn, "high": high, "low": low,
                     "close": close, "volume": 1000})
    return pd.DataFrame(rows)


def compare(frame):
    return run_family(frame, instrument(), frame.iloc[100]["date"], frame.iloc[-1]["date"])


def test_same_data_capital_cost_and_accounting_for_all_family_members():
    report = compare(market())
    assert tuple(report["results"]) == STRATEGIES
    assert report["warmup_observations"] == 100
    for result in report["results"].values():
        assert result["metrics"]["initial_capital"] == 500000
        assert len(result["ledger"]) == 40
        assert result["metrics"]["net_gain"] == pytest.approx(
            result["metrics"]["realized_gain"] + result["metrics"]["unrealized_gain"])
        for row in result["ledger"]:
            assert row["portfolio_value"] == pytest.approx(row["cash"] + row["quantity"] * row["close"])
            assert row["cash"] >= 0 and row["quantity"] == int(row["quantity"])


def test_s0_first_open_buy_and_no_forced_exit():
    result = compare(market())["results"]["S0_BUY_AND_HOLD"]
    assert result["ledger"][0]["action"] == "BUY"
    assert result["ledger"][0]["execution_price"] == 10000
    assert result["metrics"]["completed_trades"] == 0
    assert result["metrics"]["open_trades"] == 1


def test_s1_same_day_tp_not_credited_and_s2_dual_touch_uses_stop():
    frame = market({100:(10000,11000,9800,10000),101:(10000,11000,9500,10500)})
    result = compare(frame)["results"]
    s1 = result["S1_FIXED_TAKE_PROFIT"]
    assert s1["ledger"][0]["action"] == "BUY"
    assert s1["ledger"][0]["ambiguous"]
    assert s1["trades"][0]["exit_date"] == frame.iloc[101]["date"].isoformat()
    assert s1["trades"][0]["exit_reason"] == "TAKE_PROFIT"
    s2 = result["S2_FIXED_TP_SL"]
    assert s2["trades"][0]["exit_reason"] == "STOP_LOSS"
    assert s2["trades"][0]["exit_price"] == 9600
    assert s2["ambiguity_count"] >= 1


def test_s2_same_day_stop_and_s3_twentieth_day_time_stop():
    same_day = compare(market({100:(10000,10300,9400,9800)}))["results"]["S2_FIXED_TP_SL"]
    assert same_day["trades"][0]["entry_date"] == same_day["trades"][0]["exit_date"]
    assert same_day["trades"][0]["exit_reason"] == "STOP_LOSS"
    assert same_day["ledger"][0]["action"] == "BUY+SELL"
    frame = market({100:(10000,10100,9800,10000)})
    s3 = compare(frame)["results"]["S3_FIXED_TP_SL_TIME"]
    assert s3["trades"][0]["holding_days"] == 20
    assert s3["trades"][0]["exit_reason"] == "TIME_STOP"


def test_s2_gap_below_stop_exits_at_open_not_optimistic_stop_price():
    frame = market({100:(10000,10100,9800,10000),101:(9000,9100,8500,8800)})
    trade = compare(frame)["results"]["S2_FIXED_TP_SL"]["trades"][0]
    assert trade["exit_reason"] == "STOP_LOSS"
    assert trade["exit_price"] == 9000


def test_s4_uses_previous_close_and_s5_has_prior_atr_snapshot():
    frame = market({100:(10000,11000,9800,11000),101:(11000,11200,10700,11000)})
    result = compare(frame)["results"]
    s4 = result["S4_TREND_FILTERED_TP_SL_TIME"]
    assert s4["ledger"][0]["action"] != "BUY"  # current close cannot pass today's filter
    assert s4["metrics"]["trend_fail_days"] >= 1
    s5 = result["S5_ATR_ADAPTIVE_EXIT"]
    assert s5["ledger"][0]["action"] == "BUY"
    assert s5["ledger"][0]["target"] is not None
    assert s5["ledger"][0]["stop"] is not None
    changed = market({100:(10000,15000,9800,14000),101:(11000,11200,10700,11000)})
    s5_changed = compare(changed)["results"]["S5_ATR_ADAPTIVE_EXIT"]
    assert s5_changed["ledger"][0]["target"] == s5["ledger"][0]["target"]


def test_s6a_and_s7_close_signals_fill_only_next_open():
    mean_reversion = compare(market({100:(10000,10000,8000,8000),101:(9000,9100,8900,9000)}))
    s6 = mean_reversion["results"]["S6A_PURE_MEAN_REVERSION"]
    assert s6["ledger"][0]["action"] != "BUY"
    assert s6["ledger"][1]["action"] == "BUY"
    assert s6["ledger"][1]["execution_price"] == 9000
    breakout = compare(market({100:(10000,10600,9900,10500),101:(10600,10800,10500,10700)}))
    s7 = breakout["results"]["S7_BREAKOUT_TREND_FOLLOWING"]
    assert s7["ledger"][0]["action"] != "BUY"
    assert s7["ledger"][1]["action"] == "BUY"
    assert s7["ledger"][1]["execution_price"] == 10600


def test_s6b_confirmed_reversal_next_open_and_price_band_tick():
    changes = {97:(10000,10050,9650,9700),98:(9700,9750,9350,9400),
               99:(9400,9450,9050,9100),100:(9100,9600,9000,9500),
               101:(9600,9700,9500,9600)}
    s6b = compare(market(changes))["results"]["S6B_CONFIRMED_REVERSAL"]
    assert s6b["ledger"][0]["action"] != "BUY"
    assert s6b["ledger"][1]["action"] == "BUY"
    assert s6b["ledger"][1]["execution_price"] == 9600
    assert krx_stock_tick(199900) == 100
    assert krx_stock_tick(200000) == 500
