# FECM Market Phase Engine v1 — Price-only Child Architecture

상위 기준: [ZERO_MARKET_LAB_META.md](../ZERO_MARKET_LAB_META.md). FECM의 Cycle/Phase는 자연법칙이나 미래 예측식이 아니라 **시점별 관측을 검증·반증하기 위한 프레임**이다. 이 문서는 구현 전 규칙 후보와 검증 계약이며 Phase 판정 알고리즘을 확정하지 않는다.

## 책임과 순서

Universe → 시점별 Price Evidence → Phase Detection → Phase Transition → Asset Discovery → Strategy Research. Phase Engine은 환경을 설명하고 Strategy Engine은 그 환경에서의 행동을 별도로 실험한다. Phase 이름은 매수·매도 명령, 자동 추천, 종목 전체 또는 시장 전체의 단일 계절이 아니다. 동일 날짜의 시장·업종·회사·상품은 서로 다른 Phase일 수 있다. v1은 **개별 자산 가격만** 사용하므로 시장·업종 Phase나 상대강도까지 판정했다고 주장하지 않는다.

## 데이터·시점 계약

- 자산별 상승 날짜순 OHLCV, 가격 조정·분할·배당 정책, 거래 캘린더, 출처·버전·관측시각을 함께 보관한다. 중복일, 결측, OHLC 불일치, 기업행동을 검사한다. 기존 5년 시세와 별도 warm-up을 재사용할 수 있다.
- MA200에는 최소 200개의 **완료된 거래일 종가**가 필요하다. 5거래일 MA200 기울기를 쓰는 후보에는 첫 평가 시점 전 최소 205개의 완료 관측을 확보한다. 자료가 부족하면 `UNKNOWN / INSUFFICIENT_HISTORY`로 두고 다른 Phase로 억지 분류하지 않는다.
- 거래일 *t* 장중 진입에 쓰는 Phase/EntryFilter는 **t−1 장 마감까지 확정된** 관측으로 고정한다. t 종가가 확정된 뒤 계산한 Phase는 t 관측의 연구 라벨로 보관할 수 있으나, 첫 사용 가능한 주문은 t+1 이후다. 신호 계산 시각과 체결 가능 시각을 별도 필드로 남긴다.
- 시점별 판정 함수는 해당 시점 이후의 행을 잘라도 같아야 한다(prefix invariance). 사후 20/60/120거래일 결과는 라벨을 먼저 고정한 뒤 평가할 때만 결합한다. 사후 고점·저점으로 과거 Phase를 수정하지 않는다.

## 다섯 Phase의 초기 Evidence 후보 — 확정 규칙 아님

| Phase | 현재까지 관찰 가능한 가격 Evidence 후보 | 해석·반증 주의 |
| --- | --- | --- |
| WINTER | Close < MA200, MA200 기울기 < 0, MA50 < MA200 | 약한 장기추세 후보. 단일 조건만으로 CASH를 강제하지 않는다. |
| SPRING_CANDIDATE | 하락속도 둔화, MA50/그 기울기 개선, Higher Low 후보, 기존 낙폭 회복 | 핵심 연구 상태. 반등이 다시 WINTER로 꺾일 수 있다. **매수 추천 아님.** |
| SPRING | 회복 추세와 단기·중기 구조 개선이 당시 데이터로 확인 | SPRING_CANDIDATE에서 전환되었는지 검증해야 한다. |
| SUMMER | Close > MA200, MA50 > MA200, MA50·MA200 기울기 > 0 | 후행 확인일 수 있다. S0/S1/S7 중 어느 행동이 유리한지는 별도 실험. |
| AUTUMN | 높은 가격대에서 MA50/MA200 상승속도 둔화, 신고가 갱신 실패, 모멘텀 약화 | 고점 예고가 아니다. 우선 신규 진입 제한·기존 포지션 점검의 연구 후보이며 자동 매도 아님. |

`UNKNOWN`은 데이터 부족·혼합 Evidence·충돌 시 보조 상태 후보이며 여섯 번째 투자 계절이 아니다. `TRANSITION` 역시 추후 필요성 검토 대상이다. Phase 경계, 기울기 계산 기간, Higher Low·신고가의 관측 창, 전이 확인 일수는 **실험 전에** 정의·버전 고정한다. 이번 문서는 임의의 가중점수, 예컨대 “Spring 82점”, 또는 “Spring 확률 87%”를 만들지 않는다. 정성적 Evidence strength도 v1에서는 생략한다.

## PhaseEvidence와 출력 계약 후보

각 자산·관측일에 Boolean/수치 원자료와 `available_at`을 보존한다. v1 후보: `price_above_ma200`, `ma50_above_ma200`, `ma50_slope`, `ma200_slope`, `drawdown_recovery`, `higher_low`, `higher_high`, `breakout`, `volatility`. `relative_strength_improving`과 `volume_confirmation`은 필드 확장 후보로 명시하되 **price-only v1 판정에 사용하지 않는다**. 뉴스·재무제표·수급·금리·거시·ML·AI도 v1에서 제외한다.

