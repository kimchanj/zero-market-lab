# FECM Parent / Child Multi-Timeframe Phase — STEP 3 연구

상위 기준: [ZERO_MARKET_LAB_META.md](../ZERO_MARKET_LAB_META.md). 이 문서는 **연구 후보의 사전 정의와 검증 결과**를 분리해 기록한다. `PRICE_PHASE_V1` 규칙·기존 일별 라벨·[첫 결과](fecm-market-phase-engine-v1-results.md)·[실패 분석](fecm-market-phase-v1-failure-analysis.md)을 수정하지 않는다. Parent/Child 상태는 주문·추천·새 공식 Phase가 아니다. 현재 6종목만 Development Set으로 사용하며 Holdout은 열지 않는다.

## 1. 실험 전 고정: Why Multi-Timeframe / 기존 한계

단일 v1의 WINTER·Candidate 지속기간 중앙값은 각각 3거래일, SPRING 7, SUMMER 39, AUTUMN 17일이고 종목별 연간 전이는 약 4.9~8.4회다. False Spring 59/75, 60거래일 내 Autumn→Summer 복귀 67/87은 한 라벨이 다른 시간축의 움직임을 섞는다는 가설을 낳는다. 그러나 Parent/Child 분리가 이 결과를 개선한다고 전제하지 않는다.

## 2. 실험 전 고정: Parent / Child 연구용 후보와 상태 계약

두 후보만 계산한다. **A:** Parent `MA200`·20거래일 변화·10거래일 연속확인, Child `MA50`·5거래일 변화·3거래일 연속확인. **B:** Parent `MA200`·40거래일 변화·10거래일 연속확인, Child `MA20`·3거래일 변화·3거래일 연속확인. 두 후보는 수익률 순위로 선택하지 않는다. B는 Parent 반응을 늦추고 Child 반응을 빠르게 했을 때 안정성·churn·해석이 어떻게 바뀌는지 보는 **대조적 구조 후보**다. 이 수치는 STEP 2 결과에서 채굴한 최적값이 아니며 현재 데이터에서 탐색·조정하지 않는다.

각 Layer에서 해당 평균과 기울기가 준비되지 않으면 `UNKNOWN`. 그 외 당일 종가·당일 확정 평균·과거 평균만으로 네 가지 **기술 상태**를 산출한다. `Close>MA ∧ slope>0` → `SUMMER`(평균 위의 상승), `Close≤MA ∧ slope<0` → `WINTER`(평균 아래의 하락), `Close>MA ∧ slope≤0` → `SPRING`(하락/평탄 평균 위 회복), 나머지 `Close≤MA ∧ slope≥0` → `AUTUMN`(상승/평탄 평균 아래 조정). 이름은 v1과 같아도 **규칙·의미·버전이 다르다**. 이 후보에는 `SPRING_CANDIDATE`가 없다. 별도 단계의 후보확인 조건을 임의로 끼워 넣지 않기 위함이다. v1 Candidate 사건의 Child 회복 맥락은 `SPRING`과 `SUMMER`를 **각각** 보고, 필요 시 둘을 합친 `child_recovery`를 설명용으로만 쓴다.

각 raw 상태가 Layer별 확인일수 연속 유지돼야 확정 전이하며 대기 중에는 기존 확정 상태를 유지한다. 최초 충분한 데이터 이전과 최초 확정 이전은 `UNKNOWN`; `UNKNOWN`도 확정 상태가 아니다. 시간축마다 서로 다른 Phase가 동시에 있을 수 있다. `CombinedPhaseState`는 `symbol, date, parent_phase, child_phase, parent_evidence, child_evidence, parent_days, child_days, parent_transition, child_transition, candidate_id, rule_config_hash, available_at`을 갖는다. 모든 필드는 해당 거래일 종가까지의 가격과 이전 상태만 쓴다. 이후 20/60/120거래일 수익·낙폭·후속 전이는 **별도 사후 결과 테이블**에만 붙인다.

