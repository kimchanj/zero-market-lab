# Roadmap / Completion gates

## Cross-Asset & Hedge Research Track

기존 STEP 번호와 분리한 후속 Track이다. STEP 5 Chart Zoom/Pan/Autoscale 안정화가 production chart 연결의
Critical Gate다.

0. HEDGE STEP 0 — Research / Data Design
1. HEDGE STEP 1 — Data Foundation
2. HEDGE STEP 2 — Normalized 100 Comparison
3. HEDGE STEP 3 — Rolling / Downside Correlation
4. HEDGE STEP 4 — Drawdown Hedge Effectiveness
5. HEDGE STEP 5 — Fixed Allocation Backtest
6. HEDGE STEP 6 — Dynamic Hedge Research
7. HEDGE STEP 7 — Automatic Hedge Allocation Search

현재는 Architecture, Data Requirement, Research Question만 설계했으며 prototype과 production UI는 구현하지 않는다.

## Generic Explainable Simulator Prototype

TIGER 360750 Data/Chart foundation 승인 뒤, 정규화된 OHLCV를 Instrument·Strategy·Execution·Cost와
분리해 실행하는 prototype을 구현했다. 이는 기존 STEP 번호를 변경하거나 STEP 6을 시작한 것이 아니다.
고정 실제 구간과 synthetic 다중자산 fixture로 Daily Ledger, DecisionRecord, 거래 생명주기,
비용 포함 손익과 차트/table 연결을 검증한다. 다음 확장은 사용자 검토 뒤 별도 scope로 정한다.

각 단계는 이전 결과를 검토하고 사용자 `STEP N 시작` 지시가 있을 때만 시작한다.

| STEP | 범위 | 해당 단계 완료 증거 |
| --- | --- | --- |
| 0 | Foundation | Charter, ADR, Case, Data Strategy, Roadmap, DoD, 문서 검토·commit·journal |
| 1 | Real S&P500 Data | 공급자/조건/기간 검증, loading·provenance·validation 테스트, 실제 데이터 raw chart 확인 |
| 2 | Single Strategy | 월 적립·cash·position·buy·valuation·Buy & Hold, 회계 테스트 및 실행 확인 |
| 3 | Synthetic Engine Verification | 결정론적 fixture로 경계·불변식·손계산 예상값 검증 |
| 4 | 3 Strategy Comparison | A/B/C 동일 입력 실행, 익절/재진입과 B 보존 조건 검증 |
| 5 | Interactive Comparison UI | Parameter Panel, Market/Portfolio Chart, Metrics 재실행·비교 확인 |
| 6 | Strategy Event Visualization | 거래·적립 이벤트와 marker 일치, 이벤트 의미·필터 검증 |
| 7 | Risk & Return Analytics | 현금흐름 조정 수익률, drawdown·MDD·회복·변동성 예상값과 화면 검증 |
| 8 | Goal-Based Simulation | 목표 정의를 확정하고 Goal Analyzer·상태·목표 전 위험 검증 |
| 9 | Starting-Date Sensitivity | 월별 시작 cohort, 목표 달성률·기간 분포·censoring·국면 의존성 검증 |
| 10 | Parameter Sensitivity / Case #01 Research | 사전 정의 구간·threshold 민감도·반증·실패·학습 결과 기록 |
| 11 | Cost / Slippage / Execution | 비용·체결 모델 비교, 정보 이용 시점과 회계 검증 |
| 12 | TIGER 360750 | 공식 상품 정보·실제 데이터·배당·비용·환율 검증 |
| 13 | S&P500 vs TIGER | 공통 기간, PR/TR·통화·상품 차이 명시 비교 |
| 14 | Macro Overlay | FED Rate·CPI·USD/KRW 시점 정렬과 화면 검증 |
| 15+ | Reference Strategy / Portfolio / Multi Asset / Rebalancing / Pension / ISA / Tax | 기존 의도를 보존해 별도 설계와 단계별 승인 범위로 확장 |

STEP 3은 검증 심화 단계이며 STEP 1/2의 테스트를 그때까지 유예한다는 뜻이 아니다.

STEP 0~5의 번호와 완료 이력은 바꾸지 않는다. 위 변경은 아직 시작하지 않은 단계의 연구 의존성을
구체화한 것이다. Goal-Based Simulation과 Starting-Date Sensitivity의 정의, 상태, 편향 통제,
한국어 UX 기준은 [Goal-Based Investment Simulation](goal-based-simulation.md)을 따른다.
별도 Goal Prototype v1은 STEP 8 완료나 단계 선행 시작으로 판정하지 않으며, 재사용 가능한 최소 계약을
검증하는 격리 실험으로 기록한다.

## Reference Strategy Research Track (Case #01 이후)

