"""UI-independent Case #01 comparison application service."""

from dataclasses import dataclass
import math
from pathlib import Path

import numpy as np
import pandas as pd

from zero_market_lab.backtest import BacktestResult, run_case01_comparison


MAX_MONTHLY_CONTRIBUTION = 1_000_000_000.0
MAX_TAKE_PROFIT_PERCENT = 100.0
MAX_REENTRY_MONTHS = 120


class ParameterValidationError(ValueError):
    """A human-readable collection of invalid research parameters."""

    def __init__(self, messages: list[str]):
        super().__init__(" ".join(messages))
        self.messages = messages


@dataclass(frozen=True)
class Case01ComparisonConfig:
    start_date: str
    end_date: str
    monthly_contribution: float = 500_000.0
    take_profit_percent: float = 5.0
    reentry_months: int = 1


@dataclass(frozen=True)
class ComparisonOutput:
    config: Case01ComparisonConfig
    market: pd.DataFrame
    results: dict[str, BacktestResult]
    metrics: list[dict]
    insights: dict[str, bool]


def latest_dataset(root: Path) -> Path:
    candidates = sorted((root / "data" / "processed").glob("*/sp500_price_daily.parquet"))
    if not candidates:
        raise FileNotFoundError("No STEP 1 processed S&P500 dataset was found.")
    return candidates[-1]


def load_latest_market(root: Path) -> pd.DataFrame:
    return pd.read_parquet(latest_dataset(root))


def dataset_bounds(market_data: pd.DataFrame) -> tuple[pd.Timestamp, pd.Timestamp]:
    dates = pd.to_datetime(market_data["date"])
    return dates.min().normalize(), dates.max().normalize()


def validate_config(
    config: Case01ComparisonConfig,
    market_data: pd.DataFrame,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    errors: list[str] = []
    try:
        start = pd.Timestamp(config.start_date).normalize()
        end = pd.Timestamp(config.end_date).normalize()
    except (TypeError, ValueError):
        raise ParameterValidationError(["Start Date와 End Date를 올바르게 입력하세요."])

    if pd.isna(start) or pd.isna(end):
        raise ParameterValidationError(["Start Date와 End Date를 모두 입력하세요."])

    data_start, data_end = dataset_bounds(market_data)
    if start >= end:
        errors.append("Start Date는 End Date보다 앞서야 합니다.")
    if start < data_start or start > data_end:
        errors.append(f"Start Date는 데이터 범위 {data_start.date()}~{data_end.date()} 안이어야 합니다.")
    if end < data_start or end > data_end:
        errors.append(f"End Date는 데이터 범위 {data_start.date()}~{data_end.date()} 안이어야 합니다.")

    contribution = config.monthly_contribution
    if (
        not isinstance(contribution, (int, float))
        or not math.isfinite(contribution)
        or contribution <= 0
        or contribution > MAX_MONTHLY_CONTRIBUTION
    ):
        errors.append("Monthly Contribution은 0보다 크고 1,000,000,000 이하여야 합니다.")

    take_profit = config.take_profit_percent
    if (
        not isinstance(take_profit, (int, float))
        or not math.isfinite(take_profit)
        or take_profit <= 0
        or take_profit > MAX_TAKE_PROFIT_PERCENT
    ):
        errors.append("Take Profit은 0%보다 크고 100% 이하여야 합니다.")

    reentry = config.reentry_months
    if (
        not isinstance(reentry, (int, float))
        or not math.isfinite(reentry)
        or not float(reentry).is_integer()
        or reentry <= 0
        or reentry > MAX_REENTRY_MONTHS
    ):
        errors.append("Reentry Months는 1~120 사이의 정수여야 합니다.")

    if errors:
        raise ParameterValidationError(errors)
    return start, end


def _metrics(code: str, result: BacktestResult) -> dict:
    final = result.daily_states.iloc[-1]
    events = result.events

    def count(event_type: str) -> int:
        return int((events.event_type == event_type).sum())

    return {
        "strategy": code,
        "final_portfolio_value": float(final.portfolio_value),
        "total_contribution": float(final.total_contribution),
        "investment_gain": float(final.portfolio_value - final.total_contribution),
        "final_cash": float(final.cash),
        "final_quantity": float(final.quantity),
        "buy_count": count("BUY") + count("REENTRY"),
        "sell_count": count("SELL"),
        "take_profit_count": count("TAKE_PROFIT"),
        "reentry_count": count("REENTRY"),
        "cash_waiting_days": int(result.metadata["cash_waiting_days"]),
    }


def same_exposure(a: BacktestResult, b: BacktestResult) -> bool:
    """Compare the A/B control invariant with the project's float tolerance."""
    return all(
        np.allclose(
            a.daily_states[column].to_numpy(),
            b.daily_states[column].to_numpy(),
            rtol=1e-12,
            atol=1e-9,
        )
        for column in ("portfolio_value", "quantity", "cash")
    )


def run_comparison(
    market_data: pd.DataFrame,
    config: Case01ComparisonConfig,
) -> ComparisonOutput:
    start, end = validate_config(config, market_data)
    dates = pd.to_datetime(market_data["date"])
    filtered = market_data.loc[(dates >= start) & (dates <= end), ["date", "close"]].copy()
    if len(filtered) < 2:
        raise ParameterValidationError(["선택 기간에는 시장 관측값이 최소 2개 필요합니다."])

    results = run_case01_comparison(
        filtered,
        monthly_contribution=float(config.monthly_contribution),
        take_profit_rate=float(config.take_profit_percent) / 100.0,
        reentry_months=int(config.reentry_months),
    )
    metrics = [_metrics(code, result) for code, result in results.items()]
    control_value = metrics[0]["final_portfolio_value"]
    for row in metrics:
        delta = row["final_portfolio_value"] - control_value
        row["delta_vs_a"] = delta
        row["delta_vs_a_percent"] = (
            0.0 if control_value == 0 else delta / control_value * 100.0
        )

    a_b_overlap = same_exposure(results["A"], results["B"])
    return ComparisonOutput(
        config=config,
        market=filtered.reset_index(drop=True),
        results=results,
        metrics=metrics,
        insights={"a_b_overlap": a_b_overlap},
    )
