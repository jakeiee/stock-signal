#!/usr/bin/env python3
"""
Wind APP手机记录估值数据辅助工具

本工具帮助管理通过Wind APP手动记录的指数估值数据
提供数据录入、验证、整合到系统的完整功能
"""

import os
import json
import csv
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import sys

# ========================================================================
# 配置部分
# ========================================================================

# 目标指数信息
INDICES_INFO = {
    "H30269": {
        "name": "红利低波",
        "launch_date": "2012-10-26",
        "expected_pe_range": (5.0, 20.0),  # 合理PE范围
        "expected_pb_range": (0.5, 3.0),   # 合理PB范围
        "expected_div_range": (1.0, 8.0)   # 合理股息率范围%
    },
    "931468": {
        "name": "红利质量", 
        "launch_date": "2020-05-21",
        "expected_pe_range": (8.0, 30.0),
        "expected_pb_range": (0.8, 4.0),
        "expected_div_range": (0.5, 5.0)
    },
    "931446": {
        "name": "东证红利低波",
        "launch_date": "2020-04-21",
        "expected_pe_range": (5.0, 20.0),
        "expected_pb_range": (0.5, 3.0),
        "expected_div_range": (1.0, 8.0)
    }
}

# 数据存储路径
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wind_app_recorded_data")
os.makedirs(DATA_DIR, exist_ok=True)

# 数据文件名
CURRENT_DATA_FILE = os.path.join(DATA_DIR, "current_wind_data.json")
HISTORICAL_DATA_FILE = os.path.join(DATA_DIR, "historical_wind_data.csv")
BACKUP_DATA_FILE = os.path.join(DATA_DIR, "backup_data.json")

# ========================================================================
# 数据记录功能
# ========================================================================

def create_data_template():
    """创建数据录入模板"""
    print("\n" + "="*80)
    print("Wind APP数据记录模板")
    print("="*80)
    
    template = {
        "操作说明": "使用Wind APP查看指数估值后，按此模板记录数据",
        "记录时间": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "数据点示例": {
            "指数代码": "H30269",
            "指数名称": "红利低波", 
            "记录日期": "2026-03-31",
            "PE_TTM": 8.52,
            "PB": 1.02,
            "dividend_yield_pct": 4.2,
            "数据来源": "Wind APP手机",
            "备注": "季度末数据"
        },
        "三个目标指数": list(INDICES_INFO.keys()),
        "记录频率建议": "每季度末记录一次（3/31, 6/30, 9/30, 12/31）",
        "存储位置": DATA_DIR
    }
    
    # 保存模板文件
    template_file = os.path.join(DATA_DIR, "data_recording_template.txt")
    with open(template_file, 'w', encoding='utf-8') as f:
        f.write("Wind APP估值数据记录指南\n")
        f.write("=" * 50 + "\n\n")
        
        for idx_code, info in INDICES_INFO.items():
            f.write(f"【{info['name']} ({idx_code})】\n")
            f.write(f"发布日: {info['launch_date']}\n")
            f.write(f"数据查询路径: Wind APP → 搜索'{idx_code}'或'{info['name']}'\n")
            f.write(f"需要记录的指标:\n")
            f.write(f"  1. 滚动市盈率 (PE-TTM)\n")
            f.write(f"  2. 市净率 (PB)\n")
            f.write(f"  3. 股息率（如有）\n")
            f.write(f"合理范围参考:\n")
            f.write(f"  - PE: {info['expected_pe_range'][0]}-{info['expected_pe_range'][1]}\n")
            f.write(f"  - PB: {info['expected_pb_range'][0]}-{info['expected_pb_range'][1]}\n")
            f.write(f"  - 股息率: {info['expected_div_range'][0]}%-{info['expected_div_range'][1]}%\n")
            f.write("\n")
    
    print(f"✅ 数据记录模板已创建: {template_file}")
    
    # 创建手机备忘录格式
    print("\n📱 手机备忘录格式:")
    print("-" * 40)
    for idx_code, info in INDICES_INFO.items():
        print(f"【{info['name']} ({idx_code})】")
        print(f"{datetime.now().strftime('%Y-%m-%d')}: PE= , PB= , 股息率= %")
        print("备注: ")
        print()


