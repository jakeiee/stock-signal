"""
标准模块接口定义
所有模块必须实现BaseModule接口
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from pathlib import Path


@dataclass
class ModuleMetadata:
    """模块元数据"""
    name: str  # 模块名称
    version: str  # 版本号
    description: str  # 描述
    author: str = ""  # 作者
    dependencies: List[str] = field(default_factory=list)  # 依赖模块
    tags: List[str] = field(default_factory=list)  # 标签


@dataclass
class StepResult:
    """步骤执行结果"""
    success: bool  # 是否成功
    data: Any = None  # 返回数据
    error: str = ""  # 错误信息
    duration: float = 0.0  # 执行时长（秒）


class Step(ABC):
    """步骤基类"""

    @abstractmethod
    def execute(self, context: Dict[str, Any]) -> StepResult:
        """执行步骤"""
        pass

    @abstractmethod
    def get_name(self) -> str:
        """获取步骤名称"""
        pass


class BaseModule(ABC):
    """标准模块接口"""

    @abstractmethod
    def get_metadata(self) -> ModuleMetadata:
        """获取模块元数据"""
        pass

    @abstractmethod
    def get_steps(self) -> List[Step]:
        """获取模块步骤列表"""
        pass

    @abstractmethod
    def validate_config(self) -> bool:
        """验证模块配置"""
        pass

    @abstractmethod
    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """运行模块"""
        pass

    def initialize(self) -> bool:
        """初始化模块（可选实现）"""
        return True

    def cleanup(self) -> bool:
        """清理模块资源（可选实现）"""
        return True

    def health_check(self) -> bool:
        """健康检查（可选实现）"""
        return True
