#!/usr/bin/env python3
"""
仓位管理CLI工具 - Position Manager CLI

快速获取仓位配置建议和调仓建议

使用方法：
    # 1. 查看市场配置建议
    python -m market_monitor.analysis.position_cli market

    # 2. 查看止损建议
    python -m market_monitor.analysis.position_cli stop-loss --loss 0.08 --weight 0.15 --total 100000

    # 3. 查看调仓建议（需提供持仓文件）
    python -m market_monitor.analysis.position_cli rebalance --positions data/positions.json

    # 4. 交互式配置
    python -m market_monitor.analysis.position_cli interactive

    # 5. 生成配置报告
    python -m market_monitor.analysis.position_cli report --output position_report.md
"""

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Optional

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from market_monitor.analysis.position_manager import (
    PositionManager,
    Market,
    TrendDirection,
    quick_market_allocation,
    load_config_from_json,
)


def cmd_market(args):
    """市场配置建议命令"""
    pm = PositionManager()

    # 从参数或交互获取估值数据
    if args.a_pe is not None:
        a_pct = min(100, max(0, (args.a_pe - 8) / 30 * 100))
    else:
        a_pct = float(input("请输入A股PE值 (8-38): ") or 15)

    if args.hk_pb is not None:
        hk_pct = min(100, max(0, (args.hk_pb - 0.5) / 1.5 * 100))
    else:
        hk_pct = float(input("请输入港股PB值 (0.5-2.0): ") or 1.2)

    if args.us_cape is not None:
        us_pct = min(100, max(0, (args.us_cape - 10) / 30 * 100))
    else:
        us_pct = float(input("请输入美股CAPE值 (10-40): ") or 25)

    # 获取趋势
    trend_str = input("请输入A股趋势 (bullish/neutral/bearish，默认为neutral): ") or "neutral"
    try:
        trend = TrendDirection(trend_str)
    except ValueError:
        trend = TrendDirection.NEUTRAL

    result = quick_market_allocation(
        a_stock_pe=a_pct * 0.3 + 8,  # 还原PE值
        hk_pb=hk_pct * 0.015 + 0.5,
        us_cape=us_pct * 0.3 + 10,
        trend={"a_stock": trend_str, "hk_stock": "neutral", "us_stock": "neutral"},
    )

    print("\n" + "=" * 60)
    print("📊 市场配置建议")
    print("=" * 60)
    print(f"输入: A股PE={a_pct * 0.3 + 8:.1f}, 港股PB={hk_pct * 0.015 + 0.5:.2f}, 美股CAPE={us_pct * 0.3 + 10:.1f}")
    print()

    for market_id, data in result["market_allocations"].items():
        print(f"【{data['name']}】")
        print(f"  估值百分位: {data['valuation_percentile']:.1f}% ({data['valuation_level']})")
        print(f"  趋势: {data['trend']}")
        print(f"  估值系数: {data['valuation_coef']:.2f}")
        print(f"  趋势系数: {data['trend_coef']:.2f}")
        print(f"  目标仓位: {data['target_weight']*100:.1f}%")
        print(f"  调整幅度: {data['adjustment']*100:+.1f}%")
        print()
    print(f"总权益仓位: {result['total_equity_ratio']*100:.1f}%")
    print(f"现金仓位: {result['cash_ratio']*100:.1f}%")


def cmd_stop_loss(args):
    """止损建议命令"""
    pm = PositionManager()

    loss_pct = args.loss
    weight = args.weight
    total = args.total

    result = pm.calculate_stop_loss(loss_pct, weight, total)

    print("\n" + "=" * 60)
    print("📉 止损建议")
    print("=" * 60)
    print(f"当前亏损: {loss_pct*100:.1f}%")
    print(f"当前仓位: {weight*100:.1f}% (市值: ¥{weight * total:,.0f})")
    print()
    print(f"建议动作: {result['action']}")
    print(f"建议仓位: {result['suggested_weight']*100:.1f}%")
    print(f"仓位调整: {result['adjustment']*100:+.1f}%")

    if result['reduce_scale']:
        print(f"减仓比例: {result['reduce_scale']*100:.0f}%")

    print()
    print(f"定投补仓: {result['dca_recommendation']['description']}")
    if result['dca_recommendation']['amount'] > 0:
        print(f"补仓金额: ¥{result['dca_recommendation']['amount']:,.0f}")

    if result['risk_alert']:
        print()
        print("⚠️ 风险警告: 亏损超过15%，建议认真评估持仓决策!")


