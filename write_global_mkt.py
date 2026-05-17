#!/usr/bin/env python3
"""
修复 global_mkt.py：重写 _fetch_kline() 使用 westock-data-skillhub CLI
"""
import re

with open('/Users/liuyi/WorkBuddy/stock-signal/market_monitor/data_sources/global_mkt.py', 'r') as f:
    content = f.read()

# 查找 _fetch_kline 函数的开始和结束
# 开始：def _fetch_kline(
# 结束：下一个 def 或文件结束
pattern = r'def _fetch_kline\(\s*\n.*?(?=\ndef |(?=\nclass ))'
# 更简单的办法：找到函数开始行，然后逐行找到函数结束
lines = content.split('\n')
new_lines = []
i = 0
skip_until = -1

while i < len(lines):
    line = lines[i]
    
    # 检测到 _fetch_kline 函数定义，跳过旧实现
    if '_fetch_kline(' in line or 'def _fetch_kline(' in line:
        # 写入新实现
        new_lines.append('def _fetch_kline(')
        new_lines.append('    secid: str,')
        new_lines.append('    n: int = 15,')
        new_lines.append('    timeout: int = 8,')
        new_lines.append(') -> list:')
        new_lines.append('    """')
        new_lines.append('    通过 westock-data-skillhub CLI 获取最近 n 根日 K 线数据。')
        new_lines.append('    ')
        new_lines.append('    secid 格式：us.DJI, us.SPX, hk.HSI, jp.N225 等')
        new_lines.append('    ')
        new_lines.append('    Returns:')
        new_lines.append('        列表，每项为 (date_str, close_price: float)，按日期升序。')
        new_lines.append('        失败返回空列表。')
        new_lines.append('    """')
        new_lines.append('    import subprocess, json, re')
        new_lines.append('    ')
        new_lines.append('    cmd = ["npx", "--yes", "westock-data-skillhub@latest", "kline", secid, "day", str(max(n, 30))]')
        new_lines.append('    try:')
        new_lines.append('        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)')
        new_lines.append('        if result.returncode != 0:')
        new_lines.append('            print(f"[westock-data] CLI 失败: {result.stderr[:200]}")')
        new_lines.append('            return []')
        new_lines.append('        ')
        new_lines.append('        # 解析 Markdown 表格输出')
        new_lines.append('        output = []')
        new_lines.append('        in_data = False')
        new_lines.append('        for line in result.stdout.split("\\n"):')
        new_lines.append('            if line.strip().startswith("| date"):')
        new_lines.append('                in_data = True')
        new_lines.append('                continue')
        new_lines.append('            if not in_data or line.strip().startswith("| ---"):')
        new_lines.append('                continue')
        new_lines.append('            if not line.strip() or not line.strip().startswith("|"):')
        new_lines.append('                break')
        new_lines.append('            # 解析表格行: | date | open | last | high | low | ...')
        new_lines.append('            parts = [p.strip() for p in line.split("|")]')
        new_lines.append('            if len(parts) >= 4:')
        new_lines.append('                dt = parts[1].strip()')
        new_lines.append('                try:')
        new_lines.append('                    close = float(parts[3].strip())  # "last" 列是收盘价')
        new_lines.append('                    output.append((dt, close))')
        new_lines.append('                except (ValueError, IndexError):')
        new_lines.append('                    pass')
        new_lines.append('        ')
        new_lines.append('        print(f"[westock-data] {secid} 获取 {len(output)} 条数据")')
        new_lines.append('        return output[-n:] if len(output) >= n else output')
        new_lines.append('    except Exception as e:')
        new_lines.append('        print(f"[westock-data] 异常: {type(e).__name__}: {e}")')
        new_lines.append('        return []')
        new_lines.append('')
        
        # 跳过旧函数实现
        i += 1
        while i < len(lines):
            # 下一个 def 或空行+def 表示函数结束
            if lines[i].strip().startswith('def ') or lines[i].strip().startswith('def_'):
                break
            i += 1
        continue
    
    new_lines.append(line)
    i += 1

# 写回文件
with open('/Users/liuyi/WorkBuddy/stock-signal/market_monitor/data_sources/global_mkt.py', 'w') as f:
    f.write('\n'.join(new_lines))

print("已重写 _fetch_kline() 函数")
