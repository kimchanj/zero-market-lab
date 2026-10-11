# Trader UX Accuracy / S1 Robustness — 이어받기 기록

기준: 2026-10-09, `main` HEAD `ee62796e198b6c1a4dd148908c3a35d2405ba797`. 이 기록과 다른 미커밋 작업을 보존한다. 사용자 화면 검토 전 commit/push하지 않는다.

## 이번 구간에 완료한 작업

- 마지막 실행 조건과 현재 입력을 분리했다. 전략, 기간, 자금, S1 파라미터, 비용을 바꾸면 기존 결과에 stale 배너와 흐림 표시가 뜬다. 재실행하면 배너가 사라진다. 기간·연도·안정성의 추가 분석은 마지막 실행 조건을 사용한다.
- 실행 조건 표시는 선택 전략이 S1일 때만 진입·익절 파라미터를 포함한다.
- S1 기본 결과에 같은 기간 S0의 최종자산과 S1-S0 차액을 표시하고 배당 미반영 가능성을 알린다.
- 마지막 미청산 포지션의 평가손익률, 보유 기간, 보유 시작 후 종가 기준 최악 평가손익·수익률을 엔진 결과와 기본 화면에 추가했다. 장중 최저가 기준 손실은 아니다.
- 기존 S3 합성 테스트가 20거래일 `TIME_STOP` 체결을 검증함을 확인했다.
- 브라우저에서 S1 TP 5% 실행 → 입력 3% 변경 시 stale 경고와 기존 결과 유지 → 재실행 후 TP 3% 결과와 stale 해제를 확인했다. 로컬 화면: `http://127.0.0.1:8074/asset_discovery/` (서버는 종료될 수 있음).
- 전체 테스트 `240 passed`, `pip check` 정상, `node --check` 정상, `git diff --check` 오류 없음.

## 이어서 할 작업 (P0 우선)

1. **Affordability:** 현재가·가용현금·수수료 포함 최대 정수 매수수량을 자산/셀에 추가한다. 0주 매수 불가를 `NOT_AFFORDABLE`로 표시하고, 매도 후 재진입 실패를 별도 `REENTRY_BLOCKED_BY_CAPITAL` 이벤트로 기록한다. 과거 기간에 실제 매수한 전략과 현재 시드로 매수 불가능한 상태는 서로 다른 개념으로 분리한다.
2. **Rolling:** S0를 같은 rolling window마다 계산하고 S1 초과수익·방어·상승 놓침을 집계한다. `NOT_AFFORDABLE`, `FLAT`, 데이터 부족을 양/음수 비율 분모에서 분리하고 6M/1Y 결과를 다시 산출한다. 겹치는 창은 독립 표본이 아님을 유지한다.
3. **ISA / 비용:** 중개형 ISA 종목 가능 여부와 KOSPI·KOSDAQ·국내 ETF 거래세를 최신 공식 자료로 확인한 뒤 상품 메타데이터와 버전이 있는 비용 프로필을 만든다. 확인 전 임의 세율·계좌 혜택을 거래별 P/L에 섞지 않는다. 미국 개별주는 연구 자산으로 유지한다.
4. **화면:** 기본 후보표에 현재가·매수가능 수량·ISA 가능 여부, S1 위험 설명, 데이터 품질 한 줄, S3 Time Stop 미발생 시 S2와 동일한 이유를 추가한다. S1 승률/PF는 상세 영역에서만 보이고 완료 거래에 국한된 수치임을 명시한다. 단일 실행 흐름과 기간별 비교를 기본 정보 구조로 재검토한다.
5. **Paper Trading:** 전략·비용·체결 규칙 버전과 데이터 provenance를 고정하는 계약, 후보 체크리스트, 미래 관측 데이터만 추가하는 절차를 설계한다. 실제 주문 기능은 만들지 않는다.

## 재개 절차

1. `git status`, `git diff --stat`, `git diff --cached`, `git log -5`로 기존 변경을 확인한다. `reset`, `clean`, `checkout`으로 삭제하지 않는다.
2. 위 P0 1번부터 진행하고 변경마다 단위 테스트와 실제 화면을 확인한다.
3. 최종 회귀 검사: `.\.venv\Scripts\python.exe -m pytest -q`, `.\.venv\Scripts\python.exe -m pip check`, `node --check experiments/asset_discovery/app.js`, `git diff --check`.
4. 사용자가 화면을 검토하기 전에는 commit/push하지 않는다.

