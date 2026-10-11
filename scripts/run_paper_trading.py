"""Local paper-trading CLI. Never submits a broker order or recommends an asset."""

from __future__ import annotations

import argparse
from decimal import Decimal
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zero_market_lab.asset_discovery.catalog import LocalOHLCVCatalog, load_universe  # noqa: E402
from zero_market_lab.paper_trading.engine import (create_account, journal, open_store,  # noqa: E402
                                                  record_correction, run_day, status)


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "artifacts/paper_trading/paper.sqlite3")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create", help="Create one immutable S1 paper account")
    create.add_argument("--name", required=True)
    create.add_argument("--symbol", required=True)
    create.add_argument("--strategy", choices=("S1", "S1_FIXED_TAKE_PROFIT"), default="S1")
    create.add_argument("--capital", type=Decimal, required=True)
    create.add_argument("--start-date", required=True)
    create.add_argument("--mode", choices=("HISTORICAL_REPLAY", "LIVE_FORWARD"),
                        default="HISTORICAL_REPLAY")
    create.add_argument("--entry-offset-pct", type=Decimal, default=Decimal("-1"))
    create.add_argument("--tp-pct", type=Decimal, default=Decimal("5"))
    create.add_argument("--buy-fee-rate", type=Decimal, default=Decimal("0.00015"))
    create.add_argument("--sell-fee-rate", type=Decimal, default=Decimal("0.00015"))
    create.add_argument("--sell-tax-rate", type=Decimal, default=Decimal("0"))
    create.add_argument("--slippage-rate", type=Decimal, default=Decimal("0"))
    run = commands.add_parser("run", help="Process one actual daily OHLCV bar")
    run.add_argument("--account", required=True)
    run.add_argument("--as-of", required=True)
    show = commands.add_parser("status", help="Read current account state")
    show.add_argument("--account", required=True)
    history = commands.add_parser("journal", help="Read append-only daily journal")
    history.add_argument("--account", required=True)
    correction = commands.add_parser("correction", help="Append a data-correction audit event")
    correction.add_argument("--account", required=True)
    correction.add_argument("--date", required=True)
    correction.add_argument("--reason", required=True)
    args = parser.parse_args(argv)
    try:
        with open_store(args.db) as con:
            if args.command == "create":
                assets = {item["symbol"]: item for item in load_universe(ROOT / "config/universe_seed_kr_us.json")}
                if args.symbol not in assets:
                    raise ValueError("Symbol must be chosen explicitly from the six seed assets")
                result = create_account(con, name=args.name, symbol=args.symbol,
                                        currency=assets[args.symbol]["currency"],
                                        capital=args.capital, start_date=args.start_date,
                                        mode=args.mode, entry_offset_pct=args.entry_offset_pct,
                                        tp_pct=args.tp_pct, buy_fee_rate=args.buy_fee_rate,
                                        sell_fee_rate=args.sell_fee_rate,
                                        sell_tax_rate=args.sell_tax_rate,
                                        slippage_rate=args.slippage_rate)
            elif args.command == "run":
                cfg = status(con, args.account)
                frame, provenance = LocalOHLCVCatalog(ROOT).load(cfg["symbol"])
                result = run_day(con, args.account, args.as_of, frame, provenance)
            elif args.command == "status":
                result = status(con, args.account)
            elif args.command == "journal":
                result = journal(con, args.account)
            else:
                result = record_correction(con, args.account, args.date, args.reason)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, KeyError, FileNotFoundError) as error:
        print(f"Paper trading rejected: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(cli())
