"""
持仓ETF详细分析报告生成脚本。

生成一份详尽的持仓分析 Markdown 报告，包含：
- 持仓概览与汇总统计
- 每只ETF的详细技术分析
- 知行趋势线信号解读
- 成交量与量价配合分析
- 异常量能警示
- 操作建议

使用方法：
    python -m market_monitor.report.portfolio_report --positions-file ./positions.json
    python -m market_monitor.report.portfolio_report --positions-file ./positions.json --output ./report.md
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import argparse
from datetime import datetime
from typing import List, Dict

from market_monitor.data_sources.index_analysis import (
    load_etf_index_mapping,
    analyze_portfolio_indices,
)
from market_monitor.analysis import zhixing


def generate_detailed_report(etf_analysis: List[Dict], output_path: str = None) -> str:
    """
    生成详细的持仓ETF分析 Markdown 报告。

    Args:
        etf_analysis: 持仓ETF分析结果列表
        output_path: 可选，保存到的文件路径

    Returns:
        Markdown 格式的报告文本
    """
    if not etf_analysis:
        return "# 📊 持仓ETF分析报告\n\n暂无持仓数据\n"

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # ── 汇总统计 ───────────────────────────────────────────────────────────────
    total = len(etf_analysis)
    avg_score = sum(e.get("pattern_score", 0) for e in etf_analysis) / total if total else 0
    bullish = [e for e in etf_analysis if "多头排列" in e.get("position", "")]
    buy_signals = [e for e in etf_analysis if e.get("signal") == "BUY"]
    good_pattern = [e for e in etf_analysis if e.get("pattern_score", 0) >= 60]
    sell_signals = [e for e in etf_analysis if e.get("signal") == "SELL"]

    # 按评分排序
    sorted_etfs = sorted(etf_analysis, key=lambda x: x.get("pattern_score", 0), reverse=True)

    # ── 构建 Markdown ───────────────────────────────────────────────────────────
    lines = []

    # 标题
    lines.append("# 📊 持仓ETF详细分析报告")
    lines.append(f"\n**报告生成时间**: {now}\n")
    lines.append("---\n")

    # 1. 持仓概览
    lines.append("## 1️⃣ 持仓概览\n")

    # 信号汇总
    lines.append("### 📈 信号汇总\n")
    summary_items = []
    if buy_signals:
        summary_items.append(f"🟢 买入信号 **{len(buy_signals)}** 只")
    if bullish:
        summary_items.append(f"🟢 多头排列 **{len(bullish)}** 只")
    if good_pattern:
        summary_items.append(f"✅ 好形态 **{len(good_pattern)}** 只")
    if sell_signals:
        summary_items.append(f"🔴 卖出信号 **{len(sell_signals)}** 只")

    total_bear = [e for e in etf_analysis if "空头排列" in e.get("position", "")]
    if total_bear:
        summary_items.append(f"🔴 空头排列 **{len(total_bear)}** 只")

    summary_items.append(f"📊 平均评分 **{avg_score:.0f}**/100")

    lines.append("| " + " | ".join([""] + summary_items + [""]) + " |")
    lines.append("|:" + "|".join(["---" for _ in summary_items]) + "|")
    lines.append("| " + " | ".join(["**状态**"] + summary_items) + " |\n")

    # 持仓明细表
    lines.append("### 📋 持仓明细\n")
    lines.append("| ETF名称 | 跟踪指数 | 知行信号 | 排列状态 | 评分 | 操作建议 |")
    lines.append("|:--------|:--------|:---------|:---------|:----:|:--------:|")

    for e in sorted_etfs:
        etf_name = e.get("etf_name", "")[:12]
        index_name = e.get("index_code", "")[:10]
        signal = e.get("signal", "")
        position = e.get("position", "")
        score = e.get("pattern_score", 0)
        price_pos = e.get("price_position_60d", 50)

        # 信号解读
        if signal == "BUY":
            sig_text = "🟢买入"
        elif signal == "SELL":
            sig_text = "🔴卖出"
        elif signal == "HOLD_BULL":
            sig_text = "🟡持多"
        elif signal == "HOLD_BEAR":
            sig_text = "🟠持空"
        elif "多头排列" in position:
            sig_text = "🟢多头"
        elif "空头排列" in position:
            sig_text = "🔴空头"
        else:
            sig_text = "⚪观望"

        # 操作建议
        if signal == "BUY":
            action = "🔴买入"
        elif signal == "SELL":
            action = "🟢卖出"
        elif signal == "HOLD_BULL":
            action = "✅持有"
        elif signal == "HOLD_BEAR":
            action = "⚠️减仓"
        elif price_pos < 20:
            action = "💡关注"
        else:
            action = "⏸️观望"

        lines.append(f"| {etf_name} | {index_name} | {sig_text} | {position or '纠缠整理'} | {score:.0f} | {action} |")

    lines.append("")

    # 2. 详细分析
    lines.append("---\n")
    lines.append("## 2️⃣ 详细技术分析\n")

    for i, e in enumerate(sorted_etfs, 1):
        etf_name = e.get("etf_name", "")
        index_code = e.get("index_code", "")
        index_name = e.get("index_name", "")

        lines.append(f"### {i}. {etf_name} ({index_code})\n")
        lines.append(f"**跟踪指数**: {index_name}\n")

        # 知行信号
        signal = e.get("signal", "")
        position = e.get("position", "")
        trend_dir = e.get("trend_direction", "")

        lines.append("#### 📉 知行趋势线信号\n")
        lines.append(f"| 指标 | 数值 |")
        lines.append("|:-----|:-----|")

        if signal == "BUY":
            sig_icon = "🟢"
            sig_text = "买入信号"
        elif signal == "SELL":
            sig_icon = "🔴"
            sig_text = "卖出信号"
        elif signal == "HOLD_BULL":
            sig_icon = "🟡"
            sig_text = "多头持有"
        elif signal == "HOLD_BEAR":
            sig_icon = "🟠"
            sig_text = "空头持有"
        else:
            sig_icon = "⚪"
            sig_text = "观望"

        lines.append(f"| 知行信号 | {sig_icon} {sig_text} |")
        lines.append(f"| 排列状态 | {position or '纠缠整理'} |")
        lines.append(f"| 趋势方向 | {trend_dir or '震荡'} |\n")

        # 均线分析
        lines.append("#### 📊 均线分析\n")
        ma5 = e.get("ma5", 0) or 0
        ma10 = e.get("ma10", 0) or 0
        ma20 = e.get("ma20", 0) or 0
        ma60 = e.get("ma60", 0) or 0
        close = e.get("close", 0) or 0

        def safe_pct(val, ref):
            if ref and ref != 0:
                return f"{'▲' if val > ref else '▼'} {abs((val/ref-1)*100):.2f}%"
            return "N/A"

        lines.append(f"| 均线 | 数值 | 价格对比 |")
        lines.append("|:----:|:----:|:--------:|")
        lines.append(f"| MA5 | {ma5:.4f} | {safe_pct(close, ma5)} |")
        lines.append(f"| MA10 | {ma10:.4f} | {safe_pct(close, ma10)} |")
        lines.append(f"| MA20 | {ma20:.4f} | {safe_pct(close, ma20)} |")
        lines.append(f"| MA60 | {ma60:.4f} | {safe_pct(close, ma60)} |\n")

        # KDJ 分析
        lines.append("#### 🎯 KDJ 指标\n")
        kdj_k = e.get("kdj_k", 0)
        kdj_d = e.get("kdj_d", 0)
        kdj_j = e.get("kdj_j", 0)

        if kdj_k < 20:
            kdj_status = "🔴 超卖区域，可能反弹"
        elif kdj_k > 80:
            kdj_status = "🟢 超买区域，注意风险"
        elif kdj_k > kdj_d and kdj_d > 50:
            kdj_status = "🟡 强势区域"
        elif kdj_k < kdj_d and kdj_d < 50:
            kdj_status = "🟠 弱势区域"
        else:
            kdj_status = "⚪ 中性区域"

        lines.append(f"| 指标 | 数值 | 状态 |")
        lines.append("|:----:|:----:|:-----:|")
        lines.append(f"| K | {kdj_k:.2f} | {'偏高' if kdj_k > 70 else '偏低' if kdj_k < 30 else '正常'} |")
        lines.append(f"| D | {kdj_d:.2f} | - |")
        lines.append(f"| J | {kdj_j:.2f} | - |")
        lines.append(f"| **综合判断** | - | {kdj_status} |\n")

        # RSI 分析
        lines.append("#### 📉 RSI 指标\n")
        rsi = e.get("rsi14", 50)

        if rsi < 30:
            rsi_status = "🔴 严重超卖，可能企稳反弹"
            rsi_icon = "🔴"
        elif rsi < 40:
            rsi_status = "🟠 超卖区域，谨慎偏多"
            rsi_icon = "🟠"
        elif rsi < 60:
            rsi_status = "⚪ 中性区域"
            rsi_icon = "⚪"
        elif rsi < 70:
            rsi_status = "🟡 偏强区域"
            rsi_icon = "🟡"
        else:
            rsi_status = "🟢 超买区域，注意风险"
            rsi_icon = "🟢"

        lines.append(f"| RSI(14) | **{rsi:.2f}** |")
        lines.append(f"| **状态判断** | {rsi_icon} {rsi_status} |\n")

        # 成交量分析
        lines.append("#### 📊 成交量分析\n")
        vol_ratio = e.get("volume_ratio", 1)
        vol_match = e.get("volume_price_match_detail", False)
        price_pos = e.get("price_position_60d", 50)

        lines.append(f"| 指标 | 数值 | 解读 |")
        lines.append("|:----:|:----:|:-----:|")

        if vol_ratio > 2:
            vol_status = "🔴 巨量放大"
        elif vol_ratio > 1.5:
            vol_status = "🟡 明显放量"
        elif vol_ratio < 0.5:
            vol_status = "🟢 地量萎缩"
        elif vol_ratio < 0.8:
            vol_status = "🟠 缩量整理"
        else:
            vol_status = "⚪ 量能正常"

        lines.append(f"| 放量倍数 | {vol_ratio:.2f}x | {vol_status} |")

        if vol_match:
            vol_match_text = "✅ 量价配合健康"
        else:
            vol_match_text = "⚠️ 量价背离"

        lines.append(f"| 量价配合 | {'是' if vol_match else '否'} | {vol_match_text} |")
        lines.append(f"| 60日价格位置 | {price_pos:.1f}% | {'低位' if price_pos < 30 else '高位' if price_pos > 70 else '中性'} |\n")

        # MACD 分析
        lines.append("#### 📉 MACD 指标\n")
        macd_diff = e.get("macd_diff", 0)
        macd_dea = e.get("macd_dea", 0)
        macd_hist = e.get("macd_hist", 0)

        if macd_hist > 0:
            macd_status = "🟢 红柱（多方主导）"
        else:
            macd_status = "🔴 绿柱（空方主导）"

        lines.append(f"| 指标 | 数值 |")
        lines.append("|:----:|:----:|")
        lines.append(f"| DIF | {macd_diff:.6f} |")
        lines.append(f"| DEA | {macd_dea:.6f} |")
        lines.append(f"| MACD柱 | {macd_hist:.6f} |")
        lines.append(f"| **状态** | {macd_status} |\n")

        # 异常量能警示
        abnormal = e.get("abnormal_signals", [])
        if abnormal:
            lines.append("#### ⚠️ 异常量能警示\n")
            for sig in abnormal:
                sig_type = sig.get("type", "")
                desc = sig.get("description", "")
                severity = sig.get("severity", "")
                emoji = "🔴" if severity == "danger" else "🟡" if severity == "warning" else "🟢"
                lines.append(f"- {emoji} **{sig_type}**: {desc}")
            lines.append("")

        lines.append("---\n")

    # 3. 综合建议
    lines.append("## 3️⃣ 综合操作建议\n")

    # 分类建议
    if buy_signals:
        lines.append("### 🟢 重点关注（买入信号）\n")
        for e in buy_signals:
            lines.append(f"- **{e.get('etf_name', '')}**: 出现买入信号，可适当关注")
        lines.append("")

    if bullish and not buy_signals:
        lines.append("### 🟡 持有观察（多头排列）\n")
        for e in bullish:
            lines.append(f"- **{e.get('etf_name', '')}**: 多头排列中，可继续持有")
        lines.append("")

    # 超跌关注
    oversold = [e for e in etf_analysis if e.get("rsi14", 50) < 35 and e.get("price_position_60d", 50) < 30]
    if oversold:
        lines.append("### 💡 超跌关注（低位+超卖）\n")
        for e in oversold:
            lines.append(f"- **{e.get('etf_name', '')}**: RSI={e.get('rsi14', 0):.0f}, 价格位置={e.get('price_position_60d', 0):.0f}%，等待企稳信号")
        lines.append("")

    # 空头排列
    if total_bear and not buy_signals and not bullish:
        lines.append("### 🔴 谨慎对待（空头排列）\n")
        lines.append("- 持仓整体处于下降趋势，建议控制仓位\n")
        lines.append("- 耐心等待趋势扭转信号\n")
        lines.append("")

    # 4. 风险提示
    lines.append("## 4️⃣ 风险提示\n")
    lines.append("1. 📊 本报告仅供参考，不构成投资建议")
    lines.append("2. ⚠️ 市场有风险，投资需谨慎")
    lines.append("3. 📈 过往业绩不代表未来表现")
    lines.append("4. 🔄 建议定期复盘，动态调整持仓")

    lines.append("\n---\n")
    lines.append(f"*报告生成时间: {now}*")

    # 合并
    md = "\n".join(lines)

    # 保存
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(md)
        print(f"✅ 报告已保存: {output_path}")

    return md


def main():
    parser = argparse.ArgumentParser(description="生成持仓ETF详细分析报告")
    parser.add_argument("--positions-file", "-p", default="./positions.json",
                        help="持仓配置文件路径 (默认: ./positions.json)")
    parser.add_argument("--output", "-o", default=None,
                        help="输出文件路径 (默认: 自动生成)")

    args = parser.parse_args()

    # 加载持仓
    import json
    positions_file = args.positions_file
    if os.path.exists(positions_file):
        with open(positions_file, 'r', encoding='utf-8') as f:
            positions = json.load(f)
        etf_codes = [p.get("code", "") for p in positions]
        etf_names = [p.get("name", "") for p in positions]
        etf_codes = [c for c in etf_codes if c.startswith(("51", "15", "56"))]
        print(f"📂 从 {positions_file} 加载 {len(etf_codes)} 只ETF")
    else:
        print(f"❌ 持仓文件不存在: {positions_file}")
        return

    # 执行分析
    print("🔄 正在分析持仓ETF...")
    result = analyze_portfolio_indices(
        etf_codes=etf_codes,
        etf_names=etf_names,
    )

    if not result:
        print("❌ 分析失败")
        return

    indices = result.get("indices", [])
    print(f"✅ 分析完成: {len(indices)} 只ETF")

    # 生成报告
    if args.output:
        output_path = args.output
    else:
        date_str = datetime.now().strftime("%Y-%m-%d")
        output_path = f"./portfolio_report_{date_str}.md"

    md = generate_detailed_report(indices, output_path)
    print(f"\n📊 报告已生成: {output_path}")


if __name__ == "__main__":
    main()
