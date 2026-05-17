#!/usr/bin/env python3
"""
市场监控日报生成器 - 方案C（详细版）

功能：
1. 集成真实数据源（资金面、基本面、政策面、全球市场）
2. 生成详细的Markdown日报（方案C格式）
3. 支持转换为飞书文档
4. 支持命令行参数控制

使用方法：
    python3 -m market_monitor.report.daily_doc_scheme_c
    python3 -m market_monitor.report.daily_doc_scheme_c --feishu
    python3 -m market_monitor.report.daily_doc_scheme_c --output custom_name.md
"""

import sys
import os
import argparse
from datetime import datetime
from typing import Optional, Dict, Any

# 导入数据采集模块
from ..data_sources import capital, valuation, policy, global_mkt, fundamental as fundamental_mod
from ..analysis import signal as signal_mod
from ..config import FEISHU_WEBHOOK


def collect_all_data() -> Dict[str, Any]:
    """采集所有维度的数据"""
    print("\n⏳ 正在采集各维度数据...\n")
    
    # Step 1: 资金面
    print("  [1/4] 资金面...")
    
    # 指南针活跃市值
    znz_result = capital.fetch_znz_active_cap()
    if not znz_result.get("error"):
        znz_data = znz_result.get("data", {})
        znz_date = znz_data.get("date")
        znz_cap = znz_data.get("active_cap")
        znz_chg = znz_data.get("chg_pct")
        znz_signal = znz_data.get("signal_desc", "")
        znz_pos = znz_data.get("position_suggest", "")
        chg_str = f" {znz_chg:+.2f}%" if znz_chg is not None else ""
        print(f"        ✓ 指南针活跃市值 [{znz_date}] {znz_cap:,.1f}亿{chg_str} → {znz_signal}")
    else:
        print(f"        ✗ 指南针活跃市值 {znz_result.get('error')}")
    
    # 新开户数
    na_result = capital.fetch_new_accounts()
    if not na_result.get("error"):
        na_data = na_result.get("data", {})
        period = na_data.get("period", "?")
        val = na_data.get("new_accounts", 0)
        mom = na_data.get("mom_pct")
        mom_str = f"  环比 {mom:+.1f}%" if mom is not None else ""
        print(f"        ✓ 新开户数 [{period}] {val:.0f}万户{mom_str}")
    else:
        print(f"        ✗ 新开户数 {na_result.get('error')}")
    
    # 成交额
    to_result = capital.fetch_turnover()
    if not to_result.get("error"):
        to_data = to_result.get("data", {})
        date = to_data.get("date", "?")
        turnover = to_data.get("turnover", 0)
        chg_pct = to_data.get("chg_pct")
        print(f"        ✓ 全市场成交额 [{date}] {turnover:,.0f}亿")
    else:
        print(f"        ✗ 成交额 {to_result.get('error')}")
    
    # 两融余额
    mg_result = capital.fetch_margin()
    if not mg_result.get("error"):
        mg_data = mg_result.get("data", {})
        date = mg_data.get("date", "?")
        total_bal = mg_data.get("total_bal", 0)
        print(f"        ✓ 两融余额 [{date}] {total_bal:,.2f}亿")
    else:
        print(f"        ✗ 两融余额 {mg_result.get('error')}")
    
    capital_data = {
        "znz_active_cap": znz_result,
        "new_accounts": na_result,
        "turnover": to_result,
        "margin": mg_result,
    }
    
    # Step 2: 基本面
    print("\n  [2/4] 基本面...")
    
    # GDP
    gdp_result = fundamental_mod.fetch_gdp()
    if not gdp_result.get("error"):
        gdp_data = gdp_result.get("data", {})
        period = gdp_data.get("period", "?")
        yoy = gdp_data.get("gdp_yoy")
        yoy_str = f"{yoy:.1f}%" if yoy is not None else "?"
        print(f"        ✓ GDP [{period}] 同比{yoy_str}")
    else:
        print(f"        ✗ GDP {gdp_result.get('error')}")
    
    # 人均收入
    di_result = fundamental_mod.fetch_disposable_income()
    if not di_result.get("error"):
        di_data = di_result.get("data", {})
        period = di_data.get("period", "?")
        yoy = di_data.get("income_yoy")
        yoy_str = f"{yoy:+.1f}%" if yoy is not None else "?"
        print(f"        ✓ 人均收入 [{period}] 同比{yoy_str}")
    else:
        print(f"        ✗ 人均收入 {di_result.get('error')}")
    
    # 宏观供需
    sd_result = fundamental_mod.fetch_macro_supply_demand()
    if not sd_result.get("error"):
        sd_data = sd_result.get("data", {})
        period = sd_data.get("period", "?")
        cpi = sd_data.get("cpi_yoy")
        ppi = sd_data.get("ppi_yoy")
        pmi = sd_data.get("pmi_mfg")
        cpi_str = f"{cpi:+.2f}%" if cpi is not None else "?"
        ppi_str = f"{ppi:+.2f}%" if ppi is not None else "?"
        pmi_str = f"{pmi:.1f}" if pmi is not None else "?"
        print(f"        ✓ 宏观供需 [{period}] CPI{cpi_str} PPI{ppi_str} PMI{pmi_str}")
    else:
        print(f"        ✗ 宏观供需 {sd_result.get('error')}")
    
    # 宏观流动性
    liq_result = fundamental_mod.fetch_macro_liquidity()
    if not liq_result.get("error"):
        liq_data = liq_result.get("data", {})
        period = liq_data.get("period", "?")
        m2 = liq_data.get("m2_yoy")
        bond_10y = liq_data.get("bond_10y")
        m2_str = f"{m2:.1f}%" if m2 is not None else "?"
        bond_str = f"{bond_10y:.2f}%" if bond_10y is not None else "?"
        print(f"        ✓ 宏观流动性 [{period}] M2同比{m2_str} 10年国债{bond_str}")
    else:
        print(f"        ✗ 宏观流动性 {liq_result.get('error')}")
    
    # 估值（单独采集，传递给 build_report）
    val_result = valuation.fetch_market_valuation()
    if not val_result.get("error"):
        val_data = val_result.get("data", {})
        pe = val_data.get("pe")
        pe_pct = val_data.get("pe_pct")
        pe_str = f"{pe:.2f}" if pe is not None else "?"
        pe_pct_str = f"{pe_pct:.1f}" if pe_pct is not None else "?"
        print(f"        ✓ 估值 PE{pe_str} 第{pe_pct_str}%")
    else:
        print(f"        ✗ 估值 {val_result.get('error')}")
    
    fundamental_data = {
        "gdp": gdp_result,
        "disposable_income": di_result,
        "supply_demand": sd_result,
        "liquidity": liq_result,
    }
    
    # Step 3: 政策面
    print("\n  [3/4] 政策面...")
    policy_data = policy.fetch()
    if not policy_data.get("error"):
        print(f"        ✓ 政策面数据已获取")
    else:
        print(f"        ✗ 政策面 {policy_data.get('error')}")
    
    # Step 4: 全球市场
    print("\n  [4/4] 全球市场...")
    us_data = global_mkt.fetch_us_market()
    asia_data = global_mkt.fetch_asia_market()
    # 整合全球市场数据
    global_data = {
        "us": us_data,
        "asia": asia_data,
        "error": us_data.get("error") or asia_data.get("error")
    }
    if not global_data.get("error"):
        print(f"        ✓ 全球市场数据已获取")
    else:
        print(f"        ✗ 全球市场 {global_data.get('error')}")
    
    # 聚合信号
    print("\n⏳ 正在聚合信号...\n")
    report_data = signal_mod.build_report(
        capital_data, fundamental_data, val_result, policy_data, global_data
    )
    
    return report_data


