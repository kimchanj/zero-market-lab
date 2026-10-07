# Generic Multi-Asset Explainable Trading Simulator

## 목적과 범위

이 모듈은 일봉 OHLCV로 실행되는 투자 규칙을 자산과 분리하고, 매 거래일의 판단·체결·회계를
재현할 수 있게 기록한다. 현재 실증 사례는 `KRX:360750`이지만 코어에는 종목코드별 분기가 없다.
주식·ETF처럼 정수 단위로 거래하는 자산과 가상자산처럼 소수 단위를 허용하는 자산을 같은 계약으로
실행하는 synthetic smoke test를 둔다. 다중자산 포트폴리오와 실시간 주문은 현재 범위가 아니다.
`compare_results`는 여러 `SimulationResult`에서 최종자산, 순손익·수익률, 완료/Open 거래,
승률, 보유기간, 평균 거래손익, 비용과 MDD를 공통 행으로 만든다. 원본 결과가 각 자산의 Ledger와
Trade Summary drill-down source다. 실제 삼성전자·BTC 데이터 비교 UI는 아직 만들지 않았다.

기존 FRED S&P500, STEP 1~5, Goal Simulation, Plotly UI는 그대로 유지한다. 이 모듈은 기존
Lightweight Charts 기반 TIGER V2 화면에 결과를 공급하며 차트 엔진을 교체하지 않는다.

## 계층과 책임

```text
Provider → Instrument → MarketBar → Strategy Parameters
         → Execution / Cost → Portfolio accounting
         → DecisionRecord → Daily Ledger
         → Trade / Period Summary → Chart and Table
```

- `Provider`는 외부 데이터를 표준 `MarketBar` 목록으로 바꾼다.
- `Instrument`는 symbol, market, currency, timezone, 거래단위, 호가단위, 수량·통화 정밀도와 데이터 의미를 선언한다.
- `MarketBar`는 timestamp, open, high, low, close, volume을 필수로 가진다. trading value, NAV, bid, ask는 선택 필드다. 현재 주기는 1D다.
- `StrategyParameters`는 진입·익절 규칙을 선언한다. 시장데이터 취득이나 체결을 수행하지 않는다.
- `Execution`은 호가 반올림, touch 판정, 수량, 비용과 일봉 내 순서 불확실성을 처리한다.
- Engine은 현금·포지션·평균단가를 갱신하고 단일 source of truth인 Ledger를 만든다.
- UI는 Engine이 만든 값과 설명만 표시한다. 브라우저에서 전략이나 손익을 재계산하지 않는다.

구현 위치는 `src/zero_market_lab/simulator/`다. `FrameOHLCVProvider`는 현재 CSV/DataFrame
adapter이며, 다른 공급자는 같은 `load_ohlcv` 계약으로 추가한다.

## 프로토타입 규칙

실제 데이터 확인용 고정 조건은 다음과 같다.

| 항목 | 값 |
| --- | --- |
| 자산 | TIGER 미국S&P500 (`KRX:360750`) |
| 기간 | 2023-01-04~2023-04-04, 62 거래일 |
| 초기 현금 | 500,000 KRW |
| 진입 주문 | 당일 Open의 1% 아래, 호가단위로 내림 |
| 진입 체결 | `Low <= entry limit`이면 limit 가격에 체결 |
| 익절 주문 | 평균 매입가의 5% 위, 호가단위로 올림 |
| 익절 체결 | 진입 이후 거래일에 `High >= target`이면 target 가격에 전량 체결 |
| 재진입 | 매도 다음 거래일부터 같은 진입 규칙 재평가 |
| 수량 | 정수 주, 수수료 포함 가용현금 이내 최대 수량 |
| 자금 운용 | 잔여현금 보존, 매도대금 전액 다음 거래에 재사용 |

Open을 본 뒤 계산한 limit 주문이 같은 날 Low에서 체결될 수 있다고 가정한다. 일봉만으로 Open 이후
고가·저가의 발생 순서를 알 수 없으므로, 진입과 익절 가격이 같은 bar에서 모두 touch되면
`AMBIGUOUS_ENTRY_EXIT`를 남기고 매도하지 않는다. gap에서 더 유리한 가격도 가정하지 않고 limit
가격을 쓴다. 이 정책은 일봉의 정보 한계를 드러내기 위한 보수적 baseline이며 intraday 실행을
재현한다는 뜻이 아니다.

## 비용과 순수익

비용은 매수 수수료, 매도 수수료, 매도세와 고정 수수료를 분리한 `CostConfig`로 주입한다.
실증 화면은 **매수·매도 각 0.015%, 매도세 0%**를 연구용 예시로 사용한다. 특정 증권사·계좌의
검증된 실비가 아니므로 투자 판단용 비용값으로 간주하면 안 된다.