def cmd_rebalance(args):
    """调仓建议命令"""
    pm = PositionManager()

    # 加载持仓
    positions_path = args.positions or "data/positions.json"

    if not os.path.exists(positions_path):
        print(f"❌ 找不到持仓文件: {positions_path}")
        return

    with open(positions_path, "r", encoding="utf-8") as f:
        positions = json.load(f)

    print(f"\n📁 已加载 {len(positions)} 条持仓记录")

    # 交互式获取估值数据
    print("\n请输入各持仓的估值百分位 (0-100，留空默认为50):")
    valuations = {}
    for pos in positions:
        code = pos.get("code", "")
        name = pos.get("name", "")
        val = input(f"  {code} {name}: ") or "50"
        try:
            valuations[code] = {"percentile": float(val), "metric": "pe"}
        except ValueError:
            valuations[code] = {"percentile": 50.0, "metric": "pe"}

    # 交互式获取趋势
    print("\n请输入各持仓的趋势 (bullish/neutral/bearish，留空默认为neutral):")
    trends = {}
    for pos in positions:
        code = pos.get("code", "")
        name = pos.get("name", "")
        trend_str = input(f"  {code} {name}: ") or "neutral"
        try:
            trends[code] = TrendDirection(trend_str)
        except ValueError:
            trends[code] = TrendDirection.NEUTRAL

    # 计算总市值
    total_value = sum(
        pos.get("shares", 0) * pos.get("cost_price", 0)
        for pos in positions
    )

    # 添加计算所需字段
    for pos in positions:
        pos["weight"] = pos.get("shares", 0) * pos.get("cost_price", 0) / total_value if total_value > 0 else 0
        pos["loss_pct"] = 0.0  # 假设当前盈亏为0
        pos["value"] = pos.get("shares", 0) * pos.get("cost_price", 0)
        # 推断市场
        code = pos.get("code", "")
        if code.startswith("5") or code.startswith("15"):
            pos["market"] = Market.A_STOCK.value
            pos["style"] = "high_elasticity"
        elif code.startswith("hk") or code.startswith("港"):
            pos["market"] = Market.HK_STOCK.value
            pos["style"] = "high_elasticity"
        else:
            pos["market"] = Market.A_STOCK.value
            pos["style"] = "balanced"

    # 生成调仓建议
    summary = pm.suggest_rebalance(positions, valuations, trends)
    print(pm.generate_report(summary))


def cmd_interactive(args):
    """交互式配置命令"""
    print("\n" + "=" * 60)
    print("🎯 交互式仓位配置")
    print("=" * 60)

    pm = PositionManager()

    # 1. 风险偏好
    print("\n请选择风险偏好:")
    print("  1. 保守型 (权益仓位≤60%)")
    print("  2. 稳健型 (权益仓位≤80%)")
    print("  3. 激进型 (权益仓位≤95%)")

    risk_choice = input("请输入选项 (1-3，默认为2): ") or "2"
    risk_map = {"1": "conservative", "2": "moderate", "3": "aggressive"}
    risk = risk_map.get(risk_choice, "moderate")

    # 2. 市场估值
    print("\n请输入各市场估值百分位 (0-100):")
    valuations = {}
    for market in [Market.A_STOCK, Market.HK_STOCK, Market.US_STOCK]:
        val = input(f"  {market.value}: ") or "50"
        try:
            valuations[market] = float(val)
        except ValueError:
            valuations[market] = 50.0

    # 3. 趋势
    print("\n请输入各市场趋势 (bullish/neutral/bearish):")
    trends = {}
    for market in [Market.A_STOCK, Market.HK_STOCK, Market.US_STOCK]:
        trend_str = input(f"  {market.value}: ") or "neutral"
        try:
            trends[market] = TrendDirection(trend_str)
        except ValueError:
            trends[market] = TrendDirection.NEUTRAL

    # 生成结果
    result = pm.get_market_allocation(valuations, trends)

    print("\n" + "=" * 60)
    print("📊 仓位配置建议")
    print("=" * 60)

    for market_id, data in result["market_allocations"].items():
        print(f"\n【{data['name']}】")
        print(f"  估值水平: {data['valuation_level']} ({data['valuation_percentile']:.1f}%)")
        print(f"  目标仓位: {data['target_weight']*100:.1f}%")

    print(f"\n总权益仓位: {result['total_equity_ratio']*100:.1f}%")
    print(f"现金仓位: {result['cash_ratio']*100:.1f}%")

    # 风格建议
    style_result = pm.get_style_allocation()
    print("\n📋 风格配置建议")
    for style_id, data in style_result["style_allocations"].items():
        print(f"  {data['name']}: ≤{data['max_weight']*100:.0f}%")


