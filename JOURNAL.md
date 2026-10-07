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

## 2026-10-05 — STEP 2 Monthly Buy & Hold Baseline

### 시작 상태와 범위

- main HEAD `aa4278ee39df639aa639ae83746bc351b2cf4e26`, origin/main과 일치, working tree clean.
- Strategy A만 구현했다. B/C, SELL, Take Profit, Reentry, 비용·slippage 모델,
  CAGR/MDD/Volatility, Dash, FX, Macro, Reference Strategy는 구현하지 않았다.
- STEP 1의 `date`, `close` Parquet와 validator를 그대로 재사용했다.

### 설계와 회계 규칙

- `MonthlyContributionPolicy`: 각 year-month에 입력으로 존재하는 첫 market date와 적립액 결정.
- `BuyAndHoldStrategy`: 가용 cash 매수 의도만 제공. Contribution timing과 분리.
- `Portfolio`: cash, fractional quantity, weighted average purchase price,
  total contribution 및 `quantity × market price` 평가를 담당.
- `Engine`: 입력 검증, 날짜 순회, contribution → BUY → daily valuation 순서와
  별도 Daily State / Event Log 기록을 조정.
- 월 적립 500,000 simulation units, FX OFF, cost/slippage 0, same close, fractional units 허용.
  S&P500 지수의 Benchmark Simulation이며 거래 가능한 상품 결과가 아니다.

### Synthetic verification

Fixture: 2026-01-02 100, 2026-01-05 110, 2026-02-02 125; 월 적립 100.

- 1/2: contribution 100, buy 1.0, quantity 1.0, cash 0, portfolio 100.
- 1/5: quantity 1.0 유지, portfolio 110, 이벤트 없음.
- 2/2: contribution 100, buy 0.8, quantity 1.8, cash 0, portfolio 225,
  weighted average cost `200 / 1.8 = 111.111...`.
- 신규 테스트 13개를 포함해 전체 **42 passed**. 기존 STEP 1 테스트도 모두 통과.
- 날짜 역순·중복·비양수 가격, 잘못된 적립금은 실패한다. SELL 이벤트가 없음을 검증했다.

### 실제 데이터 실행과 불변식

- 입력: `data/processed/20261005T034500658318Z/sp500_price_daily.parquet`.
- 기간 2016-10-03~2026-10-02, market rows 2,514.
- contribution 121회, BUY 121회, SELL 0회.
- total contribution 60,500,000; final quantity 16,426.904043924354.
- final average purchase price 3,682.9824925151684; final market price 7,722.72.
- final cash 0; final position/portfolio value 126,860,380.39809549.
- investment gain 66,360,380.39809549. CAGR이나 전략 우월성으로 해석하지 않는다.
- 전체 실제 state에서 cash/quantity 비음수, valuation 항등식, contribution 단조 증가,
  state row 수, 월별 첫 관측일과 event 수를 별도 재검증해 모두 PASS.

### Visual verification / 제한

- 최종 run `artifacts/step_02/20261005T041738204102Z/`에 summary, states, events,
  Plotly HTML 및 Kaleido PNG를 생성했다.
- PNG를 직접 검사해 Portfolio Value와 Total Contribution 두 선, 2016~2026 날짜 방향,
  월 적립 계단, 주요 하락 구간, FX OFF / Fractional Units / Cost 0 / Dividend Excluded 표기를 확인했다.
- Price Return만 사용하고 배당·FX·현금이자·세금·실제 체결 가능성은 반영하지 않는다.
  same-close fractional execution과 0 비용은 회계 검증용 가정이다.

### Git gate

전체 테스트, dependency 검사, diff·공백·파일 범위를 검토한 후 기능 commit과 origin/main push를 수행한다.
STEP 3는 시작하지 않았다.

### STEP 2 종료 기록

- 기능 commit `9d7f3aa2d245ee56e8d1674866668e36fc1f1d5f`
  (`feat: implement monthly buy and hold baseline`) 생성 및 origin/main push 성공.
- push 직후 `git ls-remote`의 main hash와 로컬 HEAD가 일치했고 working tree 변경은 없었다.
- DoD: **PASS**. Monthly Contribution, first market date, cash/quantity/average cost,
  Strategy A, state/event, synthetic/real 검증, 42 tests, 시각 검증, 문서, diff, commit/push 완료.
- 이 종료 기록은 별도 docs commit으로 보존한다. STEP 3는 시작하지 않았으며 사용자 검토 대기다.

## 2026-10-05 — STEP 3 Synthetic Engine Verification

### 시작 상태 / 범위

- main HEAD `0524bb91dd61ebc797889de042d9af6c95f957f5`, origin/main과 일치, working tree clean.
- STEP 2의 public API와 Market Data validator를 변경하지 않고 deterministic synthetic test만 추가했다.
- Strategy B/C, SELL, Reentry, 비용, 성과지표, UI 등 신규 투자기능은 구현하지 않았다.

### 검증 결과

| Scenario | Result |
| --- | --- |
| Month boundary | PASS |
| Year boundary | PASS |
| Missing calendar day 1 | PASS |
| Single-observation month | PASS |
| CONTRIBUTION → BUY → end-state order | PASS |
| Price spike | PASS |
| Price crash | PASS |
| Multi-month weighted average cost | PASS |
| Non-contribution-day state preservation | PASS |
| 10-year deterministic run | PASS |
| Repeated-run determinism | PASS |
| Empty dataset rejected | PASS |
| Duplicate date rejected | PASS |
| Unsorted date rejected | PASS |
| Null close rejected | PASS |
| Zero price rejected | PASS |
| Negative price rejected | PASS |

