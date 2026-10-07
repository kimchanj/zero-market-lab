# Architecture baseline — STEP 0

## Future Goal and Sensitivity analysis boundary

장기 연구 흐름은 `Market Data → Backtest Engine → Strategy Result → Goal Analyzer → Sensitivity Analyzer
→ Visualization`으로 확장한다. Goal Analyzer는 완성된 전략 결과에 목표 정의를 적용하는 Analytics 계층이며,
목표 달성을 매수·매도 Strategy 규칙에 넣지 않는다. Sensitivity Analyzer는 여러 시작일의 독립 run 결과를
집계한다. 전략별 실행 결과와 분석 결과를 분리하면 같은 경로에 다른 목표 정의를 재적용하고, 같은 목표를
A/B/C에 공정하게 적용할 수 있다.

`GOAL_REACHED`는 Analysis Event이고 BUY/SELL/TAKE_PROFIT/REENTRY 같은 Transaction Event가 아니다.
향후 event contract는 category와 definition version을 보존해야 한다. 목표 상태는 `GOAL_REACHED`,
`GOAL_NOT_REACHED`, `INSUFFICIENT_HORIZON`을 구분해 데이터 끝으로 인한 censoring을 실패로 오분류하지 않는다.
세부 입력·출력, 목표수익률 분모의 미결정 대안, 한국어 UX와 시간축 정책은
[Goal-Based Investment Simulation](goal-based-simulation.md)에 기록한다. Prototype v1은 Engine의
`initial_investment=0` 하위 호환 입력, `INITIAL_CONTRIBUTION` 이벤트, 별도 Goal Analyzer와 분리 UI만
구현한다. Sensitivity Analyzer와 반복 시작일 분석은 구현하지 않는다.

Goal Prototype UI는 A/B/C 선택 dropdown을 두지 않고 같은 config로 세 결과를 항상 계산한다. Visualization은
하나의 shared date axis에서 S&P500을 왼쪽 y축, A/B/C Portfolio와 목표를 오른쪽 y축에 표시한다.
Layer selector는 저장된 figure의 trace visibility만 바꾸며 Backtest를 재실행하지 않는다. C 거래 marker는
기존 Event Log의 TAKE_PROFIT/SELL/REENTRY만 사용하고 기본 OFF다. 실제값 dual-axis가 현재 범위이며
시작값 100 normalization view는 후속 후보로 남긴다.

투자 실험 입력은 `Investment Conditions`(시작일, 초기 투자금, 매월 투자금, 기간)와
`Strategy Conditions`(익절 기준, C 재진입 대기)로 분리한다. UI 숫자 문자열은 application service 경계에서
정규화하고 Engine에는 검증된 실수·정수만 전달한다. 초기 투자금과 월 투자금은 각각 0일 수 있지만 둘 다
0이면 거부한다. Goal은 선택 분석이며 월 적립금이 있으면 목표수익률 분모가 확정될 때까지 목표선과 달성
판정을 생성하지 않는다. `StrategyEvaluation` adapter가 총 납입금, 최종 평가금액, 손익, A 대비 차이,
거래 횟수, 현금 대기일, Time in Market과 현재 경로의 MDD를 Result에서 계산하며 Strategy/Engine 규칙을
복제하지 않는다.

## Future Strategy Discovery boundary

자동 전략 탐색은 `Investment Goal → Candidate Generator → Backtest Engine → Goal Analyzer → Risk Analyzer
→ Sensitivity Analyzer → Constraint Filter → Scoring / Candidate Ranking` 흐름의 Research 계층이다.
후보 생성·제약·점수·순위를 Backtest Engine이나 Strategy에 넣지 않는다. 사후 최적 경로는
`Theoretical Upper Bound`라는 별도 결과 유형으로 분리하고, 실전 후보는 각 시점까지 관찰 가능한 정보만 쓴다.

