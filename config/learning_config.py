"""
学习系统配置
集成 self-improving-agent 技能的配置和工具
"""

import os
from pathlib import Path
from datetime import datetime
import json
from typing import Dict, List, Any, Optional


# 学习系统基础配置
class LearningConfig:
    """学习系统配置类"""
    
    # 项目根目录
    PROJECT_ROOT = Path(__file__).parent.parent
    
    # 学习记录目录
    LEARNINGS_DIR = PROJECT_ROOT / ".learnings"
    
    # 学习文件
    LEARNINGS_FILE = LEARNINGS_DIR / "LEARNINGS.md"
    ERRORS_FILE = LEARNINGS_DIR / "ERRORS.md"
    FEATURE_REQUESTS_FILE = LEARNINGS_DIR / "FEATURE_REQUESTS.md"
    
    # 工具脚本路径
    TOOLS_DIR = PROJECT_ROOT / "tools"
    LOG_LEARNING_SCRIPT = TOOLS_DIR / "log_learning.sh"
    AI_LOG_SCRIPT = TOOLS_DIR / "ai_log_learning.py"
    QUICK_LOG_SCRIPT = TOOLS_DIR / "quick_log.sh"
    
    # Claude Hook配置
    CLAUDE_CONFIG_DIR = PROJECT_ROOT / ".claude"
    CLAUDE_SETTINGS_FILE = CLAUDE_CONFIG_DIR / "settings.json"
    
    # 学习系统状态
    ENABLED = True
    AUTO_REMIND = True
    AUTO_ERROR_DETECTION = True
    
    # 记录触发阈值
    MIN_SUMMARY_LENGTH = 10  # 最小总结长度
    MAX_SUMMARY_LENGTH = 200  # 最大总结长度
    MIN_DETAILS_LENGTH = 20  # 最小详情长度
    
    # 自动记录类别
    AUTO_CATEGORIES = [
        "best_practice",
        "knowledge_gap",
        "correction"
    ]
    
    # 监控的关键词（用于自动检测）
    MONITOR_KEYWORDS = {
        "errors": [
            "error:", "Error:", "ERROR:", "failed", "FAILED",
            "Command failed", "Traceback", "Exception",
            "permission denied", "not found", "does not exist"
        ],
        "learnings": [
            "should be", "must be", "important to", "note that",
            "发现", "注意", "重要", "记录", "学习到"
        ],
        "features": [
            "need to", "could you", "can you", "wish",
            "希望", "需要", "想要", "建议添加"
        ]
    }


def ensure_directories():
    """确保所有必要的目录存在"""
    config = LearningConfig
    
    # 创建目录
    config.LEARNINGS_DIR.mkdir(exist_ok=True)
    config.TOOLS_DIR.mkdir(exist_ok=True)
    config.CLAUDE_CONFIG_DIR.mkdir(exist_ok=True)
    
    # 创建文件（如果不存在）
    for filepath in [
        config.LEARNINGS_FILE,
        config.ERRORS_FILE,
        config.FEATURE_REQUESTS_FILE
    ]:
        if not filepath.exists():
            filepath.touch()


def get_learning_stats() -> Dict[str, Any]:
    """获取学习记录统计信息"""
    config = LearningConfig
    
    stats = {
        "learnings": {"total": 0, "pending": 0, "resolved": 0},
        "errors": {"total": 0, "pending": 0, "resolved": 0},
        "features": {"total": 0, "pending": 0}
    }
    
    # 统计学习记录
    if config.LEARNINGS_FILE.exists():
        content = config.LEARNINGS_FILE.read_text()
        stats["learnings"]["total"] = content.count("## [LRN-")
        stats["learnings"]["pending"] = content.count("**Status**: pending")
        stats["learnings"]["resolved"] = content.count("**Status**: resolved")
    
    # 统计错误记录
    if config.ERRORS_FILE.exists():
        content = config.ERRORS_FILE.read_text()
        stats["errors"]["total"] = content.count("## [ERR-")
        stats["errors"]["pending"] = content.count("**Status**: pending")
        stats["errors"]["resolved"] = content.count("**Status**: resolved")
    
    # 统计功能请求
    if config.FEATURE_REQUESTS_FILE.exists():
        content = config.FEATURE_REQUESTS_FILE.read_text()
        stats["features"]["total"] = content.count("## [FEAT-")
        stats["features"]["pending"] = content.count("**Status**: pending")
    
    return stats


