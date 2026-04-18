"""
Harness Step 抽象基类

定义所有执行步骤的接口和行为规范。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type
import time


class StepStatus(Enum):
    """步骤状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"


@dataclass
class StepConfig:
    """步骤配置"""
    # 重试配置
    max_retries: int = 0  # 最大重试次数
    retry_delay: float = 1.0  # 重试间隔（秒）

    # 条件执行
    skip_if: Optional[Callable[[Dict[str, Any]], bool]] = None  # 跳过条件

    # 依赖配置
    depends_on: List[str] = field(default_factory=list)  # 依赖的步骤名称

    # 超时配置
    timeout: Optional[float] = None  # 超时时间（秒）

    # 错误处理
    continue_on_error: bool = False  # 出错后是否继续

    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)


class Step(ABC):
    """
    步骤抽象基类

    所有执行步骤都应继承此类并实现 execute 方法。
    """

    # 类属性：步骤名称（子类可覆盖）
    name: str = "BaseStep"

    def __init__(self, config: Optional[StepConfig] = None):
        self.config = config or StepConfig()
        self._status = StepStatus.PENDING
        self._start_time: Optional[float] = None
        self._end_time: Optional[float] = None
        self._error: Optional[Exception] = None
        self._retry_count = 0
        self._output: Any = None

    @property
    def status(self) -> StepStatus:
        """获取当前状态"""
        return self._status

    @property
    def error(self) -> Optional[Exception]:
        """获取错误信息"""
        return self._error

    @property
    def output(self) -> Any:
        """获取执行输出"""
        return self._output

    @property
    def duration(self) -> float:
        """获取执行耗时（秒）"""
        if self._start_time and self._end_time:
            return self._end_time - self._start_time
        return 0.0

    @property
    def retry_count(self) -> int:
        """获取重试次数"""
        return self._retry_count

    def can_skip(self, context_data: Dict[str, Any]) -> bool:
        """
        检查是否应该跳过此步骤

        Args:
            context_data: 上下文数据

        Returns:
            是否跳过
        """
        if self.config.skip_if:
            try:
                return self.config.skip_if(context_data)
            except Exception:
                return False
        return False

    def should_retry(self) -> bool:
        """
        检查是否应该重试

        Returns:
            是否应该重试
        """
        if self._retry_count < self.config.max_retries:
            return True
        return False

    def _sleep_before_retry(self) -> None:
        """重试前等待"""
        if self.config.retry_delay > 0:
            time.sleep(self.config.retry_delay)

    @abstractmethod
    def validate(self) -> bool:
        """
        验证步骤配置是否正确

        Returns:
            是否有效
        """
        pass

    @abstractmethod
    def execute(self, context: 'ExecutionContext') -> Any:
        """
        执行步骤逻辑

        Args:
            context: 执行上下文

        Returns:
            步骤输出（将存储到上下文中）
        """
        pass

    def before_execute(self, context: 'ExecutionContext') -> None:
        """
        执行前的钩子方法

        子类可重写此方法实现执行前逻辑
        """
        pass

    def after_execute(self, context: 'ExecutionContext', output: Any) -> Any:
        """
        执行后的钩子方法

        子类可重写此方法实现执行后逻辑

        Args:
            context: 执行上下文
            output: 执行输出

        Returns:
            处理后的输出
        """
        return output

    def on_error(self, context: 'ExecutionContext', error: Exception) -> None:
        """
        错误处理钩子

        子类可重写此方法实现自定义错误处理

        Args:
            context: 执行上下文
            error: 异常对象
        """
        self._error = error

    def run(self, context: 'ExecutionContext') -> 'Step':
        """
        运行步骤（包含完整的生命周期）

        包括：验证 -> 跳过检查 -> 执行 -> 错误处理

        Args:
            context: 执行上下文

        Returns:
            self（支持链式调用）
        """
        # 检查是否应该跳过
        if self.can_skip(context.data):
            self._status = StepStatus.SKIPPED
            context.log("INFO", f"Step '{self.name}' skipped")
            return self

        # 记录开始
        self._status = StepStatus.RUNNING
        self._start_time = time.time()
        context.log("INFO", f"Step '{self.name}' started")

        try:
            # 执行前钩子
            self.before_execute(context)

            # 执行
            output = self.execute(context)

            # 执行后钩子
            output = self.after_execute(context, output)

            # 保存输出
            self._output = output
            self._status = StepStatus.SUCCESS
            context.log("INFO", f"Step '{self.name}' completed successfully")

        except Exception as e:
            # 错误处理
            self._error = e
            context.log("ERROR", f"Step '{self.name}' failed: {str(e)}")
            self.on_error(context, e)

            # 检查是否重试
            if self.should_retry():
                self._retry_count += 1
                self._status = StepStatus.RETRYING
                context.log("WARNING", f"Step '{self.name}' retrying ({self._retry_count}/{self.config.max_retries})")
                self._sleep_before_retry()
                return self.run(context)  # 递归重试

            self._status = StepStatus.FAILED

        finally:
            self._end_time = time.time()

        return self

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name='{self.name}' status='{self._status.value}'>"


class FunctionalStep(Step):
    """
    函数式步骤

    使用简单函数作为步骤实现，无需创建子类。
    """

    def __init__(
        self,
        name: str,
        func: Callable[[Dict[str, Any]], Any],
        config: Optional[StepConfig] = None,
    ):
        super().__init__(config)
        self.name = name
        self._func = func

    def validate(self) -> bool:
        return self._func is not None

    def execute(self, context: 'ExecutionContext') -> Any:
        return self._func(context)


def step(
    name: Optional[str] = None,
    max_retries: int = 0,
    retry_delay: float = 1.0,
    timeout: Optional[float] = None,
    continue_on_error: bool = False,
    depends_on: Optional[List[str]] = None,
) -> Callable:
    """
    步骤装饰器

    用于将普通函数包装为 Step

    Example:
        @step(name="fetch_data", max_retries=3)
        def fetch_data(context):
            return fetch_from_api()
    """
    def decorator(func: Callable) -> FunctionalStep:
        config = StepConfig(
            max_retries=max_retries,
            retry_delay=retry_delay,
            timeout=timeout,
            continue_on_error=continue_on_error,
            depends_on=depends_on or [],
        )
        step_name = name or func.__name__
        return FunctionalStep(step_name, func, config)
    return decorator
