"""
LLM 自然语言解读 —— 通过 CodeBuddy CLI 生成市场回顾和操作建议。

在报告生成后，通过 subprocess 调用 codebuddy CLI（bypassPermissions模式），
输入持仓分析和选股结果，生成自然语言解读嵌入飞书文档末尾。

使用示例：
    from market_monitor.report.llm_interpreter import generate_interpretation
    
    text = generate_interpretation(results, selection_data, report_date)
"""

import json
import subprocess
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional


# 代码仓库根目录
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _build_prompt(results: List[Dict], selection_data: Optional[Dict], date: str) -> str:
    """构建 LLM 输入提示词。"""
    
    # 统计持仓概况
    signals = {}
    for r in results:
        s = r.get('signal', '?')
        signals[s] = signals.get(s, 0) + 1
    
    positions_text = []
    for r in results[:8]:
        positions_text.append(
            f"- {r.get('etf_code','')} {r.get('index_name', r.get('etf_name',''))}: "
            f"信号={r.get('signal','')}, 评分={r.get('pattern_score',0):.0f}, "
            f"KDJ_J={r.get('kdj_j',0):.1f}, 盈亏={r.get('profit_pct',0):+.2f}%"
        )
    
    prompt = f"""你是一位专业的ETF投资分析师。请根据以下持仓分析数据，用中文生成三部分简短解读（每部分2-3句话）：

## 数据日期：{date}

## 持仓概况
{chr(10).join(positions_text)}

## 信号分布
{json.dumps(signals, ensure_ascii=False)}

## 要求
请按以下三部分输出：

### 本周市场回顾
简要分析当前持仓信号分布反映的市场状态（多空力量对比、关键指数走势）。

### 持仓优化建议  
基于信号和评分，给出1-2条具体的操作建议（如：xx指数空头排列建议减仓，xx指数接近金叉可关注）。

### 选股方向点评
（如果有选股数据会单独提供）简述当前适合关注的方向。

要求：语言简洁专业，每部分不超过3句话，不要用markdown标题，用【】标记各部分。
"""
    return prompt


def generate_interpretation(
    results: List[Dict], 
    selection_data: Optional[Dict] = None,
    date: str = None,
    timeout_seconds: int = 120,
) -> Optional[str]:
    """
    通过 CodeBuddy CLI 生成自然语言解读。
    
    Args:
        results: 持仓分析结果列表
        selection_data: 可选选股数据
        date: 报告日期
        timeout_seconds: 超时时间
    
    Returns:
        解读文本，失败返回 None
    """
    if not results:
        return None
    
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    # 获取 API Key
    api_key = os.getenv("CODEBUDDY_API_KEY", "")
    if not api_key:
        print("  ⚠ CODEBUDDY_API_KEY 未设置，跳过 LLM 解读")
        return None
    
    prompt = _build_prompt(results, selection_data, date)
    
    try:
        # 写入临时文件（避免命令行参数过长）
        temp_path = os.path.join(_REPO_ROOT, ".llm_prompt_temp.txt")
        with open(temp_path, 'w') as f:
            f.write(prompt)
        
        result = subprocess.run(
            ["codebuddy", "--permission-mode", "bypassPermissions", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env={**os.environ, "CODEBUDDY_API_KEY": api_key},
        )
        
        # 清理临时文件
        try:
            os.remove(temp_path)
        except OSError:
            pass
        
        if result.returncode != 0:
            print(f"  ⚠ LLM 解读生成失败: {result.stderr[:100]}")
            return None
        
        output = result.stdout.strip()
        if not output:
            return None
        
        return f"\n## 💡 AI 解读\n\n{output}\n"
    
    except subprocess.TimeoutExpired:
        print(f"  ⚠ LLM 解读超时 ({timeout_seconds}s)")
        return None
    except FileNotFoundError:
        print("  ⚠ codebuddy CLI 未安装，跳过 LLM 解读")
        return None
    except Exception as e:
        print(f"  ⚠ LLM 解读异常: {e}")
        return None
