# ZERO MARKET LAB — META ARCHITECTURE
## FECM 기반 시장 Phase 탐색 · 전략 검증 · 자본 생존 · 투자 시뮬레이션 연구소

Version: v1.0
Status: Parent Architecture
Role: 프로젝트 최상위 설계 기준
Priority: 모든 하위 문서·코드·실험보다 우선

---

# 0. 이 문서의 역할

이 문서는 ZERO MARKET LAB의 최상위 메타 설계도다.

프로젝트의 모든 신규 기능, 리팩터링, 연구, UI, 백테스트,
Paper Trading 및 향후 Portfolio 기능은 이 문서를 먼저 따른다.

하위 구현이 이 문서와 충돌할 경우:

1. 메타 설계의 의도를 우선 확인한다.
2. 기존 코드를 임의로 파괴하지 않는다.
3. 충돌 내용을 사용자에게 보고한다.
4. 필요한 경우 메타 설계를 먼저 수정한 후 구현한다.

이 프로젝트는 단순한 주식 백테스트 프로그램이 아니다.

ZERO MARKET LAB은:

> 시장과 자산의 Cycle / Phase를 관찰하고,
> 유리한 환경에서는 자본을 투입하며,
> 불리한 환경에서는 CASH 상태를 허용하고,
> 틀려도 살아남을 수 있는 위험구조를 설계하고,
> 이를 역사적 데이터 → Rolling → Walk-Forward → Paper Trading으로
> 단계적으로 검증하는 투자 연구 시스템이다.

---

# 1. 프로젝트의 최상위 목적

핵심 질문:

> "불확실한 미래를 예측하지 않고도,
> 현재 관측 가능한 정보만으로
> 자본을 훼손할 가능성이 높은 환경을 피하고,
> 성장 가능성이 나타나는 Phase에 자본을 배치하여,
> 반복 가능한 방식으로 자산을 성장시킬 수 있는가?"

목표는 다음이 아니다.

- 승률 100%
- 항상 수익
- 최고점/최저점 예측
- 특정 종목 추천
- 과거 수익률 최대화
- 자동 Parameter Optimization
- 미래 가격 예측

목표는 다음이다.

- 자본 생존
- 양의 기대값 가능성 검증
- 손실 크기 통제
- 회복 가능성 확인
- 자금 고착 최소화
- 시장 상황에 따른 CASH 허용
- 반복 가능한 투자기회 탐색
- 실제 미래 데이터에서 재검증

---

# 2. 최상위 연구 철학 — FECM

ZERO MARKET LAB은
Fractal Evolutionary Cycle Model(FECM)을
최상위 관찰 프레임으로 사용한다.

FECM은 자연법칙이나 미래예측 공식이 아니다.

검증·반증 가능한:

- 관찰 프레임
- 연구 가설
- 사고 좌표계

로 사용한다.

핵심 축:

1. Time / Cycle
2. Possibility / Branch
3. Lineage / Inheritance

핵심 관찰:

- Cycle
- Phase
- Phase Transition
- Phase Velocity
- Nested Cycle
- Counter-Cycle
- Branching
- Resource / Capital Flow
- Selection
- Inheritance
- New Birth
- Failure
- Falsification

---

# 3. 금융 Layer

ZERO MARKET LAB에서는 다음 Layer를 구분한다.

Civilization / Technology
↓
Economy
↓
Liquidity / Credit
↓
Interest Rate
↓
Industry / Sector
↓
Company
↓
Asset
↓
Price
↓
Financial Product
↓
Portfolio

각 Layer의 Cycle은 서로 다를 수 있다.

따라서:

"현재 시장은 봄이다"

처럼 전체 시장을 하나의 계절로 설명하지 않는다.

예:

KOSPI = Spring
Semiconductor Sector = Summer
Samsung Electronics = Autumn
Another Industry = Spring Candidate

처럼 서로 다른 Phase가 동시에 존재할 수 있다.

---

# 4. Market Phase Engine

