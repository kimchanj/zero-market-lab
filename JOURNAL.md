# JOURNAL

## 2026-10-05 — STEP 0 Foundation (Asia/Seoul)

### Baseline / Hypothesis

작업 경로 `D:\workspace\github\zero-market-lab`은 비어 있었고 Git 저장소가 아니었다.
기존 파일 및 적용 가능한 상위 AGENTS.md는 발견되지 않았다.
사용자가 제공한 STEP 0 지시문을 기준으로 문서 6개만 작성한다.
명시적인 경계와 가정을 먼저 기록하면 이후 공급자·UI·전략 변경에도 연구 재현성을 유지할 수 있다.

### Decisions / Before–After

빈 작업 폴더 → Charter, ADR-001~014, Data Strategy, Case #01, Roadmap/DoD 기준선.
Python/Pandas, Plotly, Dash 우선 후보, pytest, CSV/Parquet를 기록했다.
Engine/UI, Provider, Strategy/Execution, Account/Tax를 분리한다.
Real Data는 연구, Synthetic Data는 테스트에만 쓴다.
Case A/B/C를 동일 조건에서 비교하고 FX OFF Benchmark임을 명시했다.
C는 매도일 기준 달력 1개월 후 첫 거래일 재진입으로 구체화했다.
Same Close는 낙관적 가정, PR은 배당 제외이며 적립식 CAGR·MDD는 현금흐름을 고려해야 한다.
공식 S&P DJI와 FRED 자료를 읽고 데이터 유형 및 FRED 제공 범위 제약을 문서화했다.
장기 공급자 채택·데이터 수집·투자 결과 산출은 하지 않았다.

### Measurement / Verification

실행 가능한 코드가 없어 pytest·프로그램 실제 실행·앱 화면 검증은 N/A다.
문서 원문과 링크 구조, 필수 범위, diff 및 공백을 검토한다.
source placeholder, Engine, Strategy, UI 구현 및 framework 설치는 없다.
Git 저장소를 초기화하고 문서 변경만 commit한다. 최종 검증 결과는 아래에 기록한다.

### Remaining / Next gate

STEP 0 사용자 검토 대기. STEP 1은 아직 시작하지 않았다.
다음 단계는 공급자·사용조건·기간 검증, 환경 버전 확정, 데이터 로딩·provenance·validation 및 raw chart다.

### 최종 검증 결과

- 문서 6개 전체 staged diff 검토 완료. `git diff --cached --check` 통과.
- README의 로컬 문서 링크 대상 5개 존재 확인. 기능 코드·패키지 설치 없음.
- `git commit -m "docs: establish STEP 0 project foundation"` 실패:
  `Author identity unknown`. Git user.name / user.email 미설정.
- 사용자에게 작성자 이름·이메일을 요청했다. 임의 작성자나 전역 설정을 만들지 않는다.
- STEP 0 DoD: PARTIAL. 문서 작업 완료, Git commit과 이후 clean 상태 확인 대기.
- STEP 1 미실행. 작성자 정보 수신 후 저장소 로컬 설정, commit, 상태 확인 및 기록 갱신 필요.

## 2026-10-05 — STEP 0 종료

이 종료 기록이 위 최초 검토의 PARTIAL 및 commit 대기 상태를 대체한다.

- STEP 0 문서화 완료: Project Charter, ADR-001~014, Architecture, Data Strategy,
  Case #01, Roadmap을 기준선으로 확정했다.
- Git author를 현재 저장소 local 설정에만 적용하고 `git config --local --get`으로 확인했다.
  user.name: `kimchanj`; user.email: `101384886+kimchanj@users.noreply.github.com`.
  global 설정은 변경하지 않았다.
- 문서 6개 및 전체 staged diff를 재검토했다. 공백 검사 통과, 소스코드·UI·설치 파일 없음.
- Strategy B: 종가가 평균매입가 대비 +5% 이상이면 전량 매도 후 같은 거래일 같은 종가에 재매수.
- Strategy C: 다음 달 같은 일자를 기준일로 삼고 해당 일자가 없으면 월말로 제한한다.
  기준일을 포함하여 그 이후 첫 거래일에 재진입한다. 예: 1/31 → 2/28(윤년 2/29),
  해당 일이 거래일이면 당일, 휴장이면 다음 거래일. 기존 Case 정의를 확인했으며 변경하지 않았다.