급등락 fixture `100 → 200 → 50`은 quantity 1, average cost 100, contribution 100을 유지하고
portfolio value만 `100 → 200 → 50`으로 바뀌었다. 월별 가격 `100, 200, 50`에서는
quantity `1, 1.5, 3.5`, average cost `100, 133.333333..., 85.714285...`로 손계산값과 일치했다.

10년 business-day fixture는 2,609행, 120개월이었다. Daily State 2,609행,
CONTRIBUTION 120, BUY 120, SELL 0, 최종 contribution 60,000, cash 0으로 모든 불변식을 유지했다.
같은 3년 입력과 config를 두 번 실행한 state/event/final row는 exact equality로 일치했다.

### 정책 / 결론 / 한계

- Fractional quantity, 평균원가와 valuation 비교는 전체 STEP 3에서
  relative tolerance `1e-12`, absolute tolerance `1e-9`를 공통 적용했다.
- 검증 불변식: cash/quantity 비음수, position/portfolio valuation 항등식,
  contribution 단조 증가, represented months = contributions = buys, sells = 0,
  state rows = market rows, contribution day event order.
- 신규 16개를 포함한 전체 **58 tests PASS**, `pip check` PASS, `git diff --check` PASS.
- 발견된 production bug는 없으며 production code 변경도 없다. silent sort/drop/fill 없이 invalid input을 거부했다.
- deterministic fixture는 실제 시장·체결 모델이나 모든 floating-point 규모를 증명하지 않는다.
  STEP 4 Multi Strategy Comparison은 시작하지 않았다.

### Git gate

테스트 파일과 JOURNAL만 검토·commit하고 origin/main에 push한 뒤 hash와 clean 상태를 종료 기록에 남긴다.

### STEP 3 종료 기록

- Test commit `f093d68f842805e0d25e2b4ccbd88e090bcf5f50`
  (`test: harden buy and hold engine with synthetic scenarios`) 생성 및 origin/main push 성공.
- push 직후 `git ls-remote`의 main hash와 로컬 HEAD가 일치했고 staged/unstaged 변경은 없었다.
- DoD: **PASS**. 모든 요구 scenario, tolerance 정책, accounting invariants,
  기존 포함 58 tests, dependency/diff 검사, JOURNAL, commit/push 완료.
- 이 종료 기록은 별도 docs commit으로 보존한다. STEP 4는 시작하지 않았으며 사용자 검토 대기다.

## 2026-10-05 — STEP 4 Three Strategy Comparison

### 범위와 구현

- 시작 시 main/origin HEAD `1258ba87ea1740575663b7dfb4e83901d55e9f3c`, working tree clean을 확인했다.
- Case #01 Strategy A/B/C를 하나의 일별 엔진과 명시적 `INVESTED` / `WAITING_REENTRY` 상태로 구현했다.
- B는 +5% 익절 시 전량 매도 후 같은 거래일·같은 종가로 전액 재진입한다.
- C는 전량 매도 후 달력상 1개월 뒤 기준일 당일 또는 이후 첫 시장 관측일에 누적 현금 전액으로 재진입한다.
  월말은 calendar clamp를 사용하며 데이터가 먼저 끝나면 현금과 대기 상태를 유지한다.
- 이벤트는 CONTRIBUTION, BUY, TAKE_PROFIT, SELL, REENTRY로 분리했고 일중 순서를 보존했다.
- 비용/slippage 0, fractional units, same close, FX OFF, dividend excluded 범위만 다뤘다.

### 검증과 수정

- STEP 4 합성 테스트 11개가 event order, contribution timing, B 동일성, C 한 달 대기와 월말 clamp,
  재진입일 적립금, 열린 대기를 검증했다. 전체 **69 tests PASS**, `pip check` PASS.
- 첫 테스트 실행에서 월말 clamp parameter case 3개가 실패했다. 기준일 이후 첫 관측일이 해당 월의 첫
  관측일이기도 하므로 CONTRIBUTION 다음 REENTRY가 맞았고, production code가 아니라 fixture 기대값을 수정했다.
- 실제 실행 스크립트는 A/B의 일별 portfolio value, quantity, cash를 `1e-12` relative / `1e-9` absolute
  tolerance로 검증한 뒤에만 artifact를 생성한다.

### 실제 데이터 실행과 시각 검증

- 입력 snapshot `20261005T034500658318Z`, 2016-10-03~2026-10-02, 2,514 market rows,
  월 500,000, 총 납입 60,500,000.
- A: 최종 126,860,380.39809549, BUY 121, SELL/TAKE_PROFIT/REENTRY 0.
- B: 최종 126,860,380.39809549, BUY+REENTRY 142, SELL/TAKE_PROFIT/REENTRY 각 25.
- C: 최종 116,066,042.95602758, BUY+REENTRY 117, SELL/TAKE_PROFIT/REENTRY 각 24,
  Cash Waiting Days 754.
- artifact: `artifacts/step_04/20261005T071836772115Z/`의 summary, 전략별 state/event Parquet,
  Plotly HTML, PNG. PNG에서 A/B 선의 정확한 중첩과 C의 분리, 날짜 증가 방향, 비어 있지 않은 세 series,
  제목·축·범례를 확인했다.
- 이 실행은 성과 우월성 결론이 아니다. 배당, 비용, 세금, FX, 실제 ETF, 다른 임계값과 구간은 후속 범위다.

### Git gate

기능·테스트·문서 diff와 공백 오류를 확인한 뒤 `feat: implement case 01 multi-strategy comparison`으로
commit하고 origin/main에 push한다. 성공 hash는 별도 STEP 4 종료 기록에 남긴다. STEP 5는 시작하지 않는다.

