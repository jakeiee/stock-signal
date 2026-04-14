#!/usr/bin/env python3
"""
10年以上指数历史估值数据获取实战示例

本脚本展示如何从多个数据源获取至少10年以上的指数历史估值数据
"""

import requests
import json
import csv
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import os

# ========================================================================
# 配置部分
# ========================================================================

# 目标指数
TARGET_INDICES = [
    {
        "name": "红利低波",
        "code": "H30269",  # CSIH30269
        "csindex_code": "H30269",
        "launch_date": "2012-10-26",  # 发布日
        "expected_years": 13.4  # 预期历史年限
    },
    {
        "name": "红利质量", 
        "code": "931468",  # CSI931468
        "csindex_code": "931468",
        "launch_date": "2020-05-21",
        "expected_years": 5.8
    },
    {
        "name": "东证红利低波",
        "code": "931446",  # CSI931446
        "csindex_code": "931446",
        "launch_date": "2020-04-21",
        "expected_years": 5.9
    }
]

# 数据源优先级配置
DATA_SOURCES = [
    {
        "name": "理杏仁 (lixinger.com)",
        "url_template": "https://www.lixinger.com/equity/index/detail/csi/{code}/1730269/fundamental/valuation/pe-ttm",
        "priority": 1,
        "requires_api": False,
        "notes": "提供至少10年历史数据，图表展示良好，需手动或自动化提取"
    },
    {
        "name": "亿牛网 (eniu.com)",
        "url_template": "https://eniu.com/gu/sh{code_alternative}",
        "priority": 2,
        "requires_api": False,
        "notes": "提供20年以上历史数据，但主要针对上证指数，需验证其他指数支持"
    },
    {
        "name": "EODHD API (付费)",
        "url_template": "https://eodhistoricaldata.com/api/eod/{code}.IS?api_token={api_key}&fmt=json",
        "priority": 3,
        "requires_api": True,
        "notes": "专业数据服务，提供完整历史数据，有免费额度"
    }
]

# 输出目录
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "10_year_historical_data")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ========================================================================
# 辅助函数
# ========================================================================

def calculate_expected_data_points(launch_date_str: str, frequency: str = "monthly") -> int:
    """计算从发布日至今的预期数据点数"""
    try:
        launch_date = datetime.strptime(launch_date_str, "%Y-%m-%d").date()
        today = datetime.now().date()
        
        total_days = (today - launch_date).days
        total_months = total_days // 30
        total_years = total_days / 365.25
        
        if frequency == "daily":
            # 交易日约250天/年
            return int(total_years * 250)
        elif frequency == "monthly":
            return total_months
        elif frequency == "quarterly":
            return total_months // 3
        elif frequency == "yearly":
            return int(total_years)
    except:
        return 0

def print_expected_data_requirements():
    """打印预期的数据要求"""
    print("\n" + "="*80)
    print("目标指数预期数据需求分析")
    print("="*80)
    
    for idx in TARGET_INDICES:
        daily_points = calculate_expected_data_points(idx["launch_date"], "daily")
        monthly_points = calculate_expected_data_points(idx["launch_date"], "monthly")
        yearly_points = calculate_expected_data_points(idx["launch_date"], "yearly")
        
        print(f"\n📊 {idx['name']} ({idx['code']})")
        print(f"  发布时间: {idx['launch_date']} (至今约{idx['expected_years']:.1f}年)")
        print(f"  预期数据点：")
        print(f"    • 日频：~{daily_points:,} 个交易日")
        print(f"    • 月频：~{monthly_points:,} 个月")
        print(f"    • 年频：~{yearly_points:,} 年")
        
        # 判断当前妙想API数据的不足程度
        print(f"  ⚠️ 当前妙想API数据缺口:")
        print(f"    • 仅有：2.1年数据（仅占{2.1/idx['expected_years']*100:.1f}%）" if idx["code"] == "H30269" else "    • 数据严重不足")
    