- CAGR·MDD의 현금 유입 해석 주의, cash-flow adjusted return 및 향후 XIRR/MWR가
  이미 Case 문서에 명시되어 있어 수정하지 않았다.
- Roadmap에는 체크 상태가 최초 commit 전 기록이며 최종 판정은 이 JOURNAL을 따른다는 설명만 추가했다.
- Git 첫 commit 성공:
  `docs: establish ZERO MARKET LAB step 0 foundation`
  — `e6f6735b094981f81f8468b95d194286c73b8680`.
- 첫 commit 직후 `git status --short` 출력 없음: working tree clean 확인.
- 실행 기능이 없어 기능 테스트·앱 실행·화면 검증은 N/A. 문서와 Git 검증으로 종료한다.
- STEP 0 종료 판정: PASS / COMPLETE. 이 종료 기록은 JOURNAL만 별도 commit으로 보존한다.
- 다음 단계는 STEP 1(실제 데이터 공급자·환경·로딩·검증·raw chart)이며 아직 시작하지 않았다.
  사용자 시작 지시 전에는 진행하지 않는다.

## 2026-10-05 — STEP 1 Real S&P500 Data Foundation

### Baseline / Design

- 시작 시 main, clean, origin https://github.com/kimchanj/zero-market-lab.git.
  로컬 및 `git ls-remote origin refs/heads/main`은 모두
  `e581324177ac962757cb323fa4d2afa7778896a7`로 STEP 0 종료와 일치했다.
- Python 3.12는 설치되어 있지 않아 기존 Python 3.13.11을 사용했다.
  실행경로: `C:\Users\kcji2\AppData\Local\Programs\Python\Python313\python.exe`.
  pip 25.3, 프로젝트 루트 `.venv`, requirements.txt에 전이 의존성까지 고정했다.
- 직접 의존성: pandas 3.0.6, plotly 7.1.0, pytest 9.1.1, pyarrow 25.0.1, requests 2.34.2.
  Dash는 설치하지 않았다. 초기 sandbox ensurepip/네트워크/pytest cache 제한은
  승인된 실행 권한으로 해결했으며 보안 설정이나 global Python 패키지를 변경하지 않았다.
- 목적은 실제 데이터 연결과 구조 검증이다. Backtest/Strategy/Portfolio/수익률·위험지표는 구현하지 않았다.

### Implementation / Before–After

- 문서만 있는 저장소 → FRED 다운로드 adapter, 정규화, provider 독립 validation,
  명령행 inspection script, synthetic unit tests, raw/processed 분리 및 Plotly 단일 차트.
- 원본 bytes와 UTC 조회시각·URL·SHA-256·요청/실제 기간·행 수·결측 제외 날짜를 metadata에 보존했다.
  매 실행 timestamp별 snapshot으로 기존 데이터를 덮어쓰지 않는다.
- date/close만 정규화한다. 잘못된 값·중복·역순은 실패하며 빈 문자열/점 표기만 제외한다.
  오류 시 synthetic으로 대체하지 않는다. 다운로드 실패 propagation도 unit test로 확인했다.
- .gitignore로 .venv, cache, raw/processed, chart를 제외했다. 공개 Git에는 원자료나 차트를 재배포하지 않는다.

### Actual Run / Measurement

실행 명령:

```powershell
.\.venv\Scripts\python.exe scripts/inspect_sp500_data.py --start 2000-01-01 --end 2026-10-02
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
```

- Provider: FRED SP500, original source S&P Dow Jones Indices; PRICE_RETURN / DAILY_CLOSE / Dividend EXCLUDED.
- 요청: 2000-01-01~2026-10-02. 실제: 2016-10-03~2026-10-02.
- 원본 2,610행 → 결측 표기 96행 제외 → 2,514행. 실제 validation PASS.
- Warning: actual_start가 requested_start보다 늦음; 명시적 결측 96행 제외.
  주말 및 7일 초과 간격 warning은 없음. 거래소 달력 완전성까지 검증했다는 뜻은 아니다.
- snapshot: `20261005T034500658318Z`.
  raw/metadata: `data/raw/<snapshot>/fred_sp500.csv`, `fred_sp500.metadata.json`, `request.json`.
  processed: `data/processed/<snapshot>/sp500_price_daily.parquet`.
  chart: `artifacts/<snapshot>/sp500_price_daily.html`.
