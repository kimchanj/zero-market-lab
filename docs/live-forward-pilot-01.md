# STEP 6 — First LIVE_FORWARD Pilot 01

상위 기준: [ZERO MARKET LAB META](../ZERO_MARKET_LAB_META.md) · [Paper Trading MVP](paper-trading-mvp.md). 이 로그는 날짜별 확인 사실을 누적한다. `HISTORICAL_REPLAY` 결과를 `PAPER_FORWARD`로 바꾸어 쓰지 않는다.

## Pilot contract / current state

| Field | 2026-10-11 현재 |
| --- | --- |
| Git baseline | `d1ce2f2cd48693727644a443688c06b95c05fc48` (`main`, 로컬 Checkpoint) |
| Pilot ID | `live-forward-s1-000660-v1` **예정 이름; 계좌 미생성** |
| Status | `LIVE_FORWARD_WAITING_FOR_NEW_BAR` — STEP 6B 재조회 후에도 신규 확정 바 없음 |
| Asset | 사용자가 선택한 `000660` SK하이닉스 · KRX · KRW |
| Strategy | S1 Fixed Take Profit · 신규 진입 당일 TP 불인정 · Phase는 Context 전용 |
| Capital | 사용자 지정 **10,000,000 KRW**. 계좌는 아직 생성하지 않아 설정 해시는 없음 |
| Entry / TP | 현재 코드 기본값 `Open −1%` / 진입가 `+5%`; 비용 설정과 함께 계좌 생성 전 확정 필요 |
| Research cost assumptions | 매수·매도 수수료 각각 0.015%, 매도세 0%, 슬리피지 0% (실제 계좌 비용 아님) |
| Version candidates | Strategy `strategy-family-s1-v1`, Phase `PRICE_PHASE_V1` / rule hash `c89aba473399951fca616de0a34d8b0d0745d55cbb585e101f8f3822457be81f`, Fee `paper-research-cost-v1`, Fill `daily-ohlcv-s1-v1` |
| Account config hash | 없음 — 아직 계좌를 생성하지 않음 |
| Start / first as-of / first Decision | 없음 — 계좌·Decision·Order·Execution·Journal 미생성 |
| Runtime DB | 예정: Git 제외 `artifacts/paper_trading/paper.sqlite3`; Pilot 계좌는 아직 없음 |

## Daily observation log (append-only)

### 2026-10-11 KST — 준비 점검, Forward 관측 없음

