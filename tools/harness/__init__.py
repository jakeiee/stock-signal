"""
stock-signal Harness - 轻量级执行框架

统一编排 dividend_monitor 和 market_monitor 的执行流程。
"""

from .core import Harness
from .context import ExecutionContext, StepResult
from .step import Step, StepConfig, StepStatus
from .executor import Executor, SerialExecutor, ParallelExecutor
from .registry import StepRegistry

__all__ = [
    "Harness",
    "ExecutionContext",
    "StepResult",
    "Step",
    "StepConfig",
    "StepStatus",
    "Executor",
    "SerialExecutor",
    "ParallelExecutor",
    "StepRegistry",
]
