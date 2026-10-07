"""Goal analysis over an existing daily portfolio path."""

from dataclasses import dataclass
from enum import Enum
import math

import pandas as pd

from zero_market_lab.backtest import BacktestResult


class GoalStatus(str, Enum):
    GOAL_REACHED = "GOAL_REACHED"
    GOAL_NOT_REACHED = "GOAL_NOT_REACHED"
    INSUFFICIENT_HORIZON = "INSUFFICIENT_HORIZON"


@dataclass(frozen=True)
class GoalAnalysis:
    status: GoalStatus
    target_value: float
    goal_reached: bool
    goal_date: pd.Timestamp | None
    days_to_goal: int | None
    calendar_duration: str | None
    portfolio_value_at_goal: float | None
    max_drawdown_before_goal: float
    final_portfolio_value: float
    total_contribution: float
    investment_gain: float
    simple_return: float
    observation_start: pd.Timestamp
    observation_end: pd.Timestamp
    required_horizon_end: pd.Timestamp


def _validate_rate(target_return: float) -> None:
    if not math.isfinite(target_return) or target_return <= 0:
        raise ValueError("Target return must be finite and > 0")


def _max_drawdown(values: pd.Series) -> float:
    running_peak = values.cummax()
    drawdowns = values / running_peak - 1.0
    return float(drawdowns.min())


def analyze_goal(
    result: BacktestResult,
    *,
    initial_investment: float,
    target_return: float,
    required_horizon_end: str | pd.Timestamp,
    horizon_complete: bool | None = None,
) -> GoalAnalysis:
    """Analyze first target hit and path risk without changing strategy behavior."""
    if not math.isfinite(initial_investment) or initial_investment <= 0:
        raise ValueError("Initial investment must be finite and > 0")
    _validate_rate(target_return)
    states = result.daily_states
    if states.empty:
        raise ValueError("Daily portfolio state cannot be empty")

    dates = pd.to_datetime(states["date"])
    values = pd.to_numeric(states["portfolio_value"])
    start = pd.Timestamp(dates.iloc[0]).normalize()
    end = pd.Timestamp(dates.iloc[-1]).normalize()
    required_end = pd.Timestamp(required_horizon_end).normalize()
    target_value = initial_investment * (1.0 + target_return)
    reached_rows = states.loc[values >= target_value]

    if not reached_rows.empty:
        goal_row = reached_rows.iloc[0]
        goal_date = pd.Timestamp(goal_row["date"]).normalize()
        goal_index = reached_rows.index[0]
        path = values.loc[:goal_index]
        status = GoalStatus.GOAL_REACHED
        days = int((goal_date - start).days)
        duration = f"{days}일"
        value_at_goal = float(goal_row["portfolio_value"])
    else:
        goal_date = None
        path = values
        complete = end >= required_end if horizon_complete is None else horizon_complete
        status = (
            GoalStatus.GOAL_NOT_REACHED
            if complete
            else GoalStatus.INSUFFICIENT_HORIZON
        )
        days = None
        duration = None
        value_at_goal = None

    final_value = float(values.iloc[-1])
    total_contribution = float(states["total_contribution"].iloc[-1])
    gain = final_value - total_contribution
    return GoalAnalysis(
        status=status,
        target_value=target_value,
        goal_reached=status is GoalStatus.GOAL_REACHED,
        goal_date=goal_date,
        days_to_goal=days,
        calendar_duration=duration,
        portfolio_value_at_goal=value_at_goal,
        max_drawdown_before_goal=_max_drawdown(path),
        final_portfolio_value=final_value,
        total_contribution=total_contribution,
        investment_gain=gain,
        simple_return=gain / total_contribution,
        observation_start=start,
        observation_end=end,
        required_horizon_end=required_end,
    )