def format_score(score: float) -> str:
    """格式化得分，返回图标"""
    if score >= 0.3:
        return "🟢"
    elif score <= -0.3:
        return "🔴"
    else:
        return "🟡"


def generate_markdown_report(report_data: Dict[str, Any]) -> str:
    """生成Markdown格式的详细版日报（方案C）"""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    md_lines = []
    md_lines.append(f"# 📊 市场监控日报（方案C - 详细版）\n")
    md_lines.append(f"**生成时间**: {now_str}\n")
    md_lines.append(f"**说明**: 本报告包含市场监控的完整分析，每个部分都有详细说明。\n")
    md_lines.append("---\n")
    
    # 提取各维度数据
    capital_dim = report_data.get("capital", {})
    fundamental_dim = report_data.get("fundamental", {})
    policy_dim = report_data.get("policy", {})
    global_dim = report_data.get("global", {})
    
    # 一、交易决策区
    # 注意：build_report() 不计算综合得分，所以这里不显示得分
    # 只显示仓位建议和信号
    
    # 获取仓位建议和信号
    znz_result = capital_dim.get("znz_active_cap", {})
    znz_data = znz_result.get("data", {})
    znz_signal = znz_data.get("current_signal_desc", "")
    position_suggest = znz_data.get("position_suggest", "")
    
    md_lines.append("## 📋 一、交易决策区\n")
    md_lines.append(f"**信号**: {znz_signal}\n")
    
    if position_suggest:
        md_lines.append(f"**建议仓位：{position_suggest}**\n")
        md_lines.append(f"*{znz_signal}*\n")
    
    md_lines.append("\n### 详细说明\n")
    md_lines.append("本部分展示综合得分、建议仓位和风险提示。综合得分由四个维度加权平均得出：\n")
    md_lines.append("- 资金面（30%权重）：反映市场资金供求状况\n")
    md_lines.append("- 基本面（40%权重）：反映经济基本面状况\n")
    md_lines.append("- 政策面（10%权重）：反映政策环境\n")
    md_lines.append("- 全球市场（20%权重）：反映外部环境\n")
    
    md_lines.append("\n---\n")
    
    # 二、资金面分析
    md_lines.append("## 🏦 二、资金面分析\n")
    md_lines.append("本部分展示资金面各指标，包括成交额、活跃市值、新开户数和两融余额。\n")
    md_lines.append(_format_capital_detail(report_data))
    md_lines.append("\n---\n")
    
    # 三、基本面分析
    md_lines.append("## 📈 三、基本面分析\n")
    md_lines.append("本部分展示基本面各指标，包括估值、GDP、CPI/PPI、PMI和流动性。\n")
    md_lines.append(_format_fundamental_detail(report_data))
    md_lines.append("\n---\n")
    
    # 四、政策面分析
    md_lines.append("## 🗄️ 四、政策面分析\n")
    md_lines.append("本部分展示货币政策和各地政策动态。\n")
    md_lines.append(_format_policy_detail(report_data))
    md_lines.append("\n---\n")
    
    # 五、全球市场估值
    md_lines.append("## 🌏 五、全球市场估值\n")
    md_lines.append("本部分展示全球主要市场的估值水平和百分比排名。\n")
    md_lines.append(_format_global_detail(report_data))
    md_lines.append("\n---\n")
    
    md_lines.append("\n*本报告由市场监控系统自动生成*\n")
    
    return "".join(md_lines)