### STEP 4 종료 기록

- Strategy A/B/C, A/B same-close control invariant, Strategy C waiting/reentry 구현과 검증을 완료했다.
- 전체 69 tests, `pip check`, `git diff --check`, 실제 S&P500 비교 실행과 visual verification이 통과했다.
- 기능 commit `c53aa8ce221a81e48a2b41c7b1acb6c8aa620881`
  (`feat: implement case 01 multi-strategy comparison`)을 생성했다.
- STEP 4 Definition of Done: **PASS / COMPLETE**.
- STEP 5 Interactive Comparison UI는 시작하지 않았다.

## 2026-10-05 — STEP 5 Interactive Comparison UI Visual MVP

### 시작 상태와 구현

- main/origin HEAD `9f157f1010d1ebd7a45379533232d998aa2ce758`, working tree clean에서 시작했다.
- Dash 4.4.1과 Flask 계열 전이 의존성을 현재 requirements 고정 방식으로 추가했다.
- `ui.service`가 입력 검증, 기간 필터, 기존 A/B/C 비교 엔진 호출과 Metrics 적응을 담당한다.
- `ui.figures`가 Market과 Portfolio Plotly figure를 만들고 `ui.app`은 layout과 callback만 담당한다.
- editable 값은 Start/End Date, Monthly Contribution, Take Profit %, C Reentry Months다.
- fixed assumptions는 S&P500 Price Index, Dividend Excluded, FX OFF, Cost/Slippage 0, Same Close,
  Fractional Units Allowed다.
- 첫 로드에서 전체 기간 기본 결과를 즉시 표시한다. Run Backtest는 페이지 이동 없이 두 차트와 Metrics를 갱신한다.

### 검증

- 신규 테스트 13개는 parameter validation, date filtering, deterministic service, A/B invariant,
  Market/Portfolio figure 계약, legend, date axis, unified hover, Dash layout/callback을 검증했다.
- 전체 **82 tests PASS**, `pip check` PASS, 구현 중간 `git diff --check` PASS.
- 실제 서버 `http://127.0.0.1:8050` 응답, Dash layout/dependencies, 서버 callback과 clientside linked-range
  callback 등록을 확인했다.
- callback에 2020-01-02~2022-12-30, 월 600,000, TP 10%, C 2개월을 전달해 HTTP 200,
  변경된 legend, 기간, 총 납입 21,600,000, validation message 없음과 Metrics 갱신을 확인했다.
- 1600×1200 실제 Chrome 렌더에서 parameter panel, 두 차트, A/B overlap, C divergence, contribution line,
  assumptions와 metrics를 확인했다. 800×1600 렌더에서 세로 reflow를 확인했다.
- 첫 렌더에서 number input의 min/step 기준 불일치로 기본값이 invalid 색으로 표시되는 UI 결함을 발견해
  min 기준을 0으로 맞추고 재렌더링으로 수정 결과를 확인했다.

### 현재 게이트

- Codex 정적 화면 검증과 callback 실행 검증은 통과했다. mouse wheel zoom, pan, unified hover,
  양방향 linked range, Reset View의 사용자 브라우저 시각 검토는 대기 중이다.
- 사용자 시각 검토 전이므로 commit/push 및 STEP 5 COMPLETE 처리를 하지 않는다.
- STEP 6 Trade / Contribution Marker는 시작하지 않았다.

## 2026-10-05 — STEP 5 Chart Engine Architecture Spike

### 재평가 범위와 근거

- 사용자 Visual Review에 따라 Dashboard 표현을 넘어선 Trading Research Workstation 적합성을 재평가했다.
- Python Market Data, Comparison Service, Engine, Portfolio, Strategy A/B/C, Event Log는 변경하지 않았다.
- 공식 문서와 release를 확인해 최신 안정 Lightweight Charts 5.2.1 standalone을 고정했다.
- v5 pane, resizable separator, marker primitive, crosshair, line/candlestick/histogram series,
  auto-size, custom primitive/plugin 가능성을 Plotly/Dash와 비교했다.

### Isolated prototype

- `experiments/lightweight_charts/`에 Python payload builder와 standalone HTML/CSS/JS prototype을 추가했다.
- 실제 S&P500 daily close 2,514개, A/B/C 각 2,514개, contribution, Strategy C 기존 event 165개를 사용했다.
- Market Price와 Portfolio A/B/C를 하나의 time scale을 공유하는 resizable 2-pane으로 표시했다.
- BUY/TAKE_PROFIT/SELL/REENTRY marker filter, native crosshair, wheel zoom, pan, quick range,
  right-side price scale, responsive auto-size를 구현했다.
- Backend comparison 실행은 약 127ms, Chrome chart setup은 약 75ms로 관측됐다. 단일 로컬 환경 측정이며
  일반적인 성능 benchmark로 해석하지 않는다.
- 전체 10년 screenshot과 2026-03~10 focus screenshot을 생성했다. Focus 화면에서 TP/SELL,
  한 달 뒤 REENTRY, C portfolio의 다른 경로를 같은 시간축에서 확인했다.
- Fake OHLC와 volume은 생성하지 않았다. 향후 SPY 또는 실제 ETF volume만 market-activity proxy 후보로 둔다.
- 공식 NOTICE와 TradingView attribution을 prototype에 포함하고 vendor source/version/SHA-256을 기록했다.

### Recommendation / gate

- 결정 권고: **MIGRATE VISUALIZATION TO LIGHTWEIGHT CHARTS**.
- Python comparison service를 계산 경계로 유지하고 stable JSON payload와 versioned Dash custom component 또는
  제한된 client adapter를 먼저 설계한다. Plotly는 정적 연구/export 역할로 유지할 수 있다.
