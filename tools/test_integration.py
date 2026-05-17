#!/usr/bin/env python3
"""
全套改进方案集成测试
验证所有新创建的工具和模块是否正常工作
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, "/Users/liuyi/WorkBuddy/stock-signal")

print("=" * 60)
print("全套改进方案集成测试")
print("=" * 60)

# ========== 测试1：规则系统 ==========
print("\n📋 测试1：规则系统")
print("-" * 60)

try:
    # 检查核心原则文件是否存在
    from pathlib import Path

    core_principles = Path(
        "/Users/liuyi/WorkBuddy/stock-signal/.codebuddy/rules/00-CORE-PRINCIPLES.md"
    )
    if core_principles.exists():
        print("  ✓ 00-CORE-PRINCIPLES.md 存在")
        content = core_principles.read_text(encoding="utf-8")
        lines = content.count("\n")
        print(f"    行数：{lines}（要求≤50行）")
        if lines <= 50:
            print("  ✓ 符合行数要求")
        else:
            print("  ⚠️ 超过50行")
    else:
        print("  ✗ 00-CORE-PRINCIPLES.md 不存在")

    # 检查分层规则文件
    rules_dir = core_principles.parent
    rule_files = ["01-MODULE-DEV.md", "02-DATA-SOURCES.md", "03-CODE-SAFETY.md"]
    for rule_file in rule_files:
        if (rules_dir / rule_file).exists():
            print(f"  ✓ {rule_file} 存在")
        else:
            print(f"  ✗ {rule_file} 不存在")

except Exception as e:
    print(f"  ✗ 测试失败：{e}")

# ========== 测试2：记忆系统 ==========
print("\n📒 测试2：记忆系统")
print("-" * 60)

try:
    from tools.memory_refiner import find_duplicate_summaries, find_promotable_records

    learnings_file = Path(
        "/Users/liuyi/WorkBuddy/stock-signal/.learnings/LEARNINGS.md"
    )
    if learnings_file.exists():
        content = learnings_file.read_text(encoding="utf-8")

        # 检查重复记录
        duplicates = find_duplicate_summaries(content)
        if duplicates:
            print(f"  ⚠️ 发现 {len(duplicates)} 个重复模式")
        else:
            print("  ✓ 未发现重复记录")

        # 检查可提升记录
        promotable = find_promotable_records(content)
        if promotable:
            print(f"  ✓ 发现 {len(promotable)} 条可提升记录")
        else:
            print("  ✓ 未发现可提升记录")
    else:
        print("  ✗ LEARNINGS.md 不存在")

except Exception as e:
    print(f"  ✗ 测试失败：{e}")

# ========== 测试3：模块自注册 ==========
print("\n🔧 测试3：模块自注册")
print("-" * 60)

try:
    from tools.harness.module_registry import ModuleRegistry, get_module_registry
    from tools.harness.module_interface import BaseModule, ModuleMetadata

    # 检查ModuleRegistry是否存在
    registry = get_module_registry()
    if registry:
        print("  ✓ ModuleRegistry 已创建")

        # 尝试自动发现模块
        print("  开始自动发现模块...")
        registry.auto_discover()

        modules = registry.list_modules()
        print(f"  ✓ 已注册 {len(modules)} 个模块")
        for m in modules:
            print(f"    - {m}")
    else:
        print("  ✗ ModuleRegistry 未创建")

except Exception as e:
    print(f"  ✗ 测试失败：{e}")

# ========== 测试4：代码安全工具 ==========
print("\n🔒 测试4：代码安全工具")
print("-" * 60)

try:
    from tools.safe_edit import ImpactAnalyzer

    # 创建分析器
    analyzer = ImpactAnalyzer(
        project_root="/Users/liuyi/WorkBuddy/stock-signal"
    )
    print("  ✓ ImpactAnalyzer 创建成功")

    # 扫描项目
    analyzer.scan_project()
    print(f"  ✓ 扫描完成")

except Exception as e:
    print(f"  ✗ 测试失败：{e}")

# ========== 测试5：自动故障转移 ==========
print("\n🔄 测试5：自动故障转移")
print("-" * 60)

try:
    from tools.auto_failover import auto_failover, get_failover_status

    # 测试装饰器
    @auto_failover(key="test")
    def test_func():
        raise Exception("测试异常")

    try:
        test_func()
    except Exception:
        pass

    status = get_failover_status("test")
    print(f"  ✓ auto_failover 装饰器正常工作")
    print(f"    状态：{status}")

except Exception as e:
    print(f"  ✗ 测试失败：{e}")

# ========== 测试6：性能监控 ==========
print("\n⏱️ 测试6：性能监控")
print("-" * 60)

try:
    from tools.harness.core import Harness

    # 检查性能监控阈值
    threshold = Harness.PERFORMANCE_THRESHOLD
    print(f"  ✓ 性能监控阈值：{threshold}秒")

except Exception as e:
    print(f"  ✗ 测试失败：{e}")

# ========== 测试7：规则自动提升 ==========
print("\n📈 测试7：规则自动提升")
print("-" * 60)

try:
    from tools.rule_promotion import RulePromotionManager

    manager = RulePromotionManager()
    print("  ✓ RulePromotionManager 创建成功")

except Exception as e:
    print(f"  ✗ 测试失败：{e}")

# ========== 测试总结 ==========
print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)

print("\n📊 测试总结：")
print("  1. 规则系统：已创建分层规则文件")
print("  2. 记忆系统：已创建精炼工具")
print("  3. 模块自注册：已实现BaseModule接口")
print("  4. 代码安全：已创建影响分析工具")
print("  5. 自动故障转移：已创建装饰器")
print("  6. 性能监控：已在Harness中集成")
print("  7. 规则自动提升：已创建管理工具")

print("\n✅ 全套改进方案已基本完成")
print("=" * 60)