## 2026-10-10 이어서 완료한 작업 — 화면 검토 대기

- 기존 미커밋 파일과 `main` HEAD를 유지했다. 이 구간에서 commit/push하지 않았다.
- **P0:** 정수주 매수 가능 수량에 수수료·슬리피지를 포함했다. 과거 0주 매수 상태와 최신 종가 기준 신규 50만 원 시드의 매수 가능성을 분리했다. S1 재진입 조건 충족 후 자금 부족은 날짜·가용현금·1주 필요금액 이벤트로 기록한다. 실제 화면에서 SK하이닉스는 과거 거래가 18회 있었지만 최신 종가 기준 0주이고, 재진입 실패 날짜 2026-01-07이 표시됨을 확인했다.
- **P0:** ISA 상품 유형은 공식 자료로 확인해 3개 KRX 종목을 후보로, 3개 미국 개별주를 연구용으로 메타데이터화했다. KOSPI/KOSDAQ/ETF의 2026년 매도세 차이를 버전 있는 참고 비용 프로필로 문서화했다. 장기간 백테스트에 2026년 세율을 일괄 소급하지 않으며, 입력 가능한 연구용 비용 가정이 실제 수익 계산에 적용된다. [근거와 제약](instrument-cost-isa-policy.md).
- **P0:** 삼성전자·SK하이닉스·NAVER의 1Y에서 S3 시간청산 0회이며 S2와 최종자산이 같음을 확인했다. 3Y 삼성전자는 시간청산 4회로 결과가 달랐다. 화면의 연구 상세에 동일 이유를 표시한다.
- **P1:** 단일 실행 버튼 뒤 기본 여섯 금액 카드, ISA 종목표, 6M~5Y 기간 표, 일별 매매기록이 표시된다. 부가 손익·위험 지표와 후보 필터는 접힌 상세에 둔다. 실제 로컬 브라우저에서 삼성전자 S1 결과·S0 비교·6기간·244일 장부 및 미국 종목 ISA 필터를 확인했다.
- **P2:** 월별 시작 6M/1Y 창에서 S1 TP 3%/5%와 동일 창 S0를 계산한다. `NOT_AFFORDABLE` 창은 별도 계수하고 플러스·S0 초과 비율에서 제외한다. 실제 6종목 결과와 표본 주의는 [rolling 기록](s1-rolling-robustness.md)에 적었다.
- **P3:** 전략·비용·체결 규칙 버전, 관측 시각·데이터 해시를 갖는 append-only 모의거래 계약 및 후보 점검표를 [설계](paper-trading-foundation.md)에 추가했다. 실행 주문·미래 관측 입력·저장소는 구현하지 않았다.
- 검증: 전체 `244 passed` (Windows 기본 임시 폴더 접근 오류로 첫 실행 실패, 권한 있는 작업공간 임시 경로에서 재실행 성공), `pip check` PASS, `node --check` PASS, `git diff --check` PASS. 임시 pytest 폴더는 제거했다.

### 남은 확인·후속 작업

1. 사용자 화면 검토 후 비용 가정과 S1 위험 설명이 충분한지 확인한다. 승인 전 commit/push 금지.
2. 정확한 과거 실거래 비용 재현에는 날짜별 세율·상품 법적 형태·계좌 수수료 검증이 필요하다. 현재 0% 기본 매도세는 연구용 가정이며 공식 비용 프리셋이 아니다.
3. ISA 실제 계좌 매수 가능 여부와 계좌 단위 세제는 증권사 계좌·상품별 확인이 필요하다. ETF는 구조만 준비했고 새 Universe 데이터는 추가하지 않았다.
4. Rolling 창은 크게 겹치며 수동 선정 6종목 표본이다. 비중복 표본 및 외부 검증과 미래 paper trading은 후속 연구다.

## 2026-10-10 후속 방향: Entry Filter + CASH

