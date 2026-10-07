# Data Strategy

## Future Cross-Asset data contract

Cross-Asset 연구는 지표 관찰과 투자성과 series를 분리한다. 기존 FRED `SP500` Price Index와 `VIXCLS`는
시장·위험 관찰에 사용한다. Treasury yield는 bond price/return이 아니므로 Hedge Effectiveness 입력으로
사용하지 않는다. 투자 가능한 성과 비교 후보는 동일 adjusted-price 계약의 SPY/TLT/GLD이며 provider 조정,
분배금, 보수, 시작일과 라이선스를 검증한 뒤 확정한다. 충분한 역사의 total-return index가 확보되면 ETF
proxy와 별도 series로 등록한다.

각 series는 instrument, source/provider, series type, currency, frequency, timezone/close convention,
adjusted status, dividend/interest handling, retrieval timestamp와 snapshot/hash를 보존한다. Daily return
correlation과 첫 normalized chart는 공통 유효 관측일 inner join을 기본으로 한다. Forward fill은 최대 gap과
휴장 의미를 정의한 별도 정책 없이는 사용하지 않는다. 상세 기준은
[Cross-Asset & Hedge Research](cross-asset-hedge-research.md)에 기록한다.

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

## STEP 1 실행 — FRED Validation Provider

2026-10-05 확인. 공급자 선택은 사용자 지시 및 공식 출처·명확한 PR 의미·접근 가능한 CSV에 근거한다.
공식 graph CSV download를 requests로 호출하며 unofficial wrapper를 사용하지 않는다.
이는 인증된 API의 가용성/SLA를 보장하지 않는 다운로드 경로다. 형식 변경 시 명시적 schema 오류로 중단한다.

| 항목 | 실행 결과 |
| --- | --- |
| Snapshot | 20261005T034500658318Z |
| 요청 | 2000-01-01~2026-10-02 (포함); 완료된 미국 거래일을 종료일로 선택 |
| 실제 | 2016-10-03~2026-10-02 |
| 행 수 | 원본 2,610 / 유효 종가 2,514 / 명시적 결측 96 |
| 의미 | SP500, PRICE_RETURN, DAILY_CLOSE, 배당 제외, USD 표시 지수 points |
| raw | data/raw/20261005T034500658318Z/fred_sp500.csv |
| metadata | 같은 폴더 fred_sp500.metadata.json 및 request.json |
| processed | data/processed/20261005T034500658318Z/sp500_price_daily.parquet |
| chart | artifacts/20261005T034500658318Z/sp500_price_daily.html |

빈 데이터·날짜 파싱·중복·오름차순·null/비수치/무한/0/음수 close·기간 경계·행 수를 검증한다.
실제 검증 PASS, 요청보다 늦은 시작 및 96개 결측 제외 경고. 주말·7일 초과 간격 경고는 없었다.
원본 bytes와 SHA-256, UTC 조회시각, 요청 URL, 실제 기간, 정규화 버전 및 제외 날짜를 보존한다.
Parquet를 다시 읽어 DataFrame 일치도 확인했다. 원본을 덮어쓰지 않는다.
정규화는 빈 문자열/점 표기만 제외하며 잘못된 숫자·중복·역순을 고치지 않고 실패시킨다.

한계: 결측일이 모두 휴장일임을 거래소 달력으로 증명한 것은 아니다. 짧은 누락은 gap warning으로 잡히지 않을 수 있다.
구조 PASS는 전 거래일 완전성·외부 공급자 대조·경제적 정확성 인증이 아니다.
현재는 단일 공급자 데이터이며 교차 검증은 후속 과제다. TR/배당/ETF 가격으로 해석하지 않는다.

## 장기 Historical Provider 후보 비교 (미채택, 2026-10-05)

아래는 공식 문서를 확인한 2개 후보이며 실제 다운로드/유료 계약 검증은 하지 않았다.
확인되지 않은 상품별 필드는 미확인으로 기록한다.

| 기준 | S&P DJI 직접 공급 | EODData |
| --- | --- | --- |
| History length | 역사 지수 level 제공; S&P500 각 series의 최초 일자는 계정 reference 조회/견적 확인 필요 | 상품은 최대 30년 EOD 이력 광고; SPX 개별 최초 일자/완전성 확인 필요 |
| Daily | EOD 제공 | EOD 제공 |
| Price Return / Total Return | 공식 PR/TR/NTR 정의; 정확한 구독 series와 권한 확인 필요 | SPX PR 식별 및 TR 별도 제공 여부 계약·샘플 확인 필요 |
| OHLC | 조사한 API 개요는 level 중심; OHLC 미확인 | ASCII 가격 데이터 제공; SPX의 실제 OHLC 필드·역사 구간 확인 필요 |
| Adjusted / dividend | PR 배당 제외, TR/NTR은 방법론별; ETF adjusted price와 별개 | 일반 주식 EOD는 split-adjusted 설명; 지수 PR/TR·배당 처리에 이 설명을 전용하지 않음 |
| API / download | 인증 REST JSON, SFTP, SPICE; Data Services 계정 필요 | 공식 API, 구매한 이력 ZIP/ASCII download |
| License / usage | 구독·데이터 라이선스 협의 필요, 공개 재배포 허가 미확인 | 일반 membership은 개인 이용, 웹 표시·상업 이용 별도 라이선스; 무단 재배포 금지 |
| Automation | 공식 인증 API는 장점; 실제 rate limit/SLA/복구 미검증 | 공식 API는 장점; plan별 호출 제한, 수정·복구 안정성 미검증 |
| Free / paid | 구독 계약형; 무료 장기 다운로드로 가정하지 않음 | 무료 tier와 유료 membership/역사 데이터 구매; 장기 무료로 가정하지 않음 |
| 판단 | 원제공자 정의·provenance 강점, 비용/계약 확인 필요 | 접근 방식·가격표 공개가 장점, SPX 의미와 품질 추가 검증 필요 |

근거: [S&P DJI API](https://www.spglobal.com/spdji/en/landing/topic/api-data-solutions/),
[S&P500 정의](https://www.spglobal.com/spdji/en/indices/equity/sp-500/),
[EODData Historical](https://www.eoddata.com/products/historicaldata.aspx),
[EODData Membership/사용조건](https://www.eoddata.com/products/default.aspx),
[EODData 공식 API](https://api.eoddata.com/).

장기 provider는 계속 미정이다. 구독 전 SPX sample, PR/TR series ID, 시작일·누락·수정정책,
OHLC, 로컬 보관 및 파생 결과 공개 권한, 자동화 제한을 검증해야 한다. FRED의 기간 제한을 우회하거나
미검증 wrapper로 장기 기록을 연결하지 않는다. 이번 단계에서 구매·계약·장기 공급자 채택은 하지 않았다.

## TIGER 360750 Actual OHLCV Track V2

2026-10-06 기준 상세한 source selection, raw/adjusted 구분, 1,508-row validation, Yahoo 교차검증과
missing-session 정책은 [TIGER ETF V2 Foundation](tiger-etf-v2-foundation.md)에 기록했다. KRX 자동
다운로드는 현재 인증이 필요해 Daum `adjusted=false`를 보조 공급자로 사용한다. 이 데이터는 실제 ETF
execution 연구용이며 FRED S&P500 benchmark history와 결합하지 않는다.
