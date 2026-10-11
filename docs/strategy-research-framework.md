# Strategy Research Framework — Child Architecture v1

상위 기준: [ZERO_MARKET_LAB_META.md](../ZERO_MARKET_LAB_META.md). 이 문서는 전략 연구의 책임과 검증 계약을 구체화한다. 현재 구현을 승인된 투자전략이나 미래 성과의 근거로 취급하지 않는다.

## 경계와 목표 구조

```text
Market / Universe → FECM Market Phase Engine → Asset Candidate
    → Strategy + EntryFilter + ExitPolicy + PositionSizing + ExecutionModel
    → Portfolio / Ledger → Historical / Rolling / Walk-Forward / Paper Trading
```

Phase Engine은 시점별 **환경의 관찰 상태와 전이 근거**를 산출한다. Asset Discovery는 그 근거를 조사할 후보를 보여준다. Strategy는 그 환경에서 가능한 행동을 시험한다. Phase는 주문이 아니며, `SPRING_CANDIDATE`는 추천이 아니다. `AUTUMN` 역시 자동 매도 명령이 아니다. EntryFilter는 신규 진입 허용 여부, ExitPolicy는 이미 보유한 포지션의 청산, PositionSizing은 허용 수량, ExecutionModel은 주문의 보수적 OHLC 체결을 맡는다. CASH는 실패가 아니라 공식 전략 상태다.

**현재 구현:** `strategy_family.py`가 전략 선택, 일부 진입·청산 규칙, 정수주 수량, OHLC 체결을 함께 실행한다. `entry_filter.py`에 `NoFilter`, S4용 `SMA100Filter`, S1-TF/S2-TF용 `MA200TrendFilter`가 분리되어 있다. 독립적인 연구용 `PRICE_PHASE_V1` 엔진과 별도 SQLite 기반 Paper Trading MVP는 구현되었으나, 공통 ExitPolicy·PositionSizing 객체 및 목표 구조 전체의 통합은 아직 없다. Phase 결과는 주문 신호가 아니며, Paper Trading의 실제 LIVE_FORWARD Pilot도 시작하지 않았다. 리팩터링은 별도 단계에서 한다.

## Strategy Family: 현재 동작과 연구 위험

공통 연구 엔진은 현재 평가 시작 전 100거래일 관측을 요구한다. S1-TF/S2-TF는 전일 MA200과 5거래일 기울기를 위해 **205거래일** 사전 관측을 추가 요구한다. 아래의 20·14·10거래일 지표는 해당 전략의 신호별 최소 준비 조건이며, 엔진 전체의 100거래일 요구를 대체하지 않는다. 모든 전략은 동일한 자산·기간·초기자금·비용 가정에서 비교한다.

| 전략 | 목적과 Entry | Exit / Risk | 시점 규칙·주요 실패 | 중점 지표 |
| --- | --- | --- | --- | --- |
| S0 Buy & Hold | 평가 첫 거래일 시가에 가능한 정수주 매수 | 기간 말 종가 평가, 자동 청산 없음 | 첫날 자금 부족·배당 제외·급락에 노출; 준비 데이터는 현 엔진 공통 100일 | 최종자산, MDD, S0 기준선 |
| S1 Fixed Take Profit | 시가 대비 설정 비율의 당일 지정가; 저가 도달 시 매수 | 평균이 아닌 해당 포지션 매수가 대비 설정 TP; **손절 없음** | 신규 매수 당일 TP 불인정; 장기 미청산 손실·자금 고착 | 총자산, 미실현손익, 최악 미청산 낙폭, 고착일 |
| S2 Fixed TP + SL | 시가 −1% 지정가 | 설정 TP/SL; SL 우선 | 신규 진입일 SL 가능; 횡보·하락장의 연속 손절 | 순손익, 최대 연속 손실, MDD, 비용 |
| S3 S2 + Time Stop | S2와 동일 | 고정 TP5/SL3 및 20거래일 시간청산 | 시간청산 전에 TP/SL로 끝나면 S2와 같음 | 시간청산 수, 보유기간, 순손익 |
| S4 Trend Filter + Fixed Exit | 전일 종가 > 전일 SMA100일 때 S2식 진입 | 고정 TP5/SL3, 20거래일 시간청산 | SMA100 필터는 Phase 판정이 아님; 늦은 진입·재손절 | 필터 통과/실패, MDD, 손절·시간청산 |
| S5 ATR Adaptive Exit | 시가 −1% 지정가, 사전 ATR14 필요 | 진입가 +3×ATR 목표, −2×ATR 손절, 20거래일 시간청산 | 변동성 급변·갭에서 고정 ATR 거리 무력화 | ATR, 손절, MDD, 비용 |
| S6-A Pure Mean Reversion | 종가가 MA20−2σ 아래면 **다음 거래일 시가** 진입 | MA20 회복 신호 후 다음 시가, 1.5×ATR 손절, 10거래일 시간청산 | 하락 추세에서 과매도 신호 반복 | 손실 연속성, 기대값, 최대 낙폭 |
| S6-B Confirmed Reversal | 3일 하락·ATR 조건 뒤 전일 고가 상향 돌파가 종가에 확인되면 **다음 시가** 진입 | S6-A와 동일 | 확인 전 반등 놓침·거짓 반전 | 거짓 신호, 기대값, MDD |
| S7 Breakout Trend Following | 종가가 이전 20일 고가 돌파 시 **다음 시가** 진입 | 이전 10일 저가 하향 이탈 신호 후 다음 시가 | 가짜 돌파·잦은 왕복손실 | 신호 수, whipsaw, S0 대비 |
| S1-TF | S1 진입 조건 **및** 전일 종가 > 전일 MA200, 전일 MA200 > 5거래일 전 MA200 | S1 TP·무손절 유지; 필터 악화만으로 기존 포지션 청산하지 않음 | 205일 준비; 상승 후 고점 부근 진입 가능, CASH로 상승 놓침 | 총자산, 미청산 위험, 현금비율, S1 paired rolling |
| S2-TF | S2 진입 조건 **및** 동일 MA200 필터 | S2 설정 TP/SL 유지; 필터 악화만으로 기존 포지션 청산하지 않음 | 205일 준비; 손절 반복을 완전히 막지 못함 | S2 대비 MDD·순손익, 현금비율, 차단 기회 |