완료 거래의 순손익은 `매도금액 - 매수금액 - 매수수수료 - 매도수수료 - 세금`이다. Open 거래의
미실현 순손익은 현재 종가 평가손익에서 이미 낸 매수수수료만 뺀 값이며, 아직 발생하지 않은 매도비용은
빼지 않는다. `required_exit_price`는 목표 순수익률을 충족하는 최소 호가를 비용 포함 방식으로 구한다.

## 설명 가능한 Ledger

각 거래일은 OHLCV, 이전/이후 현금과 수량, 평균단가, 주문가, 익절가, status/action, 체결가·수량,
매수·매도금액, 비용·세금, 실현·미실현 손익, 포트폴리오 가치, 보유기간, trade ID를 기록한다.
판단 근거는 표시문구가 아닌 구조화된 `DecisionRecord`로 보존한다.

```text
timestamp / rule_name / rule_value / observed_value /
comparison / result / reason_code / trade_id
```

한글 설명은 이 레코드에서 생성한다. 주요 reason code는 `ENTRY_FILLED`, `ENTRY_NOT_TOUCHED`,
`TAKE_PROFIT_FILLED`, `TARGET_NOT_REACHED`, `NEXT_BAR_REENTRY`,
`AMBIGUOUS_ENTRY_EXIT`, `INSUFFICIENT_CASH`다. 따라서 테이블 문구가 바뀌어도 판정 증거는 유지된다.

Trade Summary는 진입·청산, 수량, 비용, gross/net 손익, 수익률, 거래일·달력일 보유기간,
투입 전후 자금과 종료 상태를 보인다. 기간 말 미청산 포지션도 `OPEN`으로 숨기지 않는다.
Period Summary는 실현·미실현 손익, 비용, 완료/Open 거래 수, 보유기간과 portfolio-value MDD를 제공한다.

## 실제 실행 결과와 화면

고정 구간 실행 결과는 완료 거래 1건과 Open 거래 1건이다. 최종자산은 546,779원,
순손익 46,779원, 순수익률 9.3558%, 비용 231원, MDD -4.0695%다.
`TRADE-0001`은 2023-01-06 12,120원에 41주 진입해 2023-02-03 12,730원에 익절했고
순손익은 24,857원이다. `TRADE-0002`는 기간 말 Open이다. 이 구간은 출력 형태와 생명주기 확인을
위해 사전에 고정했으며 최고 수익 구간이나 최적 파라미터를 찾은 결과가 아니다.

기존 candlestick/volume chart 위에 BUY/SELL marker, 평균단가, 익절선을 추가했다. `SIM` 범위,
레이어 toggle, crosshair의 당일 상태, marker 상세, Trade Summary와 Daily Ledger가 같은 Engine
payload를 사용한다.

```powershell
.\.venv\Scripts\python.exe experiments\tiger_etf_v2\build_simulation.py
.\.venv\Scripts\python.exe -m http.server 8061 --directory experiments
```

브라우저에서 `http://127.0.0.1:8061/tiger_etf_v2/`를 연다. 생성되는 JS/JSON과
`artifacts/tiger_etf_v2_explainable/prototype_20230104_20230404/`의 Ledger CSV,
Trade CSV, Decision JSON, Period JSON은 재현 가능한 실행 산출물이며 Git에서는 제외한다.

동적 투자조건과 뉴스/연구 화면은 `scripts/run_research_ui.py`를 실행한 8062 포트에서 사용한다.
정적 8061 화면은 고정 payload를 보여주므로 날짜·금액 변경 후 재계산할 수 없다.
입력과 결과의 동기화 계약은 [Research Workstation](research-workstation.md)을 따른다.

## 검증과 제한

unit test는 entry touch/non-touch, same-bar ambiguity, 익절 성공·미도달, 다음 bar 재진입,
비용·세금·순수익, 목표 순수익 매도가, 복리 재투자, 회계 불변식, 정수·소수 수량 자산 smoke test,
잘못된 OHLC 거부와 chart payload 연결을 검사한다.

현재 결과는 raw/unadjusted 가격이며 분배금, NAV 괴리, bid/ask, slippage, 부분체결, 실제 주문시각,
호가 잔량, 휴장 캘린더 완전성, 세금·계좌 규칙을 반영하지 않는다. survivor-free universe나 여러 자산을
동시에 보유하는 포트폴리오도 아니다. 파라미터 탐색·최적화·미래 예측은 수행하지 않았다.
