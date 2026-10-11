# Historical Research → Forward Validation 기반 — Milestone Checkpoint

상위 기준: [ZERO MARKET LAB META](../ZERO_MARKET_LAB_META.md). 이 문서는 연구 결과와 현재 구현 상태를 요약한다. 투자 권고나 실거래 성과 주장이 아니다.

## Goal and built foundation

6종목 개발 표본에서 전략군 S0~S7(하위 S6-A/B), S1-TF/S2-TF, CASH·비용·정수주 체결을 비교하고, 독립적인 `PRICE_PHASE_V1` 및 연구용 Parent/Child·전이 분석으로 가설을 공격했다. [전략 설계](strategy-research-framework.md), [Phase v1 결과](fecm-market-phase-engine-v1-results.md), [실패 분석](fecm-market-phase-v1-failure-analysis.md), [다중 시간축](fecm-multi-timeframe-phase-research.md), [전이 분석](fecm-transition-dynamics-research.md)에 증거와 한계를 남겼다.

## What we learned / negative evidence

S1의 완료 거래 실현손익만으로는 미청산 손실과 현금 고착이 가려진다. CASH는 명시적 전략 상태이며 총자산·미실현손익·S0와 함께 평가해야 한다. Phase v1의 Spring 후보 75건 중 성공 16건, False Spring 59건(78.7%)이었다. Autumn 87건 중 Winter 12건, Summer 재개 67건, 미해결 7건, 검열 1건으로 과다 경고 위험이 있다. Parent/Child는 상태의 시간축 표현을 개선했으나 성공/실패 판별력이나 투자 우위는 입증하지 못했다. 전이 가설 H4/H5는 모두 **WEAK**이고 일부 State 특징이 Velocity보다 강했다. 특정 개발 표본의 역사 결과를 더 맞추기보다 미래 관측으로 검증할 필요가 있다.

## Frozen baselines and Paper Trading MVP

`PRICE_PHASE_V1` 규칙과 6개 일별 라벨 CSV 해시를 동결한다. Spring 75/16/59, Autumn 87/12/67/7/1 집계와 반증 사례를 유지하며 Holdout·v1.1·전략 연결은 아직 하지 않는다. [Paper Trading MVP](paper-trading-mvp.md)는 별도 SQLite 계좌와 의사결정·주문·체결·일별 Journal 이벤트를 사용한다. 포지션은 마지막 Journal에서 복원하며 별도 갱신형 테이블이 없다. 전략·Phase·비용·체결 버전과 설정 해시를 고정한다. T일 종가 Decision은 T+1 이후에만 체결 검토하고, append-only·재실행 멱등성·재시작 복원·S0 동일 자본/자산/시작일 기준선을 검증했다. `HISTORICAL_REPLAY`와 `PAPER_FORWARD` 증거 유형을 분리한다. 삼성전자 2026-10-06~08 재생은 **역사 재생**이며 실제 미래 검증이 아니다.

## Not proven and next step

수익 가능한 전략, Phase 예측력, Multi-Timeframe 투자 우위, H4/H5의 일반성은 입증되지 않았다. 실제 Forward 수익과 LIVE Pilot 관측은 **없다**. 현재 데이터·상품행동·배당·세금 모델에도 한계가 있다. 다음 공식 단계는 **STEP 6 — First LIVE_FORWARD Pilot**이다. 사용자와 Pilot 자산·자본·비용 가정을 확정한 후 새 데이터 refresh, 계좌 생성, 최초 미래 관측일 처리, Decision 동결, Journal append, S0 비교를 수행한다. 이 문서는 STEP 6 실행을 뜻하지 않는다.

## Git checkpoint

감사 시점 기준 `main` HEAD는 `ee62796e198b6c1a4dd148908c3a35d2405ba797`이다. 이번 Milestone 구현·연구 문서는 아직 미커밋이며, 사용자 검토 전 commit/push하지 않는다. `artifacts/`, `data/raw/`, `data/processed/`, SQLite runtime DB와 캐시는 체크포인트에서 제외한다.
