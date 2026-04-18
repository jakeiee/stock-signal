"""
Harness 与 .learnings/ 目录集成

自动记录执行日志、错误和经验教训。
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import os

from .context import ExecutionContext


class MemoryBridge:
    """
    记忆桥接器

    将 Harness 执行过程中的关键信息同步到 .learnings/ 目录。
    """

    def __init__(self, workspace_path: str = None):
        """
        Args:
            workspace_path: 工作区路径，默认使用当前目录
        """
        self.workspace_path = Path(workspace_path) if workspace_path else Path.cwd()
        self.learnings_dir = self.workspace_path / ".learnings"
        self.errors_file = self.learnings_dir / "ERRORS.md"
        self.learnings_file = self.learnings_dir / "LEARNINGS.md"

        # 确保目录存在
        self._ensure_learnings_dir()

    def _ensure_learnings_dir(self) -> None:
        """确保 .learnings 目录存在"""
        self.learnings_dir.mkdir(exist_ok=True)

        # 初始化文件
        if not self.errors_file.exists():
            self.errors_file.write_text("# 错误记录\n\n记录执行过程中遇到的错误和解决方案。\n\n")
        if not self.learnings_file.exists():
            self.learnings_file.write_text("# 经验积累\n\n记录成功和失败的执行经验。\n\n")

    def record_error(
        self,
        step_name: str,
        error: str,
        context: ExecutionContext,
        solution: Optional[str] = None,
    ) -> None:
        """
        记录错误信息

        Args:
            step_name: 步骤名称
            error: 错误描述
            context: 执行上下文
            solution: 解决方案（如果有）
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        entry = f"""## [{timestamp}] {step_name}

**错误**: {error}

**上下文**: {context.name}

**配置**: {json.dumps(context.config, ensure_ascii=False, indent=2)}

"""

        if solution:
            entry += f"**解决方案**: {solution}\n"

        entry += "\n---\n\n"

        # 追加到文件
        with open(self.errors_file, "a", encoding="utf-8") as f:
            f.write(entry)

    def record_learning(
        self,
        category: str,
        title: str,
        content: str,
        tags: Optional[List[str]] = None,
    ) -> None:
        """
        记录经验教训

        Args:
            category: 分类（如 "数据获取", "分析", "报告"）
            title: 标题
            content: 内容
            tags: 标签
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tags_str = ", ".join(tags) if tags else ""

        entry = f"""## [{timestamp}] {title}

**分类**: {category}

{tags_str}

{content}

---
"""

        # 追加到文件
        with open(self.learnings_file, "a", encoding="utf-8") as f:
            f.write(entry)

    def record_execution(self, context: ExecutionContext) -> None:
        """
        记录完整执行结果

        分析执行上下文，提取关键信息记录到经验库。
        """
        # 分析失败的步骤
        for step_name, result in context.step_results.items():
            if result.status == "failed":
                self.record_error(
                    step_name=step_name,
                    error=result.error or "Unknown error",
                    context=context,
                )

                # 提取解决方案建议
                self._suggest_solution(step_name, result, context)

        # 记录成功执行的经验
        if context.status.value == "completed":
            self._record_success_patterns(context)

    def _suggest_solution(
        self,
        step_name: str,
        result: 'StepResult',
        context: ExecutionContext,
    ) -> None:
        """根据错误类型建议解决方案"""
        error = result.error or ""

        # 简单的规则匹配
        if "timeout" in error.lower():
            solution = "考虑增加超时时间或检查数据源响应"
        elif "connection" in error.lower() or "network" in error.lower():
            solution = "检查网络连接或数据源可用性"
        elif "parse" in error.lower() or "format" in error.lower():
            solution = "检查数据格式是否发生变化"
        elif "auth" in error.lower() or "permission" in error.lower():
            solution = "检查认证凭证和权限配置"
        else:
            solution = "需要进一步调查根本原因"

        self.record_learning(
            category="问题排查",
            title=f"步骤 {step_name} 常见错误处理",
            content=f"错误: {error}\n\n建议方案: {solution}",
        )

    def _record_success_patterns(self, context: ExecutionContext) -> None:
        """记录成功的执行模式"""
        duration = context.duration
        success_count = sum(
            1 for r in context.step_results.values()
            if r.status == "success"
        )

        self.record_learning(
            category="执行统计",
            title=f"{context.name} 执行成功",
            content=f"总步骤数: {len(context.step_results)}\n"
                    f"成功步骤: {success_count}\n"
                    f"执行耗时: {duration:.2f}秒",
            tags=["执行记录"],
        )

    def get_recent_errors(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近的错误记录"""
        if not self.errors_file.exists():
            return []

        content = self.errors_file.read_text(encoding="utf-8")

        # 简单解析（提取最后 N 条）
        entries = content.split("---")
        recent = []

        for entry in entries[-limit-1:-1]:
            if entry.strip():
                recent.append({"content": entry.strip()})

        return recent

    def export_json(self, output_path: str) -> None:
        """
        导出学习数据为 JSON

        Args:
            output_path: 输出路径
        """
        data = {
            "errors": self.errors_file.read_text(encoding="utf-8") if self.errors_file.exists() else "",
            "learnings": self.learnings_file.read_text(encoding="utf-8") if self.learnings_file.exists() else "",
            "exported_at": datetime.now().isoformat(),
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
