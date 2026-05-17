#!/usr/bin/env python3
"""
修改影响分析工具
分析代码修改的影响范围，评估风险等级
"""

import os
import re
import ast
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional


# 风险等级
class RiskLevel:
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ImpactAnalyzer:
    """修改影响分析器"""

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.python_files: List[Path] = []
        self.import_graph: Dict[str, Set[str]] = {}
        self.function_calls: Dict[str, Set[str]] = {}

    def scan_project(self) -> None:
        """扫描项目，构建依赖图"""
        print("🔍 扫描项目文件...")

        # 收集所有Python文件
        for root, dirs, files in os.walk(self.project_root):
            # 跳过某些目录
            dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', '.pytest_cache', 'node_modules']]

            for file in files:
                if file.endswith('.py'):
                    self.python_files.append(Path(root) / file)

        print(f"  ✓ 发现 {len(self.python_files)} 个 Python 文件")

        # 构建导入图
        self._build_import_graph()

        # 构建函数调用图
        self._build_function_call_graph()

    def _build_import_graph(self) -> None:
        """构建模块导入图"""
        for file_path in self.python_files:
            module_name = self._get_module_name(file_path)
            self.import_graph[module_name] = set()

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # 使用AST解析导入语句
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            self.import_graph[module_name].add(alias.name)
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            self.import_graph[module_name].add(node.module)
            except Exception as e:
                print(f"  ⚠ 解析 {file_path} 失败: {e}")

        print(f"  ✓ 导入图构建完成")

    def _build_function_call_graph(self) -> None:
        """构建函数调用图（简化版）"""
        # 这里简化实现，只记录每个文件定义了哪些函数/类
        for file_path in self.python_files:
            module_name = self._get_module_name(file_path)

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                tree = ast.parse(content)
                defined = set()
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef) or isinstance(node, ast.ClassDef):
                        defined.add(node.name)

                self.function_calls[module_name] = defined
            except Exception:
                self.function_calls[module_name] = set()

        print(f"  ✓ 函数调用图构建完成")

    def _get_module_name(self, file_path: Path) -> str:
        """获取模块名称"""
        rel_path = file_path.relative_to(self.project_root)
        module_parts = rel_path.with_suffix('').parts
        return '.'.join(module_parts)

    def analyze_file(self, file_path: str) -> Dict:
        """
        分析单个文件修改的影响

        Args:
            file_path: 文件路径

        Returns:
            分析结果字典
        """
        file_path = Path(file_path)
        if not file_path.exists():
            return {"error": f"文件不存在: {file_path}"}

        module_name = self._get_module_name(file_path)

        # 评估风险等级
        risk_level = self._assess_risk(file_path)

        # 查找依赖于此模块的其他模块
        dependents = self._find_dependents(module_name)

        # 查找此模块依赖的其他模块
        dependencies = self.import_graph.get(module_name, set())

        # 查找定义的函数/类
        defined = self.function_calls.get(module_name, set())

        result = {
            "file": str(file_path),
            "module": module_name,
            "risk_level": risk_level,
            "dependents": list(dependents),
            "dependencies": list(dependencies),
            "defined": list(defined),
            "recommendation": self._get_recommendation(risk_level, file_path)
        }

        return result

    def _assess_risk(self, file_path: Path) -> str:
        """评估风险等级"""
        path_str = str(file_path)

        # HIGH: 核心模块（analysis/, report/, data_sources/）
        if any(x in path_str for x in ['/analysis/', '/report/', '/data_sources/']):
            return RiskLevel.HIGH

        # MEDIUM: 配置文件、工具脚本
        if any(x in path_str for x in ['config.py', 'tools/', 'utils/']):
            return RiskLevel.MEDIUM

        # LOW: 文档、测试
        if any(x in path_str for x in ['test_', 'README', 'docs/']):
            return RiskLevel.LOW

        # 默认MEDIUM
        return RiskLevel.MEDIUM

    def _find_dependents(self, module_name: str) -> Set[str]:
        """查找依赖于此模块的其他模块"""
        dependents = set()
        for mod, imports in self.import_graph.items():
            # 检查是否导入了目标模块
            if module_name in imports or any(imp.endswith(module_name) for imp in imports):
                dependents.add(mod)
        return dependents

    def _get_recommendation(self, risk_level: str, file_path: Path) -> str:
        """获取修改建议"""
        if risk_level == RiskLevel.HIGH:
            return f"⚠️ 高风险修改！必须先运行测试：python -m pytest tests/ -v"
        elif risk_level == RiskLevel.MEDIUM:
            return "⚠️ 中风险修改，建议运行相关测试"
        else:
            return "✅ 低风险修改，可以直接修改"

    def print_analysis(self, analysis: Dict) -> None:
        """打印分析结果"""
        print("=" * 60)
        print("修改影响分析")
        print("=" * 60)

        if "error" in analysis:
            print(f"✗ 错误: {analysis['error']}")
            return

        print(f"\n📄 文件: {analysis['file']}")
        print(f"📦 模块: {analysis['module']}")

        risk_emoji = {
            RiskLevel.HIGH: "🔴",
            RiskLevel.MEDIUM: "🟡",
            RiskLevel.LOW: "🟢"
        }
        print(f"🚨 风险等级: {risk_emoji.get(analysis['risk_level'], '⚪')} {analysis['risk_level']}")

        if analysis['dependents']:
            print(f"\n📦 依赖于此模块的模块 ({len(analysis['dependents'])}个):")
            for dep in analysis['dependents'][:5]:  # 只显示前5个
                print(f"  - {dep}")
            if len(analysis['dependents']) > 5:
                print(f"  ... 还有 {len(analysis['dependents']) - 5} 个")

        if analysis['defined']:
            print(f"\n🔧 定义的函数/类 ({len(analysis['defined'])}个):")
            for def_item in list(analysis['defined'])[:5]:  # 只显示前5个
                print(f"  - {def_item}")
            if len(analysis['defined']) > 5:
                print(f"  ... 还有 {len(analysis['defined']) - 5} 个")

        print(f"\n💡 建议: {analysis['recommendation']}")
        print("=" * 60)


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python safe_edit.py <file_path>")
        print("\n示例:")
        print("  python tools/safe_edit.py dividend_monitor/analysis/valuation.py")
        sys.exit(1)

    file_path = sys.argv[1]

    # 创建分析器
    analyzer = ImpactAnalyzer(project_root=".")

    # 扫描项目
    analyzer.scan_project()

    # 分析文件
    analysis = analyzer.analyze_file(file_path)

    # 打印结果
    analyzer.print_analysis(analysis)


if __name__ == "__main__":
    main()
