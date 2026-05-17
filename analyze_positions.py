"""
根据仓位管理方案分析当前持仓
"""
import json
import os
import sys

# 添加项目路径
sys.path.insert(0, '.')

from market_monitor.analysis.position_manager import (
    PositionManager, Market, Style, TrendDirection, AllocationSummary
)
from market_monitor.data_sources import valuation as val_module
from market_monitor.analysis.zhixing import analyze_stock

# 读取持仓
with open("data/positions.json", "r") as f:
    positions_raw = json.load(f)

print("=" * 80)
print("📊 仓位管理分析报告")
print("=" * 80)

# 初始化仓位管理器
pm = PositionManager()

# 打印当前系数配置
pm.print_coefficients()

# ── 1. 获取市场估值数据 ──────────────────────────────────────────────────────
print("\n" + "=" * 80)
print("📈 市场估值数据")
print("=" * 80)

# ETF对应的指数估值映射
ETF_INDEX_MAPPING = {
    # A股ETF
    "159852": {"index": "H30269", "name": "软件指数"},  # 软件ETF嘉实
    "159869": {"index": "931446", "name": "动漫游戏指数"},  # 游戏ETF华夏
    "562500": {"index": "931468", "name": "机器人指数"},  # 机器人ETF华夏
    # 港股ETF
    "513180": {"index": "HSTECH", "name": "恒生科技"},  # 恒生科技ETF华夏
    "159202": {"index": "HSTECH", "name": "恒生科技"},  # 恒生互联网ETF
    "159217": {"index": "HSTECH", "name": "恒生科技"},  # 港股通创新药ETF
    "513090": {"index": "HSTECH", "name": "恒生科技"},  # 香港证券ETF易方达
}

# A股估值（万得全A除金融石油石化 881003.WI）
a_stock_val = val_module.fetch_index_valuation("881003.WI")
a_pe_pct = 50
a_date = ""
if a_stock_val.get("data"):
    a_pe = a_stock_val["data"].get("pe", 0)
    a_pe_pct = a_stock_val["data"].get("pe_pct", 50)
    a_date = a_stock_val["data"].get("date", "")
    print(f"  A股（万得全A除金融石油石化）: PE={a_pe:.2f}, 历史分位={a_pe_pct:.0f}%, 日期={a_date}")
else:
    print(f"  ⚠️ 未能获取A股估值数据，使用默认值50%")

# 港股估值（恒生科技）
hk_stock_val = val_module.fetch_index_valuation("HSTECH")
hk_pe_pct = 50
hk_date = ""
if hk_stock_val.get("data"):
    hk_pe = hk_stock_val["data"].get("pe", 0)
    hk_pe_pct = hk_stock_val["data"].get("pe_pct", 50)
    hk_date = hk_stock_val["data"].get("date", "")
    print(f"  港股（恒生科技）: PE={hk_pe:.2f}, 历史分位={hk_pe_pct:.0f}%, 日期={hk_date}")
else:
    print(f"  ⚠️ 未能获取港股估值数据，使用默认值50%")

# 美股估值
us_cape_pct = 75
print(f"  美股（标普500 CAPE）: 估算历史分位={us_cape_pct:.0f}%")

# ── 2. 获取趋势信号 ──────────────────────────────────────────────────────────
print("\n" + "=" * 80)
print("📉 趋势信号（知行）")
print("=" * 80)

trends = {}
for pos in positions_raw:
    code = pos["code"]
    name = pos["name"]
    try:
        analysis = analyze_stock(code, name)
        signal = analysis.get("signal", "观望")
        position = analysis.get("position", "")
        
        # 根据信号和排列判断趋势
        if "买入" in signal or ("多头排列" in position):
            trend_dir = TrendDirection.BULLISH
        elif "卖出" in signal or ("空头排列" in position):
            trend_dir = TrendDirection.BEARISH
        else:
            trend_dir = TrendDirection.NEUTRAL
        
        trends[code] = {
            "signal": signal,
            "trend": position,
            "direction": trend_dir
        }
        print(f"  {code} {name}: {signal} {position}")
    except Exception as e:
        print(f"  {code} {name}: 分析失败 - {str(e)[:50]}")
        trends[code] = {"signal": "观望", "trend": "", "direction": TrendDirection.NEUTRAL}

# ── 3. 获取活跃市值信号 ──────────────────────────────────────────────────────
print("\n" + "=" * 80)
print("💹 活跃市值信号（A股专用）")
print("=" * 80)