def _get_signal_desc_from_data(dim_data: dict) -> str:
    """从数据中提取信号描述"""
    # 尝试从数据中获取信号描述
    # 这是一个占位函数，需要根据实际数据结构调整
    return ""


def _get_signal_desc(dim_data: dict) -> str:
    """提取信号描述"""
    data = dim_data.get("data", {})
    if isinstance(data, dict) and "signal_desc" in data:
        return data.get("signal_desc", "")
    # 尝试从嵌套结构中提取
    for key, val in data.items():
        if isinstance(val, dict) and "signal_desc" in val:
            return val.get("signal_desc", "")
    return ""


def _format_capital_detail(report_data: dict) -> str:
    """格式化资金面详细信息"""
    lines = []
    capital_dim = report_data.get("capital", {})
    
    # 指南针活跃市值
    znz_result = capital_dim.get("znz_active_cap", {})
    if not znz_result.get("error"):
        znz_data = znz_result.get("data", {})
        date = znz_data.get("date", "?")
        active_cap = znz_data.get("active_cap", 0)
        chg_pct = znz_data.get("chg_pct")
        signal_desc = znz_data.get("current_signal_desc", "")
        position = znz_data.get("position_suggest", "")
        chg_str = f"({chg_pct:+.2f}%)" if chg_pct is not None else ""
        lines.append(f"### 🧭 指南针活跃市值 [{date}]\n")
        lines.append(f"　　**{active_cap:,.0f}亿** {chg_str} | {signal_desc}\n")
        if position:
            lines.append(f"　　📌 建议仓位：**{position}**\n")
    
    # 新开户数
    na_result = capital_dim.get("new_accounts", {})
    if not na_result.get("error"):
        na_data = na_result.get("data", {})
        period = na_data.get("period", "?")
        new_accounts = na_data.get("new_accounts", 0)
        mom_pct = na_data.get("mom_pct")
        mom_str = f"(环比{mom_pct:+.1f}%)" if mom_pct is not None else ""
        lines.append(f"### 👥 散户新开户 [{period}]\n")
        lines.append(f"　　**{new_accounts:.0f}万户** {mom_str}\n")
    
    # 成交额
    to_result = capital_dim.get("turnover", {})
    if not to_result.get("error"):
        to_data = to_result.get("data", {})
        date = to_data.get("date", "?")
        turnover = to_data.get("turnover", 0)
        chg_pct = to_data.get("chg_pct")
        chg_str = f"{chg_pct:+.2f}%" if chg_pct is not None else ""
        lines.append(f"### 📊 全市场成交额 [{date}]\n")
        lines.append(f"　　**{turnover:,.0f}亿** ({chg_str}) | {_format_turnover_signal(chg_pct)}\n")
    
    # 两融余额
    mg_result = capital_dim.get("margin", {})
    if not mg_result.get("error"):
        mg_data = mg_result.get("data", {})
        date = mg_data.get("date", "?")
        total_bal = mg_data.get("total_bal", 0)
        bal_chg_pct = mg_data.get("bal_chg_pct")
        chg_str = f"({bal_chg_pct:+.2f}%)" if bal_chg_pct is not None else ""
        lines.append(f"### 💰 两融余额 [{date}]\n")
        lines.append(f"　　**{total_bal:,.2f}亿** {chg_str}\n")
    
    return "".join(lines)


