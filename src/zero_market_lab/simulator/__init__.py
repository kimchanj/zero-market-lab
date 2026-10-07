"""Generic, explainable OHLCV trading simulator."""

from .engine import simulate
from .comparison import CrossAssetSummaryRow, compare_results
from .execution import ConfigurableFeeModel, LimitTouchExecutionModel, required_exit_price
from .explanation import explain_decisions
from .models import (
    CostConfig,
    DecisionRecord,
    ExecutionConfig,
    Instrument,
    MarketBar,
    SimulationResult,
    StrategyParameters,
)
from .provider import FrameOHLCVProvider, OHLCVProvider

__all__ = [
    "ConfigurableFeeModel",
    "CrossAssetSummaryRow",
    "CostConfig",
    "DecisionRecord",
    "ExecutionConfig",
    "FrameOHLCVProvider",
    "Instrument",
    "LimitTouchExecutionModel",
    "MarketBar",
    "OHLCVProvider",
    "SimulationResult",
    "StrategyParameters",
    "explain_decisions",
    "compare_results",
    "required_exit_price",
    "simulate",
]
