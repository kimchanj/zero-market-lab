# Case #01 — Monthly S&P500 Accumulation vs Take Profit

## STEP 4 실행 명세와 관측 결과

동일한 2016-10-03~2026-10-02 S&P500 Price Index daily close 2,514건과 월 500,000
simulation units를 사용해 A/B/C를 실행했다. Price Index이므로 배당은 제외되며 FX OFF, 비용 0,
slippage 0, fractional units, same-close 체결을 적용했다.

하루의 처리 순서는 날짜 확인 → 월 적립 → C 재진입 가능 여부 확인 → 기존 보유분의 익절 조건 확인 →
전량 매도 → B 즉시 재진입 또는 C 대기 전환 → 익절이 없고 투자 상태이면 가용 현금 매수 → 일말 상태 기록이다.
익절 조건은 당일 적립금 매수 전의 기존 보유 수량과 평균매입가에 적용한다. CONTRIBUTION, BUY,
TAKE_PROFIT, SELL, REENTRY는 발생 순서대로 서로 다른 event row로 기록한다.

- A `A_MONTHLY_BUY_AND_HOLD`: 매도 없이 월 적립금을 종가에 매수한다.
- B `B_IMMEDIATE_REENTRY`: 종가가 평균매입가의 105% 이상이면 전량 매도하고 같은 거래일의 같은 종가에
  비용 차감 없이 전액 재진입한다. 재진입 직후 평균매입가는 그 종가로 재설정된다.
- C `C_DELAYED_REENTRY`: 같은 조건에서 전량 매도하고 `sell_date + DateOffset(months=1)`을 기준일로 삼는다.
  월말이 없는 경우 pandas calendar month clamp를 사용한다(예: 1월 31일 → 2월 말일). 기준일 당일 또는
  그 이후의 첫 시장 관측일에 대기 중 적립금을 포함한 전액을 재진입한다. 데이터가 먼저 끝나면 현금과
  WAITING_REENTRY 상태를 유지한다.

Cash Waiting Days는 매도일부터 재진입일까지의 달력 일수다. 종료일까지 재진입하지 못한 열린 대기는
마지막 시장 관측일까지의 달력 일수를 포함해 별도로 추적한다.

실제 실행에서 A/B의 일별 portfolio value, quantity, cash는 허용오차 내 완전 일치했다. A와 B의 최종 가치는
126,860,380.39809549, 누적 납입액은 60,500,000이었다. B는 TAKE_PROFIT/SELL/REENTRY가 각각 25회였고
평균매입가 이력만 A와 달랐다. C의 최종 가치는 116,066,042.95602758, TAKE_PROFIT/SELL/REENTRY가 각각
24회, Cash Waiting Days는 754일이었다. 이 값은 특정 기간의 관측 결과이며 C의 열위나 A/B의 우월성을
일반화하지 않는다. 배당, 비용, 세금, FX, 실제 ETF 체결, 다양한 임계값과 시장 구간은 아직 검증하지 않았다.

합성 테스트는 event order, B의 동일성 불변식, 월 적립일 익절, C의 정확한 한 달 대기, 월말 clamp,
재진입일 적립금 선반영, 데이터 종료 전 미재진입을 검증한다. 전체 테스트 69개와 실제 실행 및 PNG 시각
검증이 통과했다. 차트에서 A의 굵은 실선과 B의 점선이 겹치고 C 경로가 대기 구간에서 분리됨을 확인했다.

## Problem / Hypothesis

월 적립식 S&P500 장기투자에서 반복 익절·재진입은 Buy & Hold보다 어떤 환경에서 유리하거나 불리한가?
가설: 익절 후 현금 대기는 하락 노출을 줄일 수 있으나 상승 참여를 놓칠 수 있다.
대립 증거로 최종자산 감소, 낙폭 악화, 회복 지연, 비용 증가를 동일하게 기록한다.
전략 우월성이나 최적 threshold를 미리 결론내리지 않는다.

## Control Group / Strategy / Parameters

| 항목 | STEP 0 기준선 |
| --- | --- |
| 데이터 | 실제 S&P500 daily close, 초기 Price Index Benchmark; 공급자·기간은 STEP 1 확정 |
| 화폐 | FX OFF, 동일 화폐 기준 추상 투자단위. 실제 KRW/USD 수익률 아님 |
| 월 적립 | 500,000 simulation units, 매월 첫 거래일 |
| 초기 투자금 | 기본 0, 향후 파라미터 |
| A — Control | 가용 현금 매수 후 계속 보유, 매도 없음 |
| B — Immediate Reentry Control | 평균매입가 대비 종가 +5% 이상이면 전량 매도 후 동일 체결 세션에 재매수 |
| C — Delayed Reentry | 동일 익절 후 매도일로부터 달력상 1개월 대기 후 첫 거래일 재매수 |
| 공통 가정 | 소수 단위 허용, 차입/공매도 없음, 현금 이자 0, 기본 비용·spread·slippage 0 |
| 배당 | 초기 PR 실험은 배당 제외. TR 실험은 별도 dataset/실험으로 분리 |

S&P500 지수는 직접 거래할 수 없다. 지수 level을 가상 단위의 가격으로 사용하는
Benchmark Simulation이며 ETF 체결이나 투자 가능한 상품의 성과로 표시하지 않는다.
0 비용은 현실 추정이 아닌 검증 기준선이다. STEP 8에서 비용 민감도를 추가한다.

## Execution / Experiment

V1 제안 기준은 Same Close다. 종가를 확인해 같은 종가에 거래하는 낙관적 가정이며
현실적으로 보장되는 체결이 아니다. 결과에 모델 이름과 한계를 반드시 표시한다.

향후 구현 시 하루 처리 순서를 다음과 같이 고정한다.