- 기존 S0~S7과 이전 미커밋 변경을 보존했다. S4의 SMA100 필터를 확인하고, 공통 `EntryFilter` 구성요소를 두어 새 S1-TF/S2-TF의 전일 MA200 진입 판단에 재사용했다. 205거래일 사전 관측이 부족하면 새 셀은 `INSUFFICIENT_DATA`다.
- S1-TF는 S1 청산 규칙을, S2-TF는 S2의 TP/SL 청산 규칙을 그대로 사용한다. S2 TP/SL은 입력 가능하며 고정 비교표에서 TP3/5 × SL5/7/10을 별도로 검토한다. 필터는 보유 포지션을 강제 청산하지 않는다.
- 현금 일수·비율, 필터 통과/실패, 차단된 진입 기회, 청산거래 기대값, MDD 회복 필요수익, 실현/미실현 손익과 총자산을 기록·표시한다. 차단된 진입의 20/60거래일 후 수익률은 사후 연구용이며 실행 판단에 사용하지 않는다.
- 같은 205거래일 준비 조건에서 S1과 S1-TF TP5를 6M/1Y rolling으로 나란히 계산한다. 실제 관찰과 제한은 [방향·결과 기록](entry-filter-cash-research.md), 2026년 6월 진입 반증 사례는 [open-position case](s1-open-position-risk-case.md)에 있다.
- 기존 UI의 stale guard·매수가능성·ISA·S0 비교·금액 요약을 유지했다. 전략 비교 패널은 펼칠 때 계산하며, 실제 주문·Kelly·자동 최적화는 만들지 않았다.
- 전체 회귀 `249 passed`; `pip check`, `node --check`, `git diff --check` 통과. 기존 chart hover Node 테스트 9개도 통과했다. 샌드박스에서 Node worker spawn과 Windows pytest 임시 디렉터리 권한 오류가 나서 권한 있는 동일 명령으로 재실행했다. 검증 중 만든 pytest 임시 폴더는 제거했다.
- 실제 브라우저에서 Samsung/SK hynix/NAVER의 새 전략 선택, 총자산·실현/미실현 손익, S0 대비, 18개 고정 전략 비교, NAVER S2-TF TP5/SL7의 현금 대기와 진입 차단 100건을 확인했다. 로컬 검토 화면은 `http://127.0.0.1:8078/asset_discovery/`이다. 세션이 종료되면 `python scripts/run_research_ui.py --port 8078`로 다시 시작한다.
- 이 방향 변경도 **사용자 화면 검토 전 commit/push 금지**다. 아직 staged 파일이 없다. 최종 승인 시 현재 전체 미커밋 범위를 다시 검토하고 그때 commit/push를 결정한다.

## 2026-10-10 Child Architecture 문서 정리 — 검토 대기

- [메타 설계](../ZERO_MARKET_LAB_META.md)를 우선 읽고 Entry Filter, rolling, Paper Trading 문서 및 현재 전략 구현을 대조했다. 직접 충돌은 확인하지 않았으나 Phase Engine은 아직 미구현이며 기존 전략 엔진은 목표 컴포넌트가 완전히 분리된 구조가 아니다.
- [Strategy Research Framework](strategy-research-framework.md)에 Phase/Strategy 경계, 현재 S0~S7·S1-TF·S2-TF의 동작과 한계, CASH, 체결·비용·버전 계약, 평가 지표와 검증 사다리를 정리했다.
- [FECM Market Phase Engine v1](fecm-market-phase-engine-v1.md)에 price-only 다섯 Phase의 **규칙 후보**, point-in-time Evidence, 전이·False Spring/Autumn·사후 검증 계약을 설계했다. 확정 알고리즘, UI, 전략 연결, 자동 Capital Rotation은 구현하지 않았다.
- 다음 구현은 Phase Engine v1의 규칙·전이·실패 정의를 사용자와 검토하고 고정한 **후** 별도 단계에서 시작한다. 기존 미커밋 작업은 보존했으며 사용자 검토 전 commit/push하지 않는다.

## 2026-10-10 FECM Price-only Phase Engine STEP 1 — 화면 검토 대기