`Parent WINTER + Child SPRING/SUMMER`는 장기 하락 안의 단기 회복, `Parent SUMMER + Child AUTUMN/WINTER`는 장기 상승 안의 조정, `Parent SPRING + Child SUMMER`는 긴 평균 회복과 짧은 상승의 동시 관측, `Parent AUTUMN + Child WINTER`는 긴 평균 아래 하락과 짧은 하락의 동시 관측을 뜻하는 **해석 후보**다. 같은 Child 상태도 Parent가 다르면 의미가 다를 수 있다. 합산 점수·자동 행동을 만들지 않는다.

## 3. 실험 전 고정: 평가와 누출 차단

- Parent가 Child보다 전이 수가 적고, Phase 구간 지속기간 중앙값이 길어야 두 시간축의 **형식적 분리**가 성립한다. 비교 분모는 각 Layer의 첫 확정 이후 공통 판정 가능 기간이며, UNKNOWN 구간과 마지막 우측 검열 구간을 함께 보고한다.
- 기존 v1 사건 75 Candidate·87 Autumn의 원래 성공/실패 정의와 분모는 고정한다. 사건 당일 새 Parent/Child 맥락과 결합해 조건부 건수만 본다. 사후 결과로 당시 맥락을 수정하지 않는다.
- Parent/Child `SUMMER→AUTUMN→SUMMER`와 `WINTER→SPRING/SUMMER→WINTER` 왕복의 60거래일 내 건수를 보조 churn으로 센다. 다른 상태 경유/관측 종료는 별도 처리한다. v1의 67/59건과 **동일한 사건 정의가 아니므로** 직접 성공률 비교하지 않는다.
- 각 사건의 `child_transition`과 이후 첫 관련 `parent_transition`까지 거래일 차이를 계산하되, 미래 Parent 전이는 **사후 lead/lag 평가**다. 당시 상태 입력에는 쓰지 않는다. 처음 움직인 Child가 Parent를 예측한다고 주장하지 않는다.
- Combined State의 날짜별 빈도와 사후 수익을 기록하되 같은 상태의 연속일은 독립 표본이 아니다. 원일수·연속 Episode 수·검열을 함께 보고한다. 가격 데이터의 조정/분할·생존 편향·한국/미국 시세 차이는 기존 검증 문서의 한계를 따른다.

## 4. 사후 관찰 결과

위 후보·상태·평가 기준은 실제 실행 전에 고정했다. 구현은 [재현 스크립트](../scripts/research_multitimeframe_phase.py), 생성물은 Git 제외 `artifacts/fecm-multitimeframe-step3/{A,B}/`에 있다. 두 후보의 설정 해시와 기존 v1 일별 CSV SHA-256은 `analysis_summary.json`에 기록한다. 일별 상태 CSV, 사건별 당시 Context CSV, 16칸 Matrix, Episode, Lead/Lag, 사례 Timeline을 각각 내보낸다.

### 4.1 Parent stability / Child responsiveness

| 연구 후보 | Parent 전이 합계 | Child 전이 합계 | Parent 구간 중앙값 | Child 구간 중앙값 | Parent 60일 SUMMER→AUTUMN→SUMMER | Child 같은 왕복 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| A (200/50) | 94 | 477 | 39.5거래일 | 11거래일 | 5 | 44 |
| B (200/20) | 93 | 735 | 40거래일 | 8거래일 | 5 | 42 |

전이 수는 각 종목에서 **두 Layer가 모두 판정 가능한 공통기간** 기준이다. 구간 중앙값은 해당 Layer의 전체 6종목 Episode를 합친 기술통계로 각 Layer 마지막 6개 우측 검열 구간을 포함한다. Parent가 적게 전이하고 오래 지속한다는 **형식적 시간축 분리 조건**은 6종목 전부에서 통과했다. 다만 이는 긴 MA·긴 확인기간이라는 설계의 부분적 결과다. “더 정확한 장기 계절”의 증거가 아니다. B는 Child 전이가 훨씬 많아 짧은 가격 흔들림을 더 많이 라벨링한다. v1의 False Autumn 67건과 여기의 Parent 왕복 5건은 상태 규칙과 사건 정의가 달라 **같은 실패율의 개선으로 계산할 수 없다**. v1 WINTER↔Candidate 59건과 Parent의 Winter-recovery-Winter 왕복은 각각 A 4건, B 2건이며 동일 사건이 아니다.

