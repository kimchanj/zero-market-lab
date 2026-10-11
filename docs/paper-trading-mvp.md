# Paper Trading MVP — STEP 5 Forward Validation Foundation

상위 기준: [ZERO_MARKET_LAB_META.md](../ZERO_MARKET_LAB_META.md). 역사적 백테스트·Rolling·Phase 연구 결과는 동결한다. 이 MVP는 **한 계좌·한 자산·S1**의 일별 모의 계좌를 날짜순으로 쌓는 로컬 CLI다. 실제 주문, Broker 연결, 종목 추천, Strategy 최적화는 없다. 첫 실제 Pilot 자산은 사용자가 직접 선택한다.

## Architecture / Data Model

`LocalOHLCVCatalog → prefix-limited daily bar → previous pending order execution → PRICE_PHASE_V1 as-of snapshot → close decision → SQLite append` 순서다. 계좌 설정과 `DECISION`, `ORDER`, `EXECUTION`, `JOURNAL`, `DATA_CORRECTION` 이벤트는 `src/zero_market_lab/paper_trading/engine.py`에서 관리한다. `schema_meta.version=1`; 계좌와 이벤트 테이블에는 UPDATE/DELETE 거부 트리거가 있다. 날짜·계좌·종류의 unique 제약과 하루 전체 SQLite 트랜잭션으로 중복·중간 상태를 막는다. Cash, 단일 Position 수량·매입가·취득원가, 실현/미실현 P&L, S0 잔고는 **마지막 Journal의 파생 상태**다. 별도 갱신 가능한 Position 테이블은 두지 않아 불일치 원천을 줄였다.

첫 계좌는 전략 ID `S1_FIXED_TAKE_PROFIT`, `strategy-family-s1-v1`, `daily-ohlcv-s1-v1`, `paper-research-cost-v1`, `PRICE_PHASE_V1` 및 Phase 설정 해시와 진입·익절·비용 수치를 JSON + SHA-256으로 고정한다. 중도 변경은 금지하며 새로운 설정은 별도 계좌를 만든다. 기존 [Paper 계약](paper-trading-foundation.md)의 S1 진입 지정가, KRX 가격대별 호가단위, 매수 가능 정수주·비용 계산을 재사용한다. 수수료·세율은 **계좌 설정의 연구 가정**이다.

## Daily Workflow / Decision Timing

계좌 첫 관측일에는 S0 기준선을 같은 시작자금·첫 시가로 매수하고, Paper S1은 **첫 종가에만** 다음 거래일 BUY 조건 주문을 만든다. 이후 매일 다음 순서를 지킨다.

1. 새 일별 OHLCV의 순서·중복·가격 유효성, 관측일과 현재 날짜, 직전 누적 가격 이력 해시를 확인한다.
2. 전일 이전에 만든 SELL 목표가 주문 또는 직전 거래일 BUY 주문을 **오늘 OHLC**로 평가한다. BUY 가격은 오늘 시가의 사전 고정 오프셋으로 계산하고 당일 저가가 닿을 때만 체결한다. BUY 당일 고가가 목표가를 넘어도 그날 TP는 인정하지 않는다. 기존 포지션의 익절은 목표가 체결이며 갭 개선 체결은 인정하지 않는다.
3. 수수료·세금·슬리피지 가정을 반영해 Cash/Position을 갱신하고 당일 종가로 평가한다. `equity = cash + qty×close`, `total P/L = equity−initial capital`, 열린 포지션은 취득 비용까지 포함한 미실현손익으로 분리한다.
4. **오늘 종가 확정 후** 기존 `PRICE_PHASE_V1`의 해당 날짜 스냅샷을 Context로만 보존한다. Phase는 자동 BUY/SELL 조건이 아니다. S1은 보유 시 목표 SELL 또는 HOLD, 미보유 시 다음 날 BUY 또는 자금 부족 CASH를 기록한다.
5. 결정·주문·체결·Journal을 하나의 트랜잭션에 append한다. 동일 날짜 재실행은 원본 Journal을 반환하고 새 이벤트를 만들지 않는다.

`BUY`는 다음 세션 조건 주문, `SELL`은 다음 세션 이후 유효한 익절 목표 주문, `HOLD`는 기존 목표 주문 유지, `CASH`는 포지션 없이 현재 종가의 1주 추정 필요자금도 없는 상태다. 주문 의사결정과 실제 체결은 별도 사건이다. 진입 주문의 다음 거래일 저가가 닿았으나 현금으로 정수 1주를 살 수 없으면 `BUY_BLOCKED_INSUFFICIENT_CAPITAL`을 Journal에 남긴다. 이미 열려 있는 주문의 자금 부족과 현재 종가 기준 `NOT_AFFORDABLE`은 구분한다.

## Persistence / Audit / Correction

