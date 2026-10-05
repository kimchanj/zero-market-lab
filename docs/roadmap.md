# Roadmap / Completion gates

각 단계는 이전 결과를 검토하고 사용자 `STEP N 시작` 지시가 있을 때만 시작한다.

| STEP | 범위 | 해당 단계 완료 증거 |
| --- | --- | --- |
| 0 | Foundation | Charter, ADR, Case, Data Strategy, Roadmap, DoD, 문서 검토·commit·journal |
| 1 | Real S&P500 Data | 공급자/조건/기간 검증, loading·provenance·validation 테스트, 실제 데이터 raw chart 확인 |
| 2 | Single Strategy | 월 적립·cash·position·buy·valuation·Buy & Hold, 회계 테스트 및 실행 확인 |
| 3 | Synthetic Engine Verification | 결정론적 fixture로 경계·불변식·손계산 예상값 검증 |
| 4 | 3 Strategy Comparison | A/B/C 동일 입력 실행, 익절/재진입과 B 보존 조건 검증 |
| 5 | Interactive Comparison UI | Parameter Panel, Market/Portfolio Chart, Metrics 재실행·비교 확인 |
| 6 | Trade / Contribution Markers | 이벤트와 Marker 일치 확인 |
| 7 | Drawdown / Risk Analytics | 현금흐름 조정과 위험지표 예상값·화면 검증 |
| 8 | Cost / Slippage / Execution | 비용·체결 모델 비교, 정보 이용 시점과 회계 검증 |
| 9 | Case #01 Research | 사전 정의 구간·민감도·반증·실패·학습 결과 기록 |
| 10 | TIGER 360750 | 공식 상품 정보·실제 데이터·배당·비용·환율 검증 |
| 11 | S&P500 vs TIGER | 공통 기간, PR/TR·통화·상품 차이 명시 비교 |
| 12 | Macro Overlay | FED Rate·CPI·USD/KRW 시점 정렬과 화면 검증 |
| 13+ | Portfolio / Multi Asset / Rebalancing / Pension / ISA / Tax | 별도 설계와 단계별 승인 범위로 확장 |

STEP 3은 검증 심화 단계이며 STEP 1/2의 테스트를 그때까지 유예한다는 뜻이 아니다.

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