### 4.2 Combined State Matrix와 사후 결과

두 후보 모두 UNKNOWN을 뺀 `4×4=16`개의 조합이 실제로 나타났다. A의 대표 조합은 `Parent SUMMER + Child SUMMER` 4,730 **일별 관측**·119연속 Episode, `SUMMER+WINTER` 1,083일·76 Episode, `SUMMER+AUTUMN` 799일·101 Episode, `WINTER+SUMMER` 560일·37 Episode, `AUTUMN+WINTER` 553일·25 Episode다. B의 `SUMMER+WINTER`는 1,834일·152 Episode로 A보다 더 빈번하다. 조합은 단일 라벨보다 **긴 추세와 짧은 약화를 동시에 표현**하지만 유리한 행동을 의미하지 않는다.

별도 `combined_matrix.csv`에는 각 조합의 사후 20/60/120거래일 종가 수익률 중앙값과 120일 peak-to-trough 낙폭을 포함한다. 예컨대 A의 `SUMMER+AUTUMN` 60일 수익 중앙값은 **+5.3%**, `SUMMER+WINTER`는 **+4.7%**다. `AUTUMN+WINTER`도 60일 중앙값 **+7.3%**다. 연속일이 겹치는 창과 선정된 생존종목의 상승이 섞인 값으로, 이 조합을 매매 신호로 쓸 근거가 아니다. 미래 수익은 독립 결과 테이블에서만 계산했고 일별 Phase 산출에는 투입하지 않았다.

### 4.3 기존 Spring 75건의 Parent / Child 재분류

| 후보 | Parent WINTER: 성공 / False | Parent SPRING: 성공 / False | 그 외 Parent | Child 맥락 |
| --- | ---: | ---: | --- | --- |
| A | 15 / 59 | 1 / 0 | 없음 | 75건 모두 Child SUMMER |
| B | 15 / 59 | 1 / 0 | 없음 | 성공: SUMMER 12, SPRING 2, WINTER 2; False: SUMMER 49, SPRING 2, WINTER 3, AUTUMN 5 |

Parent WINTER에 False Spring이 집중되지만 성공 16건 중 **15건도 같은 Parent WINTER**였다. A의 Child도 두 군이 전부 SUMMER여서 분리 정보가 없다. B는 Child 맥락이 더 다양하지만 성공 16건과 실패 59건이 각 상태에서 겹치며 작은 칸의 표본도 부족하다. v1 Candidate라는 이름을 A/B의 Child SPRING과 동일시하지 않는다. `Parent WINTER + Child 단기 회복`은 **양쪽 결과 모두**의 묘사다.

### 4.4 기존 Autumn 87건의 재분류

| 후보 | Parent SUMMER 안의 60일 Winter / Summer 재개 / 미해결 / 검열 | Parent 비SUMMER | False Autumn의 Child 맥락 |
| --- | --- | --- | --- |
| A | 12 / 67 / 7 / 1 | 없음 | WINTER 38, AUTUMN 13, SUMMER 11, SPRING 5 |
| B | 11 / 67 / 7 / 1 | Winter 전환 1건은 Parent UNKNOWN | WINTER 42, SUMMER 15, AUTUMN 9, SPRING 1 |