초기 진화 방향은 고정된 Strategy 구조의 Parameter Grid Search다. Strategy Building Block 조합과 A/B/C
리팩터링은 별도 호환 계약이 마련된 이후로 유보한다. Investment Journal은 Event Log와 Daily State에서 만든
설명 projection이며 원본 event ID, state date, rule ID, 조건값과 임계값을 보존한다. 상세 설계는
[Automatic Strategy Search and Investment Journal](automatic-strategy-search.md)을 따른다. 현재 구현은 없다.

## Cross-Asset & Hedge Research boundary

Cross-Asset 연구는 `MarketSeries Registry → Provider → Provenance Validation → Alignment → Return/Drawdown
Analytics → Normalized/Correlation Visualization` 계층으로 분리한다. 초기 대상은 S&P500, 장기국채, Gold,
VIX다. VIX는 risk indicator이며, Treasury yield는 금리 관찰값이므로 어느 것도 투자 가능한 total-return
series로 취급하지 않는다. Indicator 관찰 계약과 SPY/TLT/GLD adjusted-price 기반 investable proxy 계약을
분리한다.

날짜 정렬, 기준 100 정규화, rolling/downside correlation과 drawdown episode는 Strategy Engine 밖의 Analytics
계층에 둔다. 관찰 분석을 완료한 뒤 Fixed Allocation, Dynamic Hedge 순서로 별도 Case를 만든다. Production
Unified Chart 연결의 선행조건은 STEP 5 Zoom/Pan visible-range autoscale Critical Gate 통과다. 상세 설계는
[Cross-Asset & Hedge Research](cross-asset-hedge-research.md)를 따른다. 현재 구현은 없다.

## STEP 5 Chart Engine architecture spike

Visualization Layer의 장기 적합성을 확인하기 위해 Lightweight Charts 5.2.1 prototype을
`experiments/lightweight_charts/`에 격리했다. 기존 Dash/Plotly UI와 Python Market Data, Comparison Service,
Backtest, Portfolio, Strategy, Event Log는 유지한다. Prototype은 Python이 실제 market/state/event JSON을
생성하고 브라우저 adapter가 rendering, pane, crosshair, visible range, marker filter를 담당한다.

실제 2,514 daily close, A/B/C portfolio, contribution, Strategy C의 기존 BUY/TAKE_PROFIT/SELL/REENTRY를
단일 time scale의 Market/Portfolio 2-pane chart에서 검증했다. Pane은 resizable이며 chart는 auto-size를
사용한다. Fake OHLC나 volume은 만들지 않았다.

Financial Chart Quality Gate의 최종 결정은 **MIGRATE VISUALIZATION TO LIGHTWEIGHT CHARTS**다. 현재
Plotly/Dash viewport가 zoom/pan마다 Python callback과 전체 figure redraw에 의존하는 병목을 제거하기 위한
결정이다. Production migration은 아직 시작하지 않았으며, 다음 구현 전에 versioned Dash custom component
또는 제한된 client adapter와 stable JSON contract를 설계해야 한다. Plotly는 정적 연구 결과와 export 용도로
유지할 수 있다. Prototype iframe 방식은 검증에는
충분하지만 cross-frame state와 테스트 비용 때문에 production 기본안으로 권고하지 않는다.

Future Market Activity Overlay는 S&P500 지수의 volume이 아니라 SPY trading volume 또는 실제 ETF provider의
volume을 명시적인 proxy로 사용한다. 실제 OHLC가 확보되기 전 candlestick을 만들지 않는다. 추가 indicator,
drawing, annotation은 Lightweight Charts pane/plugin/custom primitive로 별도 검증한다.

## STEP 5 UI application boundary

Dash layout/callback은 `zero_market_lab.ui.app`, 입력 검증·기간 필터·비교 실행은 UI 독립적인
`zero_market_lab.ui.service`, Plotly 변환은 `zero_market_lab.ui.figures`가 담당한다. 데이터 흐름은
Dash UI → Comparison Service → 기존 Multi-Strategy Engine → ComparisonOutput → Figure/Metrics Adapter다.
callback은 Portfolio 회계나 전략 실행 규칙을 구현하지 않는다.

