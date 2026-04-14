#!/usr/bin/env python3
"""
自我改进系统集成模块
为 dividend_monitor 和 market_monitor 提供统一的自动化学习记录功能
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Union

# 导入现有的配置
sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    from config.learning_config import (
        LearningConfig, ensure_directories, 
        get_learning_stats, quick_log_learning
    )
except ImportError:
    # 备用的配置类
    class LearningConfig:
        PROJECT_ROOT = Path(__file__).parent.parent
        LEARNINGS_DIR = PROJECT_ROOT / ".learnings"
        LEARNINGS_FILE = LEARNINGS_DIR / "LEARNINGS.md"
        ERRORS_FILE = LEARNINGS_DIR / "ERRORS.md"


class SelfImprovementTracker:
    """
    自我改进跟踪器
    用于在程序执行过程中自动记录学习点和错误
    """
    
    def __init__(self, module_name: str = "unknown"):
        """
        初始化跟踪器
        
        Args:
            module_name: 模块名称 (如 'dividend_monitor', 'market_monitor')
        """
        self.module_name = module_name
        self.ensure_learning_system()
        
        # 执行统计
        self.total_learnings = 0
        self.total_errors = 0
        self.start_time = datetime.now()
        self.errors: List[Dict] = []
        self.learnings: List[Dict] = []
    
    def ensure_learning_system(self):
        """确保学习系统目录存在"""
        config = LearningConfig
        config.LEARNINGS_DIR.mkdir(exist_ok=True)
        
        for filepath in [
            config.LEARNINGS_FILE,
            config.ERRORS_FILE
        ]:
            if not filepath.exists():
                filepath.touch()
    
    def log_error(
        self,
        error_summary: str,
        error_message: str,
        context: str,
        tool_name: str = "unknown",
        priority: str = "medium",
        fix_suggestion: str = ""
    ) -> str:
        """
        记录错误
        
        Args:
            error_summary: 错误简要描述
            error_message: 错误信息
            context: 上下文/复现步骤
            tool_name: 工具/命令名称
            priority: 优先级
            fix_suggestion: 修复建议
            
        Returns:
            记录ID
        """
        self.total_errors += 1
        
        # 获取下一个ID
        file_path = LearningConfig.ERRORS_FILE
        prefix = "ERR"
        date_str = datetime.now().strftime("%Y%m%d")
        next_id = self._get_next_id(file_path, prefix)
        
        full_id = f"{prefix}-{date_str}-{next_id}"
        iso_date = datetime.now().isoformat()
        
        # 构建记录内容
        content = f"\n## [{full_id}] {tool_name} ({self.module_name})\n\n"
        content += f"**Logged**: {iso_date}\n"
        content += f"**Priority**: {priority}\n"
        content += f"**Status**: pending\n"
        content += f"**Area**: finance_analysis\n\n"
        content += f"### Summary\n{error_summary}\n\n"
        content += f"### Error\n```\n{error_message}\n```\n\n"
        content += f"### Context\n{context}\n\n"
        
        if fix_suggestion:
            content += f"### Suggested Fix\n{fix_suggestion}\n\n"
        
        # 添加元数据
        content += "### Metadata\n"
        content += f"- Module: {self.module_name}\n"
        content += f"- Reproducible: yes\n"
        content += f"- Tags: automatic, error, {self.module_name}\n\n"
        content += "---\n"
        
        # 写入文件
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(content)
        
        # 保存到内存
        self.errors.append({
            "id": full_id,
            "summary": error_summary,
            "context": context,
            "timestamp": iso_date
        })
        
        return full_id
    
    def log_learning(
        self,
        summary: str,
        details: str,
        category: str = "best_practice",
        priority: str = "medium",
        related_files: List[str] = None
    ) -> str:
        """
        记录学习点
        
        Args:
            summary: 一句话总结
            details: 详细描述
            category: 类别
            priority: 优先级
            related_files: 相关文件列表
            
        Returns:
            记录ID
        """
        self.total_learnings += 1
        
        # 获取下一个ID
        file_path = LearningConfig.LEARNINGS_FILE
        prefix = "LRN"
        date_str = datetime.now().strftime("%Y%m%d")
        next_id = self._get_next_id(file_path, prefix)
        
        full_id = f"{prefix}-{date_str}-{next_id}"
        iso_date = datetime.now().isoformat()
        
        # 构建记录内容
        content = f"\n## [{full_id}] {category} ({self.module_name})\n\n"
        content += f"**Logged**: {iso_date}\n"
        content += f"**Priority**: {priority}\n"
        content += f"**Status**: pending\n"
        content += f"**Area**: finance_analysis\n\n"
        content += f"### Summary\n{summary}\n\n"
        content += f"### Details\n{details}\n\n"
        
        # 添加元数据
        content += "### Metadata\n"
        content += f"- Module: {self.module_name}\n"
        content += f"- Source: automatic_tracking\n"
        if related_files:
            content += f"- Related Files: {', '.join(related_files)}\n"
        content += f"- Tags: automatic, learning, {self.module_name}\n\n"
        content += "---\n"
        
        # 写入文件
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(content)
        
        # 保存到内存
        self.learnings.append({
            "id": full_id,
            "summary": summary,
            "category": category,
            "timestamp": iso_date
        })
        
        return full_id
    
    def _get_next_id(self, file_path: Path, prefix: str) -> str:
        """获取下一个ID编号"""
        date_str = datetime.now().strftime("%Y%m%d")
        max_num = 0
        
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith(f"## [{prefix}-{date_str}-"):
                        id_part = line.split(f"[{prefix}-{date_str}-")[1].split("]")[0]
                        if id_part.isdigit():
                            num = int(id_part)
                            if num > max_num:
                                max_num = num
        
        return f"{max_num + 1:03d}"
    
    def monitor_execution(self, func, *args, **kwargs):
        """
        监控函数执行，自动记录错误
        
        Args:
            func: 要执行的函数
            *args: 函数参数
            **kwargs: 函数关键字参数
            
        Returns:
            函数执行结果
        """
        try:
            result = func(*args, **kwargs)
            return result
        except Exception as e:
            # 记录错误
            error_msg = str(e)
            context = f"Function: {func.__name__}\nArgs: {args}\nKwargs: {kwargs}"
            
            self.log_error(
                error_summary=f"执行 {func.__name__} 时发生错误",
                error_message=error_msg,
                context=context,
                tool_name=func.__name__,
                priority="high",
                fix_suggestion=f"检查函数 {func.__name__} 的输入参数和内部逻辑"
            )
            raise
    
    def get_summary(self) -> Dict[str, Any]:
        """
        获取执行摘要
        
        Returns:
            摘要信息字典
        """
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        return {
            "module": self.module_name,
            "start_time": self.start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": duration,
            "total_errors": self.total_errors,
            "total_learnings": self.total_learnings,
            "errors": self.errors,
            "learnings": self.learnings
        }
    
    def print_summary(self):
        """打印执行摘要"""
        summary = self.get_summary()
        
        print("\n" + "="*60)
        print(f"🧠 模块: {summary['module']}")
        print(f"⏱️  开始时间: {summary['start_time']}")
        print(f"⏱️  结束时间: {summary['end_time']}")
        print(f"⏱️  执行时长: {summary['duration_seconds']:.2f} 秒")
        print("-"*60)
        print(f"🔴 记录错误数: {summary['total_errors']}")
        print(f"🟢 记录学习数: {summary['total_learnings']}")
        print("="*60)
        
        # 打印最近的错误
        if summary['errors']:
            print("\n📋 本次执行的错误记录:")
            for error in summary['errors'][-3:]:  # 显示最后3个
                print(f"  ❌ {error['id']}: {error['summary']}")
        
        # 打印最近的学习
        if summary['learnings']:
            print("\n📋 本次执行的学习记录:")
            for learning in summary['learnings'][-3:]:  # 显示最后3个
                print(f"  ✅ {learning['id']}: {learning['summary']}")
        
        # 显示系统总体统计
        try:
            from config.learning_config import get_learning_stats
            
            overall_stats = get_learning_stats()
            print("\n📊 系统总体统计:")
            print(f"  🔴 总错误记录: {overall_stats['errors']['total']} 个")
            print(f"  🟢 总学习记录: {overall_stats['learnings']['total']} 个")
            print(f"  🔵 总功能请求: {overall_stats['features']['total']} 个")
        except ImportError:
            print("\n📊 注意: 无法加载完整的学习统计信息")
        
        print("="*60)


# 装饰器版本
def track_execution(module_name: str = "unknown"):
    """
    跟踪函数执行的装饰器
    
    Args:
        module_name: 模块名称
        
    Returns:
        装饰器函数
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            tracker = SelfImprovementTracker(module_name)
            
            try:
                result = tracker.monitor_execution(func, *args, **kwargs)
                return result
            finally:
                # 无论是否发生错误都打印摘要
                tracker.print_summary()
        
        return wrapper
    return decorator