ZERO MARKET LAB의 상위 분석 Layer.

역할:

Universe
↓
Phase Detection
↓
Phase Transition Detection
↓
Asset Candidate Discovery
↓
Strategy Engine

Phase Engine은
"매수/매도 전략"보다 상위에 위치한다.

---

# 5. Price Season Model v1

첫 번째 구현은 Price Data 중심으로 제한한다.

Phase:

WINTER

SPRING_CANDIDATE

SPRING

SUMMER

AUTUMN

다섯 상태를 기본으로 연구한다.

---

# 6. WINTER

의미:

가격과 장기 추세가 약한 상태.

초기 Evidence 예:

Close < MA200

MA200 slope < 0

MA50 < MA200

특징:

- 장기 하락
- 약한 상대강도
- 지속적인 자본 훼손 가능성

기본 행동 후보:

CASH
관찰

---

# 7. SPRING_CANDIDATE

가장 중요한 연구 대상.

의미:

아직 상승추세가 확정되지는 않았지만
겨울 상태에서 변화가 시작되는 구간.

Evidence 후보:

- MA50 회복
- MA50 slope 상승
- MA200 하락속도 둔화
- Higher Low
- Drawdown Recovery
- 상대강도 개선
- 거래량/거래대금 변화

주의:

SPRING_CANDIDATE는 매수 추천이 아니다.

Research Candidate다.

---

# 8. SPRING

의미:

겨울에서 회복 방향으로
Phase Transition이 확인되기 시작한 상태.

목표:

초기 상승 Phase를 발견할 수 있는지 검증.

연구항목:

- Spring Candidate → Spring 전환율
- False Spring 비율
- Spring → Summer 전환율
- 평균 전환기간
- 이후 20/60/120 거래일 결과

---

# 9. SUMMER

의미:

상승추세가 비교적 명확하게 확립된 상태.

초기 Evidence 예:

Close > MA200

MA50 > MA200

MA50 slope > 0

MA200 slope > 0

이 구간에서는:

- Trend Following
- Buy & Hold
- Repeated Profit Taking

등 어떤 Strategy가 유리한지 별도로 검증한다.

---

# 10. AUTUMN

의미:

가격 수준은 아직 높을 수 있지만
추세의 힘이 약해지기 시작한 상태.

Evidence 후보:

- MA50 slope 둔화
- 신고가 갱신 실패
- Relative Strength 하락
- Momentum 약화
- MA50 이탈 증가
- MA200 상승속도 감소

중요:

AUTUMN = 즉시 매도

로 고정하지 않는다.

첫 역할:

신규 진입 제한
기존 Position 관리
다른 Spring Candidate 탐색

---

# 11. False Spring

중요한 반증 대상.

흐름:

WINTER
↓
일시적 반등
↓
SPRING처럼 보임
↓
다시 하락
↓
WINTER

Phase Engine은
False Spring을 반드시 측정해야 한다.

Metric:

- Spring Candidate 발생수
- 실제 Spring 전환수
- Summer 도달수
- False Spring 수
- False Spring 비율

---

# 12. Phase는 미래예측이 아니다

Phase Engine은:

"내일 오른다"

를 예측하지 않는다.

목표:

현재까지 관찰된 데이터가
어떤 상태에 가까운지 평가한다.

따라서:

Future Data
Look-Ahead
사후 고점/저점

을 Phase 판정에 사용하면 안 된다.

---

# 13. Capital Rotation 개념

장기적으로 ZERO MARKET LAB은
한 종목 안에서 매매만 반복하지 않는다.

핵심 질문:

> "현재 Autumn으로 이동하는 자산에서 빠져나온 자본은
> 어느 새로운 Spring으로 이동할 수 있는가?"

예:

Asset A
Summer → Autumn

↓ Capital Release

Asset B
Winter → Spring Candidate → Spring

↓

Capital Rotation Candidate

---

# 14. 전체 투자 Architecture

최상위 흐름:

Market / Universe
↓
FECM Market Phase Engine
↓
Asset Discovery
↓
Strategy Engine
↓
Risk Engine
↓
Position Sizing
↓
Execution Model
↓
Portfolio
↓
Ledger
↓
Validation
↓
Paper Trading
↓
Forward Evidence

---

# 15. Asset Discovery

목적:

단순히 과거 수익률이 높은 종목을 찾지 않는다.

찾아야 하는 것:

- 현재 Phase
- 이전 Phase
- Phase Transition Evidence
- Phase 지속기간
- Relative Strength
- Price Behavior
- Liquidity
- Current Affordability
- ISA Eligibility

장기 목표:

"어떤 종목이 지금 Spring으로 전환되고 있는가?"

---

# 16. Strategy Engine

Strategy는 Phase Engine 아래에 위치한다.

현재 주요 Strategy Family:

S0
Buy & Hold

S1
Fixed Take Profit
No Stop

S2
Fixed Take Profit + Stop Loss

S3
S2 + Time Stop

S4
Trend Filter + Fixed Exit

S5
ATR Adaptive Exit

S6
Mean Reversion / Reversal

S7
Breakout Trend Following

기존 Strategy는 삭제하지 않는다.

모든 Strategy는 연구 Evidence다.

---

# 17. Strategy 설계 원칙

Strategy를 평가할 때:

"수익률이 가장 높았는가?"

만 보지 않는다.

다음 Layer로 평가한다.

1. Capital Growth
2. Survival
3. Trade Quality
4. Capital Efficiency
5. Benchmark
6. Robustness

---

# 18. Capital Growth

필수 Metric:

Initial Capital

Cash

Market Value

Current / Final Portfolio Value

Net Profit

Net Return

Realized P/L

Unrealized P/L

Estimated Liquidation Value

---

# 19. Survival

가장 중요한 영역 중 하나.

Metric:

MDD %

MDD Amount

Max Single Loss

Max Consecutive Losses

Worst Open Drawdown

Longest Capital Lock

Recovery Days

Recovered From Max Drawdown

Required Gain to Recover

목표:

얼마 벌었는가보다
계좌가 살아남았는가를 먼저 확인한다.

---

# 20. Trade Quality

실제 이익/손실 청산이 존재하는 전략:

True Win Rate

Average Win

Average Loss

Payoff Ratio

Closed Trade Expectancy

Profit Factor

Max Single Realized Loss

주의:

승률 단독 사용 금지.

---

# 21. S1 특별 규칙

S1은 손절이 없기 때문에
완료 거래가 대부분 익절일 수 있다.

따라서:

"승률 100%"

표현을 핵심 Metric으로 사용하지 않는다.

대신:

청산거래 익절 비율

이라고 표현한다.

반드시 같이 표시:

Unrealized P/L

Worst Open Drawdown

Longest Lock Days

Current Total Portfolio Value

---

# 22. Expectancy 주의

Closed Trade Expectancy는
Open Position 손익을 포함하지 않는다.

따라서:

Trade Expectancy
≠
Portfolio Expectancy

전략 비교의 최상위 기준은:

Portfolio 결과다.

---

# 23. Capital Efficiency

ZERO MARKET LAB의 중요한 연구축.

Metric:

Average Holding Days

Profit Events Per Year

Average Days Between Profit Events

Net Profit Per 100 Trading Days

Exposure

Cash Ratio

목적:

한 번의 큰 수익이 아니라
자본을 얼마나 효율적으로 재사용할 수 있는지 평가.

---

# 24. CASH는 Strategy State다

ZERO MARKET LAB은:

BUY
SELL

뿐 아니라:

CASH

를 공식 Strategy State로 취급한다.

CASH는 실패가 아니다.

불리한 시장에서
자본을 보존하고
다음 기회를 기다리는 상태다.

---

# 25. Entry Filter

Strategy와 Entry Environment를 분리한다.

Architecture 후보:

Strategy

+

EntryFilter

+

ExitPolicy

+