- 현재 production Dash UI는 삭제하거나 교체하지 않았다. iframe은 spike에만 사용한다.
- 사용자 Architecture 검토 전 commit/push하지 않는다. STEP 5는 PARTIAL, STEP 6은 미시작이다.

## 2026-10-05 — Goal-Based Simulation Roadmap Design

### 설계 범위

- Strategy Comparison, Goal-Based Simulation, Starting-Date Sensitivity를 장기 연구의 세 축으로 정의했다.
- Goal Analyzer를 Strategy/Engine 바깥의 분석 계층으로, Sensitivity Analyzer를 시작 시점별 run 집계 계층으로 구분했다.
- 향후 입력·출력, `GOAL_REACHED` 분석 이벤트, 세 가지 목표 상태, 월별 starting cohort와 집계 지표를 문서화했다.
- 목표수익률 분모는 누적 납입금·초기 투자금·money-weighted return 대안만 기록하고 결정을 유보했다.
- 한국어 우선 용어, simulation currency와 실제 통화 구분, adaptive 날짜축·한국어 요일·상세 hover 정책을 정했다.
- end censoring, 최근 시작일의 부족한 관측기간, cohort 중첩, survivorship, 배당·비용·FX 제외,
  지수와 ETF 차이를 편향·반증 점검 항목으로 추가했다.

### Roadmap 영향과 게이트

- 완료된 STEP 0~5 이력은 유지하고 미시작 단계만 Event → Risk → Goal → Starting-Date → Parameter 순서로 재배치했다.
- Goal Analyzer, sensitivity batch, MDD, heatmap, 목표선·marker, 한국어 UI는 구현하지 않았다.
- 기존 STEP 5 Chart Engine 작업과 코드는 변경하지 않았으며 STEP 5 판정은 **PARTIAL**이다.
- commit/push하지 않았고 STEP 6을 시작하지 않았다. 다음 작업은 현재 STEP 5 Chart Engine 검토와 마무리다.

## 2026-10-05 — Automatic Strategy Search Design

- 직접 전략 설정과 자동 전략 찾기를 분리하고, 첫 자동화는 제한된 Strategy Parameter Grid를 사용하는
  Level 2로 정의했다. 자유 형식 전략 생성과 A/B/C Building Block 리팩터링은 유보했다.
- hard constraint와 soft score, 상위 후보 비교, 복잡도 penalty, 조건 미충족의 명시적 보고를 설계했다.
- 사후 최적 경로를 Theoretical Upper Bound로 격리하고, 실전 후보의 look-ahead 금지와
  Training/Validation·향후 Walk-Forward·시작 시점 민감도 검증을 명시했다.
- Event Log와 Daily State에 근거한 설명 가능한 Investment Journal 및 차트 navigation 계약을 기록했다.
- 메인 Roadmap 번호는 유지하고 별도 Strategy Discovery Research Track으로 추가했다.
- Search Engine, Candidate Generator, 투자일지 UI는 구현하지 않았다. STEP 5는 **PARTIAL**, STEP 6은 미시작이다.

## 2026-10-05 — Goal-Based Investment Simulation Prototype v1

### 구현

- 기존 Case #01 Engine에 기본값 0인 `initial_investment`를 추가했다. 첫 관측일의
  `INITIAL_CONTRIBUTION`을 월 `CONTRIBUTION`과 분리하고 기존 Portfolio 매수 흐름을 재사용했다.
- Strategy 밖 `GoalAnalyzer`가 초기 투자금 기준 목표금액, 최초 달성일, 달력일 소요기간,
  목표 전 최소 MDD, 최종가치, 손익·단순수익률을 계산한다.
- `GOAL_REACHED`, `GOAL_NOT_REACHED`, `INSUFFICIENT_HORIZON`을 구분하고 최대기간 종료일이 주말인
  경우에도 데이터가 그 이후까지 존재하면 충분한 관측으로 판정하도록 설계했다.
- 별도 포트 8070의 한국어 Dash UI에 입력, 요약, 실제 S&P500 시장 차트, Portfolio 목표선·달성 marker,
  A/B/C 비교표를 구현했다. 금액은 실제 KRW가 아닌 simulation currency로 명시했다.

### 검증 중간 결과

- 손계산 fixture `100 → 110 → 120`에서 +20% 목표를 Day 3, 2일로 판정했다.
- `100 → 80 → 90 → 120`에서 목표 전 MDD -20%를 확인했다.
- A/B의 Goal Date, Days to Goal, 목표 전 MDD 동일성 테스트가 통과했다.
- 실제 S&P500에서 2018-01-02, 2020-01-02, 2022-01-03 시작 A/B/C 예시를 실행했다.
  A/B는 세 예시 모두 동일했고 C는 별도 경로와 결과를 보였다.
- 브라우저에서 2020 시작 A의 목표일 2021-02-08, 403일, MDD -33.9%, 목표선 12,000,000과
  목표 marker를 시각 확인했다. 첫 렌더의 차트 높이 축소를 Prototype 전용 CSS로 수정했다.

### 게이트

- Starting-Date Sensitivity, 자동 전략 탐색, Search Engine, 투자일지 UI는 구현하지 않았다.
- 전체 **110 tests PASS**, `pip check` PASS, `git diff --check` PASS다. `.pytest_cache` 쓰기 권한 warning만
  발생했으며 기능 실패는 없다.
- 실제 브라우저에서 입력·요약·두 차트·목표선·목표 marker·A/B/C 표와 Strategy C 재실행을 확인했다.
- 사용자 시각 검토 전이므로 commit/push하지 않는다.
- STEP 5는 **PARTIAL**, STEP 6은 미시작이다.