csv_path = "market_monitor/data/znz_active_cap.csv"
if os.path.exists(csv_path):
    import pandas as pd
    df = pd.read_csv(csv_path)
    if not df.empty:
        zone_type, active_cap, chg_pct = pm.get_latest_active_market_cap_signal(csv_path)
        zone_desc = {"bullish": "多头区间", "neutral": "中性区间", "bearish": "空头区间"}.get(zone_type, "未知")
        cap_str = f"{active_cap:,.0f}亿" if active_cap else "N/A"
        chg_str = f"{chg_pct:+.2f}%" if chg_pct else ""
        print(f"  最新信号: {zone_desc} ({zone_type})")
        print(f"  活跃市值: {cap_str} {chg_str}")
        print(f"  当前系数: {pm.get_active_market_cap_coef(zone_type):.2f}")
else:
    print(f"  ⚠️ 活跃市值数据不存在")
    zone_type = "neutral"

# ── 4. 计算目标仓位 ──────────────────────────────────────────────────────────
print("\n" + "=" * 80)
print("🎯 仓位配置分析")
print("=" * 80)

valuations = {
    Market.A_STOCK: a_pe_pct,
    Market.HK_STOCK: hk_pe_pct,
    Market.US_STOCK: us_cape_pct,
}

trend_dict = {}
for code, trend_data in trends.items():
    if code.startswith("5"):
        trend_dict[Market.HK_STOCK] = trend_data["direction"]
    else:
        trend_dict[Market.A_STOCK] = trend_data["direction"]

market_result = pm.get_market_allocation(
    valuations=valuations,
    trends=trend_dict,
    active_market_cap_signals={Market.A_STOCK: zone_type}
)

print(f"\n生成时间: {market_result['generated_at']}")
print(f"\n📊 市场配置建议:")
for market_id, data in market_result['market_allocations'].items():
    market_name = {"a_stock": "A股", "hk_stock": "港股", "us_stock": "美股"}.get(market_id, market_id)
    val_level = {"extremely_low": "极度低估", "low": "低估", "fair": "合理", "high": "偏高", "extremely_high": "极度偏高"}.get(data.get("valuation_level", ""), data.get("valuation_level", ""))
    trend = {"bullish": "多头", "neutral": "中性", "bearish": "空头"}.get(data.get("trend", ""), data.get("trend", ""))
    print(f"  {market_name}:")
    print(f"    估值分位: {data['valuation_percentile']:.1f}% ({val_level})")
    print(f"    趋势: {trend}")
    print(f"    基础仓位: {data['base_weight']*100:.0f}%")
    print(f"    估值系数: {data['valuation_coef']:.2f}")
    print(f"    趋势系数: {data['trend_coef']:.2f}")
    if 'active_market_cap_coef' in data:
        print(f"    活跃市值系数: {data['active_market_cap_coef']:.2f}")
    print(f"    原始权重: {data['raw_weight']*100:.1f}%")
    print(f"    目标仓位: {data['target_weight']*100:.1f}%")
    print(f"    建议调整: {data['adjustment']*100:+.1f}%")

print(f"\n📋 汇总:")
print(f"  权益仓位: {market_result['total_equity_ratio']*100:.1f}%")
print(f"  现金仓位: {market_result['cash_ratio']*100:.1f}%")

# ── 5. 持仓调仓建议 ──────────────────────────────────────────────────────────
print("\n" + "=" * 80)
print("⚠️ 持仓调仓建议")
print("=" * 80)

total_cost = sum(p["shares"] * p["cost_price"] for p in positions_raw)
total_value = total_cost * 0.94

positions_for_analysis = []
for pos in positions_raw:
    code = pos["code"]
    name = pos["name"]
    shares = pos["shares"]
    cost = pos["cost_price"]
    cost_value = shares * cost
    current_value = cost_value * 0.94
    loss_pct = (current_value - cost_value) / cost_value
    
    market = "hk_stock" if code.startswith("5") else "a_stock"
    
    positions_for_analysis.append({
        "code": code,
        "name": name,
        "market": market,
        "style": "high_elasticity",
        "weight": cost_value / total_cost,
        "loss_pct": loss_pct,
        "value": cost_value,
    })

