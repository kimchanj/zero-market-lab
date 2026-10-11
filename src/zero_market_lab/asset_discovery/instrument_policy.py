"""Current instrument reference policy; historical execution costs stay explicit.

The reference rates are not silently applied to backtests spanning prior tax
periods. Broker commissions remain account-specific user inputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


ISA_SOURCE = "https://securities.miraeasset.com/mw/mks/mks4659/n01.do"
ISA_FOREIGN_SOURCE = "https://securities.miraeasset.com/bbs/board/message/list.do?categoryId=1296&curPage=5&direction=1&listType=1&searchEndDay=14&searchEndMonth=01&searchEndYear=2026&searchStartDay=14&searchStartMonth=01&searchStartYear=2025&searchType=2&startId=09pDx~&startPage=1"
STOCK_TAX_SOURCE = "https://www.law.go.kr/LSW/lsSideInfoP.do?docCls=jo&joBrNo=00&joNo=0005&lsiSeq=280901&urlMode=lsScJoRltInfoR"
STOCK_TOTAL_SOURCE = "https://www.nabo.go.kr/board/file/down.do?fid=33319156"
ETF_TAX_SOURCE = "https://regulation.krx.co.kr/contents/RGL/03/03060105/RGL03060105.jsp"


@dataclass(frozen=True)
class InstrumentCostProfile:
    instrument_type: str
    exchange_segment: str
    buy_fee_rate: Decimal | None
    sell_fee_rate: Decimal | None
    sell_tax_components: tuple[tuple[str, Decimal], ...]
    slippage_rate: Decimal | None
    effective_date: date
    source_note: str
    version: str = "reference-2026-01"

    def as_dict(self) -> dict:
        return {"instrument_type": self.instrument_type,
                "exchange_segment": self.exchange_segment,
                "buy_fee_rate": None if self.buy_fee_rate is None else float(self.buy_fee_rate),
                "sell_fee_rate": None if self.sell_fee_rate is None else float(self.sell_fee_rate),
                "sell_tax_components": {name: float(rate) for name, rate in self.sell_tax_components},
                "slippage_rate": None if self.slippage_rate is None else float(self.slippage_rate),
                "effective_date": self.effective_date.isoformat(),
                "source_note": self.source_note, "version": self.version,
                "applied_to_backtest": False}


def current_cost_reference(instrument_type: str, exchange_segment: str) -> InstrumentCostProfile | None:
    """Verified 2026 transaction-tax reference; not a complete historic schedule."""
    taxes = {
        ("KRX_STOCK", "KOSPI"): (("securities_transaction_tax", Decimal("0.0005")),
                                   ("rural_special_tax", Decimal("0.0015"))),
        ("KRX_STOCK", "KOSDAQ"): (("securities_transaction_tax", Decimal("0.002")),),
        ("KRX_ETF", "KRX"): (),
    }
    key = (instrument_type, exchange_segment)
    if key not in taxes:
        return None
    source = (ETF_TAX_SOURCE if instrument_type == "KRX_ETF" else
              STOCK_TAX_SOURCE + " ; " + STOCK_TOTAL_SOURCE)
    return InstrumentCostProfile(instrument_type, exchange_segment, None, None, taxes[key],
                                 None, date(2026, 1, 1), source)