- 루트 메타 설계와 Child Architecture, Entry Filter 연구 기록을 우선 대조했다. 전략의 기존 결과를 바꾸지 않는 독립 `market_phase` 패키지와 여섯 종목 CSV/JSON 검증 스크립트를 추가했다.
- `PRICE_PHASE_V1`의 MA50/MA200, 기울기 5/10거래일, 3거래일 전이 확인, False Spring/Autumn 60거래일을 **실제 결과 관찰 전** 문서화했다. 설정 해시를 모든 일별 출력에 기록한다. Phase[t]는 t 종가까지의 데이터만 쓰며 t+1 이후에만 행동 연구에 사용 가능하다.
- 최초 실행 출력 `artifacts/fecm-price-phase-v1-20261010/`을 보존했다. 사후 평가의 Summer 소요일 및 낙폭 계산 정정본은 `artifacts/fecm-price-phase-v1-20261010-validated/`에 두었고 여섯 일별 라벨 CSV 해시는 최초본과 모두 같다. [전체 결과·실패·사례](fecm-market-phase-engine-v1-results.md)를 참조한다.
- 후보 75건 중 확인 16건, False Spring 59건. Autumn 87건 중 60일 안에 Summer로 복귀한 건 67건이다. 삼성전자 2026-06-25 Summer에서 07-27 Autumn까지 21거래일이 걸렸다. 결과를 보고 규칙을 조정하지 않았다.
- 다음 단계: 사용자 검토 후 v1을 그대로 독립 표본에서 반증하고, 원인 분석을 별도 `v1.1` 가설로 문서화한다. S1/S2/S7 자동 연결, Capital Rotation, 실제 주문, UI 고도화는 시작하지 않는다. 이전 Trader UX·Entry Filter의 미커밋 변경도 계속 보존한다. **사용자 검토 전 commit/push 금지.**
- 검증: 전체 Python `255 passed`, JavaScript hover `9 passed`, `pip check` 정상, `node --check` 정상, `git diff --check` 공백 오류 없음. Windows 샌드박스의 pytest 임시 폴더 접근 거부와 Node child-process `EPERM`은 권한 있는 동일 명령 재실행에서 해소했다. 생성한 pytest 임시 폴더만 삭제했다.

## 2026-10-10 PRICE_PHASE_V1 실패 분석 STEP 2 — 검토 대기

- STEP 1의 `PRICE_PHASE_V1` 규칙·상태 기계·엔진 소스·기존 결과 문서를 동결했다. 6종목 일별 CSV 해시와 기준 집계 Candidate 75/확인 16/False Spring 59, Autumn 87/Winter 12/Summer 재개 67/미해결 7/검열 1을 검사한 후에만 분석했다.
- 독립 [분석 스크립트](../scripts/analyze_phase_failures.py)가 당시 Evidence만 snapshot으로 만들고 사후 수익·낙폭은 별도 결과 열에 붙인다. CSV/JSON 산출물은 Git 제외 `artifacts/fecm-price-phase-v1-failure-analysis-step2/`에 있다. 새 Phase UI나 전략 연결은 없다.
- [성공/실패 비교 기록](fecm-market-phase-v1-failure-analysis.md): Spring 성공군은 MA200에 더 가깝지만 Higher Low는 실패군에서 더 흔하다. Autumn은 Winter군의 장기 기준 위치가 약한 반면 67건이 빠르게 Summer로 복귀한다. 30거래일 보조 묶음에서 Spring 75건→29 Episode로 중복 민감도가 크다. 삼성 신호 지연은 Summer 조건의 장기 기울기와 3일 확인 구조가 설명한다.
- 다음 STEP: 현재 6종목은 Development Set으로 고정하고 Holdout 선정 기준을 사전 명시한다. v1.1 가설은 1~2개만 선택해 독립 자료에서 반증한다. **이번 STEP에서는 규칙 변경·새 Holdout 적용·commit/push를 하지 않는다.**
- 최종 검증: Python 전체 `259 passed`, 기존 JS hover `9 passed`, `pip check`·`node --check`·`git diff --check` 통과. 분석 파일 3개의 재실행 SHA-256이 동일했고 입력 일별 Phase CSV 6개의 SHA-256도 STEP 1 값과 모두 동일했다. pytest 임시 경로 권한 오류 방지를 위해 전체 Python 검사는 권한 있는 동일 명령으로 실행했다.

## 2026-10-10 FECM Multi-Timeframe STEP 3 — 검토 대기

