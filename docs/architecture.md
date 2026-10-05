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

## 향후 데이터 계약 (구현 없음)

Daily state: date, market_price, cash, quantity, position_value, portfolio_value,
total_contribution, average_purchase_price, strategy_name, action, buy_amount,
sell_amount, transaction_cost, drawdown.

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
