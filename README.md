# ZERO MARKET LAB

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

## 현재 범위

STEP 1 — Real S&P500 Data Foundation. FRED SP500 CSV를 저장·정규화·검증하고 Plotly 단일 차트를 만든다.
Backtest Engine, Strategy, Portfolio, 성과지표, Dash UI는 구현하지 않았다.
STEP 2는 사용자 검토와 `STEP 2 시작` 지시 후에만 진행한다.

초기 연구는 S&P500 Benchmark 월 적립과 익절·재진입 A/B/C 비교다.
실제 ETF 매매, KRW 수익률, 세금, 계좌, 다중자산은 후속 범위다.

## 문서

- [Architecture와 ADR](docs/architecture.md): 책임 경계, 기술스택, 상태와 이벤트 계약
- [Data Strategy](docs/data-strategy.md): 데이터 의미, provenance, 공급자 검증
- [Case #01](cases/case_01/README.md): 가설, 비교군, 실행 규칙, 지표와 반증
- [Roadmap / Definition of Done](docs/roadmap.md): 단계별 범위와 완료 게이트
- [JOURNAL](JOURNAL.md): 결정과 검증 기록

## 개발 기준

Python / Pandas / Plotly / Dash(초기 UI 후보 1순위) / pytest / CSV·Parquet / Git·GitHub / Markdown.
설치된 Python 3.13.11과 프로젝트 `.venv`를 사용한다(3.12 미설치).
직접 의존성은 pandas, plotly, pytest, pyarrow, requests이며 전이 의존성까지 requirements.txt에 버전을 고정했다.
현재 작업환경은 Windows PowerShell, 로컬 경로 `D:\workspace\github\zero-market-lab`이다.
GitHub public 저장소: https://github.com/kimchanj/zero-market-lab, branch `main`.

## 실행 (PowerShell, 프로젝트 루트)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/inspect_sp500_data.py --start 2000-01-01 --end 2026-10-02
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

각 단계는 Design → Implement → Automated Test → Actual Run → Visual Verification → Git Commit → JOURNAL을 따른다.
문서 전용 단계는 실행 테스트와 앱 화면 검증을 N/A로 기록하고 문서·diff를 검토한다.
단계 완료만으로 다음 단계 실행을 허용하지 않는다.