val_for_rebalance = {}
etf_valuation_details = {}
for pos in positions_for_analysis:
    code = pos["code"]
    if pos["market"] == "a_stock":
        # 尝试获取ETF对应的指数估值
        index_info = ETF_INDEX_MAPPING.get(code)
        if index_info:
            index_val = val_module.fetch_index_valuation(index_info["index"])
            if index_val.get("data"):
                pe_pct = index_val["data"].get("pe_pct", a_pe_pct)
                pe = index_val["data"].get("pe", 0)
                date = index_val["data"].get("date", "")
                val_for_rebalance[code] = {"percentile": pe_pct, "metric": "pe"}
                etf_valuation_details[code] = {"pe": pe, "pe_pct": pe_pct, "date": date, "index_name": index_info["name"]}
                continue
        val_for_rebalance[code] = {"percentile": a_pe_pct, "metric": "pe"}
    else:
        # 尝试获取ETF对应的指数估值
        index_info = ETF_INDEX_MAPPING.get(code)
        if index_info:
            index_val = val_module.fetch_index_valuation(index_info["index"])
            if index_val.get("data"):
                pe_pct = index_val["data"].get("pe_pct", hk_pe_pct)
                pe = index_val["data"].get("pe", 0)
                date = index_val["data"].get("date", "")
                val_for_rebalance[code] = {"percentile": pe_pct, "metric": "pe"}
                etf_valuation_details[code] = {"pe": pe, "pe_pct": pe_pct, "date": date, "index_name": index_info["name"]}
                continue
        val_for_rebalance[code] = {"percentile": hk_pe_pct, "metric": "pe"}

trend_for_rebalance = {}
for pos in positions_for_analysis:
    code = pos["code"]
    trend_for_rebalance[code] = trends.get(code, {}).get("direction", TrendDirection.NEUTRAL)

summary = pm.suggest_rebalance(positions_for_analysis, val_for_rebalance, trend_for_rebalance)

print(f"\n生成时间: {summary.generated_at}")
print(f"组合总成本: {total_cost:,.0f} 元")
print(f"组合估算市值: {total_value:,.0f} 元")
print(f"估算浮亏: {(total_value - total_cost):,.0f} 元 ({(total_value/total_cost - 1)*100:+.1f}%)")
print(f"\n当前持仓调仓建议:")
print("-" * 100)
print(f"{'代码':<8} {'名称':<10} {'当前':<7} {'目标':<7} {'调整':<7} {'指数PE':<8} {'分位':<6} {'趋势':<6} {'止损'}")
print("-" * 100)

for item in summary.rebalance_items:
    code = item['code']
    adj_sign = "+" if item["adjustment"] >= 0 else ""
    val_lvl = {"extremely_low": "极低", "low": "低估", "fair": "合理", "high": "偏高", "extremely_high": "极高"}.get(item.get("valuation_level", ""), item.get("valuation_level", "")[:4])
    trend = {"bullish": "多头", "neutral": "中性", "bearish": "空头"}.get(item.get("trend", ""), item.get("trend", "")[:4])
    
    # 获取ETF对应的指数估值
    val_detail = etf_valuation_details.get(code, {})
    pe_str = f"{val_detail.get('pe', '-'):>7.1f}" if val_detail.get('pe') else "      -"
    pct_str = f"{val_detail.get('pe_pct', '-'):>5.0f}%" if val_detail.get('pe_pct') else "    -"
    
    print(f"{code:<8} {item['name']:<10} {item['current_weight']*100:>5.1f}% {item['target_weight']*100:>5.1f}% {adj_sign}{item['adjustment']*100:>4.1f}% {pe_str} {pct_str} {trend:>6} {item['stop_loss_action']}")

print("-" * 80)

# 汇总调整
total_adjustment = sum(item["adjustment"] for item in summary.rebalance_items)
print(f"净调整: {total_adjustment*100:+.1f}%")

# ── 6. 风险提示 ──────────────────────────────────────────────────────────────
print("\n" + "=" * 80)
print("⚠️ 风险提示")
print("=" * 80)

if a_pe_pct > 70:
    print(f"  🟡 A股估值偏高（PE分位 {a_pe_pct:.0f}%），注意仓位控制")
elif a_pe_pct < 30:
    print(f"  🟢 A股估值偏低（PE分位 {a_pe_pct:.0f}%），可适度加仓")

if hk_pe_pct > 70:
    print(f"  🟡 港股估值偏高（PE分位 {hk_pe_pct:.0f}%）")
elif hk_pe_pct < 30:
    print(f"  🟢 港股估值偏低（PE分位 {hk_pe_pct:.0f}%），可适度关注")

print("\n" + "=" * 80)