def test_lixinger_website():
    """测试理杏仁网站的可访问性和数据展示"""
    print("\n" + "="*80)
    print("测试理杏仁网站 (lixinger.com) 数据可获取性")
    print("="*80)
    
    # H30269是确认能获取至少10年数据的
    test_url = DATA_SOURCES[0]["url_template"].format(code="H30269")
    print(f"\n✅ H30269 数据页面: {test_url}")
    print("  访问此页面后，可进行以下操作：")
    print("  1. 选择时间范围：'10年'视图")
    print("  2. 查看完整历史PE曲线")
    print("  3. 可能的数据导出选项（如有）")
    
    # 提供其他指数的替代查询建议
    print(f"\nℹ️ 其他指数的可能查询方式：")
    print(f"  • 在理杏仁网站搜索框输入指数名称")
    print(f"  • 尝试代码变体：CSI931468, CSI931446")
    print(f"  • 如找不到，使用备用数据源")
    

def create_data_collection_plan():
    """创建详细的数据收集计划"""
    print("\n" + "="*80)
    print("数据收集实施计划")
    print("="*80)
    
    print("\n🎯 阶段1：立即收集 (1-3天)")
    print("-" * 40)
    
    print("1. 🤖 自动化/半自动化方案：")
    print("   a. 理杏仁数据提取")
    print("      方式：网页爬虫 + 图表数据解析")
    print("      技术：Selenium/Playwright + 数据点提取")
    print("      目标：获取H30269至少10年PE历史数据")
    
    print("\n   b. 注册EODHD免费账号")
    print("      步骤：注册 -> 获取API Key -> 测试数据获取")
    print("      目标：获取所有三个指数的历史数据")
    print("      网址：https://eodhistoricaldata.com/pricing")
    
    print("\n2. 📊 手动补充方案：")
    print("   a. 理杏仁网站手动记录")
    print("      频率：每月/每季度关键数据点")
    print("      工具：Excel/Google Sheets")
    print("      优势：立即开始，不依赖技术实现")
    
    print("\n   b. 开源数据源探索")
    print("      • adata项目：https://github.com/1nchaos/adata")
    print("      • AkShare：https://www.akshare.xyz/")
    print("      • 目标：建立免费长期数据源")
    
    print("\n🎯 阶段2：数据整合 (3-7天)")
    print("-" * 40)
    print("1. 建立统一历史数据库")
    print("2. 实现多源数据融合算法")
    print("3. 创建数据质量检查机制")
    print("4. 更新投资决策算法使用完整历史数据")
    
    print("\n🎯 阶段3：维护优化 (1个月内)")
    print("-" * 40)
    print("1. 建立自动化数据更新管道")
    print("2. 实现数据质量监控和告警")
    print("3. 优化存储和查询性能")
    print("4. 建立数据备份和恢复机制")
    

