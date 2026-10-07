"""Print Goal Prototype results for three real S&P500 start dates."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zero_market_lab.goal_ui.service import (
    GoalSimulationConfig,
    STRATEGIES,
    korean_date,
    run_goal_simulation,
)
from zero_market_lab.ui.service import load_latest_market


def main() -> int:
    market = load_latest_market(ROOT)
    print("start | strategy | status | goal_date | days | pre_goal_mdd | final_value")
    print("--- | --- | --- | --- | ---: | ---: | ---:")
    for start in ("2018-01-02", "2020-01-02", "2022-01-03"):
        output = run_goal_simulation(market, GoalSimulationConfig(start_date=start))
        for code in "ABC":
            item = output.analyses[code]
            print(
                f"{start} | {STRATEGIES[code]} | {item.status.value} | "
                f"{korean_date(item.goal_date) if item.goal_date else '-'} | "
                f"{item.days_to_goal if item.days_to_goal is not None else '-'} | "
                f"{item.max_drawdown_before_goal:.2%} | {item.final_portfolio_value:,.0f}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
