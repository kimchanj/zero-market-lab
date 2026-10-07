# Cross-Asset & Hedge Research Track

이 문서는 S&P500 하락기에 장기국채·금·VIX가 실제로 어떤 관계와 방어 특성을 보였는지 검증하기 위한
별도 연구 Track이다. 현재 STEP 5 Chart Zoom/Pan/Autoscale Critical Gate 통과가 production UI 연결의
선행조건이다. 이번 변경은 설계만 기록하며 Strategy Engine과 production chart layer를 확장하지 않는다.

## 연구 목적과 반증 가능한 질문

핵심 질문은 “S&P500 하락기에 어떤 자산이 실제로 방어 역할을 했으며 그 관계가 Regime에 따라 바뀌었는가?”다.
장기 전체기간 상관 하나로 헤지를 판정하지 않고 2018 Q4, 2020 COVID, 2022 inflation/rate-hike처럼 메커니즘이
다른 하락국면을 분리한다.

- **RQ-HEDGE-01**: S&P500과 장기적으로 낮거나 음의 상관을 보인 자산은 무엇인가?
- **RQ-HEDGE-02**: S&P500 하락일과 주요 drawdown 구간에 양의 수익 또는 낮은 손실을 보인 자산은 무엇인가?
- **RQ-HEDGE-03**: Stock/Bond correlation은 Regime에 따라 얼마나 변하는가?
- **RQ-HEDGE-04**: Gold는 어떤 Regime에서만 헤지 역할을 하는가?
- **RQ-HEDGE-05**: VIX 위험지표와 실제 투자 가능한 VIX 상품 성과는 어떻게 다른가?
- **RQ-HEDGE-06**: 고정·동적 Hedge가 상승기 수익 희생 대비 drawdown을 충분히 줄이는가?

“장기국채는 주식 하락기에 헤지다”라는 가설은 주요 하락기에 동반 하락하고, downside correlation이 지속적으로
양수이며, portfolio drawdown 감소가 없거나 상승기 희생 대비 방어효과가 작으면 반증된다. Gold와 후속
투자 가능 Hedge에도 같은 구조를 적용한다.

## 두 데이터 계약을 분리한다

지표 관찰과 투자성과를 한 표본에 섞지 않는다.

| 역할 | 초기 후보 | Series type | 사용 범위 |
| --- | --- | --- | --- |
| 시장 benchmark | FRED `SP500` | Price index, daily close, 배당 제외 | 기존 시장 관찰과 drawdown 기준 |
| 장기국채 관찰 | 20Y/30Y Treasury yield | Yield, percent | 금리 메커니즘 overlay 전용, hedge return 금지 |
| 위험지표 | FRED `VIXCLS` | Volatility index, daily close | Risk indicator/signal 전용, Buy & Hold 금지 |
| 투자 가능 주식 proxy | SPY adjusted series 후보 | ETF adjusted price | Hedge portfolio 성과 비교 후보 |
| 투자 가능 장기국채 proxy | TLT adjusted series 후보 | ETF adjusted price | 분배금 반영 방식 검증 후 사용 |
| 투자 가능 금 proxy | GLD adjusted series 후보 | ETF adjusted price | 보수·추적오차 포함 proxy |

FRED `SP500`은 daily close Price Index이며 배당을 포함하지 않는다. FRED `VIXCLS`는 옵션가격이 반영한
단기 변동성 기대의 지수다. FRED에서 확인한 신규 Treasury total-return 후보는 현재 장기 검증에 충분한
역사가 없어 바로 채택하지 않는다. 따라서 장기국채 성과는 yield를 가격처럼 사용하지 않고, TLT adjusted
series 또는 충분한 역사의 licensed total-return index를 공급자·조정 방식 검증 후 결정한다.

Normalized 관찰 화면에서 `SP500`과 VIX를 함께 표시할 수 있지만, Hedge Effectiveness 수익률 계산은
SPY/TLT/GLD처럼 동일한 investable adjusted-price 계약으로 맞추는 것을 우선한다. 서로 다른 price/total-return
정의를 사용하면 화면과 결과에 명시하고 성과 우열을 주장하지 않는다.

## MarketSeries와 provenance

`MarketDataProvider`는 symbol을 하드코딩하지 않고 다음 `MarketSeries` metadata를 반환해야 한다.

- stable series ID, symbol, display name, asset class
- provider와 원 source
- instrument / index / ETF 여부
- series type: price, adjusted price, total return, yield, volatility index
- currency, frequency, timezone/close convention
- adjusted status와 dividend/distribution/interest 처리
- observation start/end, retrieval timestamp, snapshot/hash, license note

VIX에는 `investable=false`, Treasury yield에는 `performance_series=false`를 기록한다. 값의 단위가 같아 보여도
metadata contract가 다르면 portfolio return 입력으로 자동 승격하지 않는다.

## 날짜 정렬 정책

원본 series와 누락일을 보존한 뒤 분석 목적별로 alignment를 선택한다.