PositionSizing

+

ExecutionModel

EntryFilter 예:

NoFilter

MA200TrendFilter

향후:

SpringPhaseFilter

ConfirmedReversalFilter

---

# 26. Trend Filter v1

첫 실험:

Previous Close > Previous MA200

AND

Previous MA200 slope > 0

→ Entry Allowed

그 외:

→ CASH

중요:

오늘 진입 판단은
t-1 데이터만 사용한다.

---

# 27. Position Sizing

향후 중요한 Risk Layer.

현재 기본:

Full Capital / Integer Shares

향후 연구:

Fixed Risk 0.5%

Fixed Risk 1%

Fixed Risk 2%

Kelly는 충분한 Evidence 전까지 사용하지 않는다.

---

# 28. Position Sizing 철학

핵심 질문:

"무엇을 살까?"

뿐 아니라:

"얼마를 걸까?"

한 번의 실패가
계좌 전체를 훼손하면 안 된다.

---

# 29. Execution Model

Backtest와 Paper Trading의
체결규칙은 동일해야 한다.

Execution Rule은 Version 관리.

예:

DAILY_OHLC_V1

Strategy Result마다:

fill_rule_version

저장.

---

# 30. OHLC Ambiguity

Daily OHLC만으로는
Intraday Sequence를 알 수 없다.

따라서 보수적 정책 사용.

기존 원칙:

New Entry + Same-day TP
→ 인정하지 않음

New Entry + Same-day SL
→ 인정

TP + SL simultaneous ambiguity
→ SL first

Gap Stop
→ Open <= SL이면 Open fill

---

# 31. Cost Model

모든 결과는 거래비용을 반영한다.

구성:

Buy Fee

Sell Fee

Sell Tax

Slippage

Instrument Type별 분리.

예:

KRX Stock

KRX ETF

US Research Stock

Fee Model도 Version 관리.

---

# 32. ISA Layer

Strategy와 Account Type을 분리한다.

Strategy ≠ ISA

Account Layer:

Pension

ISA

General Brokerage

Paper Account

ISA Eligibility는
Instrument Metadata에 저장.

미국 개별주는 연구 Asset로 유지 가능하지만
ISA 직접 매수 후보와 분리한다.

---

# 33. Validation Ladder

어떤 전략도
Backtest 성공만으로 채택하지 않는다.

검증 순서:

Historical Backtest
↓
Multi-Period
↓
Rolling Window
↓
Walk-Forward
↓
Paper Trading
↓
Forward Evidence
↓
Actual Investment Review

---

# 34. Multi-Period

필수:

6M

1Y

2Y

3Y

4Y

5Y

목적:

특정 기간 우연인지 확인.

---

# 35. Rolling Robustness

필수:

Rolling 6M

Rolling 1Y

각 Window는 독립 초기자금으로 실행.

Metric:

Positive Window Ratio

Beats S0 Ratio

Worst Window

Median Return

MDD

Open-at-End Ratio

Longest Lock

Cash Ratio

---

# 36. Rolling Sample 주의

1개월 간격 Rolling Window는
서로 겹치는 Sample이다.

따라서 독립 표본처럼 해석하지 않는다.

Window Count와
Overlap 경고를 함께 표시.

---

# 37. S0 Benchmark

모든 Active Strategy는
가능하면 동일 기간 S0와 함께 본다.

하지만:

S0를 이기지 못하면 무조건 실패

는 아니다.

비교:

Final Capital

MDD

Recovery

Exposure

Cash Ratio

Worst Window

즉:

수익을 얼마나 포기하고
Risk를 얼마나 줄였는지도 평가한다.

---

# 38. Walk-Forward

중요.

Training 구간과
Forward 구간을 분리한다.

예:

Prior 12M
→ Candidate / Strategy Selection

Next 3M
→ Frozen Forward Evaluation

미래 데이터를 이용한
사후 선택 금지.

---

# 39. Paper Trading

실제 과거 Backtest와 분리한다.

