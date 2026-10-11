# FECM Transition Dynamics — STEP 4

상위 기준: [ZERO_MARKET_LAB_META.md](../ZERO_MARKET_LAB_META.md). 이 절의 **사전 계약**은 Development Set의 STEP 4 통계를 계산하기 전에 고정했다. `PRICE_PHASE_V1` 일별 라벨·Spring/Autumn 사건·사후 결과, STEP 3의 Parent/Child 후보 A/B와 결과를 변경하지 않는다. 여기의 수치는 당일 종가 후 관찰 가능한 설명 Feature이며 Phase Rule, 매매 신호, 점수 또는 확률이 아니다.

## 1. Why Transition Dynamics

동일 Parent 상태 안에 서로 다른 사후 결과가 공존했다. State(당시 위치)와 Velocity(최근 변화), Persistence(최근 유지)를 분리해 볼 필요가 있다. 이것이 예측력을 보장하지 않는다.

## 2. Previous Hypothesis Failures

H1 narrow — “False Spring은 Parent WINTER 안의 Child Spring에 집중된다”는 Development Set에서 **지지되지 않았다**. 실패 59/59뿐 아니라 성공 15/16도 Parent WINTER였고, A Child는 75건 모두 SUMMER였다. H2 narrow — “False Autumn은 Parent SUMMER 안의 Child Autumn이다”도 **지지되지 않았다**. Summer 복귀 67/67과 Winter 전환 12/12 모두 A Parent SUMMER였으며 Summer 복귀군의 A Child AUTUMN은 13/67뿐이다. Parent 이름만으로 결과를 구별하지 않는다. H3는 이번 검증대상이 아니다.

## 3. H4 — Spring Transition Strength

**사전 가설:** v1 Candidate 당일, 성공 Spring은 False Spring보다 장기 하락 둔화(`ma200_slope_change_10d`의 높은 값)와 단기 회복 지속(`positive_ma50_slope_days_10d`, `recovery_persistence_days`의 높은 값)이 함께 나타날 수 있다. **현재 상태: UNTESTED.** 1차 지표는 성공군 median `ma200_slope_change_10d` − 실패군 median이며, 양수 방향을 예상한다. Secondary는 MA50 양의 기울기 일수와 MA200 거리 변화다. 결과를 본 뒤 1차 지표를 바꾸지 않는다.

## 4. H5 — Autumn Transition Pressure

**사전 가설:** v1 Autumn 당일, 이후 Winter로 전환한 군은 Summer 복귀군보다 52주 고점 낙폭이 최근 10거래일에 더 빠르게 확대(`drawdown_change_10d`의 낮은 값)되고 MA50 약화가 더 지속(`negative_ma50_slope_days_10d`의 높은 값)되었을 수 있다. **현재 상태: UNTESTED.** 1차 지표는 Winter군 median `drawdown_change_10d` − Summer 복귀군 median이며 음수 방향을 예상한다. Secondary는 음의 MA50 기울기 일수와 `failed_recovery_count_10d`. 결과를 본 뒤 1차 지표를 바꾸지 않는다.

## 5. Feature Definitions

입력은 기존 6종목의 로컬 OHLC와 Frozen 일별 CSV다. 모든 창은 **거래일** 기준이고 당일 t를 포함한다. 결측 준비기간은 null이며 0으로 대체하지 않는다. `slope50[t] = MA50[t]/MA50[t−5]−1`, `slope200[t] = MA200[t]/MA200[t−10]−1`; 기울기 변화는 각각 `slope50[t]−slope50[t−5]`, `slope200[t]−slope200[t−10]`. 수익률·거리·기울기는 소수(0.01 = 1%), 일수는 정수다. `price_minus_maX_pct = Close/MAx−1`. `price_minus_ma200_change_10d`는 거리의 t−10 대비 **percentage-point가 아닌 소수 차분**이다. `drawdown_from_52w_high = Close/max(High[t−251:t])−1`; 완전한 252개 관측이 필요하다. `recovery_from_recent_low = Close/min(Low[t−19:t])−1`은 v1과 같은 20일 저점 개념이다. 52주 고점 기준 `days_since_recent_high`는 동일 최고가가 재출현하면 가장 최근 위치까지의 거래일 수다.

