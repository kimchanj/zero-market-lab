from datetime import datetime
from decimal import Decimal
import json

import pytest

from zero_market_lab.simulator.accumulation import run_accumulation
from zero_market_lab.simulator.models import CostConfig, Instrument, MarketBar
from scripts.build_pages_demo import build_site
from zero_market_lab.simulator.service import run_simulation
from zero_market_lab.research.snapshot import build_snapshot, markdown
from zero_market_lab.research.news import CatalogNewsProvider


def fixture_bars(dates=("2026-01-02", "2026-02-02", "2026-03-02"), prices=(10000, 20000, 25000)):
    return [MarketBar(datetime.fromisoformat(day), *[Decimal(price)]*4, volume=Decimal(100))
            for day, price in zip(dates, prices)]


def fixture_instrument():
    return Instrument("TEST", "TEST", "Fixture", "EQUITY", "KRX", "KRW", "Asia/Seoul",
                      lot_size=Decimal(1), tick_size=Decimal(1))


def test_monthly_integer_shares_cash_carry_and_external_flows():
    result = run_accumulation(fixture_instrument(), fixture_bars(), Decimal(0),
                              Decimal(50000), CostConfig(), "PERIODIC_CONTRIBUTION")
    rows = result["ledger"]
    assert [row["purchase_quantity"] for row in rows] == [5, 2, 2]
    assert [row["cash_after"] for row in rows] == [0, 10000, 10000]
    assert [row["total_contributions"] for row in rows] == [50000, 100000, 150000]
    assert rows[-1]["position_qty_after"] == 9
    assert rows[-1]["portfolio_value"] == 235000
    assert result["summary"]["net_profit"] == 85000
    assert result["summary"]["net_return"] == pytest.approx(85000 / 150000)
    assert result["summary"]["average_purchase_price"] == pytest.approx(140000 / 9)
    assert len(result["cashflows"]) == 3
    assert len(result["chart"]["markers"]) == 3
    for row in rows:
        assert row["portfolio_value"] == pytest.approx(row["cash_after"] + row["position_qty_after"] * row["close"])
        assert row["cumulative_gain"] == pytest.approx(row["portfolio_value"] - row["total_contributions"])


def test_first_available_observation_when_period_starts_mid_month_and_holiday():
    result = run_accumulation(fixture_instrument(),
                              fixture_bars(("2026-01-15", "2026-01-16", "2026-02-02"), (10000, 11000, 20000)),
                              Decimal(0), Decimal(50000), CostConfig(), "PERIODIC_CONTRIBUTION")
    assert [item["date"] for item in result["cashflows"]] == ["2026-01-15", "2026-02-02"]
    assert result["ledger"][1]["contribution_amount"] == 0


def test_buy_fee_is_not_a_contribution_and_lump_sum_has_one_buy():
    costs = CostConfig(buy_fee_rate=Decimal("0.001"))
    result = run_accumulation(fixture_instrument(), fixture_bars(), Decimal(50000),
                              Decimal(0), costs, "LUMP_SUM_BUY_HOLD")
    assert result["summary"]["total_contributions"] == 50000
    assert result["summary"]["buy_count"] == 1
    assert result["summary"]["total_buy_fees"] == 40
    assert result["ledger"][0]["cash_after"] == 9960
    assert result["ledger"][-1]["position_qty_after"] == 4
    assert result["ledger"][-1]["portfolio_value"] == pytest.approx(4 * 25000 + 9960)


def test_periodic_initial_capital_is_invested_when_monthly_amount_is_zero():
    result = run_accumulation(fixture_instrument(), fixture_bars(), Decimal(50000),
                              Decimal(0), CostConfig(), "PERIODIC_CONTRIBUTION")
    assert result["ledger"][0]["purchase_quantity"] == 5
    assert result["summary"]["total_contributions"] == 50000


def test_pages_artifact_is_synthetic_and_read_only(tmp_path):
    site = build_site(tmp_path / "site", end=datetime(2020, 10, 7).date())
    html = (site / "index.html").read_text(encoding="utf-8")
    assert "ZML_STATIC_DEMO=true" in html
    assert 'src="research.js"' not in html
    assert not (site / "generated").exists()
    assert not (site / "research_input.json").exists()
    assert "/api/" not in (site / "chart.js").read_text(encoding="utf-8")
    for name in ("tiger_data.js", "simulation_data.js"):
        content = (site / name).read_text(encoding="utf-8")
        assert '"synthetic":true' in content
        assert "Daum Finance" not in content


def test_periodic_service_result_can_feed_research_snapshot():
    market = [{"date": day, "open": price, "high": price, "low": price,
               "close": price, "volume": 100} for day, price in
              (("2026-01-02", 10000), ("2026-02-02", 20000), ("2026-03-02", 25000))]
    instrument = fixture_instrument().__dict__.copy()
    instrument["lot_size"] = instrument["tick_size"] = "1"
    bundle = {"market": market, "simulation": {"instrument": instrument,
              "costs": {"buy_fee_rate": "0", "sell_fee_rate": "0", "sell_tax_rate": "0",
                        "fixed_buy_fee": "0", "fixed_sell_fee": "0", "label": "TEST"}}}
    result = run_simulation(bundle, {"strategy_id": "PERIODIC_CONTRIBUTION", "start": "2026-01-01",
                                     "end": "2026-03-31", "initial_capital": "0",
                                     "contribution_amount": "50000"})
    packet = build_snapshot(result, market, CatalogNewsProvider([]),
                            datetime(2026, 1, 1).date(), datetime(2026, 3, 31).date())
    assert "PERIODIC_CONTRIBUTION" in markdown(packet)
    assert packet["strategy_window"]["external_contributions_in_window"] == 150000
    assert json.dumps(result)