시작일 이후:

새로운 시장 데이터만 추가.

Flow:

New Data
↓
Signal
↓
Decision
↓
Order
↓
Execution
↓
Journal

과거 Decision 수정 금지.

---

# 40. Paper Trading Versioning

필수:

Strategy Version

Strategy Config Hash

Fee Model Version

Fill Rule Version

Data Source

Data Timestamp

Decision Timestamp

---

# 41. Paper Trading 목적

실제 주문 자동화가 아니다.

목적:

과거 데이터에서 발견한 우위가
미래 데이터에서도 유지되는지 확인.

---

# 42. Paper Candidate Checklist

후보 선정은 자동화하지 않는다.

Checklist:

ISA 매수 가능

현재 시드로 매수 가능

Historical 검증

Rolling 검증

S0 비교

Worst Window 확인

MDD 감당 가능

Maximum Lock 감당 가능

사용자가 최종 결정.

---

# 43. Data Architecture

공통 OHLCV:

timestamp

open

high

low

close

volume

optional:

trading_value

nav

etc.

Metadata:

symbol

name

asset_class

instrument_type

market

currency

timezone

lot_size

tick_size

fractional_allowed

calendar

data_source

adjustment_policy

isa_eligible

---

# 44. Data Integrity

반드시:

Duplicate 제거

Ascending Date

OHLC validity

Missing value 확인

Corporate Action 처리

Split 처리

Adjustment Metadata

Data Source 기록

---

# 45. 배당

배당 미반영 여부를 명확히 표시한다.

S0 Buy & Hold와의 비교에서는
배당 미반영으로 S0 Total Return이
과소평가될 수 있음을 표시.

---

# 46. UI 철학

Trader 화면은 단순해야 한다.

기본 화면:

투자 조건

투자 결과

종목 비교

기간별 성과

매매기록

Research 정보는 Accordion.

---

# 47. 기본 화면 핵심 질문

사용자가 즉시 알아야 한다.

얼마를 넣었는가?

현재 얼마인가?

얼마를 벌거나 잃었는가?

실현손익은 얼마인가?

미실현손익은 얼마인가?

그냥 보유보다 어땠는가?

현재 물렸는가?

최악에는 얼마까지 떨어졌는가?

얼마나 오래 돈이 묶였는가?

---

# 48. Research UI

Accordion:

S1 Robustness

Strategy Comparison

Market Phase

Regime

Yearly Analysis

Price Behavior

Cost Detail

Data Quality

Developer Metadata

---

# 49. Research와 Trader UI 분리

Trader View:

실제 의사결정에 필요한 최소정보.

Research Lab:

왜 결과가 나왔는지 분석하는 상세정보.

---

# 50. Phase Discovery UI 장기 목표

예:

| Asset | Current Phase | Previous Phase | Transition Evidence | Days in Phase | Relative Strength |
|------|------|------|------|------|------|
| A | SPRING_CANDIDATE | WINTER | 4/6 | 12 | Rising |
| B | SPRING | WINTER | 5/6 | 21 | Rising |
| C | SUMMER | SPRING | 6/6 | 83 | Strong |
| D | AUTUMN | SUMMER | 4/6 | 17 | Falling |

SPRING_CANDIDATE는
추천이 아니라 Research Candidate다.

---

# 51. Phase Engine 검증

Phase Detector 자체를 먼저 검증한다.

Spring Metric:

Spring Candidate Count

Confirmed Spring Count

Summer Transition Count

False Spring Rate

Spring → Summer Days

20/60/120D Forward Return

Autumn Metric:

Autumn Signal Count

Autumn → Winter Rate

Summer Resume Rate

Post-Autumn Drawdown

---

# 52. Phase Engine 구현 순서

STEP 1
Phase Definition

STEP 2
Price-only Rules

STEP 3
Historical Label Analysis

STEP 4
Look-Ahead Audit

STEP 5
False Spring Analysis

STEP 6
False Autumn Analysis

STEP 7
Discovery UI