기본 DB는 Git 제외 `artifacts/paper_trading/paper.sqlite3`다. SQLite 파일을 백업할 때는 쓰기 중 작업을 중단하고 SQLite Backup API 또는 checkpoint가 반영된 스냅샷을 사용해야 한다. Journal은 재시작 후 DB에서 복원한다. 각 행에 출처, 공급자 다운로드 시각, 조정 정책, 당일 바 SHA-256, 당시까지 전체 바 SHA-256, 전략·Phase·비용·체결 버전과 설정 해시를 기록한다. 이전 가격 이력 중 **하루라도** 바뀌면 다음 실행을 중단한다. `correction` 명령은 정정 사유만 append하며 기존 결정·체결을 변경하거나 자동 재개하지 않는다. 정정 영향 분석과 새 계좌/버전 여부는 별도 검토가 필요하다.

## Replay vs Live Forward / as-of Protection

`HISTORICAL_REPLAY`는 과거 데이터를 하루씩 재생해 엔진과 시점 계약을 검사하는 **역사 재생**이다. `PAPER_FORWARD` 성과로 표시하지 않는다. `LIVE_FORWARD`는 계좌 생성일 이후의 시장 관측일만 받고, 공급자 `retrieved_at`이 계좌 생성 시각 이후이면서 **시장 현지 날짜로 관측일 다음 날 이후**인 새 refresh를 요구한다. 당일 장중 미완성 바를 종가로 오인하지 않는 보수적 제한이다. 두 모드 모두 현재 시장 현지 날짜보다 미래 `as_of`를 거부한다. 데이터가 없거나 휴장일이면 가짜 바·Journal을 만들지 않는다. 처음 처리하는 날부터 관측 날짜순으로 한 거래일도 건너뛰지 않는다. 계산 전 가격 프레임은 `as_of_date`까지 절단한다. 현 공급자 데이터의 최종일은 한국 2026-10-08, 미국 2026-10-07이므로 2026-10-10 기준 새 LIVE 관측이 아직 없어 실제 Forward Pilot 실행은 보류다.

## CLI / How to Start a Pilot

PowerShell 예시. 아래 005930은 **문법 설명용**이며 추천·Pilot 선정이 아니다. `--db`는 하위 명령 앞에 둔다.

```powershell
.\.venv\Scripts\python.exe scripts/run_paper_trading.py create --name example-replay --symbol 005930 --capital 500000 --start-date 2026-10-06 --mode HISTORICAL_REPLAY
.\.venv\Scripts\python.exe scripts/run_paper_trading.py run --account example-replay --as-of 2026-10-06
.\.venv\Scripts\python.exe scripts/run_paper_trading.py status --account example-replay
.\.venv\Scripts\python.exe scripts/run_paper_trading.py journal --account example-replay
```

사용자가 종목·자금·전략 가정과 [후보 점검표](paper-trading-foundation.md)를 검토한 후 첫 `LIVE_FORWARD` 계좌를 만든다. 생성 직후 기존 역사 시세로 첫날을 채우지 않는다. 새 거래일의 실제 데이터 refresh가 확인되면 그 날짜만 `run --as-of YYYY-MM-DD`로 처리한다. 현재는 새 공급자·자동 refresh·예약 실행을 추가하지 않았다.

CLI 역사 재생 검증에서는 **Pilot 선정이 아닌 예시**로 삼성전자 2026-10-06~08의 기존 로컬 시세를 사용했다. 10-06 종가 BUY 조건 주문 → 10-07 지정가 미도달 → 10-08 다음 날 주문 1주 체결이 기록됐다. 10-08 현재 Cash 233,460원, 보유 1주, 총자산 496,460원, 미실현손익 −3,540원이었다. 세 행 모두 `HISTORICAL_REPLAY`이며 미래 성과가 아니다. 같은 날짜 재실행·재시작 후 조회는 원본 기록을 유지한다.

## Known Limitations / Next Step

- S1만 연결했다. S2/S7, 다중 자산, 자동 UI, 브로커 주문, 실제 세금 자동 추정은 범위 밖이다. CLI 검증 후 사용자가 Pilot을 고르면 추가한다.
- 정정 이벤트는 감사 기록일 뿐 자동 재계산·마이그레이션이 아니다. 과거 바가 바뀐 계좌는 fail-closed 상태로 남는다.
- 장중 호가·체결량·순서 정보가 없어 일별 OHLC 보수적 체결 가정이며 실제 주문 체결을 보장하지 않는다.
- S0와 S1은 동일 첫 관측일/자금이지만 S0는 첫 시가 진입, S1은 첫 종가 결정 후 다음 거래일부터 진입 가능하다. 이는 사전 정의한 시점 차이이지 성과 우열의 근거가 아니다.
- 당일 종가 Phase는 다음 거래일 의사결정 Context로만 쓰고 Phase가 S1 신호를 생성하지 않는다. 배당·기업행동·환율·시세 정정의 완전한 재현도 아직 없다.