`Parent SUMMER + Child AUTUMN`이라는 **좁은 H2 표현은 맞지 않는다**: False Autumn 다수의 Child는 이미 WINTER이거나 SUMMER였다. `Parent SUMMER 안의 Child 약화`라는 넓은 표현은 많은 사건을 설명하지만, **Winter로 이어진 12건도 같은 Parent SUMMER**에 있으므로 결과를 구분하지 못한다. B의 UNKNOWN 1건은 긴 Parent 준비기간의 결측이며 Winter군에 억지 배정하지 않았다. Child가 SUMMER인 Autumn 사건도 있어 두 모델의 Phase 의미가 다름을 보여준다.

### 4.5 Samsung, SK hynix, NAVER 및 성공 Spring

- **삼성전자 2026:** 두 후보 모두 06-25 `Parent SUMMER + Child SUMMER`. A Child `SUMMER→AUTUMN`은 **07-09**, `AUTUMN→WINTER`는 **07-27**; B Child `SUMMER→WINTER`는 **07-03**이다. v1 AUTUMN 확정은 **07-27**. 따라서 B의 Child 약화는 v1보다 24달력일 먼저 보였지만, 07-03 종가 시점에서 이후의 큰 하락을 알았다는 뜻은 아니다. 두 Parent는 10-08까지 SUMMER였으며 이 관측 구간에서 Parent 약화 전이가 없었다. A의 Child는 09-30 SUMMER, B는 08-19 SUMMER로 복귀했다. 빠른 Child 경고와 잦은 왕복이 동시에 존재한다.
- **SK하이닉스:** 2025-09-08 v1 AUTUMN→09-15 SUMMER 재개 사건에서 A Parent는 계속 SUMMER, Child는 09-08 AUTUMN→09-09 SPRING→09-15 SUMMER다. B Parent도 SUMMER이지만 09-08 Child는 이미 SUMMER다. **두 후보가 같은 조정을 동일하게 라벨링하지 않는다.** 2026-07-30 v1 AUTUMN은 최종 관측일까지 우측 검열이며 A/B 모두 Parent SUMMER+Child WINTER였다. 그 뒤 가격 상승을 곧바로 Summer 재개로 재분류하지 않는다.
- **NAVER:** 2026-06-05·08-06·09-09의 세 v1 Candidate는 A에서 모두 `Parent WINTER + Child SUMMER`였고 이후 세 건 모두 v1 Winter로 복귀했다. B에서도 Parent WINTER이지만 Child는 각각 SUMMER, SUMMER, WINTER다. “Parent Winter 안의 단기 상승”이 실패 사례를 묘사할 수는 있어도 **성공 사건과 구분되지 않는다**.
- **성공 예시:** 삼성 2025-06-24, SK 2023-05-22, NAVER 2023-05-16의 세 Candidate→Spring→Summer 사건은 A/B에서 모두 `Parent WINTER + Child SUMMER`였다. 이는 위 NAVER 실패 사건과 같은 조합이다. 성공 사례는 결과 확인 후 고른 설명용이며 확률 추정이 아니다.

모든 날짜의 Parent/Child 상태와 전이는 각 후보의 `case_timelines.csv` 및 종목별 `*_combined.csv`에서 확인 가능하다.

### 4.6 Alignment와 Lead / Lag

`Parent SPRING + Child SUMMER`, `Parent AUTUMN + Child WINTER` 같은 방향 정렬은 **범주형 관찰**로만 남긴다. A에서 각각 487일/22 Episode, 553일/25 Episode다. 반대 방향처럼 보이는 `Parent SUMMER + Child WINTER`도 1,083일/76 Episode로 흔하다. 이것이 일시 조정인지 장기 전환의 초기인지 단일 날짜에는 알 수 없다.

사후 `lead_lag.csv`는 Child 전이 뒤 **120거래일 이내** 첫 Parent 전이와 같은 강약 방향의 첫 Parent 전이까지의 거래일 차이를 기록한다. A Child 전이 511건 중 약화 방향 253건, 그중 같은 방향 Parent 전이가 이후 100건(관측 가능한 일부)의 lag 중앙값 **38.5거래일**이다. B는 Child 835건, 약화 방향 420건 중 147건, lag 중앙값 **43거래일**이다. 해당 후속 Parent가 없는 건과 관측 종료로 120일을 다 보지 못한 건은 따로 남겼다. **이 수치는 사후 짝짓기이며 선행 예측력이나 독립 관측을 뜻하지 않는다.** 삼성 2026의 Child 약화 후 Parent 약화 전이는 마지막 관측일까지 없으므로 성공적인 리드 사례로 세지 않는다.

