# Data Strategy

## 의미와 공급자

S&P Dow Jones Indices를 Index 정의 및 Return 유형의 official reference로 사용한다.
공식 [S&P 500 페이지](https://www.spglobal.com/spdji/en/indices/equity/sp-500/)는
Price Return, Total Return, Net Total Return을 구별한다. 확인일: 2026-10-05.

| Series type | 해석 |
| --- | --- |
| S&P500 Price Index | 가격 변화, 배당 수익 제외 |
| S&P500 Total Return Index | 지수 방법론에 따른 배당 재투자 포함 |
| S&P500 Net Total Return Index | 방법론의 원천징수 가정 등을 적용한 배당 재투자 |
| ETF Market Price | 거래소에서 관찰되는 상품 가격 |
| ETF NAV | 순자산가치. 실제 체결가격과 동일하다고 가정하지 않음 |

TR/NTR은 특정 한국 계좌의 세후 성과를 뜻하지 않는다. Adjusted Price라는 이름만으로
TR임을 단정하지 않고 공급자의 조정 방법을 확인한다. TR과 별도 배당 현금을 중복 반영하지 않는다.

[FRED SP500](https://fred.stlouisfed.org/series/SP500)의 2026-10-05 확인 내용:
일별 종가 Price Index로 배당을 포함하지 않고 daily history 제공 범위는 10년이다.
따라서 validation 후보로 사용하되 장기 연구 공급자로 단독 의존하지 않는다.
원자료의 저작권·재배포 제한은 별도 검토하며 공개 Git에 데이터를 자동 포함하지 않는다.

장기 Historical Provider는 **미정**이다. STEP 1에서 공식/라이선스 공급자와 접근 가능한
후보를 기간, PR/TR, 품질, 수정정책, 이용·저장·재배포 조건, 비용 측면에서 비교한다.
특정 공급자를 지금 채택하거나 API의 사용 가능성을 보장하지 않는다.
검증 실패 시 기간 축소와 제약을 기록하거나 중단하며 synthetic data로 연구 기간을 메우지 않는다.

## Provenance와 재현성

각 snapshot에 instrument, series_type, source(URL 및 식별자), retrieval_timestamp(UTC),
start/end_date, frequency, currency, adjusted 여부, adjustment_method, dividend_handling,
source/license_note를 보존한다. 지수 points와 표시 통화도 구분한다.
추가로 dataset_id, raw checksum, timezone/calendar, missing-data policy,
변환 버전·정규화 규칙을 저장한다. raw는 원본 유지, processed는 추적 가능한 파생물이다.
동일 실험의 A/B/C는 같은 snapshot을 사용한다. config, dataset hash, code commit으로 run을 재현한다.

정렬, 날짜 중복, 양수 가격, 빈값, 누락 거래일, 빈 구간, 빈도·통화·시리즈 일치를 검증한다.
휴장일과 누락 데이터를 구별하고 가격을 임의 전방 채움하여 거래하지 않는다.
다른 공급자와 공통 날짜를 대조하고 차이가 조정 방식인지 오류인지 기록한다.
원본 데이터의 수정 가능성을 고려해 재다운로드로 기존 실험 입력을 조용히 교체하지 않는다.

Research는 Real Historical Data, Unit/Engine Test는 결정론적 Synthetic Fixture를 사용한다.
synthetic 결과에는 TEST ONLY를 표시하고 투자 가설의 증거로 보고하지 않는다.
Macro는 향후 관측 대상일과 실제 발표·이용가능 시각, 수정 vintage를 구분해 look-ahead를 방지한다.

## 후속 자산 범위

S&P500 Baseline 이후 TIGER 미국S&P500(360750)을 조사한다.
Daily/Adjusted Market Price, Volume, NAV, Distribution, Inception/Listing Date,
Tracking Index, Fee/TER, Actual Trading Cost, Bid/Ask Spread 가용성,
Tracking Difference, FX Exposure를 공식 상품·거래소 자료로 확인한다.
이번 단계는 상품 사양을 확정하지 않는다. 상장 이전을 실제 ETF 기록으로 만들지 않으며
S&P500과 비교할 때 검증된 공통 데이터 기간을 사용한다.

장기 자산: S&P500, NASDAQ100, Semiconductor, AI/Technology, Global Equity;
Cash/T-Bill, Short Treasury, US 10Y/30Y, Bond ETF; Gold, Commodity, Oil; USD, KRW, USD/KRW.
Macro: FED Policy Rate, Treasury Yield, Inflation, Real Yield, Unemployment, GDP/Growth, USD, Oil.
서로 다른 거래 달력·발표 빈도를 동일 Timeline에 표시하되 미공개 정보를 과거에 배치하지 않는다.
