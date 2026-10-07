# Automatic Strategy Search and Investment Journal

이 문서는 후속 `Strategy Discovery Research Track`의 설계 기준선이다. 현재 STEP 5와 Goal Simulation
Prototype의 구현 범위가 아니다. Search Engine, 후보 생성, 투자일지 UI, Strategy Building Block 리팩터링은
별도 시작 지시와 완료조건이 있을 때 구현한다.

## 최상위 연구 질문과 두 모드

사용자가 투자 시작일, 초기 투자금, 월 추가 투자금, 기대수익률, 목표금액, 최대 투자기간,
허용 가능한 최대 손실을 입력했을 때 다음을 연구한다.

> 이 목표를 더 자주, 더 빠르게, 더 적은 위험으로 달성한 매수·매도 규칙이 과거 데이터에 존재했는가?

- **직접 전략 설정 (Manual Strategy)**: 사용자가 익절·손절·재진입·정기매수 등 규칙을 직접 정한다.
- **자동 전략 찾기 (Automatic Strategy Search)**: 사용자는 목표와 제약을 정하고 시스템이 사전에 허용된
  전략 구성요소와 파라미터 조합을 비교한다.

초기 자동화는 AI가 임의의 규칙을 생성하는 방식이 아니다. 제한된 Strategy Building Block과 명시적인
Parameter Grid를 사용하는 Level 2 Parameter Search부터 시작한다.

## 목표, 제약과 평가

Investment Goal 후보는 목표금액, 목표수익률, 최대 기간, 최대 허용 drawdown, 최대 매매 횟수,
최대 현금 대기기간이다. Hard Constraint를 먼저 적용하고 통과 후보만 Soft Score로 순위를 매긴다.

| 구분 | 예시 |
| --- | --- |
| Hard Constraint | 목표 달성, drawdown ≤ 20%, 매매 횟수 ≤ 20회, 현금 대기 ≤ 6개월 |
| Soft Score | 더 짧은 목표 도달기간, 더 낮은 위험, 더 높은 시작일별 달성률, 더 낮은 복잡도 |

조건을 만족하는 후보가 없으면 결과를 숨기거나 제약을 임의 완화하지 않고
`조건을 만족하는 전략을 찾지 못했습니다.`라고 표시한다. 단일 Best Strategy만 제시하지 않고 상위 후보의
목표 상태·도달일·기간·최종가치·drawdown·매매 횟수·현금 대기·시작일 민감도·검증기간 결과를 비교한다.

초기 Candidate Space 후보는 Take Profit 3/5/7/10/15%, Reentry 즉시/1주/1개월/2개월,
Stop Loss 없음/-5/-10/-15%, 월 정기매수다. Stop Loss와 주 단위 Reentry는 현재 구현되어 있지 않다.
후속 후보는 Moving Average, Momentum, Drawdown Rule, Volatility Rule, Cash Allocation이다.

## 분석 흐름과 책임 경계

```text
Investment Goal
  → Candidate Generator
  → Backtest Engine
  → Goal Analyzer
  → Risk Analyzer
  → Sensitivity Analyzer
  → Constraint Filter
  → Scoring / Candidate Ranking
```

`StrategySearchEngine`은 이 흐름을 조정하는 Research 계층이다. Backtest Engine에 탐색, 점수, 순위를
넣지 않는다. Candidate Generator는 처음에는 유한한 Grid Search를 사용하며 Random Search,
Bayesian Optimization, Evolutionary Search는 후보 공간과 계산비용이 정당화될 때만 검토한다.

자동화 수준은 다음처럼 구분한다.

1. **Level 1 — Manual Strategy**: 사람이 규칙과 파라미터를 선택한다.
2. **Level 2 — Parameter Search**: 고정된 전략 구조에서 허용된 파라미터를 탐색한다.
3. **Level 3 — Strategy Structure Search**: Entry, Exit, Take Profit, Stop Loss, Reentry,
   Contribution, Position Sizing, Cash Rule을 조합한다.

