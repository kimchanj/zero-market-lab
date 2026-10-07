# Goal-Based Investment Simulation and Starting-Date Sensitivity

이 문서는 장기 연구 기능의 설계 기준선이다. 승인된 별도 Prototype v1에서 단일 시작일 Goal Analyzer와
목표선·목표 marker를 최소 구현했지만 STEP 8 전체 완료를 뜻하지 않으며 STEP 5의 완료 판정도 변경하지 않는다.
Sensitivity Analyzer와 반복 시작일 분석은 각각의 승인된 후속 단계에서 구현하고 검증한다.

## 연구 목적과 세 축

ZERO MARKET LAB은 최종 자산가치만 비교하지 않는다. 같은 적립 조건에서 목표에 도달하는 경로, 걸린 시간,
목표 전 위험, 시작 시점에 따른 재현성을 함께 분석한다.

1. **Strategy Comparison**: 동일한 데이터·현금흐름·체결 가정에서 A/B/C의 경로와 결과를 비교한다.
2. **Goal-Based Simulation**: 정해진 목표를 달성했는지, 언제 달성했는지, 그 전까지 어떤 위험을 겪었는지 분석한다.
3. **Starting-Date Sensitivity**: 투자 시작일을 반복 이동해 결과가 특정 진입 시점이나 시장 국면에 의존하는지 공격한다.

전략의 품질은 Return, Goal, Risk, Behavior, Stability의 다섯 축으로 본다. 높은 최종 수익이나 높은 목표
달성률 하나만으로 우월성을 판정하지 않는다.

## Goal-Based Simulation 정의

향후 입력 계약 후보는 다음과 같다.

| 입력 | 의미 |
| --- | --- |
| 투자 시작일 | 자금 투입과 전략 실행을 시작할 시장 관측 범위의 기준 |
| 초기 투자금 | 첫 실행일에 투입할 금액. 현재 Case #01 기본값 0이며 향후 입력으로 추가 |
| 월 적립금 | 각 월의 적립 정책에 따라 유입되는 현금 |
| 목표수익률 | 선택한 목표금액 정의에 적용할 비율 |
| 최대 투자기간 | 목표 도달을 관찰할 최대 기간과 censoring 기준 |

향후 출력 계약 후보는 누적 납입금, 포트폴리오 가치, 투자손익, 명시된 분모의 수익률, 목표수익률,
목표금액, 목표 도달 여부, 최초 도달일, 도달기간, 목표 도달 전 최대낙폭, 최종 상태다. 금액은
`simulation currency` 단위를 기본으로 하며, 실제 KRW나 USD로 확정된 경우에만 해당 통화를 표시한다.

### 목표수익률 분모 — 결정 유보

월 적립식 투자에서는 목표수익률의 분모가 시간에 따라 바뀐다. 아래 세 대안을 구현 전에 별도 ADR 또는
실험 설계에서 확정한다.

- **A. 누적 납입금 기준**: `target_value(t) = cumulative_contribution(t) × (1 + target_return)`.
- **B. 초기 투자금 기준**: 초기 투자금에 목표수익률을 적용한다. 월 적립금의 역할을 별도로 정의해야 한다.
- **C. Money-weighted 기준**: 현금흐름 시점을 반영한 XIRR/MWR 목표로 정의한다.

현재는 어느 월 적립식 목표 정의도 기본값으로 채택하지 않는다. Prototype에서 초기 투자금만 있는 경우에는
B 정의를 선택 기능으로 사용할 수 있다. 월 적립금이 양수이면 목표선·목표 달성 판정을 숨기고 누적 납입금,
평가금액과 투자손익을 표시한다. 결과에는 선택한 정의, 분모, 계산 시각을 반드시 표시한다.

## 분석 계층과 이벤트 경계

```text
Market Data
  → Backtest Engine
  → Strategy Result
  → Goal Analyzer
  → Sensitivity Analyzer
  → Visualization
```

Backtest Engine과 Strategy는 주문·체결·포트폴리오 경로를 만든다. Goal Analyzer는 완성된 Strategy Result와
목표 정의를 읽어 최초 달성 여부·시점·기간·목표 전 위험을 계산한다. Sensitivity Analyzer는 시작 시점을
바꾼 여러 독립 run의 Goal Result를 모아 분포와 국면 의존성을 계산한다. 목표 도달 조건을 Strategy의
매수·매도 규칙 안에 넣지 않는다.

`GOAL_REACHED`는 거래가 아니라 **Analysis Event**다. 기존 `BUY`, `SELL`, `TAKE_PROFIT`, `REENTRY`,
`CONTRIBUTION` 같은 Transaction/Portfolio Event와 별도 namespace 또는 event category로 보존한다.
향후 차트는 계산된 목표금액 선과 최초 목표 달성 marker를 표시할 수 있지만, 거래 marker와 같은 의미로
표현하지 않는다.

목표 상태는 다음 세 값으로 구분한다.

| 상태 | 한국어 표시 | 의미 |
| --- | --- | --- |
| `GOAL_REACHED` | 목표 달성 | 유효 관측기간 안에 목표를 최초로 충족 |
| `GOAL_NOT_REACHED` | 목표 미달성 | 요구한 최대 투자기간을 모두 관측했지만 목표에 도달하지 못함 |
| `INSUFFICIENT_HORIZON` | 관측기간 부족 | 데이터 끝 때문에 요구한 최대 투자기간을 끝까지 관측할 수 없음 |

