"""
Harness 核心引擎

统一编排步骤执行，管理执行流程。
"""

from typing import Any, Callable, Dict, List, Optional, Tuple, Type
import logging

from .context import ExecutionContext, ExecutionStatus, StepResult
from .step import Step, StepConfig, StepStatus
from .executor import Executor, SerialExecutor, ParallelExecutor
from .registry import StepRegistry


logger = logging.getLogger(__name__)


class Harness:
    """
    Harness 核心引擎

    负责步骤注册、依赖管理、执行编排和结果收集。
    """

    def __init__(
        self,
        name: str,
        config: Optional[Dict[str, Any]] = None,
        executor: Optional[Executor] = None,
        registry: Optional[StepRegistry] = None,
    ):
        """
        Args:
            name: Harness 名称
            config: 配置参数
            executor: 执行器，默认使用串行执行器
            registry: 步骤注册表
        """
        self.name = name
        self.config = config or {}
        self._steps: List[Step] = []
        self._executor = executor or SerialExecutor()
        self._registry = registry or StepRegistry()

        # Hooks
        self._before_all: List[Callable[[ExecutionContext], None]] = []
        self._after_all: List[Callable[[ExecutionContext], None]] = []
        self._on_step_start: List[Callable[[Step, ExecutionContext], None]] = []
        self._on_step_end: List[Callable[[Step, ExecutionContext], None]] = []
        self._on_error: List[Callable[[Exception, ExecutionContext], None]] = []

    def add_step(self, step: Step, position: Optional[int] = None) -> 'Harness':
        """
        添加执行步骤

        Args:
            step: 步骤实例
            position: 插入位置，None 表示追加到末尾

        Returns:
            self（支持链式调用）
        """
        if position is None:
            self._steps.append(step)
        else:
            self._steps.insert(position, step)
        return self

    def add_steps(self, steps: List[Step]) -> 'Harness':
        """
        批量添加步骤

        Args:
            steps: 步骤列表

        Returns:
            self
        """
        self._steps.extend(steps)
        return self

    def remove_step(self, step_name: str) -> bool:
        """
        移除指定步骤

        Args:
            step_name: 步骤名称

        Returns:
            是否成功移除
        """
        for i, step in enumerate(self._steps):
            if step.name == step_name:
                self._steps.pop(i)
                return True
        return False

    def get_step(self, step_name: str) -> Optional[Step]:
        """获取指定步骤"""
        for step in self._steps:
            if step.name == step_name:
                return step
        return None

    def register_step_type(self, name: str, step_class: Type[Step]) -> None:
        """注册步骤类型到注册表"""
        self._registry.register(name, step_class)

    def create_step(self, step_type: str, **kwargs) -> Step:
        """从注册表创建步骤"""
        return self._registry.create(step_type, **kwargs)

    # ==================== Hooks ====================

    def before_all(self, callback: Callable[[ExecutionContext], None]) -> 'Harness':
        """注册执行前回调"""
        self._before_all.append(callback)
        return self

    def after_all(self, callback: Callable[[ExecutionContext], None]) -> 'Harness':
        """注册执行后回调"""
        self._after_all.append(callback)
        return self

    def on_step_start(self, callback: Callable[[Step, ExecutionContext], None]) -> 'Harness':
        """注册步骤开始回调"""
        self._on_step_start.append(callback)
        return self

    def on_step_end(self, callback: Callable[[Step, ExecutionContext], None]) -> 'Harness':
        """注册步骤结束回调"""
        self._on_step_end.append(callback)
        return self

    def on_error(self, callback: Callable[[Exception, ExecutionContext], None]) -> 'Harness':
        """注册错误回调"""
        self._on_error.append(callback)
        return self

    # ==================== Execution ====================

    def execute(
        self,
        data: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> ExecutionContext:
        """
        执行 Harness

        Args:
            data: 初始数据
            progress_callback: 进度回调 (step_name, current, total)

        Returns:
            执行上下文
        """
        # 创建执行上下文
        context = ExecutionContext(name=self.name, config=self.config)

        # 初始化数据
        if data:
            for key, value in data.items():
                context.set(key, value)

        try:
            # 执行前 Hooks
            for callback in self._before_all:
                callback(context)

            context.start()

            # 执行步骤
            context = self._executor.execute(
                self._steps,
                context,
                progress_callback=progress_callback,
            )

            # 检查是否有失败的步骤
            has_failures = any(
                r.status == "failed"
                for r in context.step_results.values()
            )

            context.complete(success=not has_failures)

        except Exception as e:
            logger.exception("Harness execution failed")
            context.error(f"Harness execution failed: {str(e)}")
            context.complete(success=False)

            # 错误 Hooks
            for callback in self._on_error:
                callback(e, context)

        finally:
            # 执行后 Hooks
            for callback in self._after_all:
                callback(context)

        return context

    def dry_run(self) -> List[Dict[str, Any]]:
        """
        模拟执行（不实际执行步骤）

        返回将要执行的步骤列表及其依赖关系。
        """
        plan = []
        for step in self._steps:
            plan.append({
                "name": step.name,
                "class": step.__class__.__name__,
                "depends_on": step.config.depends_on,
                "max_retries": step.config.max_retries,
                "timeout": step.config.timeout,
                "skip_if": "defined" if step.config.skip_if else None,
            })
        return plan

    # ==================== Utilities ====================

    def validate(self) -> Tuple[bool, List[str]]:
        """
        验证 Harness 配置

        Returns:
            (是否有效, 错误信息列表)
        """
        errors = []

        # 检查步骤名称唯一性
        names = [s.name for s in self._steps]
        duplicates = [n for n in names if names.count(n) > 1]
        if duplicates:
            errors.append(f"Duplicate step names: {set(duplicates)}")

        # 检查循环依赖
        if self._has_circular_dependency():
            errors.append("Circular dependency detected")

        # 检查步骤有效性
        for step in self._steps:
            if not step.validate():
                errors.append(f"Step '{step.name}' validation failed")

        # 检查依赖引用的步骤是否存在
        all_names = set(names)
        for step in self._steps:
            for dep in step.config.depends_on:
                if dep not in all_names:
                    errors.append(f"Step '{step.name}' depends on non-existent step '{dep}'")

        return len(errors) == 0, errors

    def _has_circular_dependency(self) -> bool:
        """检测循环依赖"""
        # 构建依赖图
        graph: Dict[str, List[str]] = {}
        for step in self._steps:
            graph[step.name] = step.config.depends_on.copy()

        # DFS 检测环
        visited = set()
        rec_stack = set()

        def has_cycle(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)

            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        for node in graph:
            if node not in visited:
                if has_cycle(node):
                    return True

        return False

    @property
    def steps(self) -> List[Step]:
        """获取步骤列表"""
        return self._steps.copy()

    def __repr__(self) -> str:
        return f"<Harness name='{self.name}' steps={len(self._steps)}>"