`previous_phase`는 v1 사건 직전의 확정 Phase다. `parent_phase`,`child_phase`는 STEP 3 **A**의 당시 연구 라벨을 설명용으로 복사한다. B를 유리한 쪽으로 선택하지 않는다. `ma50_slope_positive`, `ma200_slope_improving`, `close_above_ma50`, `drawdown_worsening_10d`는 0과의 부호 비교로만 만든 Boolean 설명 Feature이며 최적화 임계값이 아니다. 사후 `group`,`days_to_outcome` 등은 별도 Outcome 열로만 병합하고 Feature 함수에는 전달하지 않는다. 사건 분모는 기존 Spring `CONFIRMED` 16 vs `FALSE_SPRING` 59, Autumn `WINTER` 12 vs `FALSE_AUTUMN` 67; 미해결 7/검열 1은 비교에서 제외하되 원래 사건을 보존한다.

## 6. Velocity

`drawdown_change_5d/10d = drawdown[t]−drawdown[t−5/10]`; **음수일수록 낙폭 확대**다. 기울기 변화와 MA200 거리 변화도 위처럼 signed 차분이다. 편의상 절댓값·속도 점수로 바꾸지 않는다. 동일 고점 기준이 창 사이에 바뀔 수 있으므로 drawdown 변화는 가격 변화와 완전히 같지 않다.

## 7. Persistence

`positive_ma50_slope_days_10d`,`negative_ma50_slope_days_10d`,`close_above_ma50_days_10d`,`days_below_ma50_10d`는 t−9:t의 참 일수다. 결측이 하나라도 있으면 null. `recovery_persistence_days`는 t에서 거슬러 올라가는 **연속 Close>MA50** 거래일 수이며 첫 MA50 유효일 전에는 null; 보이는 이력 내 최장 길이는 관측 시작으로 좌측 검열될 수 있다. `failed_recovery_count_10d`는 최근 10개 관측일에서 전일 `Close>MA50`였고 당일 `Close≤MA50`인 교차의 수다. 첫 비교일의 전일은 창 밖이어도 당시 과거일이면 허용한다. 완전한 10일과 전일 MA50가 필요하다. 이는 추후 반등 실패를 뒤돌아 세지 않는 **당시 확인된 이탈 사건**이며 “매도 실패”가 아니다. `recent low retest failure`와 `new_high_failure duration`은 이번 두 가설의 고정 Feature에 넣지 않고 Future Candidate로 남긴다.

## 8. Spring Analysis

사전 계약 후 [독립 분석 스크립트](../scripts/research_transition_dynamics.py)를 6종목 Development Set에 실행했다. 원본 사건 **16 성공 / 59 False**, 결측 없이 75건을 비교했다. 생성 CSV/JSON은 재배포 전 데이터 라이선스를 확인해야 하므로 Git 제외 `artifacts/fecm-transition-dynamics-step4/`에 둔다. 각 사건의 raw Feature와 결과 Outcome은 별도 열이며 `*_diff.csv`에는 유효 건수·평균·중앙값·표준편차·25/75분위·중앙값 차·Cohen's d, `*_categorical.csv`에는 참/범주 비율을 둔다.

| Feature | 성공 중앙값 | False 중앙값 | 차이(성공−False) | 기술적 효과크기 d |
| --- | ---: | ---: | ---: | ---: |
| `price_minus_ma200_pct` — State | +3.35% | −5.96% | +9.31%p | +1.64 |
| `ma200_slope` — State | −0.56% | −1.06% | +0.51%p | +0.48 |
| `ma200_slope_change_10d` — **H4 Primary** | +0.292%p | +0.159%p | +0.133%p | +0.21 |
| `price_minus_ma200_change_10d` — Velocity | +7.88%p | +5.75%p | +2.13%p | +0.64 |
| `positive_ma50_slope_days_10d` — Persistence | 4일 | 9일 | **−5일** | −0.51 |
| `recovery_persistence_days` — Persistence | 8.5일 | 16일 | **−7.5일** | −0.53 |

H4 Primary와 거리 변화는 예상 방향이나 **가장 큰 분리는 오히려 당시 MA200과의 거리(State)**였다. MA50 양의 기울기 유지와 MA50 위 연속일은 예측과 반대다. `Close>MA50`·당일 양의 MA50 기울기는 Candidate의 구성 조건이어서 양 군 모두 100%로 차별력이 **0**이다. 52주 고점 낙폭은 성공 −16.45%, False −26.66%로 State 차이가 있지만 사건 정의와 생존 종목의 영향을 받는다. 종목별 H4 Primary 차이는 6종목 중 4종목에서 양수, 삼성·SK에서는 음수다. 이 표본에서 “State보다 Velocity/Persistence가 더 잘 분리한다”는 주장은 성립하지 않는다.

## 9. Autumn Analysis

