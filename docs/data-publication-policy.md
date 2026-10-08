# Data Publication Policy

ZERO MARKET LAB의 현재 공식 프로젝트 URL은
https://github.com/kimchanj/zero-market-lab 이다. 현재 V2는 Python 서버의
`/api/simulate`, `/api/research`를 사용하는 로컬 연구 앱이다. 저장소 URL은 실행 가능한
웹 앱 주소가 아니다. 별도 GitHub Pages 읽기 전용 데모에는 합성 시세와 사전 계산
결과만 게시하며, Python API를 사용하는 새 시뮬레이션·뉴스 조회는 로컬에만 남긴다.

## 로컬 실행 모드

`LOCAL_RESEARCH`(기본)는 `experiments/tiger_etf_v2/`의 로컬 생성 payload와
`data/news/official_context_catalog.json`을 읽는다. 실제 TIGER 360750 시세는
`scripts/fetch_tiger_360750.py`가 Daum Finance에서 2026-10-06에 수집한 비수정 일봉
1,508행(2020-08-07~2026-10-06)이다. 원본과 가공 데이터는 `data/raw/tiger_360750/`,
`data/processed/tiger_360750/` 및 로컬 생성 JS/JSON에 저장하고 Git에서 제외한다.
`data/provenance/`에는 출처·해시·행수 등 메타데이터만 기록한다.

`PUBLIC_DEMO`는 `scripts/build_public_demo.py`가 수학 함수로 결정적으로 생성한
합성 OHLCV를 `experiments/public_demo/`에 기록하는 선택적 **로컬** 모드다. 빌더는
실제 시세 파일을 읽거나 외부 API를 호출하지 않는다. 화면에는 합성 데이터 배지를 표시하며
뉴스 카탈로그는 비워 합성 가격을 실제 사건과 연결하지 않는다. 두 모드 모두 같은
`FrameOHLCVProvider`와 시뮬레이션 Engine을 사용하고 서버는 loopback 주소에만 바인딩한다.

## 데이터 공개 경계

- Daum Finance 시세의 원천 제공자, 이용조건과 역사적 OHLCV 재배포 허용 범위는 아직
  확인되지 않았다. 따라서 실제 가격이나 생성된 시세 payload를 저장소에 포함하지 않는다.
- `data/raw/`, `data/processed/`, `experiments/tiger_etf_v2/tiger_data.js`,
  `simulation_data.js`, `research_input.json`, `experiments/public_demo/`, `.env`는
  Git 제외 대상이다.
- 합성 데이터는 실제 TIGER 가격·수익률·시장 사건을 재현하지 않으며 투자 판단 자료로
  사용해서는 안 된다.

GitHub Pages 산출물은 `scripts/build_pages_demo.py`가 별도 생성한다. 생성물은
`artifacts/`에 두어 Git 추적에서 제외하고, Actions가 실행할 때 합성 데이터만 만들어
Pages artifact로 업로드한다. 실제 데이터 파일이나 `research_input.json`은 게시하지 않는다.
