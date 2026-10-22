"""Local-only Historical Replay visual simulator; no LIVE_FORWARD API."""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import sys
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zero_market_lab.paper_trading.replay_ui import ReplayController  # noqa: E402
from zero_market_lab.paper_trading.manual_replay import ManualReplayController  # noqa: E402
from zero_market_lab.transit.calendar import at_market_close, year_calendar  # noqa: E402

ASSETS = ROOT / "experiments/paper_replay"
MANUAL_ASSETS = ROOT / "experiments/manual_replay"
VENDOR = ROOT / "experiments/lightweight_charts/vendor/lightweight-charts.standalone.production.js"
ACCOUNT = r"([a-zA-Z0-9_-]{1,100})"


def handler_for(controller: ReplayController, manual: ManualReplayController | None = None):
    class Handler(BaseHTTPRequestHandler):
        def _json(self, payload: dict | list, code: int = 200):
            data = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)

        def _error(self, error: Exception):
            code = 404 if isinstance(error, (KeyError, FileNotFoundError)) else 400
            self._json({"error": str(error)}, code)

        def _static(self, file: Path, mime: str):
            data = file.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            parsed = urlsplit(self.path)
            path = parsed.path
            static = {"/": (ASSETS / "index.html", "text/html; charset=utf-8"),
                      "/index.html": (ASSETS / "index.html", "text/html; charset=utf-8"),
                      "/app.js": (ASSETS / "app.js", "text/javascript; charset=utf-8"),
                      "/style.css": (ASSETS / "style.css", "text/css; charset=utf-8"),
                      "/vendor/lightweight-charts.js": (VENDOR, "text/javascript; charset=utf-8")}
            if manual is not None:
                static.update({"/manual/": (MANUAL_ASSETS / "index.html", "text/html; charset=utf-8"),
                               "/manual/app.js": (MANUAL_ASSETS / "app.js", "text/javascript; charset=utf-8"),
                               "/manual/style.css": (MANUAL_ASSETS / "style.css", "text/css; charset=utf-8")})
            if path in static:
                self._static(*static[path])
                return
            try:
                if path == "/api/meta":
                    params = parse_qs(parsed.query, strict_parsing=True) if parsed.query else {}
                    if set(params) - {"symbol"} or any(len(values) != 1 for values in params.values()):
                        raise ValueError("Invalid asset parameters")
                    self._json(controller.meta((params.get("symbol") or [None])[0]))
                elif path == "/api/accounts":
                    self._json(controller.accounts())
                elif path == "/api/accounts/hidden":
                    self._json(controller.hidden_accounts())
                elif path == "/api/transit/current":
                    params = parse_qs(parsed.query, strict_parsing=True)
                    if set(params) != {"date", "currency"} or any(len(v) != 1 for v in params.values()):
                        raise ValueError("date and currency are required")
                    self._json(at_market_close(params["date"][0], params["currency"][0]))
                elif path == "/api/transit/year":
                    params = parse_qs(parsed.query, strict_parsing=True)
                    if set(params) != {"year"} or len(params["year"]) != 1:
                        raise ValueError("year is required")
                    self._json(year_calendar(int(params["year"][0])))
                elif path == "/api/transit/gate-metrics":
                    params = parse_qs(parsed.query, strict_parsing=True)
                    if set(params) - {"symbol", "year", "gate", "as_of"} or not {"symbol", "year", "gate"} <= set(params) or any(len(v) != 1 for v in params.values()):
                        raise ValueError("symbol, year and gate are required")
                    self._json(controller.transit_metrics(params["symbol"][0],
                                                          int(params["year"][0]),
                                                          int(params["gate"][0]),
                                                          (params.get("as_of") or [None])[0]))
                elif path == "/api/transit/market-year":
                    params = parse_qs(parsed.query, strict_parsing=True)
                    if set(params) != {"symbol", "year"} or any(len(v) != 1 for v in params.values()):
                        raise ValueError("symbol and year are required")
                    self._json(controller.transit_market_year(params["symbol"][0],
                                                              int(params["year"][0])))
                elif manual is not None and path == "/api/manual/meta":
                    self._json(manual.meta())
                elif manual is not None and path == "/api/manual/accounts":
                    self._json(manual.accounts())
                elif manual is not None and (match := re.fullmatch(rf"/api/manual/{ACCOUNT}/state", path)):
                    self._json(manual.state(match.group(1)))
                elif match := re.fullmatch(rf"/api/replay/{ACCOUNT}/state", path):
                    params = parse_qs(parsed.query, strict_parsing=True) if parsed.query else {}
                    if set(params) - {"view_date"} or any(len(values) != 1 for values in params.values()):
                        raise ValueError("Invalid view parameters")
                    self._json(controller.state(match.group(1), (params.get("view_date") or [None])[0]))
                else:
                    self._json({"error": "Not found"}, 404)
            except (ValueError, KeyError, FileNotFoundError) as error:
                self._error(error)
            except Exception:
                self._json({"error": "Replay data could not be loaded; check local data and server logs"}, 500)

        def do_POST(self):
            expected_origin = f"http://127.0.0.1:{self.server.server_port}"
            if self.headers.get("Origin") not in {None, expected_origin}:
                self._json({"error": "Cross-origin request denied"}, 403)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 4096:
                    raise ValueError("Request body size invalid")
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError("JSON object required")
                path = urlsplit(self.path).path
                if path == "/api/replay/create":
                    if set(body) - {"start_date", "capital", "symbol", "strategy",
                                     "entry_offset_pct", "take_profit_pct", "buy_budget"}:
                        raise ValueError("Unsupported simulation option")
                    result = controller.create(start_date=body.get("start_date"),
                                               capital=str(body.get("capital", "10000000")),
                                               symbol=body.get("symbol", "000660"),
                                               strategy=body.get("strategy", "S1"),
                                               entry_offset_pct=str(body.get("entry_offset_pct", "-1")),
                                               take_profit_pct=str(body.get("take_profit_pct", "5")),
                                               buy_budget=(str(body["buy_budget"]) if body.get("buy_budget") is not None
                                                           else None))
                    self._json(result, 201)
                elif manual is not None and path == "/api/manual/create":
                    if set(body) - {"start_date", "initial_krw", "initial_usd"}:
                        raise ValueError("Unsupported manual account option")
                    self._json(manual.create(start_date=body.get("start_date"),
                                             initial_krw=str(body.get("initial_krw", "10000000")),
                                             initial_usd=str(body.get("initial_usd", "0"))), 201)
                elif manual is not None and (match := re.fullmatch(rf"/api/manual/{ACCOUNT}/next", path)):
                    if body:
                        raise ValueError("Next day takes no options")
                    self._json(manual.next_day(match.group(1)))
                elif manual is not None and (match := re.fullmatch(rf"/api/manual/{ACCOUNT}/order", path)):
                    if set(body) - {"symbol", "side", "budget", "quantity"}:
                        raise ValueError("Unsupported manual order option")
                    self._json(manual.order(match.group(1), symbol=body.get("symbol"),
                                            side=body.get("side"), budget=body.get("budget"),
                                            quantity=body.get("quantity")))
                elif match := re.fullmatch(rf"/api/replay/{ACCOUNT}/next", path):
                    if body:
                        raise ValueError("Run Next Day takes no options")
                    self._json(controller.next_day(match.group(1)))
                elif match := re.fullmatch(rf"/api/replay/{ACCOUNT}/hide", path):
                    if body:
                        raise ValueError("Hide account takes no options")
                    self._json(controller.hide_account(match.group(1)))
                elif match := re.fullmatch(rf"/api/replay/{ACCOUNT}/restore", path):
                    if body:
                        raise ValueError("Restore account takes no options")
                    self._json(controller.restore_account(match.group(1)))
                else:
                    self._json({"error": "Not found"}, 404)
            except (ValueError, TypeError, KeyError, FileNotFoundError) as error:
                self._error(error)
            except Exception:
                self._json({"error": "Replay action failed; no new day was shown"}, 500)

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8076)
    parser.add_argument("--db", type=Path, default=ROOT / "artifacts/paper_trading/replay_ui.sqlite3")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Port must be 1–65535")
    controller = ReplayController(ROOT, args.db)
    manual = ManualReplayController(ROOT, args.db.with_name("manual_replay.sqlite3"))
    print(f"Historical Replay UI: http://127.0.0.1:{args.port}/", flush=True)
    ThreadingHTTPServer(("127.0.0.1", args.port), handler_for(controller, manual)).serve_forever()


if __name__ == "__main__":
    main()
