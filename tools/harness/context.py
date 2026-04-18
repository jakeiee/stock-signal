"""
Harness 执行上下文管理

管理执行过程中的状态、数据传递和结果追踪。
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
import threading


class ExecutionStatus(Enum):
    """执行状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class StepResult:
    """单步执行结果"""
    step_name: str
    status: str  # "success", "failed", "skipped"
    output: Any = None
    error: Optional[str] = None
    duration: float = 0.0  # 耗时（秒）
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "step_name": self.step_name,
            "status": self.status,
            "output": self.output,
            "error": self.error,
            "duration": self.duration,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


class ExecutionContext:
    """
    执行上下文管理器

    管理 Harness 执行过程中的所有状态和数据。
    采用线程安全设计，支持在多步骤间传递数据。
    """

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        self.name = name
        self.config = config or {}
        self.status = ExecutionStatus.PENDING
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None

        # 数据存储（步骤间共享数据）
        self._data: Dict[str, Any] = {}

        # 步骤执行结果
        self._step_results: Dict[str, StepResult] = {}

        # 执行日志
        self._logs: list = []

        # 线程锁
        self._lock = threading.Lock()

    @property
    def data(self) -> Dict[str, Any]:
        """获取共享数据字典"""
        return self._data

    @property
    def step_results(self) -> Dict[str, StepResult]:
        """获取所有步骤结果"""
        return self._step_results

    @property
    def logs(self) -> list:
        """获取执行日志"""
        return self._logs

    def get(self, key: str, default: Any = None) -> Any:
        """获取上下文数据"""
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """设置上下文数据"""
        with self._lock:
            self._data[key] = value

    def has(self, key: str) -> bool:
        """检查数据是否存在"""
        return key in self._data

    def record_step_result(self, result: StepResult) -> None:
        """记录步骤执行结果"""
        with self._lock:
            self._step_results[result.step_name] = result

    def get_step_result(self, step_name: str) -> Optional[StepResult]:
        """获取指定步骤的结果"""
        return self._step_results.get(step_name)

    def log(self, level: str, message: str, **kwargs) -> None:
        """
        记录执行日志

        Args:
            level: 日志级别 (INFO, WARNING, ERROR, DEBUG)
            message: 日志消息
            **kwargs: 附加字段
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message,
            **kwargs
        }
        with self._lock:
            self._logs.append(log_entry)

    def info(self, message: str, **kwargs) -> None:
        """记录 INFO 日志"""
        self.log("INFO", message, **kwargs)

    def warning(self, message: str, **kwargs) -> None:
        """记录 WARNING 日志"""
        self.log("WARNING", message, **kwargs)

    def error(self, message: str, **kwargs) -> None:
        """记录 ERROR 日志"""
        self.log("ERROR", message, **kwargs)

    def debug(self, message: str, **kwargs) -> None:
        """记录 DEBUG 日志"""
        self.log("DEBUG", message, **kwargs)

    def start(self) -> None:
        """标记执行开始"""
        self.status = ExecutionStatus.RUNNING
        self.start_time = datetime.now()
        self.info(f"Harness '{self.name}' started")

    def complete(self, success: bool = True) -> None:
        """
        标记执行完成

        Args:
            success: 是否成功完成
        """
        self.end_time = datetime.now()
        self.status = ExecutionStatus.COMPLETED if success else ExecutionStatus.FAILED

        duration = 0.0
        if self.start_time:
            duration = (self.end_time - self.start_time).total_seconds()

        status_str = "completed" if success else "failed"
        self.info(f"Harness '{self.name}' {status_str}", duration=f"{duration:.2f}s")

    @property
    def duration(self) -> float:
        """获取执行耗时（秒）"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0

    def get_summary(self) -> Dict[str, Any]:
        """获取执行摘要"""
        total_steps = len(self._step_results)
        success_steps = sum(1 for r in self._step_results.values() if r.status == "success")
        failed_steps = sum(1 for r in self._step_results.values() if r.status == "failed")

        return {
            "name": self.name,
            "status": self.status.value,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration": self.duration,
            "total_steps": total_steps,
            "success_steps": success_steps,
            "failed_steps": failed_steps,
            "step_results": [r.to_dict() for r in self._step_results.values()],
            "logs": self._logs,
        }

    def __repr__(self) -> str:
        return f"<ExecutionContext name='{self.name}' status='{self.status.value}' steps={len(self._step_results)}>"