## 2026-10-05 — Goal UI Compact Controls / Unified Layer Chart Revision

### UI와 차트

- 큰 header와 card form을 40px header, 한 줄 compact toolbar, 한 줄 goal overview로 축소했다.
- native date input으로 직접 `YYYY-MM-DD` 입력, popup calendar, 키보드 접근을 제공하고 데이터 종료일 기준
  1W/1M/3M/6M/1Y/3Y/ALL 시작일 preset을 추가했다.
- 전략 dropdown을 제거했다. 모든 Goal Simulation은 같은 조건으로 A/B/C를 동시에 실행한다.
- 분리 Market/Portfolio 차트를 하나의 Unified Research Chart로 교체했다. S&P500은 왼쪽 축,
  A/B/C Portfolio와 목표·goal marker·C event marker는 오른쪽 축을 사용한다.
- Layer selector는 Market/A/B/C/Target/C Events trace visibility만 변경한다. C Events는 기본 OFF이며
  기존 TAKE_PROFIT/SELL/REENTRY Event Log에서 만든다.
- A/B 동일 경로 설명과 전략별 도움말, A/B/C compact 결과 strip을 추가했다.

### 브라우저 검증

- 2020-01-02, 초기금 10,000,000, 월추가 0, 목표 20%, 5년 조건에서 unified chart,
  dual axis, A/B overlap, C divergence, 목표선과 marker를 확인했다.
- native date popup의 calendar grid와 navigation controls를 확인했고 직접 2022-01-03을 입력해
  목표일 2024-09-30, 1,001일 결과로 갱신되는 것을 확인했다.
- 3Y quick preset이 2023-10-02로 입력을 바꾸는 것을 확인했다.
- C 거래 표시를 켜면 Backtest 입력 변경 없이 C 익절·매도·재진입 marker가 즉시 나타났다.
- 첫 렌더에서 flex가 입력 폭을 축소하는 문제를 발견해 각 입력에 고정 min-width를 적용했다.

### 게이트

- 계산 로직은 변경하지 않았다. 전체 **114 tests PASS**, `pip check` PASS, `git diff --check` PASS다.
  `.pytest_cache` 쓰기 권한 warning 외 기능 실패는 없다.
- 사용자 시각 승인 전 commit/push하지 않는다. STEP 5는 **PARTIAL**, STEP 6은 미시작이다.

## 2026-10-05 — Investment Experiment UX & Evaluation Revision

- 입력 변경 오류를 실제 브라우저에서 재현했다. Dash `type=number`가 값을 교체하는 동안 `None`을 State로
  게시해 화면에는 값이 보여도 service validation이 실패할 수 있었다. 숫자 필드를 text input으로 바꾸고
  service 경계에서 숫자 문자열·유한성·범위를 한 번에 검증해 화면 값과 config mapping을 일치시켰다.
- 일반 Simulation은 `initial_investment >= 0`, `monthly_contribution >= 0`을 허용하고 둘 다 0일 때만 거부한다.
  초기금 0인 경우 첫 관측일의 월 납입과 매수가 한 번만 발생하는 regression test를 추가했다.
- 상단을 투자 조건과 전략 조건으로 분리하고 `월 50만원 적립` preset을 추가했다. Goal은 선택 section으로
  이동했으며 월 적립식에는 목표 정의 확정 전까지 목표선과 달성 판정을 표시하지 않는다.
- Strategy A를 benchmark로 두고 총 납입금, 최종 평가금액, 투자손익, A 대비 금액·비율, 익절/매도/재진입,
  현금 대기일, Time in Market, 현재 경로 MDD와 사실 기반 verdict를 A/B/C card에 표시한다.
- 브라우저 Scenario 1(초기 10,000,000, 월 0, 5%, 5년)은 A/B 18,013,567, C 17,504,166,
  C의 A 대비 -509,401(-2.83%), 현금 대기 347일로 확인했다.
- Scenario 2(초기 0, 월 500,000, 5%, 1개월, 요청 10년/가용 데이터 2026-10-02까지)는
  총 납입금 41,000,000, A/B 69,423,748, C 63,118,342, C의 A 대비 -6,305,405(-9.08%),
  현금 대기 470일로 확인했다.
- Scenario 3(초기 0, 월 500,000, 10%, 2개월)는 A/B 69,423,748, C 65,582,389,
  C의 A 대비 -3,841,358(-5.53%), 익절/매도/재진입 8/8/8회, 현금 대기 494일로 확인했다.
- Unified Chart와 layer control을 유지했다. 사용자 시각 승인 전 commit/push하지 않으며 STEP 5는
  **PARTIAL**, STEP 6은 미시작이다.

## 2026-10-05 — Critical Chart Visible-Range Autoscale Fix

- Wheel/box zoom과 pan에서 X축만 바뀌고 Y축이 전체기간 범위를 유지하는 문제를 브라우저에서 재현했다.
- 원인은 relayoutData 처리 부재, Plotly 6 typed-array(`bdata`)를 범위 계산이 읽지 못한 문제, 동일
  `uirevision`이 서버 계산 Y range보다 stale UI 축을 우선한 문제의 조합이었다.
- `viewport.py`에 visible X slice, 활성 layer, 8% padding, flat/no-point fallback을 다루는 pure function을
  추가했다. Left는 S&P500만, Right는 A/B/C와 visible Target만 사용하며 event marker는 제외한다.
- Target은 Goal layer가 켜져 있으면 항상 Right autoscale에 포함한다. 목표가 포트폴리오에서 멀면 범위가
  넓어질 수 있으며 이는 현재 Goal 가시성 우선 정책이다.