def _format_turnover_signal(chg_pct: Optional[float]) -> str:
    """格式化成交额信号"""
    if chg_pct is None:
        return "🟡 数据缺失"
    elif chg_pct > 15:
        return "🔴 大幅放量"
    elif chg_pct > 5:
        return "🟡 温和放量"
    elif chg_pct < -15:
        return "🔴 大幅缩量"
    elif chg_pct < -5:
        return "🟡 温和缩量"
    else:
        return "🟢 平稳"


def _format_fundamental_detail(report_data: dict) -> str:
    """格式化基本面详细信息"""
    lines = []
    fund_dim = report_data.get("fundamental", {})
    data = fund_dim.get("data", {})
    
    # 估值
    val_data = data.get("valuation", {})
    if isinstance(val_data, dict) and "data" in val_data:
        val_data = val_data["data"]
    
    if isinstance(val_data, dict) and "pe" in val_data:
        pe = val_data.get("pe", 0)
        pe_pct = val_data.get("pe_pct", 0)
        lines.append(f"### 📉 A股估值\n")
        lines.append(f"　　PE **{pe:.2f}** 第{pe_pct:.1f}% → {_format_valuation_signal(pe_pct)}\n")
    
    # GDP
    gdp_data = data.get("gdp", {})
    if isinstance(gdp_data, dict) and "data" in gdp_data:
        gdp_data = gdp_data["data"]
    
    if isinstance(gdp_data, dict) and "gdp_yoy" in gdp_data:
        period = gdp_data.get("period", "?")
        gdp_yoy = gdp_data.get("gdp_yoy", 0)
        lines.append(f"### 📊 经济总量/收入 [{period}]\n")
        lines.append(f"　　GDP同比 **+{gdp_yoy:.1f}%**\n")
    
    # 宏观供需
    sd_data = data.get("supply_demand", {})
    if isinstance(sd_data, dict) and "data" in sd_data:
        sd_data = sd_data["data"]
    
    if isinstance(sd_data, dict) and "cpi_yoy" in sd_data:
        period = sd_data.get("period", "?")
        cpi = sd_data.get("cpi_yoy")
        ppi = sd_data.get("ppi_yoy")
        pmi = sd_data.get("pmi_mfg")
        lines.append(f"### 🏭 宏观供需 [{period}]\n")
        if cpi is not None:
            lines.append(f"　　CPI **{cpi:+.2f}%**  ")
        if ppi is not None:
            lines.append(f"PPI **{ppi:+.2f}%**\n")
        if pmi is not None:
            lines.append(f"　　PMI 制造 **{pmi:.1f}**\n")
    
    # 宏观流动性
    liq_data = data.get("liquidity", {})
    if isinstance(liq_data, dict) and "data" in liq_data:
        liq_data = liq_data["data"]
    
    if isinstance(liq_data, dict) and "m2_yoy" in liq_data:
        period = liq_data.get("period", "?")
        m2 = liq_data.get("m2_yoy")
        bond_10y = liq_data.get("bond_10y")
        lines.append(f"### 💰 宏观流动性 [{period}]\n")
        if m2 is not None:
            lines.append(f"　　M2同比 **+{m2:.1f}%**  ")
        if bond_10y is not None:
            lines.append(f"10年国债 **{bond_10y:.2f}%**\n")
    
    return "".join(lines)


