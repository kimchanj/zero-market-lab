# Instrument / ISA / 2026 cost reference

Checked 2026-10-10. This is a source-backed **current reference**, not an automatic historical tax schedule or account-specific fee quote.

| Instrument | Intermediate ISA direct purchase | 2026 sale tax reference |
| --- | --- | --- |
| KRX-listed stock (KOSPI) | Eligible instrument type | Securities transaction tax 0.05% + rural special tax 0.15% = 0.20% |
| KRX-listed stock (KOSDAQ) | Eligible instrument type | Securities transaction tax 0.20% |
| KRX-listed ETF (investment trust) | Eligible instrument type | No securities transaction tax; distribution/holding-period income tax is a different issue |
| US-listed individual stock | Not directly purchasable | Not modeled as an ISA candidate |

Sources: [Mirae Asset intermediate ISA product list](https://securities.miraeasset.com/mw/mks/mks4659/n01.do), [Mirae Asset overseas-stock FAQ](https://securities.miraeasset.com/bbs/board/message/list.do?categoryId=1296&curPage=5&direction=1&listType=1&searchEndDay=14&searchEndMonth=01&searchEndYear=2026&searchStartDay=14&searchStartMonth=01&searchType=2&startId=09pDx~&startPage=1), [2026 Securities Transaction Tax Enforcement Decree §5](https://www.law.go.kr/LSW/lsSideInfoP.do?docCls=jo&joBrNo=00&joNo=0005&lsiSeq=280901&urlMode=lsScJoRltInfoR), [National Assembly Budget Office 2026 tax guide](https://www.nabo.go.kr/board/file/down.do?fid=33319156), [KRX ETF tax rules](https://regulation.krx.co.kr/contents/RGL/03/03060105/RGL03060105.jsp).

`InstrumentCostProfile` separates tax components from brokerage commission and slippage. Its 2026 rates are shown as reference metadata (`applied_to_backtest=false`). The current simulator still uses the **user-configurable research assumptions** recorded in each run. A 1Y–5Y backtest crosses earlier tax periods, so applying 2026 rates to every historical sale would misstate results. Before an official-cost replay is enabled, add a date-indexed tax schedule and verify exchange segment, ETF legal form, product taxation, account commission, and effective dates. ISA account-level tax benefits are outside trade-by-trade market P/L.

The six seeds remain a manually selected research sample. US stocks remain available with the ISA-only UI filter switched off. ISA eligibility indicates product type, not a guarantee of a particular account's trading permissions.