- Quick Range는 Simulation 시작일을 바꾸지 않고 View State만 변경한다. Simulation 재실행은 full range로
  reset하며 Zoom/Pan은 Backtest를 실행하지 않는다. stale 축 보존을 막기 위해 `uirevision`은 사용하지 않는다.
- Plotly 기본 Reset이 callback redraw 이후 현재 viewport를 초기 상태로 간주하는 문제를 피하려고 전용
  `Reset View`를 추가하고 기본 zoom-in/out/autoscale/reset modebar 버튼은 제거했다.
- 2016-10-03~2026-10-02 full range와 COVID box zoom을 브라우저에서 확인했다. COVID zoom에서 Left tick은
  2,200~3,600, Right tick은 17.16M~32.09M으로 visible data에 맞게 재계산됐다. Pan 후 Right range도
  17.13M~33.47M으로 갱신됐다.
- 실제 Dash callback에서 pattern-matching ID가 `AttributeDict`로 전달되어 quick range가 실패하는 문제를
  추가 발견했다. 문자열 ID 비교를 type-safe하게 바꾼 뒤 1Y/3Y quick range와 전용 `Reset View`의 full-range
  복원을 브라우저에서 확인했다.
- S&P500 only, A only, C only, S&P500+A, S&P500+C, A+B+C, 전체 layer 조합을 확인했다. 활성 trace가 없는
  반대편 Y축은 숨겨 의미 없는 기본 눈금이 나타나지 않도록 했다.
- 최종 회귀 검증은 **134 tests PASS**, `pip check` PASS, `git diff --check` PASS다. `.pytest_cache` 쓰기 권한
  warning 1건 외 기능 실패는 없다. 사용자 시각 승인 전이므로 commit/push하지 않는다.

## 2026-10-05 — Cross-Asset & Hedge Research Design

- S&P500, Long Treasury, Gold, VIX를 대상으로 한 별도 Hedge Research Track을 설계했다.
- Indicator 계약(`SP500`, Treasury yield, `VIXCLS`)과 investable adjusted-price 후보(SPY/TLT/GLD)를 분리했다.
  Yield와 VIX level을 투자수익 series로 사용하지 않는다.
- 공통 유효 관측일 inner join, 기준 100, daily-return rolling/downside correlation, S&P drawdown episode와
  Hedge Effectiveness 후보를 문서화했다.
- HEDGE STEP 1~7을 기존 Roadmap 번호와 분리했다. Chart Autoscale Critical Gate 통과 전 production layer와
  isolated prototype을 구현하지 않는다. Strategy Engine 변경도 없다.
- 사용자 승인 전 commit/push하지 않으며 STEP 5는 **PARTIAL**, STEP 6은 미시작이다.

## 2026-10-06 — Interaction State Binding / Financial Chart Quality Gate

- Run 클릭 순간 브라우저의 시작일·초기금·월 적립금·기간·익절·재진입·Goal 입력을 하나의 atomic snapshot으로
  묶어 Python simulation callback에 전달하도록 변경했다. 입력 변경만으로는 simulation을 실행하지 않는다.
- 변경 직후 Run을 눌러도 2016-10-03, 초기금 0, 월 500,000, 10년, TP 10%, 재진입 2개월이 모두 반영됐다.
  A 최종값 126,860,380, C 최종값 121,652,694, C 매도/재진입 11/11회로 확인했다.
- Quick Range의 1W/1M/3M/6M/1Y/3Y/ALL calendar semantics와 dataset boundary clipping을 테스트했다.
  Quick Range 전후 simulation summary가 변하지 않는 것도 브라우저에서 확인했다.
- Hover customdata는 Engine daily state와 event log를 사용해 시장가격, 수량, 현금, 평가금액, 납입금, 손익,
  평균매입가, 상태, 행동, 재진입 예정일, A 대비 차이와 실제 숫자 계산식을 표시한다.
- Plotly/Dash는 viewport interaction마다 Python callback과 full figure redraw를 수행한다. 연속 Quick Range에서
  이전 요청이 늦게 표시되는 현상을 재현해 browser-local interaction 기준을 FAIL로 판정했다.
- Lightweight Charts spike에 1W~ALL calendar range와 Market/A/B/C/Contribution visibility를 추가했다.
  2,514 market points, A/B/C 각 2,514 points, 165 events에서 20 wheel + 20 pan 반복 후에도 축·series·marker가
  유지됐고 interaction 중 server 요청은 없었다.
- Financial Chart Engine 최종 결정은 **MIGRATE TO LIGHTWEIGHT CHARTS**다. Production migration은 아직
  시작하지 않았고 Plotly UI도 삭제하지 않았다. 사용자 승인 전 commit/push하지 않으며 STEP 5는 PARTIAL,
  STEP 6은 미시작이다.

## 2026-10-06 — TIGER 미국S&P500 Actual ETF V2 Foundation

- Legacy FRED/STEP 1~5/Goal/Plotly 구현을 그대로 두고 `tiger_v2` package와 별도 chart experiment를 추가했다.
- KRX 자동 다운로드는 로그인 자격증명이 필요한 상태임을 확인했다. 공식 TIGER factsheet로 상품·설정일·
  거래단위·분배 정책을 확인하고, Daum Finance `adjusted=false`를 자동 수집 보조 공급자로 채택했다.
- 실제 360750 raw OHLCV 1,508행, 2020-08-07~2026-10-06을 snapshot으로 저장했다. OHLC, 양수 가격,
  non-negative volume, null, 중복, 오름차순 검증은 PASS다. 상장 전 합성·보간·forward-fill은 없다.
