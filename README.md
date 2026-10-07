# ZERO MARKET LAB

## STEP 5 Interactive Comparison UI

Case #01의 Strategy A/B/C 결과를 같은 시간축에서 탐색하는 Dash Visual MVP다. Market Price와 Portfolio를
분리해 표시하고, A/B/C와 Total Contribution, unified hover, adaptive date axis, vertical guide,
mouse-wheel zoom, pan, 양방향 x축 range 연동, Reset View, 비교 Metrics를 제공한다.

Start/End Date, Monthly Contribution, Take Profit %, Strategy C Reentry Months는 실제 엔진 파라미터로
연결된다. Run Backtest는 입력을 검증하고 데이터 기간을 필터링한 뒤 기존 비교 엔진을 재실행한다.
Asset, dividend, FX, cost, slippage, execution, fractional-unit 가정은 화면에 고정값으로 표시한다.

```powershell
.\.venv\Scripts\python.exe scripts/run_case01_comparison.py
.\.venv\Scripts\python.exe scripts/run_case01_ui.py
```

Dash UI는 `http://127.0.0.1:8050`에서 열린다. 초기 로드에서 전체 데이터 기간과 기본값 500,000 / 5% /
1개월로 결과를 즉시 표시한다. 브라우저 traceback은 노출하지 않고 잘못된 입력은 사람이 읽는 메시지로 표시한다.
CAGR, MDD, volatility, recovery, trade marker, drawdown, 비용, FX, Macro Overlay는 아직 포함하지 않는다.

### Chart Engine architecture spike

STEP 5를 commit하기 전에 Lightweight Charts 5.2.1을 `experiments/lightweight_charts/`에서 격리 검증한다.
현재 Dash/Plotly UI나 Python 계산 계층을 교체하지 않으며, 실제 daily close와 기존 Strategy C Event Log로
2-pane financial chart, crosshair, wheel zoom/pan, event markers, responsive resize를 검증한다.

```powershell
.\.venv\Scripts\python.exe experiments/lightweight_charts/build_prototype.py
.\.venv\Scripts\python.exe -m http.server 8060 --directory experiments/lightweight_charts
```

Prototype: `http://127.0.0.1:8060`. 집중 검증 예시는
`http://127.0.0.1:8060/?from=2026-03-01&to=2026-10-02&events=core`이다.
결정 근거는 `experiments/lightweight_charts/DECISION.md`에 기록한다. 2026-10-06 Financial Chart
Quality Gate의 최종 결정은 **MIGRATE TO LIGHTWEIGHT CHARTS**이며, production migration은 아직
시작하지 않았다.

### Goal Simulation Prototype v1

STEP 5와 분리된 한국어 연구 UI에서 투자 조건(시작일·초기 투자금·매월 투자금·기간)과
전략 조건(익절 기준·C 재진입 대기기간)을 나누어 입력하고 A/B/C를 항상 동시에 비교한다.

```powershell
.\.venv\Scripts\python.exe scripts/run_goal_ui.py
.\.venv\Scripts\python.exe scripts/run_goal_examples.py
```

UI는 `http://127.0.0.1:8070`에서 열린다. Compact toolbar의 native date input, 시작일 quick preset,
`월 50만원 적립` preset은 초기금 0, 매월 500,000, 10년, 익절 5%, C 재진입 1개월을 입력한다.
초기 투자금과 매월 투자금 중 하나만 양수여도 실행할 수 있다. Unified Research Chart는 S&P500을
왼쪽 축, A/B/C와 선택 가능한 목표·C 거래 marker를 오른쪽 축에서 같은 날짜로 비교한다.
목표 기반 분석은 선택 기능이다. `초기 투자금 × (1 + 목표수익률)`은 초기금만 있는 경우에만 적용하며,
월 적립금이 있으면 잘못된 목표선을 그리지 않고 총 납입금·평가금액·투자손익을 우선 표시한다.
각 전략 card는 A 대비 금액·비율, 매매 횟수, 현금 대기일, 시장 참여율과 사실 기반 판정을 표시한다.
Goal Analyzer는 Strategy 밖에서 목표 상태·최초 달성일·기간·목표 전 MDD를 계산한다.
Starting-Date Sensitivity와 자동 전략 탐색은 구현하지 않았다.

실제 과거 시장데이터로 투자 가설을 검증·반증하는 Interactive Backtest Research Lab.
목적은 자동매매 수익률 극대화가 아니라, 같은 시장환경에서 전략의 차이가 발생한 이유를 이해하는 것이다.

## Project Charter

상위 연구방 `20_금융_메인`은 금융 개념·경제 메커니즘·가설·해석을 담당하고,
이 프로젝트는 실험 설계의 명문화, 재현 가능한 구현, 측정, 시각적 검증을 담당한다.