- 기존 `PRICE_PHASE_V1` 엔진·파라미터·일별 라벨과 STEP 1·2 연구결과를 동결했다. Parent/Child **연구용** A(MA200/50)·B(MA200/20) 두 후보의 규칙·평가 기준은 [STEP 3 문서](fecm-multi-timeframe-phase-research.md)에 실제 시세 실행 전에 기록했다. 6개 Development 종목만 분석했고 Holdout은 열지 않았다.
- [독립 분석 스크립트](../scripts/research_multitimeframe_phase.py)는 당일 종가까지의 정보로 Parent/Child 조합을 만들고 기존 Spring 75·Autumn 87 사건의 사후 결과는 별도 파일에서만 결합한다. 출력은 Git 제외 `artifacts/fecm-multitimeframe-step3/`에 있다.
- A의 Parent/Child 전이는 공통기간 94/477건, B는 93/735건으로 두 시간축의 **형식적 분리**는 관찰됐다. 하지만 Spring 성공 16건 중 15건과 False 59건 모두 Parent WINTER였다. A의 Autumn 87건 모두 Parent SUMMER이며 B도 86건이 Parent SUMMER, 1건은 UNKNOWN이다. 즉 Parent 맥락만으로 결과를 분리하지 못했다. H1/H2의 좁은 표현에는 반례가 있고 H3도 아직 입증되지 않았다.
- 삼성 2026 급락에는 Child 약화가 v1 Autumn보다 먼저 표시됐지만 Parent는 마지막 관측일까지 Summer였다. SK 2025의 빠른 Summer 복귀도 Parent Summer 안에서 일어났다. 더 빠른 상태 묘사와 예측·전략 개선은 다르다.
- 다음 단계는 사용자 검토 후 후보 1개·상태 의미·가설/반증·Holdout 구성 기준을 **결과를 보기 전에** 확정하는 것이다. 현재 후보를 수익률로 고르거나 v1.1 규칙·Strategy·Rotation·UI를 변경하지 않는다. 사용자 검토 전 commit/push하지 않는다.
- STEP 3 검증: Python 전체 `263 passed`, 기존 JavaScript hover `9 passed`, `pip check`·`node --check`·`git diff --check` 통과. 결과 CSV/JSON의 재실행 SHA-256과 기존 v1 일별 라벨 6개 SHA-256이 모두 동일했다. 검증이 만든 pytest 임시 폴더만 제거했다.

## 2026-10-10 FECM Transition Dynamics STEP 4 — 검토 대기

- [STEP 4 사전 계약·Development Set 결과](fecm-transition-dynamics-research.md)에 H4(Spring 장기 하락 둔화·회복 지속)와 H5(Autumn 낙폭 확대·약화 지속)를 **결과 실행 전** 5/10거래일 Feature, 기존 Outcome, 1차 지표, 반증 방향과 함께 고정했다. 연구 전용 [스크립트](../scripts/research_transition_dynamics.py)는 기존 Phase Engine·Parent/Child 모델·Strategy/UI를 수정하지 않는다.
- Frozen v1 Spring 성공 16/False 59, Autumn Winter 12/Summer 복귀 67/미해결 7/검열 1을 그대로 사용했다. 결과 CSV/JSON은 Git 제외 `artifacts/fecm-transition-dynamics-step4/`에 있다. H4 Primary 차이는 +0.133%p이나 MA50 회복 지속은 예상과 반대였다. H5 Primary 차이는 −0.90%p이나 약화 지속은 예상과 반대이고 회복 실패 중앙값은 같다. 두 가설 모두 **WEAK**. State의 MA200 거리 차이가 두 가설의 Velocity 차이보다 컸다.
- 삼성 2026 약화, SK 2025 빠른 복귀, NAVER 2026 세 False Spring, 기존 성공 Spring 세 사례의 당일 Feature와 설명용 전후 Timeline을 보존했다. 단일 사례의 조기 경고를 예측력으로 제시하지 않는다. 기존 v1 6개 일별 CSV SHA-256은 유지한다.
- **STEP 4 연구·문서 작성은 완료, 사용자 검토 대기. Holdout 준비는 미완료.** 다음에는 H4/H5를 그대로 표본 외 반증할지 별도 버전으로 재설계할지 검토하고, 먼저 Holdout 선정·자료품질 규칙을 고정한다. 이번에는 Holdout을 선택·실행하지 않았고 threshold 최적화·새 Phase Rule·Strategy 연결·Capital Rotation·UI·commit/push를 하지 않았다.
- 검증: 전체 Python **267 passed**, 기존 JavaScript hover **9 passed**, `pip check`·`node --check`·`git diff --check` 통과. 분석 출력은 두 독립 경로 재실행에서 동일 SHA-256이고 v1 일별 라벨 6개·사건 JSON 6개·STEP 3 A 문맥 CSV 6개의 Frozen 해시 검사가 통과했다. Windows 샌드박스의 pytest 임시 경로·Node spawn 접근 거부는 권한 있는 동일 명령 재실행으로 해소했다.