def print_stats():
    """打印学习统计信息"""
    stats = get_learning_stats()
    
    print("🧠 学习系统统计")
    print("═" * 40)
    
    print(f"🟢 学习记录: {stats['learnings']['total']} 个")
    print(f"   ├─ 待处理: {stats['learnings']['pending']}")
    print(f"   └─ 已解决: {stats['learnings']['resolved']}")
    
    print(f"🔴 错误记录: {stats['errors']['total']} 个")
    print(f"   ├─ 待处理: {stats['errors']['pending']}")
    print(f"   └─ 已解决: {stats['errors']['resolved']}")
    
    print(f"🔵 功能请求: {stats['features']['total']} 个")
    print(f"   └─ 待处理: {stats['features']['pending']}")
    
    print("═" * 40)


def get_recent_entries(limit: int = 5) -> Dict[str, List[str]]:
    """获取最近的记录条目"""
    config = LearningConfig
    
    entries = {
        "learnings": [],
        "errors": [],
        "features": []
    }
    
    # 读取最近的学习记录
    if config.LEARNINGS_FILE.exists():
        with open(config.LEARNINGS_FILE, 'r') as f:
            lines = f.readlines()
            for i, line in enumerate(reversed(lines)):
                if line.startswith("## [LRN-"):
                    entries["learnings"].append(line.strip()[3:])
                    if len(entries["learnings"]) >= limit:
                        break
    
    # 读取最近的错误记录
    if config.ERRORS_FILE.exists():
        with open(config.ERRORS_FILE, 'r') as f:
            lines = f.readlines()
            for i, line in enumerate(reversed(lines)):
                if line.startswith("## [ERR-"):
                    entries["errors"].append(line.strip()[3:])
                    if len(entries["errors"]) >= limit:
                        break
    
    # 读取最近的功能请求
    if config.FEATURE_REQUESTS_FILE.exists():
        with open(config.FEATURE_REQUESTS_FILE, 'r') as f:
            lines = f.readlines()
            for i, line in enumerate(reversed(lines)):
                if line.startswith("## [FEAT-"):
                    entries["features"].append(line.strip()[3:])
                    if len(entries["features"]) >= limit:
                        break
    
    return entries


def should_record_learning(content: str, category: str) -> bool:
    """判断是否应该记录学习"""
    config = LearningConfig
    
    if not config.ENABLED:
        return False
    
    # 检查内容长度
    if len(content) < config.MIN_SUMMARY_LENGTH:
        return False
    
    if len(content) > config.MAX_SUMMARY_LENGTH:
        return True  # 过长也需要记录，因为可能包含重要信息
    
    # 检查是否在自动记录类别中
    if category not in config.AUTO_CATEGORIES:
        return False
    
    # 检查是否包含监控关键词
    for keyword in config.MONITOR_KEYWORDS["learnings"]:
        if keyword.lower() in content.lower():
            return True
    
    return False


def quick_log_learning(summary: str, details: str = "", category: str = "best_practice"):
    """快速记录学习点（编程方式）"""
    config = LearningConfig
    
    if not config.ENABLED:
        return
    
    # 确保目录存在
    ensure_directories()
    
    # 生成ID
    date_str = datetime.now().strftime("%Y%m%d")
    
    # 获取下一个ID
    next_id = 1
    if config.LEARNINGS_FILE.exists():
        content = config.LEARNINGS_FILE.read_text()
        # 查找现有ID
        import re
        pattern = re.compile(rf"^## \[LRN-{date_str}-(\d{{3}})\]", re.MULTILINE)
        matches = pattern.findall(content)
        if matches:
            max_id = max(int(match) for match in matches)
            next_id = max_id + 1
    
    record_id = f"LRN-{date_str}-{next_id:03d}"
    iso_date = datetime.now().isoformat()
    
    # 构建记录
    record = f"\n## [{record_id}] {category}\n\n"
    record += f"**Logged**: {iso_date}\n"
    record += f"**Priority**: medium\n"
    record += f"**Status**: pending\n"
    record += f"**Area**: backend\n\n"
    record += f"### Summary\n{summary}\n\n"
    
    if details:
        record += f"### Details\n{details}\n\n"
    
    record += "### Metadata\n"
    record += "- Source: python_api\n"
    record += "- Tags: automatic\n\n"
    record += "---\n"
    
    # 写入文件
    with open(config.LEARNINGS_FILE, 'a') as f:
        f.write(record)
    
    return record_id


# 初始化
ensure_directories()


if __name__ == "__main__":
    """测试学习系统"""
    print("🧠 测试学习系统配置")
    print_stats()
    
    # 测试快速记录
    test_id = quick_log_learning(
        "学习系统初始化测试",
        "这是在初始化过程中创建的测试记录。",
        "best_practice"
    )
    
    if test_id:
        print(f"✅ 测试记录已创建: {test_id}")
    
    print_stats()