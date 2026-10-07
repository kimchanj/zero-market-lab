"""Application service for one-start-date investment experiments."""

from dataclasses import dataclass
import logging
import math

import pandas as pd

from zero_market_lab.analytics import GoalAnalysis, analyze_goal
from zero_market_lab.backtest import BacktestResult, run_case01_comparison


LOGGER = logging.getLogger(__name__)


STRATEGIES = {
    "A": "A — 장기보유",
    "B": "B — 익절 후 즉시 재진입",
    "C": "C — 익절 후 대기 후 재진입",
}


class GoalParameterError(ValueError):
    pass


@dataclass(frozen=True)
class GoalSimulationConfig:
    start_date: str
    initial_investment: float = 10_000_000.0
    monthly_contribution: float = 0.0
    max_years: int = 5
    take_profit_percent: float = 5.0
    reentry_months: int = 1
    goal_enabled: bool = True
    target_return_percent: float = 20.0


@dataclass(frozen=True)
class StrategyEvaluation:
    strategy: str
    total_contribution: float
    final_portfolio_value: float
    investment_gain: float
    delta_vs_a: float
    delta_percent_vs_a: float
    take_profit_count: int
    sell_count: int
    reentry_count: int
    cash_waiting_days: int
    time_in_market: float
    max_drawdown: float
    verdict: str


@dataclass(frozen=True)
class GoalSimulationOutput:
    config: GoalSimulationConfig
    market: pd.DataFrame
    results: dict[str, BacktestResult]
    evaluations: dict[str, StrategyEvaluation]
    analyses: dict[str, GoalAnalysis]
    actual_start: pd.Timestamp
    required_horizon_end: pd.Timestamp
    goal_active: bool
    warnings: tuple[str, ...]


def _finite(value: object) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value)


def _number(value: object, label: str) -> float:
    if isinstance(value, bool):
        raise GoalParameterError(f"{label}을 숫자로 입력하세요.")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise GoalParameterError(f"{label}을 숫자로 입력하세요.")
    if not math.isfinite(number):
        raise GoalParameterError(f"{label}을 숫자로 입력하세요.")
    return number


def _max_drawdown(values: pd.Series) -> float:
    running_peak = values.cummax()
    return float((values / running_peak - 1.0).min())


def _count(result: BacktestResult, event_type: str) -> int:
    return int((result.events["event_type"] == event_type).sum())


def _evaluate(results: dict[str, BacktestResult]) -> dict[str, StrategyEvaluation]:
    a_final = float(results["A"].daily_states["portfolio_value"].iloc[-1])
    evaluations = {}
    for code, result in results.items():
        states = result.daily_states
        final_value = float(states["portfolio_value"].iloc[-1])
        contribution = float(states["total_contribution"].iloc[-1])
        delta = final_value - a_final
        delta_percent = delta / a_final if a_final else 0.0
        time_in_market = float((states["quantity"] > 0).mean())
        if code == "A":
            verdict = "장기보유 기준전략입니다."
        elif code == "B":
            verdict = (
                "현재 가정에서는 A와 동일한 결과입니다. 같은 종가에 비용 없이 "
                "전액 재매수하므로 시장 노출이 바뀌지 않습니다."
            )
        elif delta < 0:
            verdict = (
                f"시장 밖에서 {result.metadata['cash_waiting_days']:,}일 대기하여 "
                "A보다 최종 평가금액이 낮았습니다."
            )
        elif delta > 0:
            verdict = (
                f"시장 밖에서 {result.metadata['cash_waiting_days']:,}일 대기했고 "
                "A보다 최종 평가금액이 높았습니다."
            )
        else:
            verdict = "이 관측기간에서는 A와 최종 평가금액이 같았습니다."
        evaluations[code] = StrategyEvaluation(
            strategy=code,
            total_contribution=contribution,
            final_portfolio_value=final_value,
            investment_gain=final_value - contribution,
            delta_vs_a=delta,
            delta_percent_vs_a=delta_percent,
            take_profit_count=_count(result, "TAKE_PROFIT"),
            sell_count=_count(result, "SELL"),
            reentry_count=_count(result, "REENTRY"),
            cash_waiting_days=int(result.metadata["cash_waiting_days"]),
            time_in_market=time_in_market,
            max_drawdown=_max_drawdown(states["portfolio_value"]),
            verdict=verdict,
        )
    return evaluations


def _validated_int(value: object, label: str, minimum: int, maximum: int) -> int:
    number = _number(value, label)
    if not number.is_integer():
        raise GoalParameterError(f"{label}은 정수로 입력하세요.")
    integer = int(number)
    if integer < minimum or integer > maximum:
        raise GoalParameterError(f"{label}은 {minimum}~{maximum} 사이로 입력하세요.")
    return integer


