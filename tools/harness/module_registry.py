"""
模块自注册机制
自动发现和注册模块
"""

import importlib
import pkgutil
from pathlib import Path
from typing import Dict, List, Type, Any
from .module_interface import BaseModule, ModuleMetadata


class ModuleRegistry:
    """模块注册表（单例模式）"""

    _instance = None
    _modules: Dict[str, BaseModule] = {}
    _metadata: Dict[str, ModuleMetadata] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_instance(cls) -> 'ModuleRegistry':
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = ModuleRegistry()
        return cls._instance

    def register(self, module: BaseModule) -> None:
        """
        注册模块

        Args:
            module: 模块实例
        """
        metadata = module.get_metadata()
        self._modules[metadata.name] = module
        self._metadata[metadata.name] = metadata
        print(f"  ✓ 注册模块：{metadata.name} v{metadata.version}")

    def unregister(self, module_name: str) -> bool:
        """
        取消注册模块

        Args:
            module_name: 模块名称

        Returns:
            是否成功
        """
        if module_name in self._modules:
            del self._modules[module_name]
            del self._metadata[module_name]
            print(f"  ✓ 取消注册模块：{module_name}")
            return True
        return False

    def get_module(self, module_name: str) -> BaseModule:
        """
        获取模块实例

        Args:
            module_name: 模块名称

        Returns:
            模块实例

        Raises:
            ValueError: 如果模块未注册
        """
        if module_name not in self._modules:
            raise ValueError(f"Module '{module_name}' not registered")
        return self._modules[module_name]

    def get_metadata(self, module_name: str) -> ModuleMetadata:
        """
        获取模块元数据

        Args:
            module_name: 模块名称

        Returns:
            模块元数据

        Raises:
            ValueError: 如果模块未注册
        """
        if module_name not in self._metadata:
            raise ValueError(f"Module '{module_name}' not registered")
        return self._metadata[module_name]

    def list_modules(self) -> List[str]:
        """列出所有注册的模块名称"""
        return list(self._modules.keys())

    def list_metadata(self) -> List[ModuleMetadata]:
        """列出所有注册的模块元数据"""
        return list(self._metadata.values())

    def auto_discover(self, search_paths: List[Path] = None) -> None:
        """
        自动发现模块
        
        Args:
            search_paths: 搜索路径列表，默认为['dividend_monitor', 'market_monitor', 'portfolio']
        """
        if search_paths is None:
            # 默认搜索路径（项目根目录）
            project_root = Path(__file__).parent.parent.parent
            search_paths = [
                project_root / 'dividend_monitor',
                project_root / 'market_monitor',
                project_root / 'portfolio'
            ]

        print("开始自动发现模块...")

        for search_path in search_paths:
            if not search_path.exists():
                print(f"  ⚠ 路径不存在：{search_path}")
                continue

            # 遍历路径下的所有模块
            for importer, modname, ispkg in pkgutil.iter_modules([str(search_path)]):
                try:
                    # 导入模块
                    module_path = f"{search_path.name}.{modname}"
                    module = importlib.import_module(module_path)

                    # 查找BaseModule的子类
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (isinstance(attr, type) and
                            issubclass(attr, BaseModule) and
                            attr != BaseModule):
                            # 实例化并注册
                            instance = attr()
                            self.register(instance)
                except Exception as e:
                    print(f"  ✗ 发现模块失败：{modname}，错误：{e}")

        print(f"自动发现完成，共注册 {len(self._modules)} 个模块")

    def health_check_all(self) -> Dict[str, bool]:
        """
        健康检查所有模块

        Returns:
            模块名称 -> 健康状态 的字典
        """
        results = {}
        for name, module in self._modules.items():
            try:
                results[name] = module.health_check()
            except Exception as e:
                print(f"  ✗ 健康检查失败：{name}，错误：{e}")
                results[name] = False
        return results

    def initialize_all(self) -> Dict[str, bool]:
        """
        初始化所有模块

        Returns:
            模块名称 -> 初始化状态 的字典
        """
        results = {}
        for name, module in self._modules.items():
            try:
                results[name] = module.initialize()
            except Exception as e:
                print(f"  ✗ 初始化失败：{name}，错误：{e}")
                results[name] = False
        return results

    def cleanup_all(self) -> Dict[str, bool]:
        """
        清理所有模块资源

        Returns:
            模块名称 -> 清理状态 的字典
        """
        results = {}
        for name, module in self._modules.items():
            try:
                results[name] = module.cleanup()
            except Exception as e:
                print(f"  ✗ 清理失败：{name}，错误：{e}")
                results[name] = False
        return results


# 全局模块注册表
_global_module_registry = None


def get_module_registry() -> ModuleRegistry:
    """获取全局模块注册表"""
    global _global_module_registry
    if _global_module_registry is None:
        _global_module_registry = ModuleRegistry.get_instance()
    return _global_module_registry


def register_module(module: BaseModule) -> None:
    """注册模块到全局注册表"""
    registry = get_module_registry()
    registry.register(module)


def auto_discover_modules(search_paths: List[Path] = None) -> None:
    """自动发现模块并注册到全局注册表"""
    registry = get_module_registry()
    registry.auto_discover(search_paths)


def health_check_all_modules() -> Dict[str, bool]:
    """健康检查所有模块"""
    registry = get_module_registry()
    return registry.health_check_all()