출력 초안: `symbol`, `observation_date`, `available_at`, `current_phase`, `previous_phase`, `days_in_phase`, `transition_date`, `phase_evidence`, `data_source`, `adjustment_policy`, `engine_version`, `insufficient_history_reason`. `previous_phase`와 지속기간은 당시까지 확정된 라벨의 이력에서만 산출한다. 확률적 `confidence` 값은 출력하지 않는다.

## Transition 및 실패 연구

우선 검토할 전이: WINTER → SPRING_CANDIDATE → SPRING → SUMMER → AUTUMN → WINTER. 실제 시계열은 건너뛰기·되돌림·미분류도 가능하므로 이 순서를 강제하지 않는다. 전이 행렬에는 `from`, `to`, 발생 수, 전 상태 지속 거래일, 이후 상태 지속 거래일, 동일 자산/기간별 표본 수를 기록한다. 관측 종료 때문에 결과가 아직 없는 사건은 실패로 계산하지 않고 **우측 검열**로 분리한다.

- **False Spring:** 사전에 고정한 확인 기간 안에 WINTER → SPRING_CANDIDATE 뒤 SPRING 확인 없이 WINTER로 돌아간 사건의 후보 정의. `candidate_count`, `confirmed_spring_count`, `summer_transition_count`, `false_spring_count/rate`, Summer까지 거래일, 이후 20/60/120거래일 수익을 별도 측정한다. 확인 기간·분모·동일 사건 중복 규칙을 실험 전에 고정한다.
- **False Autumn:** AUTUMN 관측 후 사전에 고정한 기간 안에 WINTER 전환 없이 SUMMER를 재개한 사건의 후보 정의. `autumn_signal_count`, `winter_transition_count`, `summer_resume_count`, 이후 낙폭을 측정한다. 현재 데이터로 Autumn을 얼마나 늦게 포착했는지도 분석한다.
- 이후 수익률·낙폭은 **사후 평가값**이다. Phase 결정, Strategy 진입, 자산 후보의 과거 선택에 되먹이지 않는다. 변경된 규칙으로 과거 라벨을 다시 만들 때는 `engine_version`을 올리고 과거 실험과 섞지 않는다.

## 검증 및 경계

1. Phase·전이·실패 정의와 관측 창을 사전 문서화한다. Seed 6종목(삼성전자·SK하이닉스·NAVER·NVDA·MSFT·AAPL)은 첫 실험용일 뿐, 선택·생존 편향을 명시한다.
2. 과거 모든 거래일을 당시 사용 가능한 데이터만으로 라벨링하고, 미래 데이터 절단·결측·분할·calendar edge case를 합성 테스트한다.
3. Spring Candidate → Spring/Summer 전환율, False Spring/Autumn, 평균 전이 기간, 사후 20/60/120거래일 결과를 원자료와 함께 검토한다. 단순 MA200 필터와 비교해 **추가 정보가 있는지** 반증한다.
4. 규칙을 고정한 뒤 다른 기간·자산의 rolling 및 Walk-Forward에서 재검증한다. 과거 성과로 후보를 선택한 동일 기간의 성적을 미래 성과처럼 사용하지 않는다. Paper Trading은 새로운 확정 관측만 append한다.
5. 삼성전자 2026년 6월은 고점 정답 라벨이 아니다. 당시 정보로 산출할 Phase가 무엇이었는지 확인하는 사례다. 기존 MA200 EntryFilter가 6월 진입을 통과시킨 [반증 기록](s1-open-position-risk-case.md)을 비교 기준으로 둔다.

Phase → 전략의 직접 결합과 자동 Capital Rotation은 v1 범위 밖이다. 장기적으로 AUTUMN 자산의 신규자금 제한, 다른 SPRING_CANDIDATE의 연구 후보화, 검증된 SPRING/SUMMER에서의 전략 후보 비교를 순서대로 시험한다. 회전 여부와 자금 배분은 별도 위험·포트폴리오 검증과 사용자 결정이 필요하다. UI, Phase badge, 실주문은 이번 문서 작업에서 구현하지 않는다.

## 구현 전 검증 질문

1. Spring Candidate를 **당시 정보만으로** 구분할 수 있는가?
2. False Spring 비율은 얼마나 높으며, 관측 기간·검열 처리에 민감한가?
3. Spring Candidate에서 Summer까지 평균 몇 거래일이 걸리는가?
4. Autumn을 위험이 이미 발생한 뒤에야 포착하는가?
5. 단순 MA200 Trend Filter에 비해 Phase Engine이 추가 정보를 주는가?
6. Phase Engine이 결국 가격 상승 뒤 “상승”이라고 부르는 후행 라벨에 불과한가?

## STEP 1 사전 고정 규칙 — PRICE_PHASE_V1

아래는 **첫 검증을 위한 결정적 후보**다. 실제 결과를 본 뒤 이 버전의 조건·기간을 바꾸지 않는다. 변경이 필요하면 결과와 실패를 보존하고 v1.1 가설로 분리한다. 고정 설정 JSON의 SHA-256을 `rule_config_hash`로 기록한다.

