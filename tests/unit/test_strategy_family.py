from datetime import date
from decimal import Decimal

import pandas as pd
import pytest

from zero_market_lab.simulator.models import CostConfig, Instrument
from zero_market_lab.simulator.strategy_family import (
    FamilyConfig, FixedTakeProfitConfig, FixedStopConfig, STRATEGIES, krx_stock_tick, run_family,
    required_gain_to_recover,
)


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
    for name, result in report["results"].items():
        if name in {"S1_TREND_FILTERED_TAKE_PROFIT", "S2_TREND_FILTERED_TP_SL"}:
            assert result["status"] == "INSUFFICIENT_DATA"
            continue
        assert result["metrics"]["initial_capital"] == 500000
        assert len(result["ledger"]) == 40
        assert result["metrics"]["net_gain"] == pytest.approx(
            result["metrics"]["realized_gain"] + result["metrics"]["unrealized_gain"])
        assert result["metrics"]["max_drawdown_amount"] >= 0
        if result["open_position"]:
            assert result["open_position"]["unrealized_pnl"] == pytest.approx(
                result["metrics"]["unrealized_gain"])
            assert result["open_position"]["unrealized_return"] == pytest.approx(
                result["metrics"]["open_unrealized_return"])
            assert result["open_position"]["worst_marked_pnl"] <= 0
            assert result["open_position"]["worst_marked_pnl"] <= result["open_position"]["unrealized_pnl"]
        else:
            assert result["metrics"]["open_worst_marked_pnl"] is None
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


def test_s1_three_percent_changes_only_s1_and_keeps_five_percent_default():
    frame = market({100: (10000, 10300, 9800, 10000),
                    101: (10000, 10300, 9800, 10000)})
    five = compare(frame)
    three = run_family(frame, instrument(), frame.iloc[100].date, frame.iloc[-1].date,
                       FamilyConfig(s1=FixedTakeProfitConfig(Decimal('-1'), Decimal('3'))))
    assert five['results']['S1_FIXED_TAKE_PROFIT']['metrics']['completed_trades'] == 0
    assert three['results']['S1_FIXED_TAKE_PROFIT']['metrics']['completed_trades'] > 0
    assert five['results']['S0_BUY_AND_HOLD']['metrics'] == three['results']['S0_BUY_AND_HOLD']['metrics']
    assert five['s1_config']['take_profit_pct'] == 5
    assert three['s1_config']['take_profit_pct'] == 3


def test_family_cost_breakdown_and_high_turnover_reduce_net_result():
    frame = market({index: (10000, 10600, 9800, 10000) for index in range(100, 140)})
    zero = run_family(frame, instrument(), frame.iloc[100].date, frame.iloc[-1].date,
                      FamilyConfig(costs=CostConfig()))['results']['S1_FIXED_TAKE_PROFIT']
    costed = run_family(frame, instrument(), frame.iloc[100].date, frame.iloc[-1].date,
                        FamilyConfig(costs=CostConfig(buy_fee_rate=Decimal('0.001'),
                                                      sell_fee_rate=Decimal('0.001'),
                                                      sell_tax_rate=Decimal('0.001')),
                                     slippage_rate=Decimal('0.001')))['results']['S1_FIXED_TAKE_PROFIT']
    metrics = costed['metrics']
    assert metrics['completed_trades'] >= 5
    assert metrics['net_return'] < zero['metrics']['net_return']
    assert metrics['total_trading_cost'] == pytest.approx(sum(metrics[key] for key in (
        'total_buy_fee', 'total_sell_fee', 'total_tax', 'total_slippage')))
    for trade in costed['trades']:
        assert trade['gross_profit'] - trade['net_profit'] == pytest.approx(trade['cost'])
    s0 = run_family(frame, instrument(), frame.iloc[100].date, frame.iloc[-1].date,
                    FamilyConfig(costs=CostConfig(buy_fee_rate=Decimal('0.001'),
                                                  sell_fee_rate=Decimal('0.001'),
                                                  sell_tax_rate=Decimal('0.001')),
                                 slippage_rate=Decimal('0.001')))['results']['S0_BUY_AND_HOLD']['metrics']
    assert s0['total_buy_fee'] > 0 and s0['total_slippage'] > 0
    assert s0['total_sell_fee'] == s0['total_tax'] == 0


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


def test_affordability_includes_rounded_fee_and_records_blocked_reentry():
    from zero_market_lab.simulator.execution import ConfigurableFeeModel, affordable_quantity
    fees = ConfigurableFeeModel(CostConfig(buy_fee_rate=Decimal("0.01")), 0)
    assert affordable_quantity(Decimal(10000), Decimal(10000), Decimal(1), fees, Decimal(0)) == 0
    assert affordable_quantity(Decimal(10100), Decimal(10000), Decimal(1), fees, Decimal(0)) == 1
    prices = market({100: (10000, 10100, 9800, 10000),
                     101: (10000, 11000, 9900, 10700),
                     102: (600000, 601000, 590000, 600000)})
    result = compare(prices)["results"]["S1_FIXED_TAKE_PROFIT"]
    assert result["metrics"]["completed_trades"] >= 1
    blocked = [event for event in result["affordability_events"]
               if event["reason"] == "REENTRY_BLOCKED_BY_CAPITAL"]
    assert blocked and blocked[0]["available_cash"] < blocked[0]["required_cash"]
    assert blocked[0]["required_qty"] == 1


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