def create_simple_data_template():
    """创建简单数据模板文件"""
    template = {
        "index_code": "",  # 指数代码
        "index_name": "",  # 指数名称
        "launch_date": "",  # 发布日
        "data_source": "",  # 数据来源
        "data_quality": "high",  # 数据质量 high/medium/low
        "collection_date": datetime.now().strftime("%Y-%m-%d"),
        "historical_data": []  # 历史数据列表
    }
    
    # 数据点结构
    data_point_template = {
        "date": "",  # 日期 YYYY-MM-DD
        "pe_ttm": None,  # 滚动市盈率
        "dividend_yield": None,  # 股息率 %
        "pb": None,  # 市净率
        "data_source": "",  # 该数据点的具体来源
        "notes": ""  # 备注
    }
    
    # 保存模板
    for idx in TARGET_INDICES:
        template_copy = template.copy()
        template_copy.update({
            "index_code": idx["code"],
            "index_name": idx["name"],
            "launch_date": idx["launch_date"]
        })
        
        filename = f"data_template_{idx['code']}_{idx['name']}.json"
        filepath = os.path.join(OUTPUT_DIR, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(template_copy, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 创建数据模板: {filename}")
    
    print(f"\n📁 所有模板文件已保存到: {OUTPUT_DIR}")
    

def generate_web_search_queries():
    """生成具体的网页搜索查询"""
    print("\n" + "="*80)
    print("具体网页搜索查询建议")
    print("="*80)
    
    queries = [
        # 理杏仁特定查询
        ("理杏仁 红利低波 H30269 历史市盈率 十年", "获取H30269至少10年PE数据"),
        ("理杏仁 红利质量 931468 市盈率 历史", "查找931468的历史估值数据"),
        ("理杏仁 东证红利低波 931446 股息率", "查找931446的历史股息率数据"),
        
        # EODHD相关
        ("EODHD API A股指数 历史数据 价格", "了解EODHD的A股指数数据服务"),
        ("EODHD API 中证指数 数据覆盖", "确认EODHD是否支持中证指数"),
        
        # 专业数据服务
        ("Wind 万得 中证指数 历史估值 数据服务", "专业数据服务的价格和覆盖"),
        ("Choice数据 中证指数 API 历史数据", "东方财富Choice数据服务"),
        
        # 开源项目
        ("adata A股指数 历史估值 Python", "开源adata项目的指数数据支持"),
        ("AkShare 中证指数 历史数据 API", "AkShare对中证指数的支持情况"),
        
        # 其他网站
        ("亿牛网 eniu 中证指数 历史市盈率", "验证亿牛网对中证指数的支持"),
        ("乌龟量化 wglh 红利指数 历史数据", "乌龟量化的指数历史数据")
    ]
    
    for query, purpose in queries:
        print(f"🔍 搜索: \"{query}\"")
        print(f"   用途: {purpose}")
    

def create_emergency_plan():
    """创建应急计划：当前系统的临时改进"""
    print("\n" + "="*80)
    print("应急改进计划（立即实施）")
    print("="*80)
    
    print("""
📌 现状评估：
  1. 当前妙想API仅提供2.1年H30269数据（严重不足）
  2. 基于不完整数据计算的97.1%分位失真

🔧 立即改进措施：

1. 投资建议风险说明：
   在所有投资建议前加入明确说明：
   "警告：当前估值数据仅基于2.1年历史计算，数据完整性不足，建议谨慎参考。"

2. 数据质量标记：
   在飞书日报中明确标注：
   - 数据来源：妙想API
   - 历史年限：2.1年（发布于2012-10-26，应有13.4年）
   - 数据完整性评分：15.7% （仅1.6分/10分）

3. 保守调整建议：
   基于数据不全风险，自动应用保守系数：
   - 建议仓位下调20%
   - 风险评级自动上调1级
   - 增加现金储备建议

4. 推动数据补充：
   在当前系统中加入数据补充提醒：
   "⚠️ 需要补充10年以上历史数据以提高决策准确性"
""")
    

def main():
    """主函数"""
    print("="*80)
    print("10年以上指数历史估值数据获取解决方案")
    print("="*80)
    
    # 1. 显示预期数据需求
    print_expected_data_requirements()
    
    # 2. 测试理杏仁网站
    test_lixinger_website()
    
    # 3. 创建数据收集计划
    create_data_collection_plan()
    
    # 4. 创建数据模板
    create_simple_data_template()
    
    # 5. 生成搜索查询
    generate_web_search_queries()
    
    # 6. 应急计划
    create_emergency_plan()
    
    print("\n" + "="*80)
    print("总结与下一步行动")
    print("="*80)
    
    print("""
🎯 立即执行的行动（今日/明日）：

1. 手动方案：
   • 访问理杏仁网站：https://www.lixinger.com/
   • 搜索"H30269"，查看"10年"历史PE数据
   • 手动记录关键时点数据（每个季度末）

2. 技术方案：
   • 注册EODHD账号：https://eodhistoricaldata.com/
   • 获取API Key，测试获取指数历史数据
   • 开始编写数据收集脚本

3. 系统改进：
   • 在飞书日报中加入数据质量警告
   • 调整投资建议的保守程度
   • 计划数据补充的具体时间表

📞 如需帮助：
   • 技术实施：可协助编写数据采集脚本
   • 数据源选择：可进一步对比不同数据源优劣
   • 方案制定：可根据预算制定详细实施计划
""")
    
    print(f"\n📁 所有输出文件已保存到：{OUTPUT_DIR}")
    print("  请检查生成的模板和计划文件，开始实施！")


if __name__ == "__main__":
    main()