- 날짜 t의 Phase는 t 종가까지 확정된 가격만 쓴다. 실행 가능한 첫 시점은 t+1이다. MA50/MA200은 각각 50/200 종가 단순평균, 기울기는 `MA50[t] > MA50[t−5]`, `MA200[t] > MA200[t−10]`이다. 평탄/개선은 현재 MA200 10일 차분이 10거래일 전 차분보다 크거나 같음을 뜻한다.
- 최근 Higher Low/High는 현재까지의 최근 10거래일 최저/최고가가 그 직전 10거래일 최저/최고가보다 높은 경우다. 20일 돌파는 t 종가가 t 이전 20거래일 최고가를 넘는 경우다. 최근 저점 회복은 `Close[t]/min(Low[t−19:t])−1 ≥ 5%`다. 52주 고점 낙폭은 252거래일 최고가가 있을 때만 계산하며, 없으면 `null`이다.
- WINTER 원자료: `Close < MA200 ∧ MA50 < MA200 ∧ MA200[t] < MA200[t−10]`.
- SUMMER 원자료: `Close > MA200 ∧ MA50 > MA200 ∧ MA50[t] > MA50[t−5] ∧ MA200[t] > MA200[t−10]`.
- SPRING_CANDIDATE 원자료: SUMMER가 아니고 `Close > MA50 ∧ MA50 기울기 양수 ∧ (Higher Low ∨ 최근 저점 대비 5% 이상 회복)`이다. 회복 Evidence는 매수 신호가 아니다.
- SPRING 원자료: `Close > MA50 ∧ MA50 기울기 양수 ∧ (Higher Low ∨ 최근 저점 대비 5% 이상 회복) ∧ (MA50 ≥ MA200 ∨ 20일 돌파)`다. SUMMER 조건이 바로 성립하더라도 이미 CANDIDATE 상태라면 SPRING 확인 단계를 건너뛰지 않는다.
- AUTUMN 원자료: 이전 확정 Phase가 SUMMER 또는 AUTUMN일 때, SUMMER 원자료가 거짓이고 `(Close < MA50 ∨ MA50 기울기 비양수 ∨ 52주 고점 낙폭 ≥ 10%)`이다. 이는 자동 청산 조건이 아니다.
- **상태별 전이**에서만 원자료를 판정한다. UNKNOWN→WINTER/SUMMER/SPRING_CANDIDATE, WINTER→SPRING_CANDIDATE, SPRING_CANDIDATE→SPRING/WINTER, SPRING→SUMMER/WINTER, SUMMER→AUTUMN, AUTUMN→SUMMER/WINTER. 허용되지 않은 직접 점프를 좋은 결과가 되도록 강제하지 않는다. 모든 변경은 같은 목표 상태의 원자료가 **3거래일 연속** 참일 때 확정하고 전이일은 세 번째 날이다. 두 후보가 동시에 확인되면 이전 상태별 명시 순서: CANDIDATE는 WINTER 우선, SPRING은 WINTER 우선, AUTUMN은 WINTER 우선, UNKNOWN은 WINTER→SUMMER→CANDIDATE 순서다. 미확정 중에는 직전 확정 상태를 유지한다. 초기 200일 미만과 아직 확정 상태가 없는 날은 UNKNOWN으로 둔다.
- False Spring은 CANDIDATE 진입 후 **60거래일 안에** SPRING/SUMMER 확인보다 먼저 WINTER로 복귀한 사건이다. Spring 확인이 먼저 오면 `CONFIRMED`; 60일 내 어느 쪽도 없으면 `UNRESOLVED`; 관측 데이터가 60일 전에 끝나면 `CENSORED`. false rate 분모는 `FALSE + CONFIRMED`; unresolved/censored 수를 함께 보고한다.
- False Autumn은 AUTUMN 진입 후 **60거래일 안에** WINTER 전환보다 먼저 SUMMER 재개가 확인된 사건이다. WINTER가 먼저면 `WINTER`; 그 외 `UNRESOLVED`/`CENSORED`를 구분한다. 어느 경우도 미래 데이터를 당시의 Phase 판정에 되먹이지 않는다.

이 규칙의 구현 버전은 `PRICE_PHASE_V1`이다. 설정 해시는 엔진 설정 JSON의 SHA-256으로 기록한다. 독립 패키지 `src/zero_market_lab/market_phase/`가 Boolean Evidence, `PhaseResult`, `PhaseTransition`, 지속기간과 사후 20/60/120거래일 평가를 만든다. Phase 라벨과 전이에는 미래 가격이 들어가지 않으며, 사후 결과는 별도 필드에만 둔다. 첫 고정 규칙 실행의 부정적 결과와 데이터 한계는 [역사 검증 결과](fecm-market-phase-engine-v1-results.md)에 보존했다. 이 STEP에서는 Strategy Engine, 주문, 자금 회전, UI를 연결하지 않았다.
