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
