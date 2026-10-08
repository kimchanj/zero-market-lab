"""Local-only research API plus existing chart assets. No outbound news requests."""
from __future__ import annotations
import argparse
from datetime import date
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
from collections import OrderedDict
from threading import Lock
from urllib.parse import urlsplit, parse_qs

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))
from zero_market_lab.research.news import CatalogNewsProvider
from zero_market_lab.research.snapshot import build_snapshot, markdown
from zero_market_lab.simulator.service import run_simulation
from scripts.run_samsung_family import build_report
from scripts.run_asset_discovery import build_report as build_discovery_report


def load_context(mode="LOCAL_RESEARCH", public_dir: Path | None = None):
    if mode not in {"LOCAL_RESEARCH", "PUBLIC_DEMO"}:
        raise ValueError("ZML_DATA_MODE must be LOCAL_RESEARCH or PUBLIC_DEMO")
    folder = (public_dir or ROOT / "experiments/public_demo") if mode == "PUBLIC_DEMO" else ROOT / "experiments/tiger_etf_v2"
    raw = (folder / "research_input.json").read_bytes()
    if mode == "PUBLIC_DEMO":
        bundle = json.loads(raw)
        if bundle["simulation"]["provenance"].get("data_mode") != "PUBLIC_DEMO" or not bundle["simulation"]["provenance"].get("synthetic"):
            raise ValueError("Public mode requires an explicitly synthetic demo bundle")
        return bundle, CatalogNewsProvider([]), sha256(raw).hexdigest()
    catalog = ROOT / "data/news/official_context_catalog.json"
    return json.loads(raw), CatalogNewsProvider.from_file(catalog), sha256(raw + catalog.read_bytes()).hexdigest()


def research_response(context, params):
    bundle, provider, fingerprint = context
    packet = build_snapshot(bundle["simulation"], bundle["market"], provider,
                            date.fromisoformat(params["start"]), date.fromisoformat(params["end"]),
                            mode=params.get("mode", "REPLAY_MODE"), hypothesis=params.get("hypothesis", ""),
                            source_hash=fingerprint)
    return {"snapshot": packet, "markdown": markdown(packet),
            "validation": markdown(packet, "validation"), "concept": markdown(packet, "concept")}


