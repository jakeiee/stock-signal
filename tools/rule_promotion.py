#!/usr/bin/env python3
"""
规则自动提升机制
监控规则使用频率，≥3次使用自动提升到00-CORE-PRINCIPLES.md
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime, timezone, timedelta


# 配置文件路径
CONFIG_FILE = Path(__file__).parent.parent / ".learnings" / "rule_promotion.json"
CORE_PRINCIPLES_FILE = Path(__file__).parent.parent / ".codebuddy" / "rules" / "00-CORE-PRINCIPLES.md"

# 提升阈值
PROMOTION_THRESHOLD = 3  # 使用次数≥3则提升


class RulePromotionManager:
    """规则提升管理器"""

    def __init__(self):
        self.config = self._load_config()
        self.rule_usage: Dict[str, int] = self.config.get("rule_usage", {})
        self.promoted_rules: List[str] = self.config.get("promoted_rules", [])

    def _load_config(self) -> dict:
        """加载配置文件"""
        if not CONFIG_FILE.exists():
            return {"rule_usage": {}, "promoted_rules": []}

        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {"rule_usage": {}, "promoted_rules": []}

    def _save_config(self) -> None:
        """保存配置文件"""
        config = {
            "rule_usage": self.rule_usage,
            "promoted_rules": self.promoted_rules,
            "last_update": datetime.now().isoformat()
        }

        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    def track_rule_usage(self, rule_name: str) -> None:
        """
        跟踪规则使用

        Args:
            rule_name: 规则名称
        """
        self.rule_usage[rule_name] = self.rule_usage.get(rule_name, 0) + 1
        self._save_config()

        # 检查是否需要提升
        if self.rule_usage[rule_name] >= PROMOTION_THRESHOLD:
            if rule_name not in self.promoted_rules:
                self.promote_rule(rule_name)

    def promoote_rule(self, rule_name: str) -> bool:
        """
        提升规则到核心原则

        Args:
            rule_name: 规则名称

        Returns:
            是否成功提升
        """
        if rule_name in self.promoted_rules:
            print(f"  ⚠️ 规则已提升：{rule_name}")
            return False

        # 读取规则内容
        rule_content = self._extract_rule_content(rule_name)
        if not rule_content:
            print(f"  ✗ 无法提取规则内容：{rule_name}")
            return False

        # 添加到核心原则文件
        success = self._append_to_core_principles(rule_name, rule_content)
        if success:
            self.promoted_rules.append(rule_name)
            self._save_config()
            print(f"  ✓ 已提升规则：{rule_name}")
            return True
        else:
            print(f"  ✗ 提升失败：{rule_name}")
            return False

    def _extract_rule_content(self, rule_name: str) -> str:
        """
        从规则文件中提取规则内容

        Args:
            rule_name: 规则名称

        Returns:
            规则内容字符串
        """
        # 搜索规则文件
        rules_dir = Path(__file__).parent.parent / ".codebuddy" / "rules"
        for rule_file in rules_dir.glob("*.md"):
            if rule_file.name == "00-CORE-PRINCIPLES.md":
                continue

            try:
                content = rule_file.read_text(encoding="utf-8")
                # 查找规则名称
                if rule_name in content:
                    # 提取包含规则名称的段落（简化版）
                    lines = content.split('\n')
                    start_idx = None
                    for i, line in enumerate(lines):
                        if rule_name in line:
                            start_idx = i
                            break

                    if start_idx is not None:
                        # 提取后续10行作为规则内容
                        end_idx = min(start_idx + 10, len(lines))
                        return '\n'.join(lines[start_idx:end_idx])
            except Exception:
                pass

        return ""

    def _append_to_core_principles(self, rule_name: str, rule_content: str) -> bool:
        """
        追加规则到核心原则文件

        Args:
            rule_name: 规则名称
            rule_content: 规则内容

        Returns:
            是否成功
        """
        try:
            if not CORE_PRINCIPLES_FILE.exists():
                print(f"  ✗ 核心原则文件不存在：{CORE_PRINCIPLES_FILE}")
                return False

            # 读取现有内容
            content = CORE_PRINCIPLES_FILE.read_text(encoding="utf-8")

            # 检查是否已包含该规则
            if rule_name in content:
                print(f"  ⚠️ 核心原则已包含该规则：{rule_name}")
                return False

            # 追加到文件末尾
            append_content = f"""

## 自动提升规则：{rule_name}

{rule_content}

> 自动提升时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
> 使用次数：{self.rule_usage.get(rule_name, 0)}次
"""

            with open(CORE_PRINCIPLES_FILE, 'a', encoding='utf-8') as f:
                f.write(append_content)

            return True

        except Exception as e:
            print(f"  ✗ 追加到核心原则失败：{e}")
            return False

    def scan_code_for_rule_usage(self, project_root: str = ".") -> Dict[str, int]:
        """
        扫描代码中的规则引用

        Args:
            project_root: 项目根目录

        Returns:
            规则名称 -> 使用次数 的字典
        """
        usage_count: Dict[str, int] = {}

        # 搜索所有Python文件
        for root, dirs, files in os.walk(project_root):
            # 跳过某些目录
            dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', '.pytest_cache', 'node_modules']]

            for file in files:
                if file.endswith('.py'):
                    file_path = Path(root) / file
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()

                        # 查找规则引用（简化版：查找注释中的规则名称）
                        # 这里可以根据实际情况调整
                        for rule_name in self.rule_usage.keys():
                            if rule_name in content:
                                usage_count[rule_name] = usage_count.get(rule_name, 0) + 1
                    except Exception:
                        pass

        return usage_count

    def auto_promote_rules(self, project_root: str = ".") -> List[str]:
        """
        自动提升使用次数≥3的规则

        Args:
            project_root: 项目根目录

        Returns:
            已提升的规则列表
        """
        print("🔍 开始扫描规则使用...")

        # 扫描代码
        usage = self.scan_code_for_rule_usage(project_root)

        # 更新使用次数
        for rule_name, count in usage.items():
            self.rule_usage[rule_name] = self.rule_usage.get(rule_name, 0) + count

        # 检查需要提升的规则
        to_promote = []
        for rule_name, count in self.rule_usage.items():
            if count >= PROMOTION_THRESHOLD and rule_name not in self.promoted_rules:
                to_promote.append(rule_name)

        # 提升规则
        promoted = []
        for rule_name in to_promote:
            if self.promote_rule(rule_name):
                promoted.append(rule_name)

        # 保存配置
        self._save_config()

        print(f"✓ 扫描完成，已提升 {len(promoted)} 条规则")
        return promoted


def main():
    """主函数"""
    import os

    print("=" * 60)
    print("规则自动提升工具")
    print("=" * 60)

    manager = RulePromotionManager()

    # 自动提升规则
    promoted = manager.auto_promote_rules(project_root=".")

    if promoted:
        print("\n已提升的规则：")
        for rule in promoted:
            print(f"  ✓ {rule}")
    else:
        print("\n没有需要提升的规则")

    print("\n" + "=" * 60)
    print("规则自动提升完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
