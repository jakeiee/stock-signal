"""
Harness 执行器

支持串行、并行、条件执行等多种策略。
"""

from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Any, Callable, Dict, List, Optional, Tuple
import threading
import time

from .context import ExecutionContext, StepResult
from .step import Step, StepStatus


class Executor(ABC):
    """
    执行器抽象基类

    定义步骤执行的基本接口。
    """

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers

    @abstractmethod
    def execute(
        self,
        steps: List[Step],
        context: ExecutionContext,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> ExecutionContext:
        """
        执行步骤列表

        Args:
            steps: 步骤列表
            context: 执行上下文
            progress_callback: 进度回调 (step_name, current, total)

        Returns:
            执行上下文
        """
        pass

    def _create_step_result(self, step: Step, context: ExecutionContext) -> StepResult:
        """创建步骤结果对象"""
        return StepResult(
            step_name=step.name,
            status=step.status.value if step.status != StepStatus.RETRYING else "failed",
            output=step.output,
            error=str(step.error) if step.error else None,
            duration=step.duration,
            metadata=step.config.metadata,
        )


class SerialExecutor(Executor):
    """
    串行执行器

    按顺序依次执行每个步骤。
    """

    def __init__(self, stop_on_error: bool = True):
        """
        Args:
            stop_on_error: 遇到错误是否停止执行
        """
        super().__init__(max_workers=1)
        self.stop_on_error = stop_on_error

    def execute(
        self,
        steps: List[Step],
        context: ExecutionContext,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> ExecutionContext:
        total = len(steps)

        for i, step in enumerate(steps):
            # 检查依赖
            if not self._check_dependencies(step, context):
                step._status = StepStatus.SKIPPED
                context.log("WARNING", f"Step '{step.name}' skipped due to unmet dependencies")
                context.record_step_result(self._create_step_result(step, context))
                continue

            # 执行步骤
            step.run(context)
            context.record_step_result(self._create_step_result(step, context))

            # 进度回调
            if progress_callback:
                progress_callback(step.name, i + 1, total)

            # 错误处理
            if step.status == StepStatus.FAILED:
                if self.stop_on_error:
                    context.error(f"Step '{step.name}' failed, stopping execution")
                    break
                else:
                    context.warning(f"Step '{step.name}' failed, continuing...")

        return context

    def _check_dependencies(self, step: Step, context: ExecutionContext) -> bool:
        """检查依赖是否满足"""
        for dep_name in step.config.depends_on:
            dep_result = context.get_step_result(dep_name)
            if not dep_result or dep_result.status != "success":
                return False
        return True


class ParallelExecutor(Executor):
    """
    并行执行器

    使用线程池并行执行步骤。
    仅执行无依赖或依赖已满足的步骤。
    """

    def __init__(self, max_workers: int = 4):
        super().__init__(max_workers)

    def execute(
        self,
        steps: List[Step],
        context: ExecutionContext,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> ExecutionContext:
        total = len(steps)
        completed = 0
        completed_names: set = set()
        remaining_steps = list(steps)
        lock = threading.Lock()

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures: Dict[Future, Step] = {}

            while remaining_steps or futures:
                # 找出可以执行的步骤
                ready_steps = [
                    s for s in remaining_steps
                    if self._are_dependencies_met(s, completed_names)
                ]

                # 提交可执行的步骤
                for step in ready_steps:
                    remaining_steps.remove(step)
                    future = executor.submit(step.run, context)
                    futures[future] = step

                # 等待完成
                if futures:
                    done_futures = []
                    for future in futures:
                        if future.done():
                            done_futures.append(future)

                    for future in done_futures:
                        step = futures.pop(future)
                        completed += 1
                        completed_names.add(step.name)

                        # 记录结果
                        context.record_step_result(self._create_step_result(step, context))

                        # 进度回调
                        if progress_callback:
                            progress_callback(step.name, completed, total)

                        # 错误处理
                        if step.status == StepStatus.FAILED:
                            context.error(f"Step '{step.name}' failed in parallel execution")

                    if done_futures:
                        time.sleep(0.1)  # 避免 CPU 忙轮询
                else:
                    if remaining_steps:
                        # 有步骤等待依赖，但无法推进（死锁检测）
                        context.error("Deadlock detected: remaining steps have unmet dependencies")
                        break
                    break

        return context

    def _are_dependencies_met(self, step: Step, completed_names: set) -> bool:
        """检查依赖是否满足"""
        for dep_name in step.config.depends_on:
            if dep_name not in completed_names:
                return False
        return True


class ConditionalExecutor(Executor):
    """
    条件执行器

    根据条件动态决定执行哪些步骤。
    """

    def __init__(
        self,
        condition_func: Callable[[ExecutionContext], List[Step]],
        executor: Optional[Executor] = None,
    ):
        """
        Args:
            condition_func: 条件函数，接收上下文返回要执行的步骤列表
            executor: 底层执行器，默认使用串行执行器
        """
        super().__init__(max_workers=1)
        self.condition_func = condition_func
        self.executor = executor or SerialExecutor()

    def execute(
        self,
        steps: List[Step],
        context: ExecutionContext,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> ExecutionContext:
        # 调用条件函数获取要执行的步骤
        steps_to_run = self.condition_func(context)
        context.log("INFO", f"ConditionalExecutor: selected {len(steps_to_run)} steps to run")

        # 使用底层执行器执行
        return self.executor.execute(steps_to_run, context, progress_callback)


class PipelineExecutor(Executor):
    """
    管道执行器

    将步骤组织为管道，前一步的输出作为后一步的输入。
    """

    def __init__(
        self,
        pipeline: List[Tuple[str, Callable[[Any], Any]]] = None,
        error_strategy: str = "stop",
    ):
        """
        Args:
            pipeline: 管道步骤列表，每个元素为 (name, transform_func)
            error_strategy: 错误策略 ("stop", "skip", "continue")
        """
        super().__init__(max_workers=1)
        self.pipeline = pipeline or []
        self.error_strategy = error_strategy

    def execute(
        self,
        steps: List[Step],
        context: ExecutionContext,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> ExecutionContext:
        # 首先执行所有非管道步骤
        non_pipeline_steps = [s for s in steps if not self._is_pipeline_step(s)]
        context = SerialExecutor().execute(non_pipeline_steps, context, progress_callback)

        # 获取初始数据
        data = context.data.get("_pipeline_input")
        total = len(self.pipeline)

        for i, (name, transform) in enumerate(self.pipeline):
            try:
                context.log("INFO", f"Pipeline step '{name}' started")
                data = transform(data)
                context.data[f"_pipeline_{name}_output"] = data

                if progress_callback:
                    progress_callback(name, i + 1, total)

            except Exception as e:
                context.error(f"Pipeline step '{name}' failed: {str(e)}")
                if self.error_strategy == "stop":
                    break
                elif self.error_strategy == "skip":
                    continue

        context.data["_pipeline_output"] = data
        return context

    def _is_pipeline_step(self, step: Step) -> bool:
        """检查是否为管道步骤"""
        return hasattr(step, '_pipeline_step') and step._pipeline_step