- raw SHA-256: `dc55759624a15112e420b3e2d06c9a8dec8007a08cf5780ae43f267f66d6e27e`.
- 테스트: **29 PASS**, 경고 없음. `pip check`: No broken requirements found.
- 최종 validator로 저장된 실제 Parquet를 재검증하고 raw 재정규화 값과 frame equality 확인.

### Visual Verification

브라우저 도구는 file URL을 정책상 차단했다. 다른 경로로 우회하지 않고 사용자에게 직접 열기를 요청했다.
사용자가 해당 snapshot HTML을 실제 Chrome에서 열어 이 채팅에 화면을 제공했고 그 화면을 검토했다.
그래프가 비어 있지 않으며 2016년 말~2026년으로 날짜가 증가한다. 약 2천~8천 지수 축과
2020년 급락·2022년 하락 구간이 보이며 뒤집힌 날짜나 명백한 렌더링 이상은 없다.
제목의 Price Index / Daily Close / Source / Dividend Excluded를 확인했다.
화면 검증 증거는 이 채팅의 사용자 첨부 이미지다. 화면만으로 전 기간 가격 정확성을 인증하지 않는다.

### Decisions / Limitations / Next

FRED는 이번 Validation Provider이며 장기 Research Provider로 확정하지 않았다.
S&P DJI 직접 API와 EODData의 공식 자료를 비교해 docs/data-strategy.md에 기간·PR/TR·OHLC·조정·배당·
접근·사용조건·자동화·비용 항목을 기록했다. 상품별 미확인 사항은 미확인으로 남겼다.
계약·구매는 하지 않았다. 단일 공급자 및 약 10년 제한, 결측일 달력 대조, raw 재배포 조건이 남은 제약이다.
STEP 2는 월 적립·현금·포지션·Buy & Hold 기준선이지만 시작하지 않았다.

### Git gate

commit 전 변경 파일/공백/diff를 검토하고 데이터 제외 여부를 확인한다.
기능 commit과 origin/main push 후 실제 hash 및 최종 상태를 후속 종료 기록으로 남긴다.

### STEP 1 종료 기록

- 기능 commit: `03cf19fc7865dbbedc745949a1b61551e8c95e81`
  (`feat: establish real S&P500 market data foundation`).
- origin/main push 성공. `git ls-remote`의 main hash와 로컬 HEAD 일치 확인.
- 해당 push 직후 working tree clean, staged/unstaged 공백 검사 통과.
- DoD: **PASS**. 환경·최소 의존성·실데이터 raw/processed/provenance·validation·29 tests·
  실제 실행·사용자 제공 화면 검토·문서·diff·commit·push·clean 확인 완료.
- 이 종료 기록은 별도 docs commit으로 보존한다. STEP 2는 시작하지 않았으며 사용자 검토 대기다.

## 2026-10-05 — STEP 1 설계 보완: Reference Strategy Library

### 목적과 결정

- 완료된 STEP 1의 데이터 구현 범위는 변경하지 않고 장기 연구 확장 기준만 문서화했다.
- 전략 출처를 User Hypothesis, Academic Reference, Practitioner Reference,
  Control / Benchmark로 구분하는 Reference Strategy Library 개념을 Architecture에 추가했다.
- Strategy ID, Name, Family, Source Type, Author/Organization, Reference/Publication,
  Publication Date, Core Hypothesis, Required Market Data, Parameter Set, Benchmark,
  Known Limitations, Evidence Type, ZERO MARKET LAB Status를 metadata 후보로 기록했다.
- 초기 Family 후보와 Reference 전략의 동일 조건 재검증 원칙을 기록했다.
  Published/과거/유명/Backtest 결과가 현재·미래·live edge를 보장하지 않는다고 명시했다.
- OOS, Look-Ahead, Survivorship, 비용, Slippage, Data Snooping, Overfitting,
  Regime Dependence, Publication/Crowding Effect를 필수 검토 대상으로 삼았다.

### 범위 보호

- Case #01 A/B/C 정의와 번호는 변경하지 않았다.
- Roadmap 번호를 다시 매기지 않고 STEP 9 이후 또는 13+와 병렬인 Research Track으로 추가했다.
- Reference Strategy 클래스, DB, Trend Following, Moving Average, Momentum,
  Portfolio Backtest, 비교 실행은 구현하지 않았다.
- 변경 범위는 README.md, docs/architecture.md, docs/roadmap.md, JOURNAL.md 네 문서뿐이다.
- STEP 1은 이미 PASS/종료 상태이며 STEP 2도 시작하지 않았다.
