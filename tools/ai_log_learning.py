#!/usr/bin/env python3
"""
AI助手使用的快速学习记录脚本
简化AI使用self-improving-agent技能的过程
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional


class LearningLogger:
    """学习记录器 - AI助手专用版本"""
    
    def __init__(self, project_root: str = None):
        self.project_root = project_root or os.getcwd()
        self.learnings_dir = Path(self.project_root) / ".learnings"
        
        # 确保目录存在
        self.learnings_dir.mkdir(exist_ok=True)
        
        # 确保文件存在
        for filename in ["LEARNINGS.md", "ERRORS.md", "FEATURE_REQUESTS.md"]:
            filepath = self.learnings_dir / filename
            if not filepath.exists():
                filepath.touch()
    
    def _get_next_id(self, file_path: Path, prefix: str) -> str:
        """获取下一个ID编号"""
        date_str = datetime.now().strftime("%Y%m%d")
        max_num = 0
        
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith(f"## [{prefix}-{date_str}-"):
                        # 提取ID部分
                        id_part = line.split(f"[{prefix}-{date_str}-")[1].split("]")[0]
                        if id_part.isdigit():
                            num = int(id_part)
                            if num > max_num:
                                max_num = num
        
        return f"{max_num + 1:03d}"
    
    def log_learning(
        self,
        summary: str,
        details: str,
        category: str = "best_practice",
        priority: str = "medium",
        area: str = "backend",
        related_files: List[str] = None,
        tags: str = "skill, learning"
    ) -> str:
        """
        记录学习点
        
        Args:
            summary: 一句话总结
            details: 详细描述
            category: 类别 (correction/knowledge_gap/best_practice/insight)
            priority: 优先级 (low/medium/high/critical)
            area: 领域 (frontend/backend/infra/tests/docs/config)
            related_files: 相关文件列表
            tags: 标签
        
        Returns:
            记录ID
        """
        file_path = self.learnings_dir / "LEARNINGS.md"
        prefix = "LRN"
        date_str = datetime.now().strftime("%Y%m%d")
        next_id = self._get_next_id(file_path, prefix)
        
        full_id = f"{prefix}-{date_str}-{next_id}"
        iso_date = datetime.now().isoformat()
        
        # 构建记录内容
        content = f"\n## [{full_id}] {category}\n\n"
        content += f"**Logged**: {iso_date}\n"
        content += f"**Priority**: {priority}\n"
        content += f"**Status**: pending\n"
        content += f"**Area**: {area}\n\n"
        content += f"### Summary\n{summary}\n\n"
        content += f"### Details\n{details}\n\n"
        
        # 添加元数据
        content += "### Metadata\n"
        content += f"- Source: ai_assistant\n"
        if related_files:
            content += f"- Related Files: {', '.join(related_files)}\n"
        content += f"- Tags: {tags}\n\n"
        content += "---\n"
        
        # 写入文件
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ 学习记录已添加: {full_id}")
        print(f"📄 文件: {file_path}")
        
        return full_id
    
    def log_error(
        self,
        summary: str,
        error_message: str,
        context: str,
        tool_name: str = "unknown",
        priority: str = "medium",
        area: str = "backend",
        related_files: List[str] = None,
        fix_suggestion: str = ""
    ) -> str:
        """
        记录错误
        
        Args:
            summary: 错误简要描述
            error_message: 错误信息
            context: 上下文/复现步骤
            tool_name: 工具/命令名称
            priority: 优先级
            area: 领域
            related_files: 相关文件
            fix_suggestion: 修复建议
        
        Returns:
            记录ID
        """
        file_path = self.learnings_dir / "ERRORS.md"
        prefix = "ERR"
        date_str = datetime.now().strftime("%Y%m%d")
        next_id = self._get_next_id(file_path, prefix)
        
        full_id = f"{prefix}-{date_str}-{next_id}"
        iso_date = datetime.now().isoformat()
        
        # 构建记录内容
        content = f"\n## [{full_id}] {tool_name}\n\n"
        content += f"**Logged**: {iso_date}\n"
        content += f"**Priority**: {priority}\n"
        content += f"**Status**: pending\n"
        content += f"**Area**: {area}\n\n"
        content += f"### Summary\n{summary}\n\n"
        content += f"### Error\n```\n{error_message}\n```\n\n"
        content += f"### Context\n{context}\n\n"
        
        if fix_suggestion:
            content += f"### Suggested Fix\n{fix_suggestion}\n\n"
        
        # 添加元数据
        content += "### Metadata\n"
        content += f"- Reproducible: yes\n"
        if related_files:
            content += f"- Related Files: {', '.join(related_files)}\n"
        content += f"- Tags: error, debugging\n\n"
        content += "---\n"
        
        # 写入文件
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ 错误记录已添加: {full_id}")
        print(f"📄 文件: {file_path}")
        
        return full_id
    
    def log_feature_request(
        self,
        capability: str,
        user_context: str,
        priority: str = "medium",
        area: str = "backend",
        complexity: str = "medium",
        implementation: str = ""
    ) -> str:
        """
        记录功能请求
        
        Args:
            capability: 功能描述
            user_context: 用户需求背景
            priority: 优先级
            area: 领域
            complexity: 复杂度 (simple/medium/complex)
            implementation: 实现建议
        
        Returns:
            记录ID
        """
        file_path = self.learnings_dir / "FEATURE_REQUESTS.md"
        prefix = "FEAT"
        date_str = datetime.now().strftime("%Y%m%d")
        next_id = self._get_next_id(file_path, prefix)
        
        full_id = f"{prefix}-{date_str}-{next_id}"
        iso_date = datetime.now().isoformat()
        
        # 构建记录内容
        content = f"\n## [{full_id}] {capability}\n\n"
        content += f"**Logged**: {iso_date}\n"
        content += f"**Priority**: {priority}\n"
        content += f"**Status**: pending\n"
        content += f"**Area**: {area}\n\n"
        content += f"### Requested Capability\n{capability}\n\n"
        content += f"### User Context\n{user_context}\n\n"
        content += f"### Complexity Estimate\n{complexity}\n\n"
        
        if implementation:
            content += f"### Suggested Implementation\n{implementation}\n\n"
        
        # 添加元数据
        content += "### Metadata\n"
        content += f"- Frequency: first_time\n"
        content += f"- Related Features: \n\n"
        content += "---\n"
        
        # 写入文件
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ 功能请求已添加: {full_id}")
        print(f"📄 文件: {file_path}")
        
        return full_id
    
    def get_stats(self) -> Dict[str, Any]:
        """获取学习记录统计信息"""
        stats = {}
        
        for filename, prefix in [
            ("LEARNINGS.md", "LRN"),
            ("ERRORS.md", "ERR"),
            ("FEATURE_REQUESTS.md", "FEAT")
        ]:
            file_path = self.learnings_dir / filename
            if not file_path.exists():
                stats[prefix.lower()] = {"total": 0, "pending": 0, "resolved": 0}
                continue
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            total = content.count(f"## [{prefix}-")
            pending = content.count("**Status**: pending")
            resolved = content.count("**Status**: resolved")
            
            stats[prefix.lower()] = {
                "total": total,
                "pending": pending,
                "resolved": resolved
            }
        
        return stats


def main():
    """命令行入口点"""
    if len(sys.argv) < 2:
        print("用法:")
        print("  python ai_log_learning.py learning <summary> <details>")
        print("  python ai_log_learning.py error <summary> <error> <context>")
        print("  python ai_log_learning.py feature <capability> <context>")
        print("  python ai_log_learning.py stats")
        sys.exit(1)
    
    logger = LearningLogger()
    
    if sys.argv[1] == "stats":
        stats = logger.get_stats()
        print("📊 学习记录统计:")
        print(json.dumps(stats, indent=2, ensure_ascii=False))
    
    elif sys.argv[1] == "learning":
        if len(sys.argv) < 4:
            print("错误: 需要提供summary和details参数")
            sys.exit(1)
        
        summary = sys.argv[2]
        details = sys.argv[3]
        
        # 可选参数
        category = sys.argv[4] if len(sys.argv) > 4 else "best_practice"
        priority = sys.argv[5] if len(sys.argv) > 5 else "medium"
        
        logger.log_learning(summary, details, category, priority)
    
    elif sys.argv[1] == "error":
        if len(sys.argv) < 5:
            print("错误: 需要提供summary、error和context参数")
            sys.exit(1)
        
        summary = sys.argv[2]
        error_msg = sys.argv[3]
        context = sys.argv[4]
        
        logger.log_error(summary, error_msg, context)
    
    elif sys.argv[1] == "feature":
        if len(sys.argv) < 4:
            print("错误: 需要提供capability和context参数")
            sys.exit(1)
        
        capability = sys.argv[2]
        context = sys.argv[3]
        
        logger.log_feature_request(capability, context)


if __name__ == "__main__":
    main()