- Yahoo raw quote의 유효 1,485 공통 날짜와 비교해 O/H/L/C 불일치 0을 확인했다. Yahoo에는 null 21행이
  있었고 volume은 602행이 달라 Daum volume을 단일 source로 명시했다.
- Lightweight Charts에 1,508 Candlestick, Volume pane, 한글 OHLC/등락률/거래량 crosshair,
  1M/3M/6M/1Y/3Y/ALL view control을 구현했다. setup 42.5ms, 반복 12 wheel + 6 pan 후 안정,
  interaction 중 server request 0건을 브라우저에서 확인했다.
- Strategy migration과 OHLC execution은 시작하지 않았다. 사용자 데이터/차트 검토 전 commit/push하지 않으며
  기존 STEP 5는 **PARTIAL**, STEP 6은 미시작이다.

## 2026-10-06 — Generic Multi-Asset Explainable Trading Simulator

- `simulator` package에 Instrument/MarketBar/Provider, Strategy parameter, limit-touch Execution,
  주입형 Fee/Tax, Portfolio accounting, DecisionRecord, Daily Ledger, Trade/Period Summary를 분리했다.
  Core에는 `360750` 등 종목별 분기를 넣지 않았다.
- Open -1% 지정가와 평균단가 +5% 익절, 정수 수량, 잔여현금, 전액 재투자를 구현했다. tick/lot,
  소수 수량, 비용 포함 최소 순수익 매도가를 공통 계약으로 처리한다.
- 일봉에서 진입과 익절 조건이 동시에 touch되면 발생 순서를 추정하지 않고 `AMBIGUOUS_ENTRY_EXIT`를
  기록해 당일 청산하지 않는다. gap fill도 유리한 가격을 가정하지 않고 사전 limit 가격을 사용한다.
- 실제 360750의 고정 2023-01-04~2023-04-04, 62 거래일을 실행했다. 초기 500,000원은 최종
  546,779원, 순손익 46,779원, 완료/Open 거래 1/1, 비용 231원, MDD -4.0695%였다.
  기간은 lifecycle 설명을 위해 고정했으며 수익 최대화나 parameter search 결과가 아니다.
- `TRADE-0001`은 2023-01-06 12,120원 41주 진입, 2023-02-03 12,730원 익절,
  순이익 24,857원, 19거래일/29일이다. `TRADE-0002`는 기간 말 40주 Open으로 미실현손익
  21,922원, 익절가까지 105원이다.
- 기존 Lightweight Charts candlestick/volume을 유지하고 BUY/SELL marker, 평균단가, 익절선,
  crosshair strategy state, Trade Summary와 펼침형 Daily Ledger를 같은 Engine payload에 연결했다.
  마커 클릭 시 해당 Ledger 행으로 이동하고 체결·비용·순손익·보유기간 설명을 표시한다.
- synthetic ETF/crypto smoke에서 정수·소수 수량을 같은 engine으로 실행하고, 공통 cross-asset summary
  row를 생성했다. 실제 삼성전자/BTC 공급자 수집과 비교 UI는 아직 구현하지 않았다.
- 실제 브라우저에서 SIM/ALL 전환, layer toggle, 초기 전략상태, BUY/SELL marker, 매도 marker의 Ledger
  이동, ENTRY 상세 설명, 누적 비용과 목표가 잔여 표시를 확인했다. console error는 없었다.
- 전체 **171 tests PASS**, `pip check` PASS, `git diff --check` PASS다. `.pytest_cache` 쓰기 권한
  warning 1건은 test 기능 실패가 아니다. 사용자 승인 전 commit/push하지 않으며 기존 STEP 5는
  **PARTIAL**, STEP 6은 미시작이다.

## 2026-10-07 — Current Version Stabilization + Research Workstation (사용자 검토 대기)

- Working tree의 기존 Legacy/FRED, STEP 5, V2와 Lightweight Charts를 보존하고 reset·삭제 없이
  중단된 작업을 이어갔다. 재현한 문제는 8061 정적 화면에서 투자조건 재계산 API가 없는 점,
  투자기간과 뉴스 연구기간의 상태 분리, 복기 표의 내부 코드 노출, 주요 영역 접기/펼치기 부재,
  뉴스 서버 장애 시 기술적인 fetch 오류 노출이었다.
- 8062 로컬 API의 `run_simulation` 입력 검증을 거쳐 같은 generic engine을 기간별로 다시 실행한다.
  결과의 Summary, Ledger, Trade, marker, 목표선, 뉴스 기본기간을 한 run ID로 연결했다.
  차트 Quick View는 투자기간과 독립적으로 유지한다.
- 투자조건·결과·복기·차트·뉴스/연구·기술 상세를 여섯 Accordion으로 정리했다. 기본 요약은
  6개 카드, 복기 기본 열은 11개 한글 열로 줄이고 판단·회계·원시 DecisionRecord는 행 안에 숨겼다.
  최소 순수익은 주문 변경이 아닌 평가 기준임을 명시하고 필요 매도가를 표시한다.
- 공식 자료 4건의 로컬 뉴스 카탈로그에서 기본 2023-01-04~2023-04-04 Replay 3건을 조회했다.
  2024년 1월은 0건 설명을 표시했다. 검증방·개념방 프롬프트와 Markdown/JSON packet을 생성했고,
  공급자 오류/서버 단절 시 매매결과가 유지되는 것을 확인했다. 뉴스와 가격의 인과관계는 미검증이다.