- 기존 `scripts/fetch_korea_universe.py --symbols 000660 --limit 1500`으로 Daum Finance 보조 공급자의 새 로컬 스냅샷을 받았다. 최초 네트워크 제한 환경에서 `ProxyError`가 났고 네트워크 권한이 있는 재시도에서 성공했다. 저장 위치는 Git 제외 `data/processed/korea_000660/20261011T135926Z/`이다.
- 공급자 수신시각 `2026-10-11T13:59:26.996472+00:00`, 정책 `adjusted=false` / `UNADJUSTED`. 1,500행, 2020-08-24~**2026-10-08**. 날짜 중복 0, 오름차순, OHLCV 검증 통과. 이전 2026-10-08 스냅샷과 CSV SHA-256이 동일하므로 기존 가격 이력의 변경은 관찰되지 않았다.
- 마지막 종가 **1,686,000 KRW**, 1주와 기본 매수 수수료 0.015%를 포함한 필요 현금 **1,686,253 KRW**. 500,000 KRW 예시 자본은 1주 매수가 불가능하다. 다른 종목·자본으로 임의 변경하지 않는다.
- 10월 9일은 한글날 공휴일, 10~11일은 주말이다. [KRX 거래일/공휴일 규칙](https://global.krx.co.kr/contents/GLB/06/0602/0602020204/GLB0602020204T1.jsp)과 [2026년 공휴일 표](https://www.bok.or.kr/eng/main/contents.do?menuNo=400373)를 참고하되, 실제 다음 거래일과 완성 일봉은 공급자 응답으로 다시 확인한다. 10월 12일은 **예상되는 다음 KRX 세션**이지 이미 확보된 Forward 데이터가 아니다.
- 현재 마지막 관측일은 이 Pilot 계좌 생성 시점 이전이다. `LIVE_FORWARD`는 계좌 생성 후 시장 관측일과 그 관측일 이후의 새 공급자 refresh를 요구한다. 따라서 과거 10월 8일 바를 첫 Forward Decision으로 처리하지 않았다.
- `LIVE_FORWARD` 계좌, 첫 Phase snapshot, S1 신호, pending order, Journal 및 S0 snapshot은 모두 **없다**. 수익 또는 성과를 기록하지 않는다.

### 2026-10-11 KST — 사용자 자본 지정

- 사용자가 첫 모의투자금을 **10,000,000 KRW**로 지정했다. 이 금액은 직전 확정 종가 기준 1주 필요자금 1,686,253 KRW를 초과한다. 같은 종가에서 기본 매수 수수료를 포함한 단순 매수 가능 수량은 **5주**(5주 필요 8,431,265 KRW; 6주 필요 10,117,517 KRW)다. 실제 S1 체결 수량은 미래 거래일의 시가·지정가·비용으로 다시 계산되므로 5주로 고정하지 않는다.
- 자산·자본은 지정됐지만 새 Forward 관측일과 그 이후의 공급자 refresh가 없어 계좌·Decision·Journal은 여전히 생성하지 않았다. 현재 연구 비용 기본값은 코드에서 읽은 **후보 설정**이며 계좌 hash는 아직 없다.

### 2026-10-11 KST — 수집 이력 연속성 수정, Pilot 시작 전 검토 대기

- 기존 수집기는 공급자의 최근 1,500행을 매번 새 전체 스냅샷으로 저장했다. 신규 거래일이 들어오면 가장 오래된 확정 행이 빠져 Paper의 과거 전체 이력 해시가 다음 날 불일치할 수 있었다.
- `fetch_korea_universe.py`는 이제 직전 로컬 스냅샷과 신규 공급자 응답의 날짜·OHLCV·거래대금을 대조하고, 변경 또는 누락된 과거 행이 있으면 저장 전에 오류 상태와 비영(非零) 종료코드로 중단한다. 검증된 새 행만 이어 붙이고 이전의 오래된 행을 유지한다. 기존 가격 이력 또는 Journal을 다시 계산하지 않는다.
- rolling window의 정상 연장과 겹침 없음·날짜 누락·과거 값 수정 거부를 별도 단위 테스트로 확인했다. **실제 신규 일봉으로 이어 붙이는 운영 검증은 아직 불가능**하므로 검토 후 다음 확정 거래일에 재확인한다. 계좌·Decision·Journal은 여전히 없다.
- 최종 회귀 검증: Python `276 passed`, 기존 JavaScript `9 passed`, `pip check`·`node --check`·`git diff --check` 통과. Windows 샌드박스의 pytest 임시 폴더 접근 제한 및 Node child-process 제한은 권한 있는 동일 명령 재실행에서 해소했다. Commit/Push는 하지 않았다.

### 2026-10-11 KST — STEP 6A 수집 안전성 Audit

- Audit 기준 HEAD는 `d1ce2f2cd48693727644a443688c06b95c05fc48`이다. 수집기·단위 테스트·이 Pilot 로그·이어받기 문서만 STEP 6A 범위로 검토했다. 계좌와 첫 Decision은 만들지 않았다.
- rolling window의 오래된 행은 유지하고, 겹치는 날짜의 누락 또는 가격·거래량·거래대금 변경은 `DATA_HISTORY_CHANGED`로 실패한다. 수집 실패는 종료코드 1이다. 새 스냅샷은 검증 후 메타데이터와 임시 CSV를 별도 폴더에 쓴 뒤 완성된 CSV만 공개하므로, 실패 시 기존 로컬 스냅샷은 손상되지 않는다.
- 동일일 데이터 재조회에서는 이전·새 행 모두 1,500, 추가 행 **0**이며 마지막 확정일은 여전히 **2026-10-08**이었다. 로컬 누적 CSV SHA-256은 `37d90ae41de73235b7d23df5bdb8a05d77159fb7ba4a6ae06b8ccf236aad796e`로 메타데이터의 `history_sha256`과 일치했다. 새 확정 일봉은 발견되지 않았다.
- 원천은 계속 `UNADJUSTED` Daum 보조 공급자다. 기업행동에 따른 과거 바 수정이 나타나면 자동 조정 또는 Journal 재계산 없이 중단하며 별도 정정 검토로 넘긴다. 거래소 달력으로 신규 세션 누락을 자동 판별하지 못하는 한계도 유지한다.
- 지정 Pilot 자산은 `000660` SK하이닉스, 시작 예정 자본은 **10,000,000 KRW**다. S1/Phase/비용/체결 버전은 후보 그대로이며 LIVE_FORWARD 계좌 설정 해시는 아직 없다. STEP 6B는 새 확정 관측일 및 연속성 검증 후 별도로 시작한다.
- STEP 6A 전체 검증: Python `278 passed`, JavaScript `9 passed`; `pip check`, `node --check`, `git diff --check` 통과. 새로 추가한 6개 수집 안전성 테스트에는 동일 재조회, rolling append, 겹침 누락·수정 거부, 실패 종료코드가 포함된다.

### 2026-10-11 KST — STEP 6B 첫 계좌 시작 조건 재확인

- 시작 기준은 안전성 Checkpoint `b88503c2d55bc2c5bf5dac6ec2dfc610da69263c`, clean `main`, `origin/main` 대비 ahead 2 / behind 0이다. 전략·Phase·비용·체결 코드는 변경하지 않았다.
- 동일 Daum Finance 보조 공급자에서 `000660`을 `adjusted=false`로 다시 수집했다. 이전 최신일과 새 최신일은 모두 **2026-10-08**, 이전/새 누적 행은 각각 1,500, 추가 행 **0**, 이력 검증 `PASS`다. 새 스냅샷은 Git 제외 `data/processed/korea_000660/20261011T142501Z/`에 있다. 저장된 누적 CSV SHA-256 `37d90ae41de73235b7d23df5bdb8a05d77159fb7ba4a6ae06b8ccf236aad796e`는 메타데이터와 일치한다.
- 2026-10-11은 일요일이며 2026-10-08 뒤의 **새 확정 거래일 일봉이 없다**. STEP 6B의 사전 조건이 성립하지 않아 `LIVE_FORWARD_WAITING_FOR_NEW_BAR`로 대기한다. 10월 8일 역사 바를 Forward로 재사용하지 않는다.
- 예정 Pilot ID `live-forward-s1-000660-v1`, 자산 `000660` SK하이닉스, 모의자본 **10,000,000 KRW**. `S1_FIXED_TAKE_PROFIT` / `strategy-family-s1-v1`, `PRICE_PHASE_V1` Context only / hash `c89aba473399951fca616de0a34d8b0d0745d55cbb585e101f8f3822457be81f`, `paper-research-cost-v1`, `daily-ohlcv-s1-v1`의 구현·문서 일치를 확인했다. Entry `Open −1%`, TP `+5%`, 매수/매도 수수료 각 0.015%, 세율·슬리피지 0은 **계좌 생성 전 후보 설정**으로 남는다.
- 런타임 `artifacts/paper_trading/paper.sqlite3`는 아직 없다. Account, config hash, start/as-of date, 첫 Phase/Signal/Decision/Order/Journal, S0 snapshot 및 손익은 모두 **미생성·미산출**이다. 첫날 상태와 미래 체결을 꾸며 기록하지 않는다.
- STEP 6B 검증: 전체 Python `278 passed`, 기존 JavaScript `9 passed`, `pip check`와 JavaScript 구문 검사 통과. 문서만 갱신했으며 자동 commit/push는 하지 않는다.
- **STEP 6B 절차와 현재 엔진의 시점 계약 충돌:** 지시문은 새 확정 바를 확인한 뒤 계좌를 만들고 그 바를 첫 `as_of`로 처리하도록 한다. 현 `run_day()`는 관측일이 **계좌 생성 현지 날짜보다 늦어야** 하고 공급자 재조회도 관측일 다음 현지 날짜 이후여야 한다. 따라서 바를 본 뒤 만든 계좌로 이미 끝난 그 바를 첫 LIVE_FORWARD 날짜로 처리할 수 없다. 새 바가 없는 이번 실행에서는 계좌를 만들지 않았으며, 다음 시도 전에 사용자 검토로 계좌 생성 순서를 확정해야 한다. 엔진·전략 규칙은 바꾸지 않았다.

## Next market-day manual procedure

1. 이번 수집 연속성 수정과 Pilot 조건에 대한 사용자 검토 후, 지정 자본 10,000,000 KRW와 코드의 비용 기본값을 계좌 생성 직전 다시 확인하고 자산·버전·설정 해시·1주 매수 가능성을 검증한다. 현재의 역사 데이터는 지표 warm-up에만 사용한다.
2. 실제 다음 KRX 거래일이 끝난 **뒤**, 기존 수집 스크립트로 새 스냅샷을 받는다. 수집 당일 바는 미완성일 수 있으므로 보수적인 현 `LIVE_FORWARD` 계약대로 **관측일 다음 현지 날짜의 refresh**로 확정한다.
3. 공급자·관측일·OHLCV·중복·오름차순·조정 정책·과거 바 해시를 확인한다. 기존 원천 바가 바뀌면 silent recompute 없이 중단한다. 외부 거래소 달력과의 자동 누락 세션 대조는 아직 없으므로 공급자의 날짜 누락도 수동 검토한다.
4. 그 날짜가 계좌 생성 이후의 최초 실제 관측일일 때만 `run --as-of`를 한 번 실행한다. 오늘 종가 Decision은 오늘 시가/저가에 체결하지 않는다. `status`와 `journal`에서 Phase Context, S1 Decision, Cash/Position/Equity, S0, 버전·provenance를 검증한다.
5. 같은 날짜 재실행에서 이벤트 수가 늘지 않는지 확인하고, 새 프로세스로 재시작하여 상태를 조회한다. 다음 거래일까지 자동 실행하지 않는다.

## Known limitations

Daum Finance는 보조 공급자이며 수정주가·기업행동·배당 및 재배포 조건의 완전 검증을 마치지 않았다. 공급자 요청은 최대 1,500행 rolling window이지만 로컬 스냅샷은 검증 후 과거 확정 행을 보존해 누적한다. 겹치는 과거 값이 바뀌거나 기존 최신 행과 연결되지 않으면 자동 정정 없이 중단한다. 거래소 달력 기준 신규 세션 누락 판별은 아직 수동 검토가 필요하며, 실제 다음 거래일의 append 동작은 아직 관찰하지 못했다.