# 集成函数，方便导入
def get_tracker(module_name: str) -> SelfImprovementTracker:
    """获取跟踪器实例"""
    return SelfImprovementTracker(module_name)


def show_system_stats():
    """显示整个系统的统计信息"""
    try:
        from config.learning_config import print_stats
        print_stats()
    except ImportError:
        # 简单版本
        config = LearningConfig
        
        errors = 0
        learnings = 0
        
        if config.ERRORS_FILE.exists():
            with open(config.ERRORS_FILE, 'r') as f:
                errors = f.read().count("## [ERR-")
        
        if config.LEARNINGS_FILE.exists():
            with open(config.LEARNINGS_FILE, 'r') as f:
                learnings = f.read().count("## [LRN-")
        
        print("🧠 学习系统统计")
        print("═" * 40)
        print(f"🔴 总错误记录: {errors} 个")
        print(f"🟢 总学习记录: {learnings} 个")
        print("═" * 40)


def main():
    """测试函数"""
    print("测试自我改进系统集成")
    
    # 测试跟踪器
    tracker = SelfImprovementTracker("test_module")
    
    # 记录一些测试数据
    tracker.log_learning(
        summary="测试学习记录系统集成",
        details="通过专门的集成模块将 self-improving-agent 技能集成到金融分析模块中。",
        category="best_practice"
    )
    
    tracker.log_error(
        error_summary="测试错误记录",
        error_message="This is a test error message",
        context="Test context for error logging",
        tool_name="test_function",
        fix_suggestion="Check test configuration"
    )
    
    tracker.print_summary()
    
    # 显示总体统计
    show_system_stats()


if __name__ == "__main__":
    main()