def record_current_data():
    """记录当前数据（交互式）"""
    print("\n" + "="*80)
    print("记录当前Wind APP数据")
    print("="*80)
    
    current_data = {}
    today = datetime.now().strftime("%Y-%m-%d")
    
    for idx_code, info in INDICES_INFO.items():
        print(f"\n📊 记录 {info['name']} ({idx_code}) 数据")
        print("-" * 40)
        
        try:
            pe = float(input(f"  请输入PE-TTM值: ").strip())
            pb = float(input(f"  请输入PB值: ").strip())
            div_yield = input(f"  请输入股息率%（如无可留空）: ").strip()
            div_yield = float(div_yield) if div_yield else None
            
            # 数据验证
            if info['expected_pe_range'][0] <= pe <= info['expected_pe_range'][1]:
                print(f"  ✅ PE值 {pe} 在合理范围内")
            else:
                print(f"  ⚠️ 警告: PE值 {pe} 超出预期范围 {info['expected_pe_range']}")
            
            if info['expected_pb_range'][0] <= pb <= info['expected_pb_range'][1]:
                print(f"  ✅ PB值 {pb} 在合理范围内")
            else:
                print(f"  ⚠️ 警告: PB值 {pb} 超出预期范围 {info['expected_pb_range']}")
            
            if div_yield and info['expected_div_range'][0] <= div_yield <= info['expected_div_range'][1]:
                print(f"  ✅ 股息率 {div_yield}% 在合理范围内")
            elif div_yield:
                print(f"  ⚠️ 警告: 股息率 {div_yield}% 超出预期范围 {info['expected_div_range']}")
            
            notes = input(f"  备注（如季度末、数据特殊情况等）: ").strip()
            
            current_data[idx_code] = {
                "index_name": info['name'],
                "record_date": today,
                "pe_ttm": pe,
                "pb": pb,
                "dividend_yield_pct": div_yield,
                "source": "Wind APP手机记录",
                "notes": notes
            }
            
        except ValueError as e:
            print(f"  ❌ 输入格式错误: {e}")
            continue
    
    # 保存当前数据
    if current_data:
        save_data = {
            "record_time": datetime.now().isoformat(),
            "record_date": today,
            "data": current_data
        }
        
        with open(CURRENT_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ 当前数据已保存到: {CURRENT_DATA_FILE}")
        return current_data
    else:
        print("\n⚠️ 未记录任何数据")
        return {}


def add_historical_data():
    """添加历史数据"""
    print("\n" + "="*80)
    print("添加历史数据记录")
    print("="*80)
    
    # 检查CSV文件是否存在
    file_exists = os.path.exists(HISTORICAL_DATA_FILE)
    
    # 准备数据
    historical_data = []
    
    print("📅 添加历史数据点（每次可添加多个）")
    print("输入'q'结束输入")
    
    while True:
        print("\n--- 新历史数据点 ---")
        
        idx_code = input("  指数代码 (H30269/931468/931446): ").strip()
        if idx_code.lower() == 'q':
            break
            
        if idx_code not in INDICES_INFO:
            print(f"  ❌ 未知指数代码: {idx_code}")
            continue
            
        record_date = input("  记录日期 (YYYY-MM-DD): ").strip()
        if record_date.lower() == 'q':
            break
            
        pe = input("  PE-TTM值: ").strip()
        pb = input("  PB值: ").strip()
        div_yield = input("  股息率%（如无可留空）: ").strip()
        notes = input("  备注: ").strip()
        
        historical_data.append({
            "index_code": idx_code,
            "index_name": INDICES_INFO[idx_code]["name"],
            "record_date": record_date,
            "pe_ttm": float(pe) if pe else None,
            "pb": float(pb) if pb else None,
            "dividend_yield_pct": float(div_yield) if div_yield else None,
            "source": "Wind APP历史数据",
            "notes": notes
        })
        
        more = input("  继续添加？(y/n): ").strip().lower()
        if more != 'y':
            break
    
    if historical_data:
        # 写入CSV文件
        mode = 'a' if file_exists else 'w'
        with open(HISTORICAL_DATA_FILE, mode, encoding='utf-8', newline='') as f:
            fieldnames = [
                "index_code", "index_name", "record_date", 
                "pe_ttm", "pb", "dividend_yield_pct", "source", "notes"
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            
            if mode == 'w':
                writer.writeheader()
            
            for row in historical_data:
                writer.writerow(row)
        
        print(f"\n✅ 成功添加 {len(historical_data)} 条历史数据到: {HISTORICAL_DATA_FILE}")
        return historical_data
    else:
        print("\n⚠️ 未添加任何历史数据")
        return []


def check_data_completeness():
    """检查数据完整性"""
    print("\n" + "="*80)
    print("数据完整性检查")
    print("="*80)
    
    # 读取历史数据
    historical_data = []
    if os.path.exists(HISTORICAL_DATA_FILE):
        with open(HISTORICAL_DATA_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            historical_data = list(reader)
    
    print(f"📊 当前历史数据总量: {len(historical_data)} 条记录")
    
    # 按指数统计
    for idx_code, info in INDICES_INFO.items():
        idx_data = [row for row in historical_data if row['index_code'] == idx_code]
        
        print(f"\n【{info['name']} ({idx_code})】")
        print(f"  数据记录条数: {len(idx_data)}")
        
        if idx_data:
            # 日期范围
            dates = [row['record_date'] for row in idx_data]
            dates.sort()
            
            # 计算时间跨度
            if len(dates) >= 2:
                try:
                    start_date = datetime.strptime(dates[0], "%Y-%m-%d")
                    end_date = datetime.strptime(dates[-1], "%Y-%m-%d")
                    days_diff = (end_date - start_date).days
                    years_diff = days_diff / 365.25
                    
                    print(f"  最早记录: {dates[0]}")
                    print(f"  最晚记录: {dates[-1]}")
                    print(f"  时间跨度: {years_diff:.1f} 年")
                except:
                    pass
            
            # 缺失季度检查
            print(f"  建议记录季度: 3/31, 6/30, 9/30, 12/31")
    
    # 检查数据质量
    print(f"\n🔍 数据质量检查:")
    if historical_data:
        bad_records = []
        for i, row in enumerate(historical_data, 1):
            idx_code = row['index_code']
            if idx_code in INDICES_INFO:
                info = INDICES_INFO[idx_code]
                
                if row['pe_ttm']:
                    pe = float(row['pe_ttm'])
                    if not (info['expected_pe_range'][0] <= pe <= info['expected_pe_range'][1]):
                        bad_records.append(f"第{i}行: PE={pe} 超出范围 {info['expected_pe_range']}")
        
        if bad_records:
            print(f"  ⚠️ 发现 {len(bad_records)} 条异常数据:")
            for record in bad_records[:5]:  # 最多显示5条
                print(f"    - {record}")
            if len(bad_records) > 5:
                print(f"    - ... 还有 {len(bad_records)-5} 条")
        else:
            print(f"  ✅ 所有数据在合理范围内")
    else:
        print(f"  ℹ️ 暂无历史数据")
    
    return historical_data


def generate_next_recording_dates():
    """生成下次记录提醒日期"""
    print("\n" + "="*80)
    print("下次记录提醒日期")
    print("="*80)
    
    today = datetime.now()
    
    # 下个季度末日期
    quarter_months = [3, 6, 9, 12]  # 3月、6月、9月、12月
    current_year = today.year
    current_month = today.month
    
    # 找到下个季度末
    next_quarter_end = None
    for month in quarter_months:
        if month > current_month or (month == current_month and today.day < 15):
            # 使用当月或下个季度的月底
            if month == current_month:
                # 当前季度末（如果还没过15号）
                next_quarter_end = datetime(current_year, month, 31)
            else:
                # 下个季度末
                next_quarter_end = datetime(current_year, month, 30 if month in [6, 9] else 31)
            break
    
    # 如果今年没有下个季度了，使用明年3月
    if not next_quarter_end:
        next_quarter_end = datetime(current_year + 1, 3, 31)
    
    print(f"📅 建议记录日期:")
    print(f"   下个季度末: {next_quarter_end.strftime('%Y-%m-%d')} ({next_quarter_end.strftime('%A')})")
    
    # 计算到下次记录还有多少天
    days_to_next = (next_quarter_end - today).days
    print(f"   距离下次记录: {days_to_next} 天")
    
    # 手机提醒设置建议
    print(f"\n📱 手机提醒设置建议:")
    print(f"   1. 日历提醒: 每季度最后一天 15:00")
    print(f"   2. 提醒内容: \"记录Wind APP指数估值数据\"")
    print(f"   3. 重复: 每季度重复")
    
    return next_quarter_end


def integrate_with_existing_system():
    """与现有系统集成建议"""
    print("\n" + "="*80)
    print("与现有系统集成建议")
    print("="*80)
    
    print("""
📊 当前系统现状：
  • 数据来源：妙想API（仅2.1年历史）
  • 数据完整性：仅15.7%（严重不足）
  • H30269的97.1%分位：基于不完整数据，失真

🔄 集成策略：

1. 立即改进（今天）：
   • 在飞书日报中加入数据完整性警告
   • 基于数据不全，自动应用保守系数
   • 标记投资建议的可信度

2. 短期过渡（1-3个月）：
   • 开始记录Wind APP数据
   • 建立本地历史数据库
   • 逐步替换不完整的妙想API数据

3. 长期整合（3-6个月）：
   • 完全使用Wind APP数据
   • 建立10年以上完整历史数据库
   • 重新计算所有百分位指标

💡 技术实现：
""")

    # 技术实现代码示例
    print("```python")
    print("# 现有系统的数据整合示例")
    print("def get_enhanced_valuation_data():")
    print("    # 首先尝试使用Wind APP数据")
    print("    wind_data = load_wind_app_data()  # 您记录的Wind数据")
    print("    if wind_data and len(wind_data) >= 40:  # 至少40个数据点")
    print("        return calculate_percentile(wind_data)")
    print("    ")
    print("    # 降级使用妙想API数据（带警告）")
    print("    miaoxiang_data = load_miaoxiang_data()")
    print("    if miaoxiang_data:")
    print("        print(\"⚠️ 警告：使用不完整历史数据（仅2.1年）\")")
    print("        return calculate_percentile(miaoxiang_data)")
    print("    ")
    print("    return None")
    print("```")
    
    print(f"\n📁 您的数据存储位置:")
    print(f"   • 当前数据: {CURRENT_DATA_FILE}")
    print(f"   • 历史数据: {HISTORICAL_DATA_FILE}")
    print(f"   • 备份数据: {BACKUP_DATA_FILE}")
    print(f"   • 模板文件: {DATA_DIR}/")


def create_backup():
    """创建数据备份"""
    print("\n" + "="*80)
    print("创建数据备份")
    print("="*80)
    
    backup_data = {
        "backup_time": datetime.now().isoformat(),
        "files": [],
        "summary": {}
    }
    
    # 检查并备份文件
    files_to_backup = [
        (CURRENT_DATA_FILE, "当前数据"),
        (HISTORICAL_DATA_FILE, "历史数据")
    ]
    
    for filepath, description in files_to_backup:
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                backup_data[description] = content
            
            backup_data["files"].append({
                "name": description,
                "path": filepath,
                "size": os.path.getsize(filepath),
                "exists": True
            })
        else:
            backup_data["files"].append({
                "name": description, 
                "path": filepath,
                "exists": False
            })
    
    # 统计信息
    if os.path.exists(HISTORICAL_DATA_FILE):
        with open(HISTORICAL_DATA_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            backup_data["summary"]["historical_records"] = len(rows)
    
    # 保存备份
    with open(BACKUP_DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(backup_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 数据备份已创建: {BACKUP_DATA_FILE}")
    print(f"   备份时间: {backup_data['backup_time']}")
    
    if "summary" in backup_data and "historical_records" in backup_data["summary"]:
        print(f"   历史数据记录数: {backup_data['summary']['historical_records']}")
    
    return backup_data


def main_menu():
    """主菜单"""
    print("\n" + "="*80)
    print("Wind APP数据记录辅助工具")
    print("="*80)
    
    while True:
        print(f"\n📱 主菜单 - 数据目录: {DATA_DIR}")
        print("1. 📝 查看数据记录模板")
        print("2. 📊 记录当前数据")
        print("3. 📅 添加历史数据")
        print("4. ✅ 检查数据完整性")
        print("5. ⏰ 查看下次记录日期")
        print("6. 🔗 与现有系统集成建议")
        print("7. 💾 创建数据备份")
        print("8. 🚪 退出")
        
        choice = input("\n请选择操作 (1-8): ").strip()
        
        if choice == '1':
            create_data_template()
        elif choice == '2':
            record_current_data()
        elif choice == '3':
            add_historical_data()
        elif choice == '4':
            check_data_completeness()
        elif choice == '5':
            generate_next_recording_dates()
        elif choice == '6':
            integrate_with_existing_system()
        elif choice == '7':
            create_backup()
        elif choice == '8':
            print("\n👋 退出程序")
            break
        else:
            print("❌ 无效选择，请重新输入")


# ========================================================================
# 主程序
# ========================================================================

if __name__ == "__main__":
    print("="*80)
    print("Wind APP手机记录估值数据辅助工具")
    print("="*80)
    print(f"📁 数据存储目录: {DATA_DIR}")
    index_names = []
    for k, v in INDICES_INFO.items():
        index_names.append(f"{v['name']}({k})")
    print(f"🎯 目标指数: {', '.join(index_names)}")
    
    # 检查是否有历史数据
    if os.path.exists(HISTORICAL_DATA_FILE):
        with open(HISTORICAL_DATA_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            print(f"📊 当前历史数据: {len(rows)} 条记录")
    else:
        print(f"📊 当前历史数据: 暂无，需要开始记录")
    
    main_menu()
    
    print(f"\n🏁 程序结束")
    print(f"💡 提示: 数据已保存到 {DATA_DIR} 目录")
    print(f"📞 如需进一步帮助，随时联系")