def handler_for(context, mode="LOCAL_RESEARCH", public_dir: Path | None = None):
    runs = OrderedDict()
    discovery_runs = OrderedDict()
    lock = Lock()
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(ROOT / "experiments"), **kwargs)

        def list_directory(self, path):
            self.send_error(404)
            return None

        def do_POST(self):
            if self.path not in {"/api/research", "/api/simulate"}:
                self.send_error(404)
                return
            # Do not allow a third-party page to drive this local endpoint.
            expected = f"http://127.0.0.1:{self.server.server_port}"
            if self.headers.get("Origin") not in {None, expected}:
                self.send_error(403)
                return
            try:
                length = int(self.headers.get("Content-Length", 0))
                if not 0 < length <= 20000:
                    raise ValueError("Request size invalid")
                params = json.loads(self.rfile.read(length))
                if self.path == "/api/simulate":
                    response = run_simulation(context[0], params)
                    with lock:
                        runs[response['run_id']] = response
                        while len(runs)>20:
                            runs.popitem(last=False)
                else:
                    selected_context = context
                    if params.get('run_id'):
                        with lock:
                            simulation = runs.get(params['run_id'])
                        if simulation is None:
                            raise ValueError('실행 결과가 만료됐습니다. 시뮬레이션을 다시 실행하세요.')
                        selected_context = ({**context[0], 'simulation': simulation}, context[1],
                                            context[2] + ':' + params['run_id'])
                    response = research_response(selected_context, params)
                status = 200
            except (ValueError, KeyError, TypeError) as error:
                response, status = {"error": str(error)}, 400
            except Exception:
                # Never expose a traceback; research context remains optional to simulation.
                message = ("뉴스 공급자 응답에 실패했습니다. 가격/매매 시뮬레이션에는 영향이 없습니다."
                           if self.path == "/api/research" else "시뮬레이션 처리에 실패했습니다. 입력과 데이터 상태를 확인하세요.")
                response, status = {"error": message}, 502
            raw = json.dumps(response, ensure_ascii=False, allow_nan=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            # Restrict static serving to the chart and its vendored chart dependency.
            path = urlsplit(self.path).path
            if path == "/api/asset-discovery" and mode == "LOCAL_RESEARCH":
                try:
                    params = parse_qs(urlsplit(self.path).query, strict_parsing=True)
                    if any(len(values) != 1 for values in params.values()) or set(params) - {"as_of", "lookback", "capital", "us_capital"}:
                        raise ValueError("Invalid discovery parameters")
                    as_of = date.fromisoformat(params["as_of"][0]) if "as_of" in params else None
                    lookback = params.get("lookback", ["1Y"])[0]
                    try:
                        capital = Decimal(params.get("capital", ["500000"])[0])
                        us_capital = Decimal(params.get("us_capital", ["500"])[0])
                    except InvalidOperation as error:
                        raise ValueError("Invalid capital") from error
                    if (not capital.is_finite() or not Decimal(10000) <= capital <= Decimal(1000000000)
                        or not us_capital.is_finite() or not Decimal(10) <= us_capital <= Decimal(1000000)):
                        raise ValueError("Invalid capital")
                    if lookback not in {"6M", "1Y", "3Y", "5Y"}:
                        raise ValueError("Invalid lookback")
                    local_versions = tuple(sorted((str(path), path.stat().st_mtime_ns)
                                                  for path in (ROOT / "data/processed").rglob("*")
                                                  if path.is_file() and path.suffix in {".csv", ".json"}
                                                  if "korea_" in str(path) or "samsung_005930" in str(path)
                                                  or "us_" in str(path)))
                    cache_key = (as_of, lookback, capital, us_capital, local_versions)
                    with lock:
                        report = discovery_runs.get(cache_key)
                    if report is None:
                        report = build_discovery_report(as_of=as_of, lookback=lookback,
                                                        capital=capital, us_capital=us_capital)
                        with lock:
                            discovery_runs[cache_key] = report
                            while len(discovery_runs) > 8:
                                discovery_runs.popitem(last=False)
                    raw = json.dumps(report, ensure_ascii=False, allow_nan=False).encode("utf-8")
                    status = 200
                except ValueError as error:
                    raw = json.dumps({"error": str(error)}, ensure_ascii=False).encode("utf-8")
                    status = 400
                except Exception:
                    raw = json.dumps({"error": "종목 발굴 실행에 실패했습니다. 로컬 데이터를 확인하세요."}, ensure_ascii=False).encode("utf-8")
                    status = 502
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(raw)
                return
            if path == "/api/samsung-family" and mode == "LOCAL_RESEARCH":
                try:
                    payload = build_report()
                    raw = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
                    status = 200
                except (ValueError, FileNotFoundError) as error:
                    raw = json.dumps({"error": str(error)}, ensure_ascii=False).encode("utf-8")
                    status = 503
                except Exception:
                    raw = json.dumps({"error": "삼성전자 비교를 계산하지 못했습니다. 로컬 데이터 상태를 확인하세요."},
                                     ensure_ascii=False).encode("utf-8")
                    status = 502
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(raw)
                return
            if mode == "PUBLIC_DEMO" and path in {"/tiger_etf_v2/tiger_data.js", "/tiger_etf_v2/simulation_data.js"}:
                asset = (public_dir or ROOT / "experiments/public_demo") / path.rsplit("/", 1)[-1]
                content = asset.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/javascript; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(content)
                return
            allowed = {"/tiger_etf_v2/", "/tiger_etf_v2/index.html", "/tiger_etf_v2/chart.js",
                       "/tiger_etf_v2/hover.js",
                       "/tiger_etf_v2/chart.css", "/tiger_etf_v2/research.js",
                       "/tiger_etf_v2/tiger_data.js", "/tiger_etf_v2/simulation_data.js",
                       "/lightweight_charts/vendor/lightweight-charts.standalone.production.js"}
            if mode == "LOCAL_RESEARCH":
                allowed.update({"/samsung_strategy_family/", "/samsung_strategy_family/index.html",
                                "/samsung_strategy_family/style.css", "/samsung_strategy_family/app.js"})
                allowed.update({"/asset_discovery/", "/asset_discovery/index.html",
                                "/asset_discovery/style.css", "/asset_discovery/app.js"})
            if path not in allowed:
                self.send_error(404)
                return
            super().do_GET()

        def do_HEAD(self):
            self.send_error(405)

    return Handler


def main():
    parser = argparse.ArgumentParser()
    mode = os.environ.get("ZML_DATA_MODE", "LOCAL_RESEARCH")
    parser.add_argument("--port", type=int, default=8062)
    parser.add_argument("--export-example", action="store_true")
    args = parser.parse_args()
    context = load_context(mode)
    if args.export_example:
        response = research_response(context, {"start": "2023-01-04", "end": "2023-04-04",
            "hypothesis": "금리 및 물가 발표와 익절 대기기간 사이에 관계가 있었는지 검증한다."})
        folder = ROOT / "artifacts/research_workstation"
        folder.mkdir(parents=True, exist_ok=True)
        for key in ("markdown", "validation", "concept"):
            (folder / f"{key}.md").write_text(response[key], encoding="utf-8")
        (folder / "snapshot.json").write_text(json.dumps(response["snapshot"], ensure_ascii=False, indent=2), encoding="utf-8")
        print(folder)
        return
    print(f"Research workstation ({mode}): http://127.0.0.1:{args.port}/tiger_etf_v2/", flush=True)
    ThreadingHTTPServer(("127.0.0.1", args.port), handler_for(context, mode)).serve_forever()


if __name__ == "__main__":
    main()