서비스 config는 Start/End Date, Monthly Contribution, Take Profit %, Reentry Months를 포함한다.
Take Profit과 Reentry Months는 기존 Strategy/Engine에 명시적 파라미터로 전달된다. fixed assumptions는
표시 전용이며 transaction cost, slippage, FX, dividend 처리 로직을 추가하지 않는다.

Market/Portfolio figure는 동일 date axis 계약과 adaptive tick format, spike guide를 사용한다. Dash의
`relayoutData` clientside callback이 두 figure의 x-axis range와 autorange reset을 동기화한다. 서버 callback은
Run Backtest에서 validation → filter → engine rerun → 두 figure와 Metrics 갱신만 수행한다.

## STEP 4 전략 상태와 실행 경계

`run_case01_strategy`는 공통 일별 회계 흐름을 담당하고 A/B/C 전략 객체는 익절 사용 여부와
`INVESTED` / `WAITING_REENTRY` 상태, 매도일, 재진입 기준일을 보유한다. `run_case01_comparison`은 동일한
검증 완료 market frame으로 세 전략을 각각 실행해 결과 객체를 분리한다. 기존
`run_monthly_buy_and_hold` public API는 Strategy A로 위임해 호환성을 유지한다.

Portfolio는 contribution, fractional buy, weighted average cost 외에 `sell_all`을 제공한다. 전량 매도는
수량을 0으로 만들고 평균매입가를 null로 재설정하며, 이후 재진입은 새 종가를 평균매입가로 설정한다.
Daily State에는 strategy name/state와 reentry target date가 추가되며, Event Log는 CONTRIBUTION, BUY,
TAKE_PROFIT, SELL, REENTRY를 독립된 순서형 행으로 보존한다.

same-close, 비용 0 조건에서 B의 매도와 재진입은 자산가치와 수량을 바꾸지 않는다. 따라서 A/B의 모든
일별 portfolio value, quantity, cash 동일성은 구현 검증 불변식이다. C는 달력 월 연산 후 첫 시장 관측일을
선택하며, 대기 중 contribution은 현금으로 누적된다. Cash Waiting Days는 달력 일수로 집계하고 열린 대기는
마지막 관측일까지 별도로 포함한다.

## Decisions

| ADR | 기준선 결정 |
| --- | --- |
| 001 | Python으로 Backtest / Analysis, Pandas 우선 |
| 002 | Plotly Interactive Visualization |
| 003 | Dash를 초기 Interactive Research UI 후보 1순위로 사용 |
| 004 | UI와 Engine 분리. Engine은 Dash / Plotly를 import하거나 알지 않음 |
| 005 | MarketDataProvider abstraction으로 공급자 교체 가능 |
| 006 | Strategy Plugin 구조. 특정 전략을 Engine에 하드코딩하지 않음 |
| 007 | Strategy의 Signal/Action과 Execution의 체결가격·시점 분리 |
| 008 | Market/Strategy와 Account/Tax 분리 |
| 009 | Real Data는 Research, deterministic Synthetic Data는 Test |
| 010 | Data Provenance 보존 |
| 011 | Price / Total Return / Net Total Return / ETF Price / NAV 구분 |
| 012 | Case #01 A/B/C 동일 기간·데이터·가정으로 비교 |
| 013 | Interactive Chart를 핵심 Product 기능으로 취급 |
| 014 | Design → Code → Test → Run → Visual Verify → Commit → Journal 완료 게이트 |

설치·인터페이스 구현은 이번 단계 범위 밖이다. pytest는 테스트, CSV/Parquet는 초기 저장 방식이다.
FastAPI + React/TypeScript는 UI 복잡도가 커질 때 별도 ADR로 재평가할 장기 대안이다.

## 책임과 데이터 흐름

아래 순서는 연구 처리 흐름이며 각 모듈의 상호 import 체인을 뜻하지 않는다.

Market Data → Backtest Engine ↔ Strategy → Execution → Portfolio → Analytics
→ Research / Experiment → Interactive Visualization. Future Account / Tax는 별도 정책 경계다.