Observe → Define → Hypothesize → Simulate → Attack → Compare → Falsify → Learn.

Market Event → Market Data → Price Movement → Strategy Action → Execution → Portfolio Result
→ Interactive Visualization → Hypothesis Verification / Falsification.

핵심 UX 질문: **언제부터 전략 간 결과가 벌어졌으며 왜 벌어졌는가?**
차트는 연구 및 디버깅의 핵심 제품 기능이다. 가설에 반하는 결과도 동등하게 기록한다.

장기 연구는 Strategy Comparison, Goal-Based Simulation, Starting-Date Sensitivity의 세 축으로 확장한다.
최종 자산가치뿐 아니라 목표 도달 여부·기간·목표 전 위험과 시작 시점별 재현성을 함께 본다.
화면은 한국어를 기본으로 하고 연구 재현에 필요한 영어 용어를 괄호나 tooltip에 병기한다.
이 방향은 현재 구현이 아니라 [Goal-Based Simulation Roadmap](docs/goal-based-simulation.md)의 후속 설계다.

그 이후에는 직접 전략 설정과 자동 전략 찾기를 분리하고, 제한된 파라미터 후보를 Goal·Risk·Sensitivity·
Validation 기준으로 비교하는 Strategy Discovery Research Track을 둔다. 단일 최고 수익률을 찾거나 미래
가격으로 만든 사후 최적 경로를 실전 전략으로 제시하지 않는다. 모든 행동은 근거 Event에 연결된 투자일지로
설명할 수 있어야 한다. 상세 기준은 [Automatic Strategy Search](docs/automatic-strategy-search.md)에 있다.

## 현재 범위

STEP 5 — Interactive Comparison UI. STEP 1 실제 데이터와 STEP 4 A/B/C 비교 엔진을 재사용하는
Desktop-first Dash UI를 구현했다. UI는 회계나 전략 규칙을 복제하지 않고 application service를 호출한다.
사용자 시각 검토 전에는 STEP 5를 완료 처리하거나 STEP 6으로 진행하지 않는다.

초기 연구는 S&P500 Benchmark 월 적립과 익절·재진입 A/B/C 비교다.
실제 ETF 매매, KRW 수익률, 세금, 계좌, 다중자산은 후속 범위다.

장기적으로 동일한 Research Engine에서 User Hypothesis Strategy, Published / Reference Strategy,
Control / Benchmark를 같은 데이터와 Execution Assumption으로 비교한다. Reference Strategy Library는
유명 전략을 정답으로 채택하는 목록이 아니라 출처·가설·데이터 요구사항·한계를 추적하고 재검증하기 위한 연구 카탈로그다.
현재는 설계만 기록했으며 Trend Following, Momentum 등 Reference Strategy는 구현하지 않았다.

## 문서