## 2026-10-10 Paper Trading STEP 5 — Forward Validation 기반, 검토 대기

- 우선순위를 **Research Expansion → Forward Validation**으로 전환했다. `PRICE_PHASE_V1` baseline과 기존 Daily CSV 해시, Parent/Child 기술 연구, H4/H5의 `WEAK` 판정, S0~S7·Rolling 결과는 동결한다. 추가 Phase 연구와 Holdout 실행은 일시중지한다.
- [Paper Trading MVP 계약·사용법](paper-trading-mvp.md)에 따라 별도 `paper_trading` 패키지와 SQLite/CLI를 추가했다. 한 계좌·한 자산·S1의 설정, Phase/전략/비용/체결 버전을 고정하고 하루씩 다음 시장 바를 처리한다. 먼저 이전 주문을 평가한 뒤 오늘 종가로 다음 Decision을 append한다. 기존 `paper_contract.py`의 방향을 구현했으나 Backtest 엔진·전략 규칙은 수정하지 않았다.
- `HISTORICAL_REPLAY`와 `LIVE_FORWARD`를 저장·표시에서 분리했다. LIVE는 계좌 생성 이후 새 시장 관측일과 생성 이후 공급자 refresh가 있어야 하므로 2026-10-10 현재 **실제 Pilot은 아직 시작하지 않았다**. 사용자가 첫 자산을 선택하기 전 임의 추천도 하지 않는다. Replay CLI에서 삼성 2026-10-06~08 3일을 검증했으며 10-08 1주 보유·Cash 233,460원·Equity 496,460원으로 기록됐다.
- 이전 전체 OHLCV 이력의 SHA-256 변화가 있으면 다음 실행을 중단한다. 정정은 감사 이벤트로만 append하고 과거 Decision을 고치지 않는다. 동일 날짜 재실행은 새 이벤트를 만들지 않으며 DB 재시작 후 마지막 Journal에서 상태를 복원한다. UI는 구현하지 않았고 CLI 출력을 검토 대상으로 한다.
- 남은 작업: 사용자 Pilot 종목·자금·비용 가정 선택, 실제 새 데이터 refresh, 첫 LIVE_FORWARD 계좌/일 실행, 정정 처리 정책 심화, S2/S7·다중 자산·간단 UI. 검토 전 commit/push하지 않는다.
- 검증: Python 전체 **272 passed**, 기존 JavaScript hover **9 passed**, `pip check`·`node --check`·`git diff --check` 통과. `PRICE_PHASE_V1` 기존 6개 일별 CSV SHA-256도 STEP 1과 동일하다. Windows pytest 임시 경로와 Node spawn 제한은 권한 있는 동일 명령으로 해결했다.

## 2026-10-10 Historical Research → Forward Validation Milestone Audit

- 기준 branch `main`, 현재 커밋 `ee62796e198b6c1a4dd148908c3a35d2405ba797`; 이후 Strategy/UX·Phase 연구·Paper MVP 변경은 미커밋이다. 기존 미커밋 파일과 연구 결과를 보존하며 사용자 승인 전 commit/push하지 않는다.
- [Milestone 요약](milestone-forward-validation-foundation.md)에 Frozen `PRICE_PHASE_V1`, Spring 75/16/59·Autumn 87/12/67/7/1, Parent/Child의 판별력 미입증, H4/H5 **WEAK**, S1의 열린 손실·CASH 위험을 묶어 기록했다. 6종목 일별 라벨 해시와 연구의 부정적 결과를 유지한다.
- 별도 Paper Trading MVP는 역사 재생과 LIVE_FORWARD 증거를 분리한다. 실제 LIVE_FORWARD 관측/수익은 없고 Pilot도 미시작이다. 다음 공식 단계는 **STEP 6 — First LIVE_FORWARD Pilot**이며 사용자 자산·자본·비용 가정과 새 공급자 refresh가 선행되어야 한다. 이 감사에서는 STEP 6을 실행하지 않는다.

### 2026-10-11 감사 재개 결과

