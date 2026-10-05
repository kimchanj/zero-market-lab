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

STEP 0 — Project Foundation. 문서만 작성했으며 실행 가능한 프로그램은 없다.
Engine, Strategy, Provider interface, UI, 데이터 다운로드, 패키지 설치는 수행하지 않는다.
STEP 1은 사용자 검토와 `STEP 1 시작` 지시 후에만 진행한다.

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
Python 버전·의존성 잠금·가상환경은 STEP 1에서 호환성을 확인해 확정한다.
현재 작업환경은 Windows PowerShell, 로컬 경로 `D:\workspace\github\zero-market-lab`이다.
GitHub 원격 저장소 연결 및 공개 배포는 아직 구성하지 않았다.

각 단계는 Design → Implement → Automated Test → Actual Run → Visual Verification → Git Commit → JOURNAL을 따른다.
문서 전용 단계는 실행 테스트와 앱 화면 검증을 N/A로 기록하고 문서·diff를 검토한다.
단계 완료만으로 다음 단계 실행을 허용하지 않는다.
