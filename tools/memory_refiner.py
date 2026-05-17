#!/usr/bin/env python3
"""
记忆精炼工具
功能：识别重复记录，提取可提升到核心原则的记录
"""

import re
from pathlib import Path

LEARNINGS_FILE = Path(__file__).parent.parent / ".learnings" / "LEARNINGS.md"


def read_learnings():
    """读取LEARNINGS.md文件"""
    if not LEARNINGS_FILE.exists():
        return ""
    return LEARNINGS_FILE.read_text(encoding="utf-8")


def find_duplicate_summaries(content):
    """识别重复记录（Summary相同且出现≥3次）"""
    # 提取所有Summary
    pattern = r"### Summary\n([^\n]+)"
    summaries = re.findall(pattern, content)

    # 统计频率
    summary_count = {}
    for s in summaries:
        summary_count[s] = summary_count.get(s, 0) + 1

    # 返回出现≥3次的
    return {k: v for k, v in summary_count.items() if v >= 3}


def find_promotable_records(content):
    """识别可提升到核心原则的记录"""
    # 匹配best_practice且priority为high/medium且status为resolved的记录
    pattern = r"## \[(LRN-[^\]]+)\] ([^\n]+)\n\*\*\*Logged\*\*\*: ([^\n]+)\n\*\*\*Priority\*\*\*: (high|medium)\n\*\*\*Status\*\*\*: resolved\n\*\*\*Area\*\*\*: ([^\n]+)\n\n### Summary\n([^\n]+)"
    matches = re.finditer(pattern, content)

    promotable = []
    for match in matches:
        promotable.append({
            "id": match.group(1),
            "categories": match.group(2).strip(),
            "priority": match.group(4),
            "summary": match.group(6).strip()
        })

    return promotable


def clean_duplicates(content, duplicates):
    """删除重复记录（保留第一条）"""
    cleaned = content

    for summary in duplicates.keys():
        # 找到所有包含此Summary的记录块
        pattern = r"## \[LRN-[^\]]+\] [^\n]+\n[\\s\\S]*?### Summary\n" + re.escape(summary) + r"[\\s\\S]*?---\n"
        matches = list(re.finditer(pattern, cleaned))

        # 保留第一条，删除其余
        for match in matches[1:]:
            cleaned = cleaned.replace(match.group(0), "")

    # 清理多余空行
    cleaned = re.sub(r"\\n{3,}", "\\n\\n", cleaned)
    return cleaned


def main():
    print("=" * 60)
    print("记忆精炼工具")
    print("=" * 60)

    # 1. 读取LEARNINGS.md
    print("\\n[1/4] 读取LEARNINGS.md...")
    content = read_learnings()
    if not content:
        print("  ✗ LEARNINGS.md 文件不存在")
        return
    print(f"  ✓ 读取成功，文件长度：{len(content)} 字符")

    # 2. 识别重复记录
    print("\\n[2/4] 识别重复记录...")
    duplicates = find_duplicate_summaries(content)
    if duplicates:
        print(f"  ✓ 发现 {len(duplicates)} 个重复模式：")
        for summary, count in duplicates.items():
            print(f"    - {summary}（出现 {count} 次）")
    else:
        print("  ✓ 未发现重复记录")

    # 3. 识别可提升记录
    print("\\n[3/4] 识别可提升到核心原则的记录...")
    promotable = find_promotable_records(content)
    if promotable:
        print(f"  ✓ 发现 {len(promotable)} 条可提升记录：")
        for r in promotable:
            print(f"    - [{r['id']}] {r['summary']}")
    else:
        print("  ✓ 未发现可提升记录")

    # 4. 清理重复记录（询问用户）
    if duplicates:
        print("\\n[4/4] 是否清理重复记录？(y/n): ", end="")
        choice = input().strip().lower()
        if choice == 'y':
            cleaned = clean_duplicates(content, duplicates)
            LEARNINGS_FILE.write_text(cleaned, encoding="utf-8")
            print(f"  ✓ 已清理重复记录，新文件长度：{len(cleaned)} 字符")
        else:
            print("  ✓ 跳过清理")

    print("\\n" + "=" * 60)
    print("记忆精炼完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