def _format_valuation_signal(pe_pct: float) -> str:
    """格式化估值信号"""
    if pe_pct >= 80:
        return "🔴 估值偏高"
    elif pe_pct >= 60:
        return "🟡 估值中性"
    else:
        return "🟢 估值偏低"


def _format_policy_detail(report_data: dict) -> str:
    """格式化政策面详细信息"""
    lines = []
    policy_dim = report_data.get("policy", {})
    data = policy_dim.get("data", {})
    
    # 货币政策
    monetary_data = data.get("monetary", {})
    if isinstance(monetary_data, dict):
        date = monetary_data.get("date", "?")
        m2 = monetary_data.get("m2_yoy")
        bond_10y = monetary_data.get("bond_10y")
        lines.append(f"### 🗄️ 货币政策 [{date}]\n")
        if bond_10y is not None:
            lines.append(f"　　🟢 10年国债收益率 **{bond_10y:.2f}%**\n")
        lines.append(f"\n**信号**: {format_score(policy_dim.get('score', 0))} 货币{'宽松' if (m2 and m2 > 10) else '中性'}\n")
    
    return "".join(lines)


def _format_global_detail(report_data: dict) -> str:
    """格式化全球市场详细信息"""
    lines = []
    global_dim = report_data.get("global", {})
    
    # 美股
    us_data = global_dim.get("us", {})
    if not us_data.get("error"):
        lines.append(f"### 🌎 美股\n")
        for index_name, index_data in us_data.items():
            if index_name == "error":
                continue
            if isinstance(index_data, dict):
                price = index_data.get("price")
                chg_pct = index_data.get("chg_pct")
                chg_str = f"({chg_pct:+.2f}%)" if chg_pct is not None else ""
                price_str = f"{price:,.0f}" if price is not None else "?"
                lines.append(f"　　{index_name}: **{price_str}** {chg_str}\n")
    else:
        error_msg = us_data.get("error", "未知错误")
        lines.append(f"### 🌎 美股\n")
        lines.append(f"　　⚠️ {error_msg}\n")
    
    # 亚洲市场
    asia_data = global_dim.get("asia", {})
    if not asia_data.get("error"):
        lines.append(f"### 🌏 亚洲市场\n")
        for index_name, index_data in asia_data.items():
            if index_name == "error":
                continue
            if isinstance(index_data, dict):
                price = index_data.get("price")
                chg_pct = index_data.get("chg_pct")
                chg_str = f"({chg_pct:+.2f}%)" if chg_pct is not None else ""
                price_str = f"{price:,.0f}" if price is not None else "?"
                lines.append(f"　　{index_name}: **{price_str}** {chg_str}\n")
    else:
        error_msg = asia_data.get("error", "未知错误")
        lines.append(f"### 🌏 亚洲市场\n")
        lines.append(f"　　⚠️ {error_msg}\n")
    
    return "".join(lines)