- `PRICE_PHASE_V1` 6개 일별 CSV와 기존 검증 산출물의 해시가 일치한다. Failure Analysis(14개 파일), Parent/Child(27개), Transition Dynamics(11개)를 별도 Git 제외 폴더에서 재생성해 기존 산출물과 파일별 SHA-256 일치를 확인했다.
- 전체 Python **272 passed**, JavaScript **9 passed**, `pip check`, `node --check`, `git diff --check` 통과. 문서의 현재 구현 상태와 README 링크, `.gitignore`의 SQLite 예외만 최소 수정했다.
- 삼성전자 2026-10-06~08 역사 재생을 새 계좌로 반복 검증했다. 3개 Journal·3개 Decision·3개 Order·1개 Execution, 재실행 중복 0, 재시작 후 Cash 233,460원·1주·총자산 496,460원·미실현손익 −3,540원이다. 증거 유형은 오직 `HISTORICAL_REPLAY`다.
- 기존 변경과 감사 산출물은 모두 미커밋으로 보존했다. 사용자 Checkpoint Commit 승인과 Push 승인은 별개이며 아직 어느 쪽도 진행하지 않았다.

## 2026-10-11 STEP 6 — 첫 LIVE_FORWARD Pilot 준비 점검

- 로컬 Checkpoint `d1ce2f2cd48693727644a443688c06b95c05fc48`에서 시작했다. `origin/main`보다 1 commit 앞서며, 이번 STEP에서 push하지 않는다. 이전 Milestone 연구·Phase·Strategy·Paper 계약은 변경하지 않았다.
- 사용자가 Pilot 후보로 `000660` SK하이닉스를 선택했다. [Pilot 로그](live-forward-pilot-01.md)에 기존 Daum 보조 공급자 재조회, 검증된 마지막 일봉 2026-10-08, 이전 CSV와 해시 동일, 1주 필요자금 1,686,253원, 계좌 미생성 상태를 기록했다.
- 2026-10-11은 일요일이고 새 계좌 생성 이후의 확정 일봉이 없다. 따라서 **`LIVE_FORWARD_BLOCKED_BY_DATA_REFRESH`**이며 역사 일봉을 Forward Decision으로 재사용하지 않았다. 비용 가정의 최종 확인과 새로운 거래일의 장 종료 후 공급자 refresh가 있어야 첫 Decision/Journal을 시작할 수 있다.
- 같은 날 사용자는 초기 모의투자금으로 **10,000,000 KRW**를 지정했다. 직전 종가 기준 1주 필요자금은 1,686,253 KRW이며 기본 수수료를 적용한 단순 매수 가능 수량은 5주다. 이는 미래 체결 수량 보장이 아니다. 데이터가 새로 확정될 때까지 계좌 미생성 상태를 유지한다.
- 수집기가 1,500행 rolling 창을 그대로 저장하면 다음 날 Paper 전체 이력 해시가 깨질 수 있어, 겹치는 과거 행을 검증하고 신규 행만 누적하는 최소 수정을 추가했다. 누락·수정된 과거 바는 거부하며 단위 테스트를 통과했다. 실제 신규 일봉 append와 사용자 검토 전에는 계좌를 만들지 않는다.

## 2026-10-11 STEP 6A — LIVE 데이터 갱신 안전성 Checkpoint

- 로컬 기준선 `d1ce2f2cd48693727644a443688c06b95c05fc48`에서 STEP 6 관련 4개 파일만 감사했다. [Pilot 로그](live-forward-pilot-01.md)에 `000660` SK하이닉스·모의자본 10,000,000 KRW·`LIVE_FORWARD_BLOCKED_BY_DATA_REFRESH`·계좌 미생성 상태를 유지한다.
- Daum의 rolling 1,500행과 로컬 누적 이력을 비교해 기존 행을 보존한다. 과거 날짜/값이 바뀌거나 빠지면 `DATA_HISTORY_CHANGED`와 비영 종료코드로 중단한다. 새 CSV는 검증된 별도 폴더에서 마지막에 공개하므로 기존 이력을 덮어쓰지 않는다. 원천 응답·누적 이력 해시와 이전/추가 행 수를 메타데이터에 기록한다.
- 2026-10-11 실제 재조회에서 추가 행 0, 마지막 확정 일봉 **2026-10-08**을 확인했다. 다음은 새로운 확정 거래일 수집 및 이력 연속성 검증이다. 아직 계좌·Phase Snapshot·Decision·Journal은 없으며 STEP 6B를 시작하지 않는다. `UNADJUSTED` 기업행동 정정과 거래소 달력 대조는 남은 위험이다.