| 경계 | 책임 / 산출물 |
| --- | --- |
| Market Data | Index·ETF·FX·Macro 공급자에서 읽기, 검증·정규화, provenance와 불변 snapshot 전달 |
| Engine | 거래일 순서, 적립, 전략 호출, 체결 적용과 일별 상태 기록을 조정 |
| Portfolio | cash, quantity, average cost, contribution, valuation 회계 및 불변식 |
| Strategy | 현재까지 관찰 가능한 상태로 Signal/Action 의도 결정 |
| Execution | 주문 가능 시각, 체결 시각·가격·수량·비용·거절 결정 |
| Analytics | 상태·이벤트로 지표 산출. 적립금과 투자성과 분리 |
| Research | 동일 dataset/config으로 비교 실행, 실험 ID·버전·결과·반증 기록 |
| UI | 입력 검증, 실행 요청, 반환된 데이터 표시. 전략/회계 계산을 복제하지 않음 |
| Account / Tax | 향후 계좌·연금저축·ISA·세금 정책. 가격/전략 Engine에 직접 삽입하지 않음 |

Strategy 확장 후보는 BuyAndHold, MonthlyAccumulation, TakeProfit, DelayedReentry,
Rebalancing 등이다. 월 적립은 공통 현금흐름 정책으로도 분리해 비교군의 조건을 일치시킨다.
MarketDataProvider는 데이터 취득 책임만 가지며 주문·포지션을 모른다.
Engine은 정규화된 입력과 추상적인 Strategy / Execution 계약만 사용한다.

## Reference Strategy Library (설계 기준선, 구현 없음)

Research Layer는 전략을 출처에 따라 다음 네 유형으로 분류할 수 있어야 한다.

```text
Strategy Source
├─ User Hypothesis
├─ Academic Reference
├─ Practitioner Reference
└─ Control / Benchmark
```

- **User Hypothesis**: 사용자가 정의한 검증 대상. 예: +5% Take Profit / Reentry.
- **Academic Reference**: 학술 논문이나 연구 문헌에 원 규칙과 근거가 있는 전략.
- **Practitioner Reference**: 투자업계의 공개 연구·방법론·실무 문헌에 근거한 전략.
- **Control / Benchmark**: Buy & Hold, Monthly Accumulation 등 비교 해석의 기준선.

Reference Strategy Library는 실행 클래스나 DB가 아니라 향후 Research Layer가 관리할 전략 metadata 계약이다.
동일한 전략 규칙이라도 출처·버전·파라미터·데이터 정의가 다르면 별도 기록으로 식별한다.
초기 metadata 후보는 다음과 같다.

| 필드 | 의미 |
| --- | --- |
| Strategy ID | 안정적인 식별자. 예: `REF-TREND-001` |
| Strategy Name | 사람이 읽는 전략명 |
| Strategy Family | Trend Following 등 연구 분류 |
| Source Type | User / Academic / Practitioner / Control |
| Original Author / Organization | 원 저자 또는 기관; 미확인 값을 추정하지 않음 |
| Reference / Publication | 논문·책·방법론·공개 자료의 정확한 인용과 URL/식별자 |
| Original Publication Date | 최초 공개일과 확인 가능한 개정판 구분 |
| Core Hypothesis | 전략이 작동한다고 주장하는 경제적·행동적 가설 |
| Required Market Data | 가격 종류, 빈도, 조정·배당·FX·자산 범위 및 신호 산출에 필요한 필드 |
| Parameter Set | 원 규칙, 기본값, 허용 범위와 사전 확정 여부 |
| Benchmark | 동일 조건에서 비교할 Control |
| Known Limitations | 편향, 비용, 용량, 국면, 재현성 등 알려진 제약 |
| Evidence Type | 논문, practitioner backtest, live record 등 증거의 성격과 범위 |
| ZERO MARKET LAB Status | Not Yet Tested / Reproduced / Partially Reproduced / Falsified / Inconclusive 등 |