- **Daily return correlation 기본값**: 같은 날짜에 두 series의 유효 종가가 모두 있는 observation을 inner join한다.
- **Normalized chart 기본값**: 선택 시작일 이후 각 series의 첫 공통 유효 관측일을 100으로 두고 inner join한다.
- **Forward fill**: 시장 휴장 차이의 의미와 최대 허용 gap을 명시한 별도 실험에서만 사용한다. correlation 기본값으로
  무조건 적용하지 않는다.
- 시간대와 close 시점이 다른 금·VIX 자료는 같은 달력 날짜가 동일 정보시점을 뜻하는지 검증한다.

정규화 공식은 `normalized_t = value_t / value_start × 100`이다. 시작값이 0, 음수, NaN이거나 공통 시작
관측이 없으면 오류로 처리한다. 미래값으로 시작점을 대체하지 않는다.

## 분석 계약

기본 상관은 price level이 아니라 aligned daily return으로 계산한다. 최초 rolling window는 60 trading days이며
20/120/252로 확장할 수 있다. `min_periods`와 NaN 수를 결과에 기록한다. Downside Correlation은
`S&P500 daily return < 0`인 공통 관측만 사용하되 표본 수를 함께 표시한다.

S&P500 drawdown은 running peak 대비 `value / running_peak - 1`로 계산한다. 최초 분석 threshold는 -10%이며,
peak→trough→recovery를 하나의 episode로 식별한다. 배경 음영은 episode 기간에만 표시하고 annotation offset이나
event marker를 autoscale 입력에 넣지 않는다.

Hedge Effectiveness 후보는 다음과 같으며 definition version을 부여한 뒤 구현한다.

- S&P500 drawdown episode 중 hedge asset cumulative return의 평균·최악값
- 양의 hedge return episode 수 / 유효 episode 수인 Hedge Success Rate
- 고정 allocation 적용 전후 MDD와 recovery 변화
- 상승기 opportunity cost와 전체기간 return 희생

Correlation이 음수라는 이유만으로 성공으로 판정하지 않는다. VIX level change는 ETF return과 같은 의미로
취급하지 않는다.

Hedge Portfolio 단계의 성공은 Final Portfolio 하나가 아니라 CAGR, MDD, Recovery Time, Goal Hit Rate,
Upside Sacrifice, Hedge Benefit, Time in Market, Strategy Complexity를 함께 본다. 핵심 비교량은 “상승수익을
얼마나 포기하고 손실·회복기간을 얼마나 줄였는가”다.

## FECM / Macro Regime 연결

Hedge 관계를 자산의 고정 속성으로 보지 않는다. `Market Regime → Rate/Liquidity/Inflation Phase → Asset
Correlation Shift → Hedge Effectiveness` 경로를 가설로 둔다. 2022 Stock/Bond 동반 하락은 Inflation Shock과
금리상승이 전통적 growth-shock hedge를 약화했는지 반증하는 특별 Case다. Gold는 inflation뿐 아니라 real
yield와 liquidity 조건을 함께 보고, VIX는 drawdown 설명력과 선행·동행 시차를 분리한다.

## UI와 단계별 구현

production UI 연결 후 layer는 시장(S&P500, Long Treasury, Gold, VIX), 전략(A/B/C), 분석(Target, Event,
Drawdown Shade, Rolling Correlation)으로 그룹화한다. 두 개 이상의 cross-asset을 비교할 때는 기준 100 mode를
우선하고 실제값 mode에서 무리한 다축을 만들지 않는다. Rolling Correlation은 -1~+1 고정축과 0 기준선을 가진
auxiliary pane 후보로 둔다.

0. **HEDGE STEP 0 — Research / Data Design**: 현재 문서, series 후보와 반증·완료조건 확정.
1. **HEDGE STEP 1 — Data Foundation**: series 결정, provider, provenance, alignment fixture.
2. **HEDGE STEP 2 — Normalized Comparison**: 기준 100 pure transform과 isolated chart.
3. **HEDGE STEP 3 — Rolling / Downside Correlation**: return-based 20/60/120/252 window.
4. **HEDGE STEP 4 — Drawdown Hedge Effectiveness**: episode, shade, downside correlation, effectiveness.
5. **HEDGE STEP 5 — Fixed Allocation**: 80/20, 70/20/10, 60/20/20 후보를 별도 portfolio case로 검증.
6. **HEDGE STEP 6 — Dynamic Hedge Research**: drawdown/volatility/trend/correlation-shift signal 연구.
7. **HEDGE STEP 7 — Automatic Hedge Allocation Search**: Goal/Risk/Stability 제약 아래 제한된 weight grid 탐색.

Cross-Asset 관찰을 Strategy Engine에 넣지 않는다. Data/Analytics/Visualization을 먼저 검증한 뒤 고정 allocation,
dynamic strategy 순으로 진행한다. Automatic Search에는 사후 최적 경로가 아니라 사전에 정의된 weight grid만
후보로 제공한다.

## 구현 전 필수 테스트

Normalization start=100, date alignment, missing-date policy, daily return, rolling/downside correlation,
drawdown episode, hedge-period return, hidden layer exclusion, no future-data leakage를 검증한다. 2018 Q4,
2020 COVID, 2022 동반 하락을 고정 regression fixture 또는 snapshot으로 포함한다.