현재 A/B/C는 즉시 Building Block 구조로 바꾸지 않는다. Entry Rule, Exit Rule, Position Sizing Rule,
Reentry Rule 등의 조합은 호환 계약과 회귀 검증을 갖춘 별도 Architecture Evolution으로 다룬다.

## 사후 최적 경로와 실전 가능 전략

전체 미래 가격을 사용한 결과는 `사후 최적 경로 (Theoretical Upper Bound)`로만 표시한다.
각 시점까지 관찰 가능한 데이터로 결정한 `실전 가능 전략`과 UI, 결과표, 데이터 타입을 분리한다.
사후 최적 경로는 Strategy Candidate 또는 실전 수익 가능성으로 해석하지 않는다.

각 실전 후보의 signal은 해당일 또는 그 이전 정보만 사용한다. Candidate를 Training Period에서 탐색하고
고정한 뒤 Validation Period에서 평가한다. 이후 Walk-Forward Validation을 검토한다. 선택된 후보는
월별 시작 시점에 다시 실행해 Goal Hit Rate, Median/Worst Time to Goal, Failure Rate,
Max Drawdown Distribution을 평가한다.

## 과최적화 통제

Look-Ahead Bias, Data Snooping, Parameter Overfitting, Multiple Testing, Regime Dependence,
Selection Bias를 실행마다 기록한다. Training 순위는 성공 판정이 아니다. Validation, 시작 시점,
시장 국면 검증을 통과해야 하며 탐색한 후보 수와 제외된 후보도 보존한다.

비슷한 목표·위험 결과에서는 규칙 수, 사용 지표 수, 파라미터 수로 정의한 Strategy Complexity가 낮은
후보를 선호하는 penalty를 검토한다. 복잡도 정의와 가중치는 결과를 본 뒤 조정하지 않고 사전에 저장한다.

## Investment Journal과 설명 가능한 행동

직접 전략과 자동 후보의 행동은 공통 Investment Journal로 기록한다. 최소 필드는 날짜, 한국어 요일,
전략과 버전, 행동, 시장가격, 매수·매도 금액, 수량, 현금, 평가금액, 총 투입금, 손익, 수익률,
행동 이유, 조건값, 임계값, 발생시킨 rule ID다.

행동 taxonomy 후보는 투자 시작, 정기매수, 추가매수, 익절, 전량매도, 부분매도, 재진입, 현금대기,
목표달성이다. 목표달성은 Analysis Event라는 기존 경계를 유지한다. 투자일지는 기존 Event Log와 Daily State를
사람이 읽는 형식으로 결합한 projection이며 독립적인 회계 원장이 아니다.

향후 `Investment Journal → Chart Navigation → Event Explanation` 연결을 제공한다. 행을 선택하면 차트가
해당 날짜로 이동하고 marker, 당시 시장가격·Portfolio 상태·행동 이유를 함께 강조한다. journal row는
원본 event ID와 state date를 보존해 화면과 근거 로그를 역추적할 수 있어야 한다.

## 한국어 UI 용어

| 내부/영문 용어 | 한국어 우선 표시 |
| --- | --- |
| Automatic Strategy Search | 자동 전략 찾기 |
| Investment Goal | 투자 목표 |
| Target Value | 목표금액 |
| Expected Return | 목표 수익률 |
| Maximum Drawdown | 최대 하락폭 |
| Trade Count | 매매 횟수 |
| Strategy Candidate | 전략 후보 |
| Backtest | 과거 데이터 시뮬레이션 |
| Validation | 검증 |
| Investment Journal | 투자일지 |
| Reason | 행동 이유 |

내부 식별자와 영어 연구 용어는 tooltip이나 괄호로 병기해 재현성을 유지한다.

## 장기 제품 정의

ZERO MARKET LAB은 차트 뷰어에 머물지 않는다. 투자 목표를 입력하고 과거 시장에서 제한된 전략 후보를
실험해 행동 시점과 이유, 자산 경로, 목표 달성 가능성, 위험, 시작 시점 민감도, 검증기간 재현성을 함께
공격하는 투자 전략 실험실을 지향한다. 과거 최적 후보는 미래 성과 보장이 아니며 조건을 만족하지 못한
결과도 동일하게 보존한다.
