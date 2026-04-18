"""
Harness 步骤注册表

支持步骤类型注册和动态创建。
"""

from typing import Any, Callable, Dict, Optional, Type
from functools import wraps

from .step import Step, StepConfig


class StepRegistry:
    """
    步骤类型注册表

    允许注册步骤类型并通过名称创建步骤实例。
    """

    def __init__(self):
        self._registry: Dict[str, Type[Step]] = {}
        self._factories: Dict[str, Callable] = {}

    def register(self, name: str, step_class: Type[Step]) -> None:
        """
        注册步骤类型

        Args:
            name: 步骤名称
            step_class: 步骤类
        """
        self._registry[name] = step_class

    def register_factory(self, name: str, factory: Callable[..., Step]) -> None:
        """
        注册步骤工厂函数

        Args:
            name: 步骤名称
            factory: 工厂函数
        """
        self._factories[name] = factory

    def create(self, name: str, **kwargs) -> Step:
        """
        创建步骤实例

        Args:
            name: 步骤名称
            **kwargs: 传递给步骤构造函数的参数

        Returns:
            步骤实例

        Raises:
            ValueError: 如果步骤类型未注册
        """
        if name in self._factories:
            return self._factories[name](**kwargs)

        if name in self._registry:
            return self._registry[name](**kwargs)

        raise ValueError(f"Step type '{name}' not registered")

    def get(self, name: str) -> Optional[Type[Step]]:
        """获取注册的步骤类型"""
        return self._registry.get(name)

    def list_types(self) -> list:
        """列出所有注册的步骤类型"""
        return list(set(self._registry.keys()) | set(self._factories.keys()))

    def __contains__(self, name: str) -> bool:
        return name in self._registry or name in self._factories


# 全局注册表
_global_registry = StepRegistry()


def register_step(name: str) -> Callable:
    """
    步骤注册装饰器

    用于注册步骤类到全局注册表。

    Example:
        @register_step("fetch_data")
        class FetchDataStep(Step):
            ...
    """
    def decorator(step_class: Type[Step]) -> Type[Step]:
        _global_registry.register(name, step_class)

        @wraps(step_class)
        def wrapper(*args, **kwargs) -> Step:
            return step_class(*args, **kwargs)

        wrapper.__name__ = step_class.__name__
        wrapper._step_name = name
        return wrapper

    return decorator


def get_registry() -> StepRegistry:
    """获取全局注册表"""
    return _global_registry


def create_step(name: str, **kwargs) -> Step:
    """从全局注册表创建步骤"""
    return _global_registry.create(name, **kwargs)