def run_goal_simulation(
    market_data: pd.DataFrame,
    config: GoalSimulationConfig,
) -> GoalSimulationOutput:
    """Run A/B/C once, then evaluate performance and an optional fixed goal."""
    try:
        requested_start = pd.Timestamp(config.start_date).normalize()
    except (TypeError, ValueError):
        raise GoalParameterError("투자 시작일을 올바르게 입력하세요.")
    if pd.isna(requested_start):
        raise GoalParameterError("투자 시작일을 입력하세요.")
    initial_investment = _number(config.initial_investment, "초기 투자금")
    monthly_contribution = _number(config.monthly_contribution, "매월 투자금")
    take_profit_percent = _number(config.take_profit_percent, "익절 기준")
    target_return_percent = _number(config.target_return_percent, "목표 수익률")
    if initial_investment < 0:
        raise GoalParameterError("초기 투자금은 0 이상이어야 합니다.")
    if monthly_contribution < 0:
        raise GoalParameterError("매월 투자금은 0 이상이어야 합니다.")
    if initial_investment == 0 and monthly_contribution == 0:
        raise GoalParameterError("초기 투자금과 매월 투자금 중 하나는 0보다 커야 합니다.")
    years = _validated_int(config.max_years, "투자 기간", 1, 50)
    reentry_months = _validated_int(config.reentry_months, "재진입 대기기간", 1, 120)
    if take_profit_percent <= 0:
        raise GoalParameterError("익절 기준은 0%보다 커야 합니다.")
    if take_profit_percent > 1_000:
        raise GoalParameterError("익절 기준은 1,000% 이하여야 합니다.")
    if config.goal_enabled and target_return_percent <= 0:
        raise GoalParameterError("목표 수익률은 0%보다 커야 합니다.")

    source = market_data.loc[:, ["date", "close"]].copy()
    source["date"] = pd.to_datetime(source["date"])
    LOGGER.debug("goal simulation requested_start=%s", requested_start.date())
    candidates = source.loc[source["date"] >= requested_start]
    if candidates.empty:
        raise GoalParameterError("투자 시작일 이후의 시장 데이터가 없습니다.")
    actual_start = pd.Timestamp(candidates["date"].iloc[0]).normalize()
    required_end = actual_start + pd.DateOffset(years=years)
    filtered = candidates.loc[candidates["date"] <= required_end].reset_index(drop=True)
    LOGGER.debug(
        "goal simulation actual_start=%s filtered_end=%s rows=%d",
        actual_start.date(), pd.Timestamp(filtered["date"].iloc[-1]).date(), len(filtered),
    )
    if len(filtered) < 2:
        raise GoalParameterError("분석할 시장 관측값이 최소 2개 필요합니다.")

    results = run_case01_comparison(
        filtered,
        monthly_contribution=monthly_contribution,
        take_profit_rate=take_profit_percent / 100.0,
        reentry_months=reentry_months,
        initial_investment=initial_investment,
    )
    evaluations = _evaluate(results)

    goal_active = bool(
        config.goal_enabled
        and initial_investment > 0
        and monthly_contribution == 0
    )
    warnings: list[str] = []
    if source["date"].max() < required_end:
        warnings.append(
            f"요청한 {years}년보다 데이터가 짧아 "
            f"{pd.Timestamp(source['date'].max()).date().isoformat()}까지만 계산했습니다."
        )
    if config.goal_enabled and monthly_contribution > 0:
        warnings.append(
            "매월 투자금이 있는 실험에서는 목표수익률 정의가 확정되지 않아 "
            "목표선과 목표 달성 판정을 표시하지 않습니다. 총 납입금·평가금액·투자손익을 확인하세요."
        )
    analyses = {}
    if goal_active:
        analyses = {
            code: analyze_goal(
                result,
                initial_investment=initial_investment,
                target_return=target_return_percent / 100.0,
                required_horizon_end=required_end,
                horizon_complete=bool(source["date"].max() >= required_end),
            )
            for code, result in results.items()
        }

    return GoalSimulationOutput(
        config=config,
        market=filtered,
        results=results,
        evaluations=evaluations,
        analyses=analyses,
        actual_start=actual_start,
        required_horizon_end=required_end,
        goal_active=goal_active,
        warnings=tuple(warnings),
    )


def korean_date(value: str | pd.Timestamp) -> str:
    date = pd.Timestamp(value)
    weekdays = ("월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일")
    return f"{date.year}년 {date.month}월 {date.day}일 {weekdays[date.weekday()]}"