원본 Autumn **87건**을 보존했다. 해결된 사건은 Winter 전환 **12건**, Summer 재개 **67건**이며 미해결 7/우측 검열 1은 기술 파일에 남기고 두 군 비교에서 제외했다. 52주 고점 자료가 부족한 Winter 1건으로 drawdown 및 Velocity의 유효 표본은 **11/67**이다.

| Feature | Winter 중앙값 | Summer 재개 중앙값 | 차이(Winter−Summer) | 기술적 효과크기 d |
| --- | ---: | ---: | ---: | ---: |
| `price_minus_ma200_pct` — State | −0.23% | +8.50% | **−8.73%p** | −0.97 |
| `drawdown_from_52w_high` — State | −12.72% | −11.41% | −1.31%p | −0.25 |
| `drawdown_change_10d` — **H5 Primary** | −3.87%p | −2.97%p | −0.90%p | −0.39 |
| `drawdown_change_5d` — Velocity | −2.55%p | −1.56%p | −0.98%p | −0.47 |
| `negative_ma50_slope_days_10d` — Persistence | 2.5일 | 3일 | **−0.5일** | −0.88 |
| `days_below_ma50_10d` — Persistence | 5일 | 7일 | **−2일** | −0.31 |
| `failed_recovery_count_10d` | 1 | 1 | **0** | +0.23 |

H5 Primary는 예상 방향이나 `drawdown_worsening_10d` 비율은 Winter 81.8%, Summer 재개 82.1%로 거의 같다. MA50 음의 기울기 일수·MA50 아래 일수는 예상과 반대이며 회복 실패 횟수 중앙값은 같다. MA200 기울기 변화도 Winter −0.07%p, Summer 재개 −0.09%p로 예상하는 “더 큰 장기 약화”가 보이지 않는다. MA200 거리 State 차이는 Velocity 차이보다 크다. Winter 사례가 없는 SK를 제외하면 H5 Primary 종목별 방향은 5종목 중 3종목만 예상과 일치한다. 이 표본에서 State보다 압력 Feature가 더 잘 구분한다는 주장은 성립하지 않는다.

## 10. Samsung

`case_samsung_transition.csv`에 2026-06-01~08-14 관측을 기록했다(08-15는 비거래일). 06-25에는 v1·A Parent·A Child 모두 Summer. 07-03에는 10일 낙폭 변화 **−11.88%p**, 최근 10일 중 MA50 아래 **1일**; 07-09에는 **−21.50%p**, **4일**, A Child Autumn. 07-20에는 **−17.49%p**, **9일**. v1 Autumn이 07-27 확정됐을 때는 낙폭 변화 **−8.28%p**, MA50 아래 **10일**, A Child Winter였고 Parent는 여전히 Summer였다. 즉 약화는 v1 확정보다 앞서 **사후 Timeline에서 관찰**되지만, 07-03 당일 이후 Winter를 예측한 적은 없다. 52주 rolling 고점이 창에서 빠질 때 변화량이 가격 변화와 달라질 수 있다.

## 11. SK hynix

`case_sk_hynix_transition.csv`에 2025-08-18~09-30을 기록했다. v1 Autumn 09-08에는 낙폭 변화가 **+5.71%p**(축소), MA50 아래 **8/10일**, A Parent Summer·Child Autumn이었다. 09-09에는 Child Spring, 09-15 v1 Summer 복귀에는 낙폭 변화 **+13.40%p**, MA50 아래 **3/10일**, A Child Summer다. 이 사례는 약화 지속기간만으로 Winter/Summer를 가르기 어렵고, 낙폭의 회복 방향을 보여준다. 두 자산의 다른 시기·다른 가격 수준을 독립 대조 실험으로 취급하지 않는다.

## 12. NAVER

세 False Spring의 `ma200_slope_change_10d`는 **+0.85%p, −0.06%p, −0.35%p**, MA50 양의 기울기 일수는 **3, 9, 3일**, MA50 위 연속일은 **5, 3, 15일**이었다. 06-05의 장기 기울기 개선과 09-09의 15일 연속 회복에도 모두 실패했다. 따라서 “개선/지속이 있으면 성공”이라는 개별 규칙은 이미 반례가 있다. 사건일 앞뒤 10거래일 설명 행은 `case_naver_transition.csv`에 보존하며 미래 행은 사건 Feature에 사용하지 않는다.

## 13. Successful Spring Cases

`successful_spring_transition_cases.csv`에 세 사건일 전후 10거래일을 저장했다. 사건일 H4 Primary는 삼성 **+0.38%p**, SK **−0.26%p**, NAVER **+0.37%p**다. SK의 성공은 장기 기울기 개선 부재라는 명확한 반례다. 세 사건의 MA50 양의 기울기 일수는 모두 3일이며 성공 조건을 찾은 표본이 아니다.