def cmd_report(args):
    """生成报告命令"""
    pm = PositionManager()

    # 模拟数据
    positions = [
        {"code": "513180", "name": "恒生科技ETF", "market": "hk_stock", "style": "high_elasticity", "weight": 0.25, "loss_pct": 0.05, "value": 25000},
        {"code": "159202", "name": "恒生互联网ETF", "market": "hk_stock", "style": "high_elasticity", "weight": 0.15, "loss_pct": -0.03, "value": 15000},
        {"code": "159217", "name": "港股通创新药ETF", "market": "hk_stock", "style": "high_elasticity", "weight": 0.12, "loss_pct": 0.08, "value": 12000},
        {"code": "159852", "name": "软件ETF嘉实", "market": "a_stock", "style": "high_elasticity", "weight": 0.10, "loss_pct": -0.02, "value": 10000},
        {"code": "159869", "name": "游戏ETF华夏", "market": "a_stock", "style": "high_elasticity", "weight": 0.05, "loss_pct": 0.10, "value": 5000},
        {"code": "562500", "name": "机器人ETF华夏", "market": "a_stock", "style": "high_elasticity", "weight": 0.08, "loss_pct": 0.12, "value": 8000},
        {"code": "513090", "name": "香港证券ETF", "market": "hk_stock", "style": "balanced", "weight": 0.05, "loss_pct": 0.03, "value": 5000},
    ]

    valuations = {
        "513180": {"percentile": 40.0, "metric": "pb"},
        "159202": {"percentile": 50.0, "metric": "pb"},
        "159217": {"percentile": 35.0, "metric": "pe"},
        "159852": {"percentile": 60.0, "metric": "pe"},
        "159869": {"percentile": 55.0, "metric": "pe"},
        "562500": {"percentile": 65.0, "metric": "pe"},
        "513090": {"percentile": 45.0, "metric": "pb"},
    }

    trends = {
        "513180": TrendDirection.BULLISH,
        "159202": TrendDirection.NEUTRAL,
        "159217": TrendDirection.BULLISH,
        "159852": TrendDirection.NEUTRAL,
        "159869": TrendDirection.BEARISH,
        "562500": TrendDirection.BEARISH,
        "513090": TrendDirection.NEUTRAL,
    }

    summary = pm.suggest_rebalance(positions, valuations, trends)
    report = pm.generate_report(summary)

    if args.output:
        output_path = args.output
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"✅ 报告已保存至: {output_path}")
    else:
        print(report)


def main():
    parser = argparse.ArgumentParser(
        description="仓位管理CLI工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m market_monitor.analysis.position_cli market --a-pe 12 --hk-pb 1.2
  python -m market_monitor.analysis.position_cli stop-loss --loss 0.08 --weight 0.15 --total 100000
  python -m market_monitor.analysis.position_cli interactive
  python -m market_monitor.analysis.position_cli report --output position_report.md
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # market 命令
    parser_market = subparsers.add_parser("market", help="获取市场配置建议")
    parser_market.add_argument("--a-pe", type=float, help="A股PE值")
    parser_market.add_argument("--hk-pb", type=float, help="港股PB值")
    parser_market.add_argument("--us-cape", type=float, help="美股CAPE值")

    # stop-loss 命令
    parser_sl = subparsers.add_parser("stop-loss", help="获取止损建议")
    parser_sl.add_argument("--loss", type=float, required=True, help="当前亏损比例 (如0.08表示8%)")
    parser_sl.add_argument("--weight", type=float, required=True, help="当前仓位权重 (如0.15表示15%)")
    parser_sl.add_argument("--total", type=float, required=True, help="组合总市值")

    # rebalance 命令
    parser_rb = subparsers.add_parser("rebalance", help="获取调仓建议")
    parser_rb.add_argument("--positions", type=str, help="持仓文件路径")

    # interactive 命令
    subparsers.add_parser("interactive", help="交互式配置")

    # report 命令
    parser_report = subparsers.add_parser("report", help="生成配置报告")
    parser_report.add_argument("--output", type=str, help="输出文件路径")

    args = parser.parse_args()

    if args.command == "market":
        cmd_market(args)
    elif args.command == "stop-loss":
        cmd_stop_loss(args)
    elif args.command == "rebalance":
        cmd_rebalance(args)
    elif args.command == "interactive":
        cmd_interactive(args)
    elif args.command == "report":
        cmd_report(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
