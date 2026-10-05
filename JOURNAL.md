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