## 14. Counter Evidence

H4 성공 16건 중 **4건**은 Primary가 0 이하(예: SK 2023-05-22 −0.26%p, NVDA 2023-01-11 −1.18%p). False Spring NAVER 2026-06-05는 +0.85%p다. H5 Winter 12건 중 drawdown 값이 준비된 11건의 **2건**은 10일 낙폭이 오히려 축소(삼성 2024-08-28 +0.34%p, AAPL 2025-02-28 +0.12%p). Spring 회복 지속성은 False군이 더 크고 Autumn 약화 지속성도 Winter군이 더 크지 않다. 사건들은 같은 자산·국면 안에서 반복되고 서로 독립이 아니다.

## 15. H4 Decision

사전 판정 원칙: Primary median 차이가 예상과 반대이거나 0이면 `NOT SUPPORTED`. Primary가 예상 방향이어도 Secondary가 서로 엇갈리거나 종목별 방향이 불안정하면 `WEAK`. Primary와 두 Secondary가 예상 방향으로 일치하고 여러 종목에 반복되면 Development Set에서만 `SUPPORTED`. 통계적 유의성·투자 실행 가능성을 뜻하지 않는다. 표본 수와 결측을 함께 보고한다.

**Development Set 판정: WEAK.** Primary +0.133%p와 거리 변화 +2.13%p는 예상 방향이지만, MA50 양의 기울기 지속 −5일 및 MA50 위 연속일 −7.5일은 역방향이다. State 거리의 기술적 효과크기(+1.64)가 기울기 변화(+0.21)보다 크다. 긴 하락의 둔화가 일부 정보를 줄 가능성은 남지만 “Transition Strength가 State보다 우수”는 현재 증거로 지지되지 않는다.

## 16. H5 Decision

H4와 같은 원칙을 적용하되 Primary 예상 방향은 음수, Secondary는 양수다. 결과를 본 뒤 이 기준을 조정하지 않는다.

**Development Set 판정: WEAK.** Primary −0.90%p는 예상 방향이나 음의 MA50 기울기 지속 −0.5일은 역방향이고 회복 실패 횟수 중앙값은 0 차이다. State `price_minus_ma200_pct`의 d(−0.97)가 Velocity d(−0.39)보다 크다. 삼성의 급격한 악화 사례를 일반화할 수 없다.

## 17. Falsification

Holdout에서 H4 Primary 차이가 0 이하이거나 H5 Primary 차이가 0 이상이면 각각 폐기한다. Secondary의 반복성, 군내 겹침, 30거래일 사건 묶음과 종목별 차이를 같이 보며, 우측 검열을 실패군에 넣지 않는다. Holdout 검사 전에 종목 선정 규칙과 자료 품질 기준을 별도로 고정한다.

## 18. Holdout Readiness

H4/H5 문구, 위 Feature·창, 기존 Outcome 정의, Primary·Secondary·반증 방향은 **이번 문서로 사전 고정**했다. 다만 두 가설이 Development Set에서 `WEAK`이고 State 우위·역방향 Persistence가 있어 **Holdout 실행 준비는 미완료**다. 우선 사용자 검토로 이 좁은 가설을 그대로 반증할지, 별도 버전으로 재설계할지 결정해야 한다. 어느 경우든 Holdout Universe의 선정·자료 품질 규칙을 결과 확인 전에 별도로 고정한다. Holdout 종목은 아직 선정하거나 열지 않았다.

## 19. Limitations

6종목 선정·생존 편향, 한국/미국 데이터 기간과 원천 차이, 조정가격·기업행동 불확실성, 중첩 사건과 공유 시장 국면, 사후 Outcome으로 나눈 군, 작은 Winter 12건을 고려한다. 52주 지표는 Winter군 1건에서 결측이다. 52주 고점이 rolling 창에서 빠지면 drawdown Velocity가 순수 가격 속도와 다르다. `recovery_persistence_days`는 MA50 위 연속일일 뿐 진정한 Higher Low 구조가 아니다. 동일 MA 기반 v1 사건과 Feature 사이에는 구성상 의존성이 있다. Cohen's d는 기술적 효과크기이고 독립성/유의성 주장이 아니다. 동일 당일 종가 Feature는 당일 장중 주문에 사용할 수 없다.

## 20. Next Step

결과를 검토한 뒤 Holdout **선정 규칙을 먼저** 문서화하고 H4/H5를 폐기할 준비를 갖춘다. v1 Phase, Strategy, Capital Rotation, UI, 임계값 및 가중 점수는 변경하지 않는다.