예시 등록안 `REF-TREND-001`은 `10-Month Moving Average`, Family `Trend Following`,
Source Type `Published / Practitioner Reference`, Core Hypothesis는 장기 하락 추세에서 노출을 줄여
drawdown을 낮출 수 있다는 주장, Benchmark는 Buy & Hold, 초기 Status는 `Not Yet Tested`다.
이는 구현·채택·수익성 판정이 아니며 실제 출처와 원 규칙은 해당 연구 Case에서 확인한다.

초기 Family 후보는 Buy & Hold, Trend Following, Time-Series Momentum,
Tactical Asset Allocation, Rebalancing, Drawdown / Risk Control, Volatility Targeting,
Risk Parity, Value / Momentum Factor, Regime-Based Strategy다. 구현 순서는 확정하지 않는다.

Published Backtest ≠ Current Profitability, Historical Profit ≠ Future Profit,
Famous Investor Usage ≠ Guaranteed Edge, Backtest Result ≠ Live Trading Result다.
모든 Reference Strategy는 User Strategy 및 Control과 동일 dataset snapshot, 비용, signal/execution timing,
통화·배당 처리, 평가기간과 metric 정의로 재검증한다. Out-of-Sample, Look-Ahead,
Survivorship, Transaction Cost, Slippage, Data Snooping, Parameter Overfitting,
Regime Dependence, Publication / Crowding Effect를 기록한다. 원 결과를 재현하지 못한 경우도 유효한 결과다.

Case #01의 A/B/C는 변경하지 않는다. Reference Strategy는 Case #01 이후 별도 Case 또는
Reference Comparison Case에서 추가하며 실제 번호는 사전에 고정하지 않는다.

## STEP 2 구현 경계 — Strategy A

최초 구현 수직 슬라이스는 `MonthlyContributionPolicy → BuyAndHoldStrategy → Portfolio → Engine`이다.
Contribution Policy는 입력 데이터에서 각 year-month의 첫 관측일과 현금 유입액만 결정한다.
Strategy는 가용 현금을 매수할 의도만 반환한다. Portfolio는 contribution, fractional buy,
weighted average cost와 일별 평가를 담당한다. Engine은 검증된 날짜 순회, 호출 순서와 state/event 기록만 조정한다.

Daily State와 Event Log는 별도 DataFrame이며 CONTRIBUTION과 BUY도 별도 행이다.
현재 Engine은 Strategy A 전용 진입점이지만 +5%·SELL·Reentry 규칙을 포함하지 않는다.
Same Close, 비용 0, slippage 0은 이번 검증 기준선이며 일반 Execution Model 구현으로 간주하지 않는다.

## 데이터 계약

STEP 2 구현 state: date, market_price, cash, quantity, average_purchase_price,
position_value, portfolio_value, total_contribution. 향후 strategy_name, action, buy/sell amount,
transaction_cost, drawdown 등은 필요 단계에서 확장한다.

position_value = quantity × market_price; portfolio_value = cash + position_value.
무차입 기준 cash·quantity는 허용 오차 이내에서 음수가 아니어야 한다.
전량 매도 후 average_purchase_price는 null, 재매수 시 새 원가로 설정한다.
금액 필드는 명시된 simulation currency를 사용하고 비용은 별도로 기록한다.
drawdown의 기준은 Case 문서의 현금흐름 조정 지표를 따른다.

Daily state는 하루 말 snapshot이고 Event/Trade Log는 여러 행이 가능한 별도 기록이다.
CONTRIBUTION, BUY, SELL, TAKE_PROFIT, REENTRY를 구분한다.
event_id, run_id, date/time, sequence, strategy, type, signal_time, execution_time,
quantity, price, gross_amount, cost, reason을 향후 계약에 포함한다.
익절 신호와 실제 매도 체결을 구분하고, 한 날짜 SELL/BUY를 하나의 action으로 소실시키지 않는다.
daily action은 요약이며 상세 로그가 근거다. Chart Marker도 이 로그에서 만든다.

## Research UI 목표

