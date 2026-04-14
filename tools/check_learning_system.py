#!/usr/bin/env python3
"""
检查学习系统工具
在主程序启动前运行，检查学习系统状态
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from config.learning_config import LearningConfig, print_stats, get_learning_stats
except ImportError:
    # 如果导入失败，创建基本的学习系统
    class LearningConfig:
        PROJECT_ROOT = project_root
        LEARNINGS_DIR = project_root / ".learnings"
        ENABLED = True
    
    print_stats = lambda: print("⚠️ 学习系统配置模块未找到")
    get_learning_stats = lambda: {}


def check_learning_system():
    """检查学习系统状态"""
    print("\n🧠 Self-Improvement Learning System")
    print("─────────────────────────────────────")
    
    # 检查目录和文件
    config = LearningConfig
    issues = []
    
    # 检查学习目录
    if not config.LEARNINGS_DIR.exists():
        issues.append("❌ 学习目录不存在: .learnings/")
    else:
        print(f"✅ 学习目录: {config.LEARNINGS_DIR}")
    
    # 检查主要文件
    for name, filepath in [
        ("学习记录", config.LEARNINGS_FILE),
        ("错误记录", config.ERRORS_FILE),
        ("功能请求", config.FEATURE_REQUESTS_FILE)
    ]:
        if filepath.exists():
            print(f"✅ {name}: {filepath.name}")
        else:
            issues.append(f"❌ {name}文件不存在: {filepath.name}")
    
    # 检查工具脚本
    print("\n🛠️  工具脚本:")
    for name, script_path in [
        ("交互式记录", config.LOG_LEARNING_SCRIPT),
        ("AI快速记录", config.AI_LOG_SCRIPT),
        ("快速记录", config.QUICK_LOG_SCRIPT)
    ]:
        if hasattr(config, script_path.__class__.__name__):
            if script_path.exists():
                print(f"  ✅ {name}: {script_path.name}")
            else:
                print(f"  ⚠️  {name}: 未找到")
    
    # 检查Claude配置
    print("\n🤖 Claude配置:")
    if config.CLAUDE_CONFIG_DIR.exists():
        print(f"  ✅ Claude配置目录: .claude/")
        
        if config.CLAUDE_SETTINGS_FILE.exists():
            print(f"  ✅ Hook配置文件: settings.json")
        else:
            issues.append("❌ Claude Hook配置文件不存在: .claude/settings.json")
    else:
        issues.append("❌ Claude配置目录不存在: .claude/")
    
    # 打印统计信息
    try:
        stats = get_learning_stats()
        if stats:
            print("\n📊 当前统计:")
            print(f"  🟢 学习记录: {stats.get('learnings', {}).get('total', 0)} 个")
            print(f"  🔴 错误记录: {stats.get('errors', {}).get('total', 0)} 个")
            print(f"  🔵 功能请求: {stats.get('features', {}).get('total', 0)} 个")
    except:
        print_stats()
    
    # 显示提醒
    print("\n💡 使用提醒:")
    print("  1. 使用 tools/log_learning.sh 交互式记录")
    print("  2. 使用 tools/quick_log.sh <command> 快速记录")
    print("  3. 定期检查 .learnings/ 目录")
    print("  4. AI助手会自动收到记录提醒")
    
    # 如果有问题，显示解决方案
    if issues:
        print("\n⚠️  需要解决的问题:")
        for issue in issues:
            print(f"  {issue}")
        
        print("\n🔧 建议修复:")
        print("  1. 运行: python config/learning_config.py 初始化系统")
        print("  2. 运行: tools/log_learning.sh 手动创建记录")
    
    print("\n✅ 学习系统检查完成")
    return len(issues) == 0


if __name__ == "__main__":
    import os
    os.chdir(project_root)
    success = check_learning_system()
    sys.exit(0 if success else 1)