- 브라우저 회귀: 초기금액 100만 원 → 최종 1,093,557원, 매수 지정가 −2% → 524,549원,
  익절 +3% → 완료 3건, 최소 순수익 +2% → 동일 매매결과/더 높은 필요 매도가,
  6개월 → 123거래일·최종 577,929원 및 연구기간 동기화. Accordion과 2023-02-02 복기 상세,
  뉴스 조회·0건·네트워크 오류도 확인했다. 임시 8063 fault-injection 서버에서 실제 공급자 예외의
  502 응답·한글 오류·기존 62개 Ledger 및 차트/요약 유지를 브라우저로도 확인했다.
- 기본/복기 상세/차트/뉴스 화면 캡처는 `artifacts/research_workstation/stabilization_*.jpg`에 저장했다.
  전체 **192 tests PASS**, `pip check`, JS syntax, `git diff --check` PASS다.
- [Research Workstation](docs/research-workstation.md)에 계좌 제약 확장 경계와 H1~H3 자산별 전략
  적합성 가설을 기록했다. 계좌 세금, 타 자산 수집, 파라미터 탐색은 시작하지 않았다.
  사용자 화면 검토 전 commit/push하지 않는다. STEP 5는 계속 **PARTIAL**, STEP 6은 미시작이다.
- 사용자 화면 피드백에 따라 기본 투자기간을 한국시간 올해 1월 1일~오늘로 변경했다.
  빠른 1·3·6개월/1년은 오늘에서 역산하고 전체는 데이터 첫 관측일~오늘을 입력한다.
  2026-10-07 브라우저에서 기본 2026-01-01~10-07, 3개월 2026-07-07~10-07을 확인했다.
  데이터 최신일이 10-06이므로 실제 관측 종료일은 10-06으로 구분되며 3개월 Ledger 61행을 검증했다.

## 2026-10-07 — 차트 Hover 매매복기 최종 체크포인트 (화면 검토 대기)

- Lightweight Charts의 기존 Crosshair 날짜를 Daily Ledger 날짜에 매핑해 OHLC 헤더 아래에 작은
  상태별 매매복기 영역을 추가했다. 매수 대기·매수 완료·보유·익절 완료·기간 말 미청산을 표시하며
  Buy/Sell Marker도 같은 Ledger 행을 사용한다. Hover 이동마다 서버 요청이나 Engine 재계산을 하지 않는다.
- 매수 미체결 가격 차이는 서버 presentation adapter가 Ledger 지정가와 당일 저가로 준비한다.
  잔여현금 부족일에는 가격 차이 대신 현금 부족 사유를 한글로 설명한다. 수량·현금·총자산·목표가·
  보유기간·순손익은 Ledger 값을 그대로 표시한다.
- 실제 TIGER 데이터의 기본 요청 2026-01-01~10-07은 관측 2026-01-02~10-06, 185거래일이다.
  대기 01-02, 매수 01-19, 보유 01-20, 익절 05-07, 미청산 10-06을 확인했고 Marker 3개가
  같은 날짜의 Ledger 체결가와 일치했다.
- 전체 Python **193 tests PASS**, Hover JS **8 tests PASS**, `pip check` 및 `git diff --check` PASS다.
  브라우저 도구가 로컬 URL 접근을 보안 정책으로 차단해 이번 변경의 실제 Hover 화면 캡처와
  시각 회귀는 미완료다. 사용자 화면 확인 전 Git commit/push하지 않는다.

## 2026-10-07 — V2 GitHub Checkpoint 및 Public Demo 배포 준비

- 사용자 V2 승인 후 Python 193개, Hover JS 8개, `pip check`, 공백 검사를 재실행했다.
  원본 TIGER OHLCV·생성 chart/simulation payload는 Git 추적 대상에 없음을 확인했다.
- V2 코드·문서·테스트 79개 파일을 `813b9a0d5a2691bc554a1b38a6ef82bd61666109`
  (`feat: build ZERO MARKET LAB trading research workstation v2`)로 commit하여
  `origin/main`에 push했고 원격 HEAD가 일치했다.
- Public Demo 빌더는 실제 시세 파일이나 외부 API를 읽지 않고 100% 합성 OHLCV를 만든다.
  `LOCAL_RESEARCH`는 기존 로컬 TIGER 1,508행을 유지한다. Public 서버는 합성 bundle만
  로드하며 공개 화면에 합성 데이터 배지를 표시하고 실제 뉴스 카탈로그는 비운다.
- Render Web Service 설정, Python 버전, 최소 runtime 의존성, health endpoint를 추가했다.
  Public URL 발급과 실제 외부 smoke test는 호스팅 계정 연결 후 진행한다. 실제 URL이 없으므로
  GitHub Website와 README Live Demo에는 값을 등록하지 않는다.

## 2026-10-07 — 배포 목표 정정: GitHub Repository 체크포인트

- 공식 프로젝트 URL은 `https://github.com/kimchanj/zero-market-lab`이다. 이 URL은
  웹 앱 실행 주소가 아니며 GitHub Pages나 외부 호스팅을 이번 단계에서 진행하지 않는다.
- 위 배포 준비 기록 이후 사용자 지시에 따라 Render 연결을 해제하고 `render.yaml`,
  `requirements-public.txt`, `.python-version`, 외부 바인딩 및 health endpoint를 제거했다.
  별도 계정·호스팅·Public URL은 생성하지 않았다.
- 합성 `PUBLIC_DEMO` 데이터 모드는 실제 데이터 공개 위험 없이 로컬에서 사용할 수 있어 유지한다.
  최종 재검증에서 Python 196개와 Hover JS 8개 테스트, `pip check`, `git diff --check`가
  모두 통과했다. 로컬 브라우저 자동 검증은 도구 보안 정책으로 재실행할 수 없어 기존 화면
  검토 기록과 자동화 테스트를 구분해 보고한다.