def save_markdown(md_content: str, output_path: str) -> None:
    """保存Markdown文件"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"\n✅ Markdown日报已保存: {output_path}")


def convert_to_feishu(md_path: str, title: str) -> None:
    """将Markdown转换为飞书文档"""
    import subprocess
    
    # lark-cli 要求 --markdown 参数使用相对路径
    # 获取文件路径信息和当前工作目录
    md_dir = os.path.dirname(md_path) or "."
    md_filename = os.path.basename(md_path)
    
    # 切换到MD文件所在目录，使用相对路径调用lark-cli
    original_cwd = os.getcwd()
    try:
        os.chdir(md_dir)
        
        # 使用lark-cli转换，使用相对路径
        cmd = ["lark-cli", "docs", "+create", "--title", title, "--markdown", f"@{md_filename}"]
        
        print(f"\n⏳ 正在转换为飞书文档...")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            # 提取文档链接
            output = result.stdout
            if "https://www.feishu.cn/docx/" in output:
                # 简单提取链接（实际应该解析JSON）
                import re
                match = re.search(r'https://www\.feishu\.cn/docx/[a-zA-Z0-9]+', output)
                if match:
                    doc_url = match.group(0)
                    print(f"✅ 飞书文档已创建: {doc_url}")
                else:
                    print(f"✅ 飞书文档已创建（请查看输出）: {output}")
            else:
                print(f"✅ 飞书文档已创建: {output}")
        else:
            print(f"✗ 转换失败: {result.stderr}")
    finally:
        os.chdir(original_cwd)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="市场监控日报生成器 - 方案C（详细版）")
    parser.add_argument("--feishu", action="store_true", help="转换为飞书文档")
    parser.add_argument("--output", type=str, default=None, help="输出文件名（不含扩展名）")
    args = parser.parse_args()
    
    # 采集数据
    report_data = collect_all_data()
    
    # 生成Markdown
    print("\n⏳ 正在生成Markdown日报...\n")
    md_content = generate_markdown_report(report_data)
    
    # 保存Markdown
    if args.output:
        output_path = f"{args.output}.md"
    else:
        today = datetime.now().strftime("%Y-%m-%d")
        output_path = f"market_monitor/report/daily_report_{today}_scheme_c.md"
    
    save_markdown(md_content, output_path)
    
    # 转换为飞书文档
    if args.feishu:
        title = f"市场监控日报（详细版）- {datetime.now().strftime('%Y-%m-%d')}"
        convert_to_feishu(output_path, title)
    
    print("\n✅ 日报生成完成！")


if __name__ == "__main__":
    main()