def test_ma200_filter_passes_only_prior_rising_trend():
    from zero_market_lab.simulator.entry_filter import MA200TrendFilter
    entry_filter = MA200TrendFilter()
    assert entry_filter.allows(pd.Series({"close_prior": 110, "ma200_prior": 100,
                                          "ma200_prior_5ago": 99}))
    assert not entry_filter.allows(pd.Series({"close_prior": 90, "ma200_prior": 100,
                                              "ma200_prior_5ago": 99}))
    assert not entry_filter.allows(pd.Series({"close_prior": 110, "ma200_prior": 100,
                                              "ma200_prior_5ago": 101}))


def test_filtered_s1_blocks_entry_without_using_todays_surge_and_preserves_open_position():
    frame = market(length=270)
    frame.loc[205, ["open", "high", "low", "close"]] = [10000, 30000, 9900, 20000]
    start, end = frame.iloc[205].date, frame.iloc[-1].date
    report = run_family(frame, instrument(), start, end,
                        strategies=("S1_FIXED_TAKE_PROFIT", "S1_TREND_FILTERED_TAKE_PROFIT"))
    plain = report["results"]["S1_FIXED_TAKE_PROFIT"]
    filtered = report["results"]["S1_TREND_FILTERED_TAKE_PROFIT"]
    assert plain["ledger"][0]["action"] == "BUY"
    assert filtered["ledger"][0]["strategy_state"] == "CASH"
    assert filtered["blocked_entries"][0]["blocked_entry_date"] == start.isoformat()
    assert filtered["blocked_entries"][0]["forward_20d_return"] is not None
    assert filtered["metrics"]["blocked_entry_opportunity_count"] >= 1
    assert filtered["metrics"]["cash_ratio"] > 0
    assert filtered["metrics"]["cash_days"] == sum(row["quantity"] == 0 for row in filtered["ledger"])

    rising = market(length=220)
    for i in range(220):
        p = 10000 + i * 100
        rising.loc[i, ["open", "high", "low", "close"]] = [p, p + 100, p - 500, p]
    rising.loc[206:, ["open", "high", "low", "close"]] = [5000, 5100, 4900, 5000]
    result = run_family(rising, instrument(), rising.iloc[205].date, rising.iloc[-1].date,
                        strategies=("S1_TREND_FILTERED_TAKE_PROFIT",))["results"]["S1_TREND_FILTERED_TAKE_PROFIT"]
    assert result["ledger"][0]["action"] == "BUY"
    assert result["ledger"][2]["strategy_state"] == "HOLD"
    assert result["ledger"][2]["quantity"] > 0
    assert result["metrics"]["completed_trades"] == 0


def test_filtered_s2_keeps_exit_policy_and_recovery_requirement():
    frame = market(length=215)
    for i in range(215):
        p = 10000 + i * 100
        frame.loc[i, ["open", "high", "low", "close"]] = [p, p + 100, p - 500, p]
    frame.loc[206, ["open", "high", "low", "close"]] = [28000, 28100, 26000, 27000]
    result = run_family(frame, instrument(), frame.iloc[205].date, frame.iloc[-1].date,
                        FamilyConfig(s2=FixedStopConfig(Decimal(5), Decimal(7))),
                        strategies=("S2_TREND_FILTERED_TP_SL",))["results"]["S2_TREND_FILTERED_TP_SL"]
    assert result["trades"][0]["exit_reason"] == "STOP_LOSS"
    assert result["metrics"]["required_gain_to_recover_pct"] >= 0
    assert required_gain_to_recover(-0.2) == pytest.approx(0.25)


def test_s2_parameter_change_does_not_mutate_s3_or_s4_rules():
    prices = market({100: (10000, 10400, 9800, 10000),
                     101: (10000, 11000, 9200, 10000)}, length=220)
    base = run_family(prices, instrument(), prices.iloc[100].date, prices.iloc[-1].date,
                      strategies=("S2_FIXED_TP_SL", "S3_FIXED_TP_SL_TIME",
                                  "S4_TREND_FILTERED_TP_SL_TIME"))["results"]
    changed = run_family(prices, instrument(), prices.iloc[100].date, prices.iloc[-1].date,
                         FamilyConfig(s2=FixedStopConfig(Decimal(3), Decimal(10))),
                         strategies=("S2_FIXED_TP_SL", "S3_FIXED_TP_SL_TIME",
                                     "S4_TREND_FILTERED_TP_SL_TIME"))["results"]
    assert base["S2_FIXED_TP_SL"]["metrics"] != changed["S2_FIXED_TP_SL"]["metrics"]
    for name in ("S3_FIXED_TP_SL_TIME", "S4_TREND_FILTERED_TP_SL_TIME"):
        assert base[name]["metrics"] == changed[name]["metrics"]


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
