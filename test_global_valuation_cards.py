#!/usr/bin/env python3
"""
全球估值卡片测试脚本。

展示三种飞书卡片风格：
  1. 紧凑表格版 (compact)
  2. 国家分组版 (group)
  3. 热力图版 (heatmap)
  
同时生成估值对比图片。
"""

import json
import os
import sys

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from market_monitor.report.global_valuation_card import (
    fetch_enhanced_global_valuation,
    generate_compact_table_card,
    generate_country_group_card,
    generate_heatmap_card,
)
from market_monitor.report.valuation_image import generate_valuation_image
from market_monitor.data_sources.trendonify import fetch_trendonify_valuation


def print_section(title):
    """打印分隔线标题"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def main():
    print("🌍 全球估值卡片生成演示")
    print("=" * 80)
    
    # 1. 获取数据
    print("\n📊 正在获取全球估值数据...")
    valuation_data = fetch_enhanced_global_valuation()
    
    print(f"\n✓ 数据获取完成")
    print(f"  日期: {valuation_data['date']}")
    print(f"  来源: {', '.join(valuation_data['sources'])}")
    
    # 打印数据摘要
    print("\n📈 估值数据摘要:")
    for market_code, market_data in valuation_data['markets'].items():
        indices = market_data.get('indices', [])
        if indices:
            primary = indices[0]
            pe = primary.get('pe', 'N/A')
            pct = primary.get('pct_10y', primary.get('pct_3y', 'N/A'))
            name = primary.get('name', '')
            print(f"  {market_code}: {name} | PE: {pe} | 分位: {pct}")
    
    # 2. 生成三种卡片
    print_section("方案1: 紧凑表格版 (compact)")
    print("特点: 简洁的横向对比表格，每行一个国家，突出PE和10年分位")
    card1 = generate_compact_table_card(valuation_data)
    print("\n生成的卡片JSON:")
    print(json.dumps(card1, ensure_ascii=False, indent=2))
    
    print_section("方案2: 国家分组版 (group)")
    print("特点: 按国家分组展示，每个国家一个独立区块，包含更多估值指标")
    card2 = generate_country_group_card(valuation_data)
    print("\n生成的卡片JSON:")
    print(json.dumps(card2, ensure_ascii=False, indent=2))
    
    print_section("方案3: 热力图版 (heatmap)")
    print("特点: 使用颜色块直观展示估值水平，适合快速扫视整体分布")
    card3 = generate_heatmap_card(valuation_data)
    print("\n生成的卡片JSON:")
    print(json.dumps(card3, ensure_ascii=False, indent=2))
    
    # 3. 生成图片
    print_section("生成估值对比图片")
    
    # 准备图片数据
    base_data = fetch_trendonify_valuation()
    img_data = {
        "date": base_data.get("date", ""),
        "US": base_data.get("US", {}),
        "HK": base_data.get("HK", {}),
        "JP": base_data.get("JP", {}),
        "KR": base_data.get("KR", {}),
    }
    
    img_path = generate_valuation_image(img_data)
    if img_path:
        print(f"✓ 图片已生成: {img_path}")
    else:
        print("✗ 图片生成失败")
    
    # 4. 使用说明
    print_section("使用说明")
    print("""
要发送卡片到飞书，请使用以下代码:

```python
from market_monitor.report.global_valuation_card import send_global_valuation_card

# 发送紧凑表格版
send_global_valuation_card(style="compact")

# 发送国家分组版
send_global_valuation_card(style="group")

# 发送热力图版
send_global_valuation_card(style="heatmap")

# 发送图片版
from market_monitor.report.global_valuation_card import generate_and_send_valuation_image
generate_and_send_valuation_image()
```

三种风格对比:
┌─────────────┬────────────────────────────────────────────┐
│ 风格        │ 适用场景                                   │
├─────────────┼────────────────────────────────────────────┤
│ compact     │ 快速浏览，信息密度高，适合日报             │
│ group       │ 详细分析，按国家分组，适合深度报告         │
│ heatmap     │ 直观对比，颜色鲜明，适合快速决策           │
│ image       │ 可视化图表，美观大方，适合展示分享         │
└─────────────┴────────────────────────────────────────────┘
""")
    
    print("\n✅ 演示完成!")
    
    return {
        "cards": {
            "compact": card1,
            "group": card2,
            "heatmap": card3,
        },
        "image_path": img_path,
        "data": valuation_data,
    }


if __name__ == "__main__":
    result = main()