1. 거래일 검증, 해당 월 첫 거래일이면 현금 적립.
2. A/B 및 대기 상태가 아닌 C는 가용 현금으로 종가 매수하고 가중평균 매입가 갱신.
3. B/C의 보유분에 대해 종가 >= average_purchase_price × 1.05이면 익절 신호 생성.
4. 전량 매도 체결. B는 비용 차감 후 가용 현금을 같은 종가에 재매수하여 원가 재설정.
5. C가 기존 대기 상태이고 재진입일이면 적립금을 포함한 가용 현금 전부로 매수.
6. 종가 평가, daily state와 순서 있는 이벤트 기록. 하루 익절 평가는 최대 한 번.

C의 1개월은 다음 월 같은 일자이며 없는 날짜는 월말로 제한한다.
예: 1월 31일 매도 → 2월 말 목표일 → 그 날짜 이후 첫 거래일.
대기 중 월 적립은 현금으로 쌓이고 조기 매수하지 않는다. 표본 종료 시 대기 중이면 현금으로 평가한다.
이는 '다음 월 적립일 재진입'과 다르며 그 규칙은 후속 별도 branch다.
시작일이 월 첫 거래일 이후면 그 달 적립을 소급하지 않는다. 비교 기간은 가능한 월 첫 거래일부터 설정한다.
재진입 branch는 혼합하지 않고 각각 config에 명명한다.

평균 매입가는 보유 매수금액(기본은 수수료 제외)의 수량 가중평균이다.
향후 비용 포함 원가 정책은 별도 명시한다. 동일 가격·0 비용·소수 단위 B의 매도/재매수는
자산가치를 보존해야 한다. A/B가 같은 결과를 낼 조건은 검증 불변식이지 실증 결론이 아니다.

Next Open, Next Close, Limit Touch는 후속 비교 모델이다.
Next Open은 open, Limit Touch는 추가 가격 경로/체결 가정이 필요하므로 close만으로 체결을 추정하지 않는다.
주문 시점에는 미래 가격을 참조하지 않는다. Same Close의 낙관성을 숨겨 look-ahead가 없다고 주장하지 않는다.

## Metrics

Final Portfolio Value, Total Contribution(초기 투자금 포함), Investment Gain = final − contribution,
Total Return, CAGR, MDD, Volatility, Recovery Time, Buy/Sell Trades, Transaction Cost,
Cash Waiting Days를 목표로 한다.

Total Return은 먼저 단순 납입 대비 손익률(gain / contribution)로 이름과 분모를 표시한다.
이는 시간가중 수익률이 아니다. 분모 0이면 N/A다.
적립식 투자에서 final/initial 또는 final/contribution의 단순 CAGR을 전략 수익률로 쓰지 않는다.
향후 일초 적립 F_t를 가정한 r_t = V_t/(V_(t-1)+F_t) − 1의 누적으로
현금흐름 조정 수익률 지수를 만든다(분모 0인 기간은 미정의 처리).
CAGR은 이 지수의 누적 성장률을 실제 경과기간으로 연율화한다. XIRR/MWR은 후속 추가한다.
체결 시점이 바뀌면 현금흐름 타이밍과 수익률 산식도 함께 검증한다.

MDD·drawdown·Recovery는 위 조정 지수 기준으로 산출하여 적립이 낙폭을 감추지 않게 한다.
원시 Portfolio Value 낙폭을 표시한다면 별도 이름을 붙인다.
Volatility는 조정 일수익률 표준편차를 사용하고 연율화 계수를 결과에 명시한다.
회복시간은 고점부터 종전 고점 회복까지 달력일, 미회복이면 미회복 상태와 관측기간을 기록한다.
매수/매도 횟수는 실제 체결 이벤트 수다. Cash Waiting Days는 C의 매도 이후~재진입 이전
대기 거래일 수로 고정하며 달력일 대기와 구별한다. 최종일 미체결 강제청산은 하지 않는다.
Time In Market, Average Purchase Price, Number of Take Profits도 후속 확장한다.

## 비교와 반증 계획

STEP 9에서 동일 기간 A/B/C를 비교하고 시작일·시장국면·3/5/7/10/15/20% threshold 민감도를 조사한다.
Dot-com, GFC, COVID, Zero Rate, Inflation, Rate Hike, Recovery의 구간 경계는 결과를 보기 전에
정의하며 데이터가 없는 구간은 미검증으로 남긴다. 사후 최고 수익률 parameter를 정답으로 선택하지 않는다.
In-Sample/Out-of-Sample은 후속 도입하며 분할과 평가 기준을 사전에 저장한다.
차이가 시작된 날짜의 가격·적립·평균원가·현금·체결 이벤트를 차트와 로그로 역추적한다.

## Bias checklist — 매 실행 기록

Look-Ahead, Survivorship(지수 역사와 현재 구성종목 재구성 구별), Dividend Handling,
Price/Adjusted Price, Trading Day, Missing Data, Market Holiday, Execution Price,
Slippage, Transaction Cost, ETF Inception Date, FX Conversion Timing, Fractional Unit.
월 1일 휴장은 다음 거래일 적립으로 처리한다. ETF inception / FX는 현재 N/A와 이유를 기록한다.

## 연구 기록 상태

Dataset: 공급자·기간·snapshot 미정. Experiment: 미실행.
Result: 없음. Counter Evidence: 미측정. Failure: 미측정.
Conclusion: 판단 유보. What We Learned: 연구 가정과 구현 경계를 정의했으며 투자성과는 아직 학습하지 않음.
향후 각 run에 Problem, Hypothesis, Control Group, Strategy, Parameters, Dataset, Experiment,
Result, Counter Evidence, Failure, Conclusion, What We Learned와 config/commit/hash를 보존한다.