STEP 8
Strategy Integration

STEP 9
Capital Rotation Research

---

# 53. 처음부터 넣지 않을 것

Phase Engine v1에는 다음을 넣지 않는다.

뉴스

재무제표

외국인/기관

금리

거시경제

AI Prediction

ML Classification

처음에는 Price 기반만.

이유:

무엇 때문에 결과가 나왔는지 검증하기 위해서다.

---

# 54. Phase Engine v2 후보

Price Model 검증 후:

Relative Strength

Volume

Trading Value

Capital Flow

Sector Strength

Fundamental Revision

등을 하나씩 추가한다.

---

# 55. Research Discipline

직관:

자유롭게 가설을 만든다.

검증:

엄격하게 한다.

항상 기록:

Hypothesis

Evidence

Counter Evidence

Failure

Falsification

Revision

---

# 56. 금지사항

미래 데이터 사용 금지.

사후적으로 좋은 조건만 선택 금지.

Synthetic 데이터를 실제 시장결과처럼 표현 금지.

과거 수익을 미래 보장처럼 표현 금지.

자동 추천 표현 금지.

"안 잃는 전략"

"100% 승률 전략"

표현 금지.

---

# 57. Git / Research History

Git은 단순 코드 저장소가 아니다.

연구 History다.

각 의미 있는 단계:

Problem

Hypothesis

Implementation

Experiment

Failure

Finding

Revision

을 기록.

---

# 58. Documentation Structure

Project Root:

ZERO_MARKET_LAB_META.md

세부 문서:

docs/

[fecm-market-phase-engine-v1.md](docs/fecm-market-phase-engine-v1.md)

[strategy-research-framework.md](docs/strategy-research-framework.md)

trader-ux-accuracy-resume.md

s1-rolling-robustness.md

yearly-regime-research.md

paper-trading-foundation.md

instrument-cost-isa-policy.md

기타 실험 문서.

---

# 59. Document Hierarchy

우선순위:

1.
ZERO_MARKET_LAB_META.md

2.
각 Component Architecture 문서

3.
Experiment / Research 문서

4.
Implementation Code

하위 문서는
상위 문서의 목적을 위반하지 않는다.

---

# 60. Codex 작업 규칙

모든 중요한 작업 시작 전:

1.
ZERO_MARKET_LAB_META.md를 읽는다.

2.
관련 docs를 읽는다.

3.
git status / diff를 확인한다.

4.
현재 구현과 메타 설계의 충돌 여부를 확인한다.

5.
작업 범위를 선언한다.

6.
구현한다.

7.
Test한다.

8.
Browser 검증한다.

9.
Research Journal / Resume 문서를 갱신한다.

10.
사용자 승인 전 commit/push하지 않는다.

---

# 61. 새로운 기능 제안 규칙

Codex가 새로운 기능을 발견했다고
바로 구현하지 않는다.

먼저:

- 왜 필요한가?
- Meta Architecture와 맞는가?
- 기존 Component와 중복인가?
- 검증 가능한가?
- Look-Ahead 위험은 없는가?

를 보고한다.

---

# 62. 프로젝트 장기 구조

FECM Market Phase Engine
        ↓
Asset Discovery
        ↓
Strategy Selection
        ↓
Risk / Position Sizing
        ↓
Execution
        ↓
Portfolio
        ↓
Validation
        ↓
Paper Trading
        ↓
Forward Evidence
        ↓
Capital Rotation

---

# 63. 최종 연구 질문

ZERO MARKET LAB의 최종 질문:

> 우리는 미래의 최고점과 최저점을 맞히지 않고도,
> 시장과 자산의 Phase 변화를 관찰하여
> 유리한 시기에는 자본을 투입하고,
> 불리한 시기에는 현금으로 기다리며,
> 틀렸을 때도 살아남을 수 있는 위험 구조를 통해
> 장기간 자본을 성장시킬 수 있는가?

이 질문을 모든 연구와 구현의 기준으로 삼는다.