### 4.7 Nested Cycle 해석, 가설과 반증

| 가설 | Development Set 관찰 | 반대 증거·한계 | Holdout에서 버릴 조건 | 현재 상태 |
| --- | --- | --- | --- | --- |
| H1. False Spring은 Parent WINTER 안의 Child SPRING에 집중된다. | Parent WINTER: False 59/59. | 성공도 15/16이 Parent WINTER. A Child는 전부 SUMMER; B의 SPRING은 양 군 2건씩. **좁은 표현은 지지되지 않음.** | 독립 종목에서도 성공과 실패의 Parent/Child 맥락 분포가 비슷하면 분리 가설 폐기. | UNTESTED; 현재 분리력 부정적 |
| H2. False Autumn은 Parent SUMMER 안의 Child AUTUMN이다. | False 67/67이 Parent SUMMER; Parent의 구조는 긴 추세다. | Winter 전환 12/12도 Parent SUMMER. False의 Child AUTUMN은 A 13/67, B 9/67뿐. **좁은 표현은 지지되지 않음.** | 독립 표본에서도 Child AUTUMN 비중이 낮거나 Winter군과 같다면 폐기. | UNTESTED; 현재 분리력 부정적 |
| H3. 큰 추세 전환은 Parent/Child 같은 방향 정렬 뒤 더 많다. | 정렬 조합과 Child 선행 사례는 존재한다. | 삼성 Child 약화 뒤 Parent는 계속 Summer; `AUTUMN+WINTER`의 A 60일 사후 수익 중앙값도 +7.3%. 사건 정의와 독립 검증 없음. | 사전 정의한 전환 Episode에서 정렬 후 큰 전환 빈도·위험 차이가 비교 Episode보다 높지 않으면 폐기. | UNTESTED; 현 STEP에서 판정 불가 |

시간축 분리는 **상태 설명을 풍부하게** 만들지만, 현재 Frozen v1의 False Spring/Autumn을 Parent Context만으로 가려내지 못했다. 특히 H1·H2의 단순 서술을 규칙이나 행동으로 옮기면 안 된다.

### 4.8 한계, Holdout 사전등록 준비와 다음 단계

두 후보의 네 구역 매핑·확인일수는 연구를 위한 임의의 결정적 가정이며 **최종 Parent/Child Phase 규칙이 아니다**. `SPRING_CANDIDATE`를 이 모델에 구현하지 않았다. 짧은 Child는 더 많은 전이를 만들고, 긴 Parent는 급락에 늦을 수 있다. 확인일수와 MA 길이가 안정성을 기계적으로 만든다. 6개 생존 종목·서로 다른 데이터 출처·가격 조정 정책, 중첩 사건·중첩 일별 forward window, 우측 검열, 표본별 관측기간 차이를 고려해야 한다. 후보 A/B를 수익률 성적순으로 선택하지 않는다.

Holdout은 **아직 열거나 선정하지 않았다**. 다음 STEP 전에 Parent/Child 중 검증할 **하나의** 구성과 상태 규칙, Phase 의미, H1/H2/H3의 1차 지표·대조 Episode·실패 조건, 자료 품질 기준, Holdout의 한국/미국·업종·규모·상승/횡보/하락 구성 기준을 고정해야 한다. 현재 결과에서는 H1/H2의 좁은 표현을 그대로 승격하기보다 **반례를 포함한 더 작은 질문**으로 재설계할 필요가 있다. 새 임계값 채굴·ML·전략 연결·자동 Capital Rotation·UI 고도화는 시작하지 않는다.