기간·초기 투자금·월 적립금·자산·Take Profit %·Reentry Rule·Transaction Cost·Execution Rule을
변경하고 공통 Timeline에서 재실행한다. Market Price / Portfolio Value(A/B/C) / Drawdown을 연결한다.
향후 Buy/Sell/Contribution Marker, Average Purchase Price, Cash, Benchmark,
Market Event, FED Rate, Inflation, USD/KRW를 추가한다.
이벤트 설명은 관찰과 인과 가설을 구분하며 차트의 동시 움직임만으로 원인을 확정하지 않는다.

## 논리 구조 (향후 생성 계획)

```text
zero-market-lab/
  README.md
  JOURNAL.md
  docs/{architecture,design,research,data}/
  data/{raw,processed,fixtures}/
  src/zero_market_lab/
    market_data/
    backtest/
    strategies/
    execution/
    portfolio/
    analytics/
    ui/
  tests/{unit,integration,fixtures}/
  cases/case_01/
```

STEP 0은 문서 수를 줄이기 위해 docs 바로 아래에 통합 문서를 둔다.
구현 단계에서 필요할 때 위 구조로 확장하며 빈 source 디렉터리나 placeholder 코드를 만들지 않는다.
테스트 입력은 tests/fixtures를 기본 소유 위치로 하고 data/fixtures와 중복 관리하지 않는다.

## Actual ETF Track V2 격리

`zero_market_lab.tiger_v2`는 TIGER 360750 acquisition parsing, validation, payload 계약만 소유한다.
`experiments/tiger_etf_v2`는 기존 vendored Lightweight Charts를 재사용하되 Plotly/Dash와 독립된 정적
financial chart다. Legacy backtest, strategy, goal UI는 수정하거나 호출하지 않는다. V2 OHLC execution과
A/B/C migration은 데이터·차트 승인 뒤 새 execution 경계로 추가한다.

## Generic Explainable Simulator 경계

`zero_market_lab.simulator`는 V2 데이터·차트 위에서 자산 독립형 일봉 실행을 검증하는 별도 core다.
의존 방향은 Provider → Instrument/MarketBar → Strategy Parameters → Execution/Cost → Portfolio
Accounting → DecisionRecord/Daily Ledger → Trade/Period Summary다. 종목별 metadata는
`Instrument` 인스턴스에만 존재하며 Engine은 `360750`이나 시장별 조건으로 분기하지 않는다.

일별 Ledger와 DecisionRecord가 계산의 source of truth다. TIGER 화면은 JSON payload를 표시하고
BUY/SELL marker, 평균단가, 익절선을 그릴 뿐 체결·손익을 다시 계산하지 않는다. 같은 bar에서 진입과
익절이 모두 가능한 경우는 `AMBIGUOUS_ENTRY_EXIT`로 기록하고 포지션을 유지한다. 비용은 주입 가능한
정책이며 실증 값은 연구용 가정이다. 계약·실행결과·제약은
[Generic Explainable Simulator](generic-explainable-simulator.md)에 기록한다.

## 현재 Research Workstation과 향후 계좌 제약

`simulator.service.run_simulation`은 UI 입력을 검증하고 선택 기간의 실제 OHLCV만 잘라 기존 generic
engine을 재실행한다. 반환된 단일 run ID의 Summary, Daily Ledger, Trade, Chart overlay를 한 화면에
전달한다. `research.snapshot`은 그 실행 결과와 독립된 공식 뉴스 카탈로그를 결합하되 거래 결과를
수정하지 않는다. `REPLAY_MODE`는 한국 거래일 종료 시점까지 공개된 자료로 제한하고,
`POST_ANALYSIS_MODE`는 사후 회고를 구분해 표기한다. 사용 흐름과 한계는
[Research Workstation](research-workstation.md)에 기록한다.

향후 `AccountProfile`은 상품 적격성, 세금·수수료, 한도와 같은 **제약 정책**으로 추가한다.
`Instrument`와 실행 엔진에는 연금저축·ISA 등 계좌 이름을 하드코딩하지 않는다. 예를 들어 연금저축의
TIGER 장기 적립, 중개형 ISA의 국내 주식 능동 매매는 별도 AccountProfile과 전략의 조합으로
표현한다. 현 프로토타입은 계좌별 세제나 상품 적격성을 계산하지 않는다.
