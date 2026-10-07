# Public Deployment / Data Safety

## 두 실행 모드

`LOCAL_RESEARCH`(기본)은 `experiments/tiger_etf_v2/`의 로컬 생성 payload와
`data/news/official_context_catalog.json`을 읽는다. 실제 TIGER 360750 시세는
`scripts/fetch_tiger_360750.py`가 Daum Finance의
`https://finance.daum.net/api/charts/A360750/days?limit=2000&adjusted=false`에서
2026-10-06에 수집한 비수정 일봉 1,508행(2020-08-07~2026-10-06)이며,
`data/raw/tiger_360750/`, `data/processed/tiger_360750/` 및 생성 JS/JSON에 저장된다.
이 파일들은 Git에서 제외한다. `data/provenance/`에는 출처·해시·행수 등 메타데이터만 기록한다.

`PUBLIC_DEMO`는 `scripts/build_public_demo.py`가 수학 함수로 결정적으로 생성한
평일 합성 OHLCV를 `experiments/public_demo/`에 기록한다. 이 빌더는 실제 시세 파일을
읽거나 외부 API를 호출하지 않는다. Public API는 해당 bundle만 로드하고, 브라우저에
합성 데이터 배지를 표시한다. 뉴스 카탈로그는 빈 값으로 제공해 합성 가격을 실제 사건과
연결하지 않는다. 가격 Snapshot·연구 프롬프트는 사용할 수 있다. 두 모드 모두 동일한
`FrameOHLCVProvider`와 시뮬레이션 Engine을 사용한다.

## 서버와 호스팅

Local Research는 기존 `127.0.0.1:8062`로 실행한다. Render Blueprint의 Public Demo는
`ZML_DATA_MODE=PUBLIC_DEMO`, `PORT`, `0.0.0.0`, `/healthz`를 사용한다. Build 단계에서
합성 payload를 생성하고, runtime에는 pandas와 표준 라이브러리 기반 Python 서버가
`/api/simulate`, `/api/research`, 허용된 정적 asset만 제공한다. 공개 URL은 실제 배포와
외부 smoke test가 끝난 뒤에만 README와 GitHub Website에 기재한다.

Render 무료 서비스는 유휴 중지와 임시 파일시스템 제약이 있다. 데이터베이스는 필요하지
않지만 서버의 최근 run cache는 재시작 시 사라진다. Demo 데이터도 build 시점까지의
합성 관측이며 실시간 업데이트가 아니다. 사용자가 새 시뮬레이션을 실행하면 Engine이
선택 기간을 다시 계산한다.

## 공개 전 확인과 남은 출처 조사

- Daum Finance 시세의 원천 제공자, 이용조건과 역사적 OHLCV 재배포 허용 범위를 확인한다.
  현재는 권한 미확인이므로 원본 시세를 저장소나 Public Hosting asset에 포함하지 않는다.
- 제3자 시세를 공개하려면 명시적 재배포·웹 표시 허용 데이터 공급자로 교체한다.
  그렇지 않으면 Public Demo는 합성 데이터로 유지한다.
- `data/raw/`, `data/processed/`, `experiments/tiger_etf_v2/tiger_data.js`,
  `simulation_data.js`, `research_input.json`, `experiments/public_demo/`, `.env`의 Git
  제외 상태와 Public asset allowlist를 확인한다.
- Public URL에서 차트·거래량·Hover·Zoom/Pan·시뮬레이션·Ledger·Quick Period·
  Accordion·연구/뉴스 제한 안내·모바일 레이아웃을 smoke test한다.
