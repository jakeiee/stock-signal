"""
stock-signal Harness - 轻量级执行框架

统一编排 dividend_monitor 和 market_monitor 的执行流程。
"""

from .core import Harness
from .context import ExecutionContext, StepResult
from .step import Step, StepConfig, StepStatus
from .executor import Executor, SerialExecutor, ParallelExecutor
from .registry import StepRegistry
from .module_registry import ModuleRegistry, get_module_registry, auto_discover_modules, register_module
from .module_interface import BaseModule, ModuleMetadata, StepResult as ModuleStepResult

import typing as t


def initialize(search_paths: t.Optional[t.List[t.Any]] = None) -> None:
    """
    初始化 Harness 框架

    自动发现并注册所有模块。

    Args:
        search_paths: 搜索路径列表，默认为['dividend_monitor', 'market_monitor', 'portfolio']
    """
    print("🔧 初始化 Harness 框架...")

    # 自动发现模块
    auto_discover_modules(search_paths)

    # 健康检查
    registry = get_module_registry()
    health_results = registry.health_check_all()

    print(f"✓ 已注册 {len(registry.list_modules())} 个模块")
    for name, health in health_results.items():
        status = "✅" if health else "❌"
        print(f"  {status} {name}")

    print("🔧 初始化完成\n")


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
    "ModuleRegistry",
    "get_module_registry",
    "auto_discover_modules",
    "register_module",
    "BaseModule",
    "ModuleMetadata",
    "initialize",
]