완료된 STEP 번호와 Case #01 A/B/C는 유지한다. Reference Strategy 연구는 STEP 10 이후 또는
15+와 병렬로 승인할 별도 Research Track이며, 지금 구현 순서를 확정하지 않는다.

1. 학술·practitioner 원문과 버전, 사용조건을 조사한다.
2. Strategy metadata와 원 규칙·데이터 요구사항·benchmark를 등록한다.
3. 원 논문의 정보 이용 시점과 파라미터를 보존해 규칙을 재현한다.
4. User Strategy / Published Strategy / Control을 동일 데이터와 execution 기준으로 실행한다.
5. 원 발표 결과와 재현 결과의 차이를 데이터·기간·비용·규칙 차이로 분석한다.
6. Transaction Cost / Slippage / 체결 지연을 반영한다.
7. Out-of-Sample, 대체 기간·자산·파라미터 민감도와 국면별 robustness를 검증한다.
8. Reproduced, Falsified, Inconclusive 등 결과와 반증 증거를 함께 기록한다.

예시 비교는 Monthly Buy & Hold, +5% Immediate Reentry, +5% 1-Month Reentry,
10-Month Moving Average, 12-Month Momentum이지만 마지막 두 전략은 현재 구현하지 않는다.
Reference Strategy 구현은 별도의 사용자 시작 지시와 Case 설계·완료조건이 필요하다.

## Strategy Discovery Research Track (메인 Roadmap 이후 또는 병렬 승인)

메인 STEP 번호와 현재 STEP 5를 변경하지 않는다. 아래 순서는 의존 관계를 나타내며 실제 번호는 해당 Track을
시작할 때 확정한다.

1. Investment Journal: Event/State 근거, 행동 이유, 차트 navigation 계약을 검증한다.
2. Automatic Strategy Search Level 2: 제한된 Parameter Grid, hard constraint, soft ranking을 구현한다.
3. Out-of-Sample / Walk-Forward Validation: training 선택과 validation 평가를 분리한다.
4. Strategy Building Blocks: Entry/Exit/Position/Reentry 등의 조합 계약을 설계한다.
5. Automatic Strategy Search Level 3: 검증된 building block의 구조 탐색을 연구한다.

Level 2 전에 Goal, Risk, Starting-Date, Parameter Sensitivity가 완료되어야 한다. Search Engine,
Candidate Generator, 투자일지 UI는 현재 구현하지 않는다. 설계와 편향 통제는
[Automatic Strategy Search](automatic-strategy-search.md)를 따른다.

## 공통 게이트

설계 → 구현 → 자동 테스트 → 실제 실행 → 화면 확인 → Git Commit → JOURNAL.
Baseline / Hypothesis / Measurement / Before–After를 기록하고 해당 없는 항목은 이유를 남긴다.
실패·제약을 감추지 않고 검증 명령, 결과, 남은 과제를 JOURNAL에 기록한다.
commit 후 JOURNAL 검증 결과를 반영하는 경우 후속 문서 commit으로 보존할 수 있다.

## STEP 0 Definition of Done

아래 체크 상태는 최초 commit 전 검토 기록이다. 최종 종료 판정과 commit 증거는 JOURNAL.md의 종료 기록을 따른다.

- [x] 기존 작업 디렉터리·파일·Git 상태 확인, 기존 파일 보존
- [x] Charter 및 포함/제외 범위 기록
- [x] ADR-001~014, Engine/UI·Provider·Strategy/Execution·Tax 경계 기록
- [x] A/B/C, 500,000, 5%, 적립·체결·대기·FX OFF·Benchmark 가정 기록
- [x] provenance, PR/TR/NTR/ETF/NAV, real/synthetic 원칙 기록
- [x] Roadmap 및 사용자 검토 게이트 기록
- [x] 미결정 사항과 위험요소 명시
- [x] 문서 링크·내용·git diff/공백 검사, 변경 파일 목록 확인
- [x] source/UI/engine 구현 및 framework 설치 없음
- [x] 실행 기능 테스트·앱 화면 확인 N/A 이유 명시
- [ ] Git commit 및 JOURNAL 기록, 저장소 상태 확인 — 작성자 정보 미설정으로 commit 대기

전체 충족은 PASS, 일부 미완료는 PARTIAL, 핵심 범위 불이행은 FAIL.
사용자 검토는 STEP 1 진입을 위한 별도 필수 게이트다.

## 미결정 사항

장기 데이터 공급자·라이선스·확정 기간, Python/패키지 버전·lock 방식,
GitHub remote, 구체 API 계약, 수치 정밀도·반올림 허용오차,
현실 거래비용·체결 모델·연율화 계수, 국면 경계·OOS 분할,
TIGER 상세 사양·FX 시각·세금 모델은 해당 STEP에서 검증 후 결정한다.
