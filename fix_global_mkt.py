#!/usr/bin/env python3
"""修复 global_mkt.py 的结构问题"""
import re

with open('/Users/liuyi/WorkBuddy/stock-signal/market_monitor/data_sources/global_mkt.py', 'r') as f:
    content = f.read()

# 找到 fetch_us_market 函数并提取嵌套的 _fetch_kline
# 方案：完全重写这个文件的结构

# 读取原有内容，提取各函数
lines = content.split('\n')
output_lines = []
in_fetch_us = False
in_nested_kline = False
nestded_kline_lines = []
i = 0

while i < len(lines):
    line = lines[i]
    
    # 检测 fetch_us_market 函数开始
    if line.strip().startswith('def fetch_us_market('):
        in_fetch_us = True
        output_lines.append(line)
        i += 1
        continue
    
    # 检测嵌套的 _fetch_kline 函数
    if in_fetch_us and line.strip().startswith('def _fetch_kline('):
        in_nested_kline = True
        nested_kline_lines = [line]
        i += 1
        continue
    
    # 在嵌套 _fetch_kline 中，收集直到函数结束
    if in_nested_kline:
        nested_kline_lines.append(line)
        # 检查函数是否结束（下一行缩进更少，且不是空行）
        if i + 1 < len(lines):
            next_line = lines[i + 1]
            # 如果函数体结束（遇到与 def 同缩进的行）
            if (not next_line.strip().startswith() and 
                not next_line.strip().startswith('#') and
                len(next_line) - len(next_line.lstrip()) <= 4):  # 缩进小于等于 4 空格
                # 函数可能结束
                if not next_line.strip() or not next_line.startswith('    '):
                    in_nested_kline = False
        i += 1
        continue
    
    # 正常添加行
    output_lines.append(line)
    i += 1

print("提取完成，正在重构文件...")
print(f"嵌套函数行数: {len(nested_kline_lines)}")

# 将嵌套函数放到正确位置（在 fetch_us_market 之前）
if nested_kline_lines:
    # 找到 fetch_us_market 的位置
    final_output = []
    for i, line in enumerate(output_lines):
        if line.strip().startswith('def fetch_us_market('):
            # 先插入嵌套函数
            # 调整缩进（去掉第一层缩进）
            for kline_line in nested_kline_lines:
                # 去掉前 4 个空格（从嵌套变成顶层）
                if kline_line.startswith('    '):
                    final_output.append(kline_line[4:])
                else:
                    final_output.append(kline_line)
            final_output.append('')  # 空行
        final_output.append(line)
    
    # 写回文件
    with open('/Users/liuyi/WorkBuddy/stock-signal/market_monitor/data_sources/global_mkt.py', 'w') as f:
        f.write('\n'.join(final_output))
    print("✓ 文件结构已修复")
else:
    print("✗ 未找到嵌套函数")
