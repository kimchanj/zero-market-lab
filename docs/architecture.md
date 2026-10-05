# Architecture baseline — STEP 0

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