- [Architecture와 ADR](docs/architecture.md): 책임 경계, 기술스택, 상태와 이벤트 계약
- [Data Strategy](docs/data-strategy.md): 데이터 의미, provenance, 공급자 검증
- [Case #01](cases/case_01/README.md): 가설, 비교군, 실행 규칙, 지표와 반증
- [Roadmap / Definition of Done](docs/roadmap.md): 단계별 범위와 완료 게이트
- [Goal-Based Simulation Roadmap](docs/goal-based-simulation.md): 목표 분석·시작 시점 민감도·한국어 연구 UX 설계
- [Automatic Strategy Search](docs/automatic-strategy-search.md): 제한 기반 후보 탐색·검증·투자일지 설계
- [Cross-Asset & Hedge Research](docs/cross-asset-hedge-research.md): S&P500·장기국채·금·VIX의 정규화,
  상관관계, drawdown 방어효과 연구 설계
- [TIGER ETF V2 Foundation](docs/tiger-etf-v2-foundation.md): 360750 실제 raw OHLCV provenance,
  검증, Candlestick/Volume chart와 OHLC execution 설계 경계
- [Generic Explainable Simulator](docs/generic-explainable-simulator.md): 자산 독립 OHLCV 실행 엔진,
  DecisionRecord, Daily Ledger, 거래 생명주기와 TIGER V2 화면 통합
- [JOURNAL](JOURNAL.md): 결정과 검증 기록

## 개발 기준

Python / Pandas / Plotly / Dash(초기 UI 후보 1순위) / pytest / CSV·Parquet / Git·GitHub / Markdown.
설치된 Python 3.13.11과 프로젝트 `.venv`를 사용한다(3.12 미설치).
직접 의존성은 pandas, plotly, pytest, pyarrow, requests, kaleido이며 전이 의존성까지 requirements.txt에 버전을 고정했다.
Kaleido는 Plotly 검증 차트의 PNG 내보내기에만 사용한다.
현재 작업환경은 Windows PowerShell, 로컬 경로 `D:\workspace\github\zero-market-lab`이다.
GitHub public 저장소: https://github.com/kimchanj/zero-market-lab, branch `main`.

## 실행 (PowerShell, 프로젝트 루트)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/inspect_sp500_data.py --start 2000-01-01 --end 2026-10-02
.\.venv\Scripts\python.exe scripts/run_monthly_buy_and_hold.py
```

매 실행은 UTC timestamp별 새 snapshot을 생성한다. raw CSV/metadata/request는 `data/raw/<snapshot>/`,
정규화한 date·close Parquet는 `data/processed/<snapshot>/`, 자체 포함 Plotly HTML은 `artifacts/<snapshot>/`에 저장한다.
출력된 HTML을 브라우저에서 직접 열어 확인할 수 있다. 서버나 Dash 설치는 필요하지 않다.
raw 및 파생 데이터·차트는 공개 재배포하지 않도록 Git에서 제외했다. Git clone만으로 원자료가 복원되지는 않는다.
다운로드 실패는 오류로 종료하며 synthetic으로 대체하지 않는다. 네트워크 접근이 필요하다.

2026-10-05 실행: 요청 2000-01-01~2026-10-02 → 실제 2016-10-03~2026-10-02,
2,514행, 구조 검증 PASS. 배당 제외 PRICE_RETURN이며 장기 연구 공급자 확정은 아니다.
결측 표기 96행 제외와 기간 축소는 warning으로 metadata에 남겼다.
사용자가 실제 HTML을 열어 제공한 화면으로 선 그래프·날짜 방향·가격 축·제목을 시각 검증했다.
전체 STEP 1 판정과 Git 증거는 JOURNAL을 따른다.

## STEP 2 Strategy A 기준

- 각 year-month에 실제로 존재하는 첫 market observation date에 500,000을 현금으로 적립한다.
- CONTRIBUTION 다음 동일 날짜 Close에서 가용현금 전액을 매수하며 fractional unit을 허용한다.
- `buy_quantity = cash / close`; 비용·slippage·FX는 0/OFF이며 매도는 없다.
- 평균매입가는 `(기존 수량 × 기존 평균원가 + 신규 수량 × 매수가) / 총수량`이다.
- 매 거래일 말 cash, quantity, average cost, position/portfolio value, total contribution을 기록한다.
- Contribution과 BUY는 같은 날 발생해도 별도 이벤트로 보존한다.

실행 결과는 `artifacts/step_02/<run-id>/`에 summary JSON, state/event Parquet,
Plotly HTML과 검증 PNG로 저장된다. 산출물은 Git에서 제외된다.
S&P500 Price Index를 가상으로 분할 매수한 Benchmark Simulation이며 직접 거래 가능한 ETF 결과가 아니다.
Investment Gain은 `final portfolio value - total contribution`일 뿐 CAGR이나 전략 우월성 지표가 아니다.

각 단계는 Design → Implement → Automated Test → Actual Run → Visual Verification → Git Commit → JOURNAL을 따른다.
문서 전용 단계는 실행 테스트와 앱 화면 검증을 N/A로 기록하고 문서·diff를 검토한다.
단계 완료만으로 다음 단계 실행을 허용하지 않는다.

## TIGER 미국S&P500 Actual ETF Track V2

V2는 Legacy FRED/Plotly track을 유지한 채 `360750`의 2020-08-07 이후 실제 원시 OHLCV를 별도
package와 Lightweight Charts 화면에서 다룬다. 1,508 bars의 Candlestick, Volume pane,
OHLC crosshair, browser-local quick range/zoom/pan을 유지한다. 데이터 준비는
`docs/tiger-etf-v2-foundation.md`를 따른다. 그 위에 자산 독립 실행·회계 엔진과 설명 가능한
Daily Ledger prototype을 추가했다. 고정 2023-01-04~2023-04-04 구간에서 Open -1% 진입과
+5% 익절 규칙을 실행하며, 결과는 [Generic Explainable Simulator](docs/generic-explainable-simulator.md)를 따른다.

현재 투자조건·기간 재실행과 뉴스/연구 패킷을 함께 보려면 다음 로컬 API 화면을 사용한다.

```powershell
.\.venv\Scripts\python.exe experiments\tiger_etf_v2\build_simulation.py
.\.venv\Scripts\python.exe scripts\run_research_ui.py
```

브라우저에서 `http://127.0.0.1:8062/tiger_etf_v2/`를 연다. 투자기간과 금액, 매수 지정가, 익절,
최소 순수익을 바꾼 후 **시뮬레이션 실행**을 누르면 Python 엔진이 다시 계산한다. 차트 1M~ALL은
화면 조회 범위만 바꾼다. 뉴스 카탈로그는 별도 선택 기능이며 매매결과를 변경하지 않는다.
입력·뉴스·연구 전달 문서 사용법은 [Research Workstation](docs/research-workstation.md)을 따른다.