S1-TF/S2-TF의 정확한 전일 판정과 차단 사건 정의는 [Entry Filter + CASH 실험](entry-filter-cash-research.md)에 있다. S4의 SMA100을 S1-TF의 MA200 실험 결과로 혼동하지 않는다. 당일 종가로 만든 신호는 당일 시가에 체결하지 않고 다음 거래일에 적용한다.

## 체결·비용·버전 계약

- 미래 가격·사후 최고점·최저점은 신호에 사용하지 않는다. 당시 확인 가능한 데이터 시각, 데이터 출처, 조정 정책, 전략 설정 해시를 기록한다.
- Daily OHLC에는 장중 순서가 없다. 신규 진입 당일 TP는 인정하지 않고 SL은 인정한다. 기존 포지션의 TP/SL 동시 접촉은 SL 우선, 갭 하락으로 시가가 SL 이하면 시가 체결한다. 이 보수적 정책을 백테스트와 미래 Paper Trading에서 동일한 `fill_rule_version`으로 고정한다.
- 비용은 매수·매도 수수료, 매도세, 슬리피지로 나눠 상품 유형과 적용 시점을 식별한다. 현재의 연구용 기본 비용을 실제 계좌 비용으로 표시하지 않는다. [상품·ISA·비용 경계](instrument-cost-isa-policy.md)를 따른다.
- 결과에는 `strategy_version`, `strategy_config_hash`, `fee_model_version`, `fill_rule_version`, 원천 데이터·관측 시각을 연결하는 계약을 둔다. [Paper Trading MVP](paper-trading-mvp.md)는 [append-only 계약](paper-trading-foundation.md)에 따라 역사 재생을 검증했으며 과거 결정을 다시 쓰지 않는다. 실제 LIVE_FORWARD Pilot은 아직 시작하지 않았다.
- 현재 기본 PositionSizing은 가용현금으로 매수 가능한 정수주다. 위험예산 0.5/1/2%와 Kelly는 구현되지 않았고, 검증 전 전략 성과에 섞지 않는다.

## 평가 Metric 계층

| Level | 연구 질문 | 함께 보는 Metric |
| --- | --- | --- |
| 1. Capital | 실제 자본은 얼마인가? | Initial Capital, Cash, Market Value, Portfolio Value, Net Profit/Return, Realized/Unrealized P/L, Estimated Liquidation Value(추정 청산비용 명시) |
| 2. Survival | 손실을 견디고 회복했는가? | MDD %/금액, Max Single Loss, Max Consecutive Losses, Recovery Days 및 미회복 여부, Required Gain to Recover, Longest Capital Lock, Worst Open Drawdown |
| 3. Trade Quality | 완료 거래의 질은? | True Win Rate, Avg Win/Loss, Payoff Ratio, Closed Trade Expectancy, Profit Factor, Max Single Realized Loss |
| 4. Capital Efficiency | 자본을 얼마나 오래·효율적으로 사용했는가? | Avg Holding Days, Profit Events/Year, Avg Days Between Profit Events, Net Profit/100 Trading Days, Exposure, Cash Ratio |
| 5. Benchmark/Robustness | 특정 구간 우연인가? | 동일 기간 S0, 6M/1Y/2Y/3Y/4Y/5Y, Rolling 6M/1Y, Worst Window, Beats S0 Ratio, Walk-Forward, Paper Trading |

**판정 우선순위는 포트폴리오 총자산·생존성이다.** 청산거래 기대값은 미청산 포지션을 제외하므로 Portfolio Expectancy가 아니다. S1은 손절이 없어 완료 거래의 높은 익절 비율·PF를 단독 성과로 제시하지 않는다. `청산거래 익절 비율`과 함께 미실현손익, 최악 미청산 낙폭, 최장 고착, 현재 총자산을 표시한다. 6M/1Y 월별 rolling 창은 겹치므로 독립 성공 확률로 해석하지 않는다.

## 검증 사다리와 반증

Historical Backtest → Multi-Period → 같은 시작 구간의 Rolling → 사전 고정한 Training/Forward 분리 → 미래 새 관측만 추가하는 Paper Trading → Forward Evidence → 실제 투자 검토. 6종목 seed는 선택·생존 편향이 있다. S0 미달을 자동 실패로 판단하지 않고 포기한 수익과 줄인 위험을 같이 기록한다. 삼성전자 2026년 6월 사례처럼 MA200 필터가 고점 부근 진입을 막지 못한 결과도 [반증 사례](s1-open-position-risk-case.md)로 보존한다. 자동 최적화·추천·실주문은 이 문서의 범위 밖이다.