## Starting-Date Sensitivity

첫 구현 후보는 월별 시작점이다. 각 월의 첫 유효 시장 관측일을 투자 시작일로 삼고 동일한 초기 투자금,
월 적립금, 목표, 최대 기간, 실행 가정으로 A/B/C를 반복한다. 주별·분기별·모든 거래일 sampling은 계산량과
관측치 의존성을 검토한 뒤 확장할 수 있다.

집계 후보는 목표 달성률, 평균·중앙값·최소·최대·P25·P75 도달기간, 목표 미달성 수,
관측기간 부족 수, 목표 도달 전 최대낙폭이다. `INSUFFICIENT_HORIZON`을 실패로 합쳐 달성률을 왜곡하지 않고,
분모와 제외 규칙을 함께 표시한다.

A/B/C는 같은 starting-date cohort와 같은 관측 가능 기간에서 비교한다. 목표 달성률뿐 아니라 도달기간 분포,
목표 전 낙폭, 미달성·관측 부족 비율, 시장 국면별 집중도를 함께 본다. 후보 시각화는 다음과 같다.

- 시작일별 결과 timeline
- 시작 연월 × 전략 또는 파라미터 heatmap
- 목표 도달기간 histogram
- 목표 전 최대낙폭과 도달기간 scatter
- A/B/C 달성률·기간·위험 비교표

## 연구 질문

- **RQ-Goal-01**: 같은 납입 조건에서 A/B/C의 목표 달성률은 어떻게 다른가?
- **RQ-Goal-02**: 목표 달성까지 걸린 시간의 중앙값과 분산은 전략별로 어떻게 다른가?
- **RQ-Goal-03**: 더 빠른 목표 달성이 목표 전 최대낙폭 증가와 교환관계를 가지는가?
- **RQ-Goal-04**: 목표 달성 결과가 특정 시작 시점이나 시장 국면에 집중되는가?
- **RQ-Goal-05**: 배당·비용·FX·실제 ETF 차이를 반영한 뒤에도 결론이 유지되는가?

## 반증과 편향 점검

가설에 불리한 결과를 동등하게 기록한다. 목표 미달성, 큰 목표 전 낙폭, 특정 국면에 집중된 성공,
넓은 도달기간 분산은 핵심 반증 증거다. 높은 달성률만으로 안정적인 전략이라고 결론 내리지 않는다.

- **End censoring**: 데이터 끝에 가까운 시작일은 충분한 최대 기간을 갖지 못할 수 있다.
- **Recent-start bias**: 최근 시작 cohort의 짧은 관측을 실패로 오분류하지 않는다.
- **Overlapping observations**: 월별 시작 cohort가 많은 동일 시장 구간을 공유하므로 독립 표본으로 가정하지 않는다.
- **Survivorship bias**: 지수 역사와 현재 구성종목을 재구성한 결과를 구별한다.
- **누락된 현실 조건**: 배당, 비용, slippage, FX를 제외한 결과에는 그 범위를 표시한다.
- **비거래 자산 문제**: S&P500 지수 자체는 거래할 수 없으며 ETF의 추적오차·보수·상장기간과 다르다.

## 한국어 연구 UX와 날짜 표시

화면의 주 언어는 한국어로 한다. 처음 등장하거나 연구 재현에 필요한 영어 용어는 괄호 또는 tooltip로
병기한다. 예: `목표 달성률 (Goal Hit Rate)`, `목표 전 최대낙폭 (Pre-goal MDD)`. 상태값은 내부 enum을
유지하되 화면에는 위 표의 한국어를 먼저 표시한다.

금액은 천 단위 구분과 한국어 친화적 축약 표시를 사용할 수 있으나 `원`을 임의로 붙이지 않는다.
`simulation currency`, KRW, USD를 명확히 구별하고 tooltip이나 상세 표에는 원값과 단위를 보존한다.

시간축 표시는 화면 범위에 따라 적응한다.

- 장기: 연도
- 중기: 연-월
- 단기: 월-일
- hover·선택 상세: 전체 날짜와 한국어 요일, 예: `2026-10-05 (월)`

Hover에는 상세 한국어 날짜, 시장가격, 포트폴리오 가치, 누적 납입금, 투자손익, 해당일 행동·분석 이벤트를
표시한다. **차트 조회 범위 (Chart View Range)**는 화면 확대·축소 상태이고,
**투자 시작일 (Investment Start Date)**은 시뮬레이션 현금흐름과 결과를 바꾸는 입력이므로 별도 상태로 관리한다.

## 구현 유보 항목

Prototype v1은 0 이상 초기 투자금, 월 적립금, 선택적인 초기 투자금 기준 목표, 단일 시작일 Goal Analyzer,
목표 전 최소 MDD, 투자 조건/전략 조건 분리 toolbar와 S&P500/A/B/C/목표/event의 unified dual-axis
chart까지 구현한다. `월 50만원 적립` 대표 preset과 A 기준 전략 평가 card를 제공한다.
Layer toggle은 rendering state만 바꾸며 계산을 다시 실행하지 않는다. 목표 정의 선택기, 일반 Risk Analytics,
Sensitivity Analyzer, starting-date batch runner, heatmap·histogram·scatter는 구현하지 않는다.
이벤트 marker와 Lightweight Charts production migration 역시 현재 STEP 5의 별도 작업이다.
