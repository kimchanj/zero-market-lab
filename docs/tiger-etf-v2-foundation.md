# TIGER 미국S&P500 Actual ETF Track V2 — Data and Chart Foundation

## 경계

V1의 FRED S&P500 Price Index, STEP 1~5 엔진, Goal Prototype, Plotly UI는 Benchmark Research
Track으로 보존한다. V2는 `src/zero_market_lab/tiger_v2/`와
`experiments/tiger_etf_v2/`에 격리한다. 데이터·차트 foundation 위에 범용 Execution/Portfolio/
Daily Ledger prototype을 추가했다. 현재 계약과 결과는 [Generic Explainable Simulator](generic-explainable-simulator.md)를 따른다.

## 데이터 선택과 provenance

공식 우선순위는 KRX → TIGER → 검증된 보조 공급자다. KRX 정보데이터시스템에는 ETF 개별종목 시세
메뉴가 있지만 2026-09 이후 자동 다운로드는 로그인 자격증명이 필요하며 현재 환경에는 `KRX_ID`와
`KRX_PW`가 없다. TIGER 공식 factsheet로 상품코드 360750, KRX 유가증권시장, 최초설정일
2020-08-06, 거래단위 1주와 분기 분배 정책을 확인했다. 자동 수집은 Daum Finance daily chart API의
`adjusted=false` 응답을 보조 공급자로 사용한다.

| 항목 | 값 |
| --- | --- |
| Instrument | TIGER 미국S&P500 |
| Symbol / ISIN | 360750 / KR7360750004 |
| 시장 / 통화 | KRX 유가증권시장 / KRW |
| 요청 기간 | 2020-08-01~2026-10-06 |
| 실제 기간 | 2020-08-07~2026-10-06 |
| 관측 행 | 1,508 daily bars |
| 실행 가격 | Daum `adjusted=false` raw Open/High/Low/Close |
| 추가 필드 | Volume, Trading Value |
| 조정 가격 | 실행 OHLC에 사용하지 않음 |

raw JSON, processed CSV, retrieval UTC, 요청 URL, 실제 범위, SHA-256, adjusted/distribution 의미,
검증 결과는 timestamp snapshot과 `data/provenance/`에 저장한다. raw와 processed는 공급자 재배포
제약과 파일 크기 때문에 Git에서 제외한다. 상장 전 가격을 만들거나 S&P500 지수와 이어붙이지 않는다.

## 검증 결과와 누락 정책

필수 가격은 양수, 거래량은 0 이상이며 High/Low 관계, 날짜 오름차순, 중복, null을 fail fast로 검사한다.
실제 snapshot은 중복 0, 필수 null 0, zero-volume 0으로 PASS했다. 달력 최대 간격은 8일이다.
주말과 KRX 휴장일은 행으로 만들지 않으며 provider observation만 보존한다. forward-fill, 보간,
synthetic bar는 금지한다. KRX 거래 캘린더와의 전 세션 완전성 대조는 후속 검증이다.

Yahoo raw quote 교차검증에서 유효한 1,485개 공통 날짜의 O/H/L/C 불일치는 모두 0이었다. Yahoo는
21개 null placeholder를 포함하고 Daum에만 존재하는 날짜가 총 23개라 보완 공급자로 사용하지 않았다.
거래량은 공통 날짜 중 602개가 달라 Daum 단일 공급자 값으로 명시하며 독립 확인됐다고 주장하지 않는다.
누락값은 다른 공급자 값으로 채우지 않았다.

## Corporate action과 분배금

Daum의 adjusted 응답과 Yahoo adjusted close는 raw execution price와 다르므로 사용하지 않는다. Yahoo는
23개 distribution event를 제공하고 TIGER 공식 factsheet도 분기 분배를 확인한다. 이번 foundation은
분배금을 잔고에 입금하거나 재투자하지 않는다. 다음 엔진 단계에서 지급기준일, 실제 지급일, 세금과
재투자 정책을 별도 이벤트 계약으로 구현해야 한다. raw 가격과 total-return 성과를 섞지 않는다.

## Financial Chart

Lightweight Charts 5.2.1을 기존 vendored asset에서 재사용한다. 1,508개 Candlestick과 동일 time scale의
Volume pane을 브라우저에서 그린다. crosshair는 한글 날짜, 시가, 고가, 저가, 종가, 전일 대비 등락률,
거래량을 표시한다. 1M/3M/6M/1Y/3Y/ALL은 view range만 바꾸며 데이터나 simulation을 다시 실행하지
않는다. 휠 zoom, drag pan, layer toggle과 crosshair는 Python callback 없이 브라우저 안에서 처리한다.

브라우저 확인에서 setup 42.5ms, 1M 범위 전환, OHLC hover, 12회 wheel과 6회 pan 후 chart/pane 유지,
interaction 중 서버 요청 0건을 확인했다. 후속 prototype에서 동일 차트에 Strategy marker,
평균매입가, 익절선과 Ledger table을 추가했다. 계산은 차트가 아니라 Python Engine이 수행한다.

## 향후 Execution Model 계약

V2는 `EXECUTION_CLOSE`, `EXECUTION_NEXT_OPEN`, `LIMIT_TOUCH_DAILY`를 Legacy same-close 모델과 분리한다.
`LIMIT_TOUCH_DAILY`에서 `limit = average_cost × (1 + take_profit_rate)`이고 High가 limit에 닿으면
사전 주문이 있었다는 조건 아래 limit에서 체결한다. Open이 limit보다 높은 gap-up이어도 price improvement를
가정하지 않고 limit에서 체결하는 보수적 baseline을 사용한다. 같은 날 sell/reentry 순서는 daily OHLC만으로
확정할 수 없으므로 유리한 intraday 순서를 만들지 않는다. B1은 다음 거래일 Open 재진입을 baseline으로 하고,
충돌하면 `AMBIGUOUS_DAILY_BAR`를 남긴다. 월 적립금은 월 첫 KRX 관측일에 입금하고 그날 Close에서 매수한다.
실제 연금저축 baseline은 integer share와 잔여 cash다. fractional mode는 별도 simulation option으로만 둔다.
현재 범용 prototype은 Open -1% 진입, +5% 익절, 다음 거래일 재진입과 same-bar 보수 정책을
구현했다. 월 적립과 B1 계약은 아직 이 prototype으로 이관하지 않았다.

## 실행

```powershell
.\.venv\Scripts\python.exe scripts\fetch_tiger_360750.py --start 2020-08-01 --end 2026-10-06
.\.venv\Scripts\python.exe scripts\crosscheck_tiger_360750.py
.\.venv\Scripts\python.exe experiments\tiger_etf_v2\build_chart.py
.\.venv\Scripts\python.exe experiments\tiger_etf_v2\build_simulation.py
.\.venv\Scripts\python.exe -m http.server 8061 --directory experiments
```

브라우저에서 `http://127.0.0.1:8061/tiger_etf_v2/`를 연다.

## 공식 참고

- [KRX ETF 개별종목 시세 추이](https://data.krx.co.kr/?scrnId=02080706)
- [TIGER 미국S&P500 공식 factsheet](https://www.tigeretf.com/upload/etf/20250804095324004654.pdf)
