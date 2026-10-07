# ZERO MARKET LAB V2 Research Workstation

현재 사용 화면은 `scripts/run_research_ui.py`가 제공하는 `tiger_etf_v2/`이다.
로컬에서는 실제 TIGER 360750 OHLCV를 사용하며, `ZML_DATA_MODE=PUBLIC_DEMO`에서는
별도 생성한 **가상 ETF·완전 합성 OHLCV**를 같은 Engine과 UI로 탐색한다.
Public Demo의 가격과 거래 결과는 실제 TIGER/시장 성과가 아니다.

로컬 실행은 `experiments/tiger_etf_v2/build_chart.py`와 `build_simulation.py`로
payload를 만든 뒤 `scripts/run_research_ui.py`를 사용한다. Public Demo는
`scripts/build_public_demo.py`가 원본 시세 파일 없이 payload를 만든다.

아래 8061 명령은 초기 정적 차트 foundation만 재현하는 이전 실험 절차다.

This isolated prototype renders validated, unadjusted daily OHLCV for KRX
`360750` with Lightweight Charts. It does not invoke Python when the user pans,
zooms, moves the crosshair, toggles layers, or changes a quick range.

```powershell
.venv\Scripts\python.exe scripts\fetch_tiger_360750.py --start 2020-08-01
.venv\Scripts\python.exe experiments\tiger_etf_v2\build_chart.py
.venv\Scripts\python.exe -m http.server 8061 --directory experiments\tiger_etf_v2
```

Open `http://127.0.0.1:8061/`. The payload builder fails before rendering if
OHLCV validation fails. No synthetic bar, forward-fill, strategy, or execution
assumption is present in this foundation.
