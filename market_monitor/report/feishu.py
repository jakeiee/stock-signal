"""
飞书机器人推送（market_monitor）。

卡片结构（与 Markdown 日报对齐，三段式）：
  ① 交易决策区：综合结论 + 建议仓位 + 主要风险点 + 近期关注
  ② 四维度快览：各维度得分 + 标签 + 一句话摘要 + 关键指标
  ③ 指标详情：资金面 / 基本面 / 政策面 / 全球市场

数据逻辑复用 md_report 中的辅助函数，格式转为飞书 lark_md。
"""

import requests
import os
from typing import Optional

from ..config import FEISHU_WEBHOOK
from ..data_sources.trendonify import fetch_trendonify_valuation
from .valuation_image import generate_valuation_image
# 临时修复：提供缺失的函数实现
def _score_icon(score, neutral_threshold=0.3):
    """根据得分返回图标"""
    if score >= neutral_threshold:
        return "🟢"
    elif score <= -neutral_threshold:
        return "🔴"
    else:
        return "🟡"

def _score_to_position(comp_score, znz_signal, cap_score, fun_score, pol_score, glb_score):
    """根据信号计算仓位建议"""
    znz_pos = znz_signal.get("position_suggest", "0-10%") if znz_signal and isinstance(znz_signal, dict) else "0-10%"
    return znz_pos, "指南针活跃市值信号"

def _collect_risks(report_data):
    """收集风险点"""
    risks = []
    # 简化的风险收集逻辑
    return risks

def _collect_watchlist(report_data):
    """收集关注事项"""
    watchlist = []
    # 简化的关注事项收集逻辑
    return watchlist

def _fmt(num, format_str=".1f"):
    """格式化数字"""
    try:
        return format(num, format_str)
    except:
        return str(num)

def _chg_str(val):
    """格式化涨跌幅"""
    if val is None:
        return "--"
    sign = "+" if val >= 0 else "-"
    return f"{sign}{abs(val):.2f}%"


# ─────────────────────────────────────────────────────────────
# 维度摘要（一句话）
# ─────────────────────────────────────────────────────────────

def _get_cap_data(cap_dim: dict) -> dict:
    """兼容多种数据结构，提取嵌套的 data 层"""
    if not isinstance(cap_dim, dict):
        return {}
    
    # 如果直接包含 znz_active_cap 等键（扁平结构）
    if "znz_active_cap" in cap_dim:
        result = {}
        for key, val in cap_dim.items():
            # 如果值是 {"data": {...}, "error": ...} 格式，提取 data 层
            if isinstance(val, dict) and "data" in val:
                result[key] = val.get("data", {})
            else:
                result[key] = val
        return result
    
    # 如果是 {"data": {...}} 包装结构
    inner = cap_dim.get("data", {})
    if isinstance(inner, dict) and "znz_active_cap" not in inner:
        # 内部又嵌套了 data
        return inner
    
    return inner


def _cap_summary(cap_dim: dict) -> str:
    cap_data = _get_cap_data(cap_dim)
    znz = cap_data.get("znz_active_cap", {})
    mg  = cap_data.get("margin", {})
    na  = cap_data.get("new_accounts", {})
    parts = []

    znz_s = znz.get("signal") if znz and znz.get("error") is None else None
    znz_c = znz.get("chg_pct") if znz and znz.get("error") is None else None
    mg_chg = mg.get("bal_chg_pct") if mg and mg.get("error") is None else None

    if znz_s == "incremental":   parts.append("🟢增量资金入场")
    elif znz_s == "exit":        parts.append("🔴资金离场警示")
    elif znz_c is not None:      parts.append("🟡活跃市值" + ("回升" if znz_c > 0 else "回落"))

    if mg_chg is not None:
        if mg_chg > 0.3:   parts.append("杠杆回暖")
        elif mg_chg < -0.3: parts.append("杠杆降温")

    na_val = na.get("new_accounts") if na and na.get("error") is None else None
    if na_val is not None:
        if na_val >= 500:      parts.append("散户情绪过热")
        elif na_val <= 200:    parts.append("散户情绪低迷")

    return " | ".join(parts) if parts else "数据获取中"


def _fun_summary(fun_dim: dict) -> str:
    fd  = fun_dim.get("data", {})
    val = fd.get("valuation", {})
    gdp = fd.get("gdp", {})
    sd  = fd.get("supply_demand", {})
    parts = []

    pe_pct  = val.get("pe_pct") if val and val.get("error") is None else None
    gdp_yoy = gdp.get("gdp_yoy") if gdp and gdp.get("error") is None else None
    pmi     = sd.get("pmi_mfg") if sd and sd.get("error") is None else None

    if pe_pct is not None:
        if pe_pct >= 80:   parts.append("估值偏高")
        elif pe_pct < 20:  parts.append("估值偏低")
        else:              parts.append("估值正常")
    if gdp_yoy is not None:
        parts.append("GDP" + ("稳健" if gdp_yoy >= 5 else ("平稳" if gdp_yoy >= 3 else "偏弱")))
    if pmi is not None:
        parts.append("PMI" + ("扩张" if pmi >= 50 else ("临界" if pmi >= 45 else "收缩")))

    return " | ".join(parts) if parts else "数据获取中"


def _glb_summary(glb_dim: dict) -> str:
    gd   = glb_dim.get("data", {})
    us   = gd.get("us", {})
    asia = gd.get("asia", {})
    parts = []

    if us and us.get("error") is None:
        spx   = (us.get("SPX") or {}).get("chg5d_pct")
        above = us.get("spx_above_ma200")
        if spx is not None:
            parts.append("美股" + ("强势" if spx >= 3 else ("回调" if spx <= -3 else "震荡")))
        if above is False:
            parts.append("均线空头")
    if asia and asia.get("error") is None:
        hsi_chg = (asia.get("HSI") or {}).get("chg5d_pct")
        if hsi_chg is not None:
            parts.append("港股" + ("走强" if hsi_chg >= 3 else ("偏弱" if hsi_chg <= -3 else "震荡")))

    return "，".join(parts) if parts else "数据获取中"


# ─────────────────────────────────────────────────────────────
# 各维度指标 KPI（关键数字，飞书卡片格式）
# ─────────────────────────────────────────────────────────────

def _cap_kpi_block(cap_dim: dict) -> str:
    """资金面指标详情块（飞书 lark_md 格式）。
    
    格式：数据 + 信号 + 趋势，判断标准移至右上方
    
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    方案说明（生成时使用其中一种方案）：
    方案1：紧凑行内式（推荐）- 数据/信号/趋势紧凑排列，判断标准在右上角
    方案2：分组标题式 - 每个指标带分组标题，右侧显示判断标准
    方案3：卡片矩阵式 - 使用分隔符形成视觉块
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    """
    cap_data = _get_cap_data(cap_dim)
    lines = []

    # ═══════════════════════════════════════════════════
    # 方案1：紧凑行内式（推荐使用）
    # ═══════════════════════════════════════════════════
    
    # ─────────────────────────────────────────────────────
    # 全市场成交额
    # ─────────────────────────────────────────────────────
    to = cap_data.get("turnover", {})
    if to and to.get("error") is None and to.get("turnover") is not None:
        to_date   = to.get("date", "?")
        turnover  = to.get("turnover")
        to_prev   = to.get("turnover_prev")
        chg_pct   = to.get("chg_pct")
        
        # 数据
        to_str = f"**{turnover:,.0f}亿**"
        prev_str = f"(昨日{to_prev:,.0f}亿)" if to_prev is not None else ""
        
        # 信号
        if chg_pct is not None:
            if chg_pct >= 15:
                to_icon, to_sig = "🔴", "放量明显"
            elif chg_pct >= 5:
                to_icon, to_sig = "🟡", "温和放量"
            elif chg_pct >= -5:
                to_icon, to_sig = "🟡", "基本持平"
            elif chg_pct >= -15:
                to_icon, to_sig = "🟡", "温和缩量"
            else:
                to_icon, to_sig = "🟢", "缩量明显"
        else:
            to_icon, to_sig = "🟡", "数据异常"
        
        # 趋势
        if chg_pct is not None:
            if chg_pct >= 15:
                trend_icon = "📈大幅放量"
            elif chg_pct >= 5:
                trend_icon = "📈温和放量"
            elif chg_pct >= -5:
                trend_icon = "➡️基本持平"
            elif chg_pct >= -15:
                trend_icon = "📉温和缩量"
            else:
                trend_icon = "📉大幅缩量"
        else:
            trend_icon = "--"
        
        # 判断标准
        criteria = "[>15%=放量 | <-15%=缩量]"
        
        lines.append(f"📊 全市场成交额 [{to_date}]")
        lines.append(f"　　{to_str} {prev_str} | {to_icon}{to_sig} | {trend_icon} {criteria}")
        lines.append("")
    
    # ─────────────────────────────────────────────────────
    # 指南针活跃市值
    # ─────────────────────────────────────────────────────
    znz = cap_data.get("znz_active_cap", {})
    if znz and znz.get("error") is None:
        znz_date = znz.get("date", "?")
        znz_cap  = znz.get("active_cap")
        znz_chg  = znz.get("chg_pct")
        znz_sig  = znz.get("signal", "neutral")
        znz_desc = znz.get("signal_desc", "")
        znz_pos  = znz.get("position_suggest", "")
        
        # 数据
        cap_str  = f"**{znz_cap/10000:.2f}万亿**" if znz_cap is not None else "--"
        chg_str  = f"({znz_chg:+.2f}%)" if znz_chg is not None else ""
        
        # 信号
        sig_icon = {"incremental": "🟢", "exit": "🔴", "neutral": "🟡"}.get(znz_sig, "🟡")
        sig_text = znz_desc or {"incremental": "增量入场", "exit": "资金离场", "neutral": "观望"}.get(znz_sig, "观望")
        
        # 趋势（基于涨跌幅趋势判断）
        if znz_chg is not None:
            if znz_chg >= 4:
                trend_icon = "📈强势"
            elif znz_chg >= 0:
                trend_icon = "➡️平稳"
            elif znz_chg >= -2.3:
                trend_icon = "➡️回落"
            else:
                trend_icon = "📉偏弱"
        else:
            trend_icon = "--"
        
        # 判断标准（放在右上方，用方括号标识）
        criteria = "[≥4%=入场 | ≤-2.3%=离场]"
        
        lines.append(f"🧭 指南针活跃市值 [{znz_date}]")
        lines.append(f"　　{cap_str} {chg_str} | {sig_icon}{sig_text} | {trend_icon} {criteria}")
        if znz_pos:
            lines.append(f"　　📌 建议仓位：**{znz_pos}**")
    else:
        lines.append("🧭 指南针活跃市值 — 暂无数据（使用 --znz 参数录入）")

    lines.append("")

    # ─────────────────────────────────────────────────────
    # 散户新开户
    # ─────────────────────────────────────────────────────
    na = cap_data.get("new_accounts", {})
    if na and na.get("error") is None and na.get("new_accounts") is not None:
        na_val = na.get("new_accounts")
        period = na.get("period", "?")
        mom    = na.get("mom_pct")
        
        # 数据
        na_str = f"**{na_val:.0f}万户**"
        mom_str = f"(环比{mom:+.1f}%)" if mom is not None else ""
        
        # 信号
        if na_val >= 600:
            na_icon, na_sig = "🔴🔴", "顶部预警"
        elif na_val >= 500:
            na_icon, na_sig = "🔴", "接近顶部"
        elif na_val >= 400:
            na_icon, na_sig = "🟡", "偏热"
        elif na_val >= 200:
            na_icon, na_sig = "🟢", "正常"
        else:
            na_icon, na_sig = "🟢🟢", "偏冷/底部"
        
        # 趋势（基于环比变化方向）
        if mom is not None:
            if mom >= 10:
                trend_icon = "📈激增"
            elif mom >= 0:
                trend_icon = "➡️增长"
            elif mom >= -10:
                trend_icon = "➡️回落"
            else:
                trend_icon = "📉骤降"
        else:
            trend_icon = "--"
        
        # 判断标准
        criteria = "[正常200-400万 | 偏热400-500万 | ≥600预警]"
        
        lines.append(f"👥 散户新开户 [{period}]")
        lines.append(f"　　{na_str} {mom_str} | {na_icon}{na_sig} | {trend_icon} {criteria}")
    else:
        lines.append("👥 散户新开户 — 暂无数据")

    lines.append("")

    # ─────────────────────────────────────────────────────
    # 杠杆资金（两融）
    # ─────────────────────────────────────────────────────
    mg = cap_data.get("margin", {})
    if mg and mg.get("error") is None:
        # 计算两融总额
        rz_bal = mg.get("rz_bal")
        rq_bal = mg.get("rq_bal")
        total_bal = rz_bal + rq_bal if rz_bal is not None and rq_bal is not None else None
        
        mg_date   = mg.get("date", "?")
        chg       = mg.get("bal_chg")
        chgpct    = mg.get("bal_chg_pct")
        rzbuy     = mg.get("rz_buy")
        mktto     = mg.get("mkt_turnover")
        tratio    = mg.get("turnover_ratio")

        # 数据
        bal_str = f"**{total_bal/10000:.2f}万亿**" if total_bal is not None else "--"
        chg_str = f"(日{chg:+.0f}亿, {chgpct:+.2f}%)" if chg is not None else ""
        
        # 信号（基于余额变化趋势）
        if chgpct is not None:
            if chgpct >= 0.5:
                mg_icon, mg_sig = "🔴", "杠杆回暖"
            elif chgpct >= 0:
                mg_icon, mg_sig = "🟡", "基本持平"
            elif chgpct >= -0.5:
                mg_icon, mg_sig = "🟡", "略有下降"
            else:
                mg_icon, mg_sig = "🟢", "杠杆降温"
        else:
            mg_icon, mg_sig = "🟡", "正常"
        
        # 趋势
        if chgpct is not None:
            if chgpct >= 0.5:
                trend_icon = "📈明显回升"
            elif chgpct >= 0:
                trend_icon = "➡️基本平稳"
            elif chgpct >= -0.5:
                trend_icon = "➡️小幅下降"
            else:
                trend_icon = "📉持续下降"
        else:
            trend_icon = "--"
        
        # 判断标准
        criteria = "[日变化>0.5%=回暖 | <-0.5%=降温]"
        
        lines.append(f"⚖️ 杠杆资金（两融） [{mg_date}]")
        lines.append(f"　　{bal_str} {chg_str} | {mg_icon}{mg_sig} | {trend_icon} {criteria}")
        
        # 附加信息（非核心显示）
        if mktto is not None:
            lines.append(f"　　💰 成交 {mktto:,.0f}亿 | 融资余额 {rz_bal:,.0f}亿")
        if rzbuy is not None:
            lines.append(f"　　📊 融资买入 {rzbuy:,.0f}亿 | 融资/成交 {tratio:.2f}%" if tratio is not None else f"　　📊 融资买入 {rzbuy:,.0f}亿")

        # 趋势警示
        try:
            from ..data_sources.capital import fetch_margin_history, analyze_margin_trend
            history = fetch_margin_history(n=20)
            trend = analyze_margin_trend(history, window=10)
            if trend.get("warning"):
                lines.append(f"\n⚠️ **趋势警示**：{trend['warning_reason']}")
        except Exception:
            pass
    else:
        lines.append("⚖️ 杠杆资金（两融）— 暂无数据")

    return "\n".join(lines)


def _fun_kpi_block(fun_dim: dict) -> str:
    """基本面指标详情块（飞书 lark_md 格式）。"""
    fd = fun_dim.get("data", {})
    lines = []

    # 估值
    val = fd.get("valuation", {})
    if val and val.get("error") is None and val.get("pe") is not None:
        pe     = val.get("pe")
        pe_pct = val.get("pe_pct")
        pb     = val.get("pb")
        div    = val.get("div_yield")
        vdate  = val.get("date", "?")
        if pe_pct is not None:
            if pe_pct >= 80:   v_icon = "🔴 估值偏高"
            elif pe_pct < 20:  v_icon = "🟢 估值偏低"
            else:              v_icon = "🟡 估值正常"
        else:
            v_icon = ""
        pb_str  = f" | PB {pb:.2f}" if pb else ""
        div_str = f" | 股息 {div:.2f}%" if div else ""
        pct_str = f"第{pe_pct:.0f}%" if pe_pct is not None else ""
        lines.append(f"📉 **A股估值** 万得全A（除金融石油石化）[{vdate}]")
        lines.append(f"　　PE **{pe:.1f}** {pct_str}{pb_str}{div_str} → {v_icon}")
    else:
        lines.append("📉 A股估值 — 暂无数据")

    lines.append("")

    # GDP + 人均收入：方案D格式（数据+走势+解读），一行显示
    gdp = fd.get("gdp", {})
    gdp_interp = fd.get("gdp_interpretation", {})
    di  = fd.get("disposable_income", {})
    has_gdp = gdp and gdp.get("error") is None and gdp.get("gdp_yoy") is not None
    has_di  = di  and di.get("error") is None  and di.get("income_yoy") is not None
    
    if has_gdp or has_di:
        period = gdp.get("period", "?") if has_gdp else di.get("period", "?")
        lines.append(f"📈 **经济总量/收入** [{period}]")
        
        # GDP数据+走势+解读（方案D格式）
        if has_gdp:
            gdp_yoy = gdp["gdp_yoy"]
            gdp_mom = gdp.get("gdp_qoq")  # 环比
            g_icon = "🟢" if gdp_yoy >= 5 else ("🟡" if gdp_yoy >= 3 else "🔴")
            gdp_trend = "↑" if gdp_mom and gdp_mom > 0 else ("↓" if gdp_mom and gdp_mom < 0 else "")
            
            # 从gdp_interpretation获取官方解读
            interp_text = ""
            if gdp_interp and gdp_interp.get("error") is None:
                interpretation = gdp_interp.get("interpretation", {})
                summary = interpretation.get("summary", "") if interpretation else ""
                if summary:
                    first_sentence = summary.split("。")[0] if "。" in summary else summary
                    # 提取核心解读（简化：去除具体数字，保留关键结论）
                    # 如："2025年，国内生产总值首次跃上140万亿元新台阶比上年增长5.0%" → "GDP首跃140万亿，稳增长"
                    if "140万亿" in first_sentence or "140万亿元" in first_sentence:
                        interp_text = "GDP首跃140万亿，稳增长"
                    elif "稳" in first_sentence or "向好" in first_sentence:
                        if "向好" in first_sentence:
                            interp_text = "经济稳中向好"
                        elif "向优" in first_sentence:
                            interp_text = "经济向优发展"
                        else:
                            interp_text = "经济运行平稳"
                    elif "增长5.0%" in first_sentence:
                        interp_text = "GDP增长5.0%，稳增长"
                    else:
                        # 取前30字
                        interp_text = first_sentence[:30] + "..." if len(first_sentence) > 30 else first_sentence
                        interp_text = first_sentence
            
            # 组装：GDP同比5.0%↑ 经济稳中向好
            if interp_text:
                lines.append(f"　　GDP同比 {gdp_yoy:+.1f}%{gdp_trend} {interp_text}")
            else:
                lines.append(f"　　GDP同比 {gdp_yoy:+.1f}%{gdp_trend} {g_icon}")
            
            # 产业结构（次要信息，可选是否显示）
            p3_pct = gdp.get("p3_pct")
            p3_delta = gdp.get("p3_pct_yoy_delta")
            if p3_pct is not None and p3_delta is not None:
                lines.append(f"　　三产占比 {p3_pct:.1f}%，同比{p3_delta:+.1f}pp")
        
        # 人均收入
        if has_di:
            di_yoy = di["income_yoy"]
            d_icon = "🟢" if di_yoy >= 6 else ("🟡" if di_yoy >= 4 else "🔴")
            lines.append(f"　　人均收入同比 {di_yoy:+.1f}% {d_icon}")

    lines.append("")

    # PMI/CPI/PPI
    sd = fd.get("supply_demand", {})
    if sd and sd.get("error") is None:
        cpi    = sd.get("cpi_yoy")
        ppi    = sd.get("ppi_yoy")
        spread = sd.get("ppi_cpi_spread")
        pmi    = sd.get("pmi_mfg")
        pmi_s  = sd.get("pmi_svc")
        period = sd.get("period", "?")
        lines.append(f"🏭 **宏观供需** [{period}]")
        
        # CPI/PPI：方案D格式（极简，数据+趋势+解读），同行显示
        if cpi is not None or ppi is not None:
            # 环比变化
            cpi_mom = sd.get("cpi_mom")
            ppi_mom = sd.get("ppi_mom")
            
            # 构建数据部分：CPI+1.3%↑/PPI-0.9% 格式
            cpi_arrow = "↑" if cpi_mom and cpi_mom > 0 else ("↓" if cpi_mom and cpi_mom < 0 else "")
            ppi_arrow = "↑" if ppi_mom and ppi_mom > 0 else ("↓" if ppi_mom and ppi_mom < 0 else "")
            
            data_parts = []
            if cpi is not None:
                data_parts.append(f"CPI{cpi:+.1f}%{cpi_arrow}")
            if ppi is not None:
                data_parts.append(f"PPI{ppi:+.1f}%{ppi_arrow}")
            data_str = "/".join(data_parts)
            
            # 官方解读（浓缩核心）
            cpi_ppi_interp = fd.get("cpi_ppi_interpretation", {})
            interp_text = ""
            if cpi_ppi_interp and cpi_ppi_interp.get("error") is None:
                interpretation = cpi_ppi_interp.get("interpretation", {})
                summary = interpretation.get("summary", "") if interpretation else ""
                if summary:
                    first_sentence = summary.split("。")[0] if "。" in summary else summary
                    # 提取核心解读（去除具体数值，保留趋势和原因）
                    # 如："2月份，受春节因素影响，CPI环比上涨1.0%，同比上涨1.3%" → "春节因素影响，CPI环比涨幅创两年新高"
                    if "受" in first_sentence and "影响" in first_sentence:
                        # 提取原因和关键结论
                        import re
                        cause_match = re.search(r'受(.+?)影响', first_sentence)
                        cause = cause_match.group(1) if cause_match else ""
                        
                        # 提取关键结论关键词
                        if "上涨" in first_sentence or "回升" in first_sentence:
                            if "最高" in first_sentence or "扩大" in first_sentence:
                                interp_text = f"{cause}：CPI环比涨幅创近两年最高"
                            elif "收窄" in first_sentence:
                                interp_text = f"{cause}，PPI降幅连续收窄"
                            else:
                                interp_text = f"{cause}，价格有所回升"
                        elif "下降" in first_sentence or "回落" in first_sentence:
                            interp_text = f"{cause}，价格继续下行"
                        else:
                            interp_text = f"{cause}"
                    else:
                        # 无法提取则简化
                        interp_text = first_sentence[:40] + "..." if len(first_sentence) > 40 else first_sentence
            
            # 组装：CPI+1.3%↑/PPI-0.9% 解读
            if interp_text:
                lines.append(f"　　{data_str} {interp_text}")
            else:
                lines.append(f"　　{data_str}")
        
        # PMI：方案C格式，制造业+非制造业+趋势+解读，同行显示不截断
        if pmi is not None or pmi_s is not None:
            # 计算环比变化
            pmi_mom = sd.get("pmi_mfg_mom")
            pmi_s_mom = sd.get("pmi_svc_mom")
            
            # 趋势箭头
            mfg_arrow = "↑" if pmi_mom and pmi_mom > 0 else ("↓" if pmi_mom and pmi_mom < 0 else "")
            svc_arrow = "↑" if pmi_s_mom and pmi_s_mom > 0 else ("↓" if pmi_s_mom and pmi_s_mom < 0 else "")
            
            # 状态标签
            mfg_status = "扩张" if pmi >= 50.5 else ("临界" if pmi >= 49.5 else "收缩") if pmi else ""
            svc_status = "扩张" if pmi_s >= 50.5 else ("临界" if pmi_s >= 49.5 else "收缩") if pmi_s else ""
            
            # 构建数据部分
            data_parts = []
            if pmi is not None:
                data_parts.append(f"制造业{pmi:.1f}{mfg_arrow}")
            if pmi_s is not None:
                data_parts.append(f"非制造业{pmi_s:.1f}{svc_arrow}")
            data_str = " / ".join(data_parts)
            
            # 官方解读（浓缩一句，不截断）
            pmi_interp = fd.get("pmi_interpretation", {})
            interp_text = ""
            if pmi_interp and pmi_interp.get("error") is None:
                interp = pmi_interp.get("interpretation", {})
                summary = interp.get("summary", "")
                if summary:
                    # 取完整第一句话，不截断
                    first_sentence = summary.split("。")[0] if "。" in summary else summary
                    # 提取核心解读：去除开头的时间/具体数值，保留趋势/原因描述
                    # 例如："2月份，受春节假期等因素影响，制造业..." → "受春节假期等因素影响，制造业景气回落"
                    if "受" in first_sentence:
                        # 找到"受X影响"部分
                        import re
                        match = re.search(r'受(.+?)影响[，\s]', first_sentence)
                        if match:
                            cause = match.group(1)  # 如"春节假期等因素"
                            # 提取核心结论（去除具体数值变化描述）
                            # 包含"下降/上升/回落/回升"等关键词的句子
                            if "下降" in first_sentence or "回落" in first_sentence:
                                if "非制造业" in first_sentence and "上升" in first_sentence:
                                    interp_text = f"受{cause}影响，制造业回落但非制造业回暖"
                                else:
                                    interp_text = f"受{cause}影响，制造业景气回落"
                            elif "上升" in first_sentence or "回升" in first_sentence:
                                interp_text = f"受{cause}影响，景气有所回升"
                            else:
                                interp_text = f"受{cause}影响"
                        else:
                            # 无法提取则保留完整句（截断到合理长度）
                            interp_text = first_sentence[:60] + "..." if len(first_sentence) > 60 else first_sentence
                    else:
                        interp_text = first_sentence
            
            # 组装：PMI 数据 解读
            if interp_text:
                lines.append(f"　　PMI {data_str} {interp_text}")
            else:
                lines.append(f"　　PMI {data_str}")

    lines.append("")

    # M2/社融/国债
    liq = fd.get("liquidity", {})
    if liq and liq.get("error") is None:
        m2   = liq.get("m2_yoy")
        sf   = liq.get("social_fin_yoy")
        bond = liq.get("bond_10y")
        period = liq.get("period", "?")
        lines.append(f"💰 **宏观流动性** [{period}]")
        if m2 is not None:
            mi = "🟢货币宽松" if m2 >= 10 else ("🟡货币稳健" if m2 >= 6 else "🔴货币偏紧")
            lines.append(f"　　M2同比 **{m2:+.1f}%** → {mi}")
        if sf is not None:
            si = "🟢融资旺盛" if sf >= 12 else ("🟡融资正常" if sf >= 8 else ("🟡融资偏弱" if sf >= 5 else "🔴融资低迷"))
            lines.append(f"　　社融同比 **{sf:+.1f}%** → {si}")
        if bond is not None:
            bi = "🟢利率低位，利好成长股" if bond < 2 else ("🟡利率偏低" if bond < 2.5 else ("🟡利率正常" if bond <= 3 else "🔴利率偏高"))
            lines.append(f"　　10年国债 **{bond:.2f}%** → {bi}")

    return "\n".join(lines)


def _policy_kpi_block(pol_dim: dict) -> str:
    """政策面指标详情块（飞书 lark_md 格式）。"""
    pol_data = pol_dim.get("data", {})
    monetary = pol_data.get("monetary", {})
    lines = []
    
    if monetary and monetary.get("error") is None:
        signal = monetary.get("signal", "🟡 货币中性")
        date = monetary.get("date", "")
        lines.append(f"**🗄️ 货币政策** [{date}]")
        
        # 数据来源
        source = monetary.get("source", "")
        
        # LPR（有数据就展示）
        lpr_1y = monetary.get("lpr_1y")
        lpr_5y = monetary.get("lpr_5y")
        if lpr_1y and lpr_5y:
            try:
                lpr_5y_val = float(lpr_5y) if isinstance(lpr_5y, str) else lpr_5y
                lpr_icon = "🟢" if lpr_5y_val <= 3.95 else "🔴"
            except:
                lpr_icon = "🟡"
            src_tag = "（AkShare）" if "akshare" in source.lower() else ""
            lines.append(f"　　{lpr_icon} LPR(1年) **{lpr_1y}%** | LPR(5年) **{lpr_5y}%**{src_tag}")
        
        # 准备金率（有数据就展示）
        rrr_large = monetary.get("rrr_large")
        rrr_small = monetary.get("rrr_small")
        if rrr_large:
            src_tag = "（AkShare）" if "akshare" in source.lower() else ""
            lines.append(f"　　🟡 存款准备金率 大行**{rrr_large}%** | 小行**{rrr_small}%**{src_tag}")
        
        # 国债收益率（有数据就展示）
        bond = monetary.get("bond_10y")
        if bond:
            try:
                bond_val = float(bond) if isinstance(bond, str) else bond
                bond_icon = "🟢" if bond_val < 2.0 else ("🟡" if bond_val < 2.5 else "🔴")
            except:
                bond_icon = "🟡"
            src_tag = "（ChinaMoney）" if "chinamoney" in source.lower() else ""
            lines.append(f"　　{bond_icon} 10年国债收益率 **{bond}%**{src_tag}")
        
        # MLF和7天逆回购无可靠数据源，不展示
        
        # 政策动态（暂不展示）
        # policy_change = monetary.get("policy_change", "")
        # if policy_change and "无" not in policy_change:
        #     lines.append("")
        #     lines.append(f"**📰 政策动态**")
        #     if "Web Search" in source:
        #         lines.append(f"　　{policy_change}（来源：{source}）")
        #     else:
        #         lines.append(f"　　{policy_change}")
        
        # 信号
        lines.append("")
        lines.append(f"**信号**: {signal}")
    else:
        lines.append("🗄️ 政策面 — 暂无数据")
    
    return "\n".join(lines)


def _glb_kpi_block(glb_dim: dict) -> tuple:
    """全球市场指标详情块（飞书 lark_md 格式）。
    
    格式参考 Trendonify: https://trendonify.com/pe-ratio/major-countries
    展示: 当前PE + 10年百分位 + 估值评级
    
    Returns:
        tuple: (text_content, image_key) - 文本内容和图片key（如果有）
    """
    gd   = glb_dim.get("data", {})
    lines = []
    img_key = None  # 飞书图片key

    # ─────────────────────────────────────────────────────
    # Trendonify 风格：PE 百分位 + 估值评级
    # 数据来源: https://trendonify.com/pe-ratio
    # 估值评级: 0-20%有吸引力 21-40%低估 41-60%合理 61-80%高估 81-100%昂贵
    # ─────────────────────────────────────────────────────
    
    # 动态获取 Trendonify PE 百分位数据
    _trendonify_data = fetch_trendonify_valuation()
    _PE_DATA = {
        "US":   _trendonify_data.get("US", {}),
        "HK":   _trendonify_data.get("HK", {}),
        "JP":   _trendonify_data.get("JP", {}),
        "KR":   _trendonify_data.get("KR", {}),
    }
    _trendonify_date = _trendonify_data.get("date", "")
    _trendonify_note = _trendonify_data.get("note", "")

    def _valuation_icon(pct):
        """根据10年百分位返回估值图标和文字"""
        if pct is None: return "", ""
        if not isinstance(pct, (int, float)): return "", ""
        if pct >= 81:    return "🔴", "昂贵"
        if pct >= 61:   return "🟠", "高估"
        if pct >= 41:   return "🟡", "合理"
        if pct >= 21:   return "🟢", "低估"
        return "🟢🟢", "有吸引力"

    def _chg_arrow(chg):
        if chg is None: return ""
        if chg >= 3:    return f" **5日{chg:+.1f}%**"
        if chg <= -3:   return f" **5日{chg:+.1f}%**"
        return f" 5日{chg:+.1f}%"

    # ─────────────────────────────────────────────────────
    # 🌏 全球市场估值概览（Trendonify 风格）
    # ─────────────────────────────────────────────────────
    # 只显示标题和日期，表格数据在图片中展示
    date_info = f" [{_trendonify_date}]" if _trendonify_date else ""
    lines.append(f"**🌏 全球市场估值** [数据源: Trendonify]{date_info}")
    lines.append("")

    # ─────────────────────────────────────────────────────
    # 生成估值图片
    # ─────────────────────────────────────────────────────
    # 构建估值图片数据
    valuation_img_data = {
        "date": _trendonify_date,
        "US": _PE_DATA.get("US", {}),
        "HK": _PE_DATA.get("HK", {}),
        "JP": _PE_DATA.get("JP", {}),
        "KR": _PE_DATA.get("KR", {}),
    }
    
    # 生成图片
    img_path = generate_valuation_image(valuation_img_data)
    
    # 如果图片生成成功，上传并返回图片key
    if img_path and os.path.exists(img_path):
        # 使用飞书图片上传接口
        from .feishu_image import upload_image_to_feishu
        img_url = upload_image_to_feishu(img_path)
        if img_url:
            # 提取 image_key (格式: fileutil/xxx -> xxx)
            img_key = img_url.replace("fileutil/", "")
            # 返回文本和图片key
            return "\n".join(lines), img_key
    
    # 图片上传失败或未生成图片，使用简化表格形式
    lines.append("| 市场 | PE | 10年%位 | 估值 |")
    lines.append("|------|-----|---------|------|")
    for market, name, ticker in [("US", "🇺🇸 美股", "SPX"), ("HK", "🇭🇰 港股", "HSI"), 
                                   ("JP", "🇯🇵 日股", "EWJ"), ("KR", "🇰🇷 韩股", "EWY")]:
        data = _PE_DATA.get(market, {})
        pe = data.get("pe", "--")
        pct = data.get("pct_10y", "--")
        icon, label = _valuation_icon(pct)
        lines.append(f"| {name} | {pe} | {pct}% | {icon}{label} |")
    
    return "\n".join(lines), None


# ─────────────────────────────────────────────────────────────
# 持仓监控和选股建议
# ─────────────────────────────────────────────────────────────

def _position_card_text(position_report: dict) -> str:
    """
    构建持仓监控卡片文本。
    
    Args:
        position_report: position_monitor.get_report_for_feishu() 返回的数据
    
    Returns:
        飞书 lark_md 格式的文本
    """
    if not position_report or "error" in position_report:
        return "暂无持仓数据"
    
    lines = []
    
    summary = position_report.get("summary", {})
    
    # 汇总统计
    lines.append(f"**📊 持仓概览**")
    lines.append(f"- 总持仓: {summary.get('total', 0)} 只")
    lines.append(f"- 多头排列: {summary.get('bullish_count', 0)} 只")
    lines.append(f"- 空头排列: {summary.get('bearish_count', 0)} 只")
    lines.append(f"- 总盈亏: {summary.get('profit', '0')} ({summary.get('profit_pct', '0')}%)")
    lines.append("")
    
    # 买入信号
    buy_alerts = position_report.get("buy_alerts", [])
    if buy_alerts:
        lines.append("**🟢 持仓中关注买入信号**")
        for alert in buy_alerts:
            lines.append(f"- {alert.get('code')} {alert.get('name')}: {alert.get('action', '')}")
        lines.append("")
    
    # 卖出信号
    sell_alerts = position_report.get("sell_alerts", [])
    if sell_alerts:
        lines.append("**🔴 持仓中关注卖出信号**")
        for alert in sell_alerts:
            profit = alert.get('profit_pct', 0)
            profit_str = f"(盈{profit:+.1f}%)" if profit else ""
            lines.append(f"- {alert.get('code')} {alert.get('name')} {profit_str}: {alert.get('action', '')}")
        lines.append("")
    
    # 持仓明细（前5）
    positions = position_report.get("positions", [])[:5]
    if positions:
        lines.append("**📋 持仓明细（部分）**")
        lines.append("| 代码 | 名称 | 信号 | 排列 | 盈亏% |")
        lines.append("|------|------|------|------|-------|")
        for p in positions:
            sig_icon = {"BUY": "🟢", "SELL": "🔴", "HOLD_BULL": "🟢", "HOLD_BEAR": "🔴"}.get(p.get("signal", ""), "🟡")
            lines.append(f"| {p.get('code', '')} | {p.get('name', '')} | {sig_icon}{p.get('signal', '')} | {p.get('position', '')} | {p.get('profit_pct', 0):+.1f}% |")
    
    return "\n".join(lines)


def _selector_card_text(selector_report: dict) -> str:
    """
    构建选股建议卡片文本。
    
    Args:
        selector_report: stock_selector.get_selector_report_for_feishu() 返回的数据
    
    Returns:
        飞书 lark_md 格式的文本
    """
    if not selector_report or "error" in selector_report:
        return "暂无选股建议"
    
    lines = []
    
    summary = selector_report.get("summary", {})
    
    # 汇总统计
    lines.append(f"**📊 选股概览**")
    lines.append(f"- 分析数量: {summary.get('total_analyzed', 0)} 只")
    lines.append(f"- 符合条件: {summary.get('final_count', 0)} 只")
    lines.append(f"- 买入信号: {summary.get('buy_signals', 0)} 只")
    lines.append(f"- 策略: {summary.get('strategy', 'KDJ超卖 + 知行趋势线')}")
    lines.append("")
    
    # 买入推荐
    buy_recs = selector_report.get("buy_recommendations", [])
    if buy_recs:
        lines.append("**🟢 ETF买入推荐**")
        lines.append("| 代码 | 名称 | 类型 | 差值% | KDJ_J | 规模(亿) |")
        lines.append("|------|------|------|-------|-------|----------|")
        for r in buy_recs:
            scale = r.get('scale', 0)
            scale_str = f"{scale/10000:.1f}" if scale else "--"
            lines.append(f"| {r.get('code', '')} | {r.get('name', '')} | {r.get('type', '')} | {r.get('trend_diff_pct', 0):.2f} | {r.get('kdj_j', 0):.1f} | {scale_str} |")
        lines.append("")
    
    # 关注推荐
    attention_recs = selector_report.get("attention_recommendations", [])
    if attention_recs:
        lines.append("**🟡 关注ETF（多头排列）**")
        for r in attention_recs[:5]:
            lines.append(f"- {r.get('code')} {r.get('name')}: {r.get('position', '')}")
    
    return "\n".join(lines)


def build_position_card(position_report: dict) -> dict:
    """构建持仓监控卡片"""
    content = _position_card_text(position_report)
    
    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": "📊 持仓监控"},
                "template": "purple"
            },
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": content}}
            ]
        }
    }


def _portfolio_etf_card_text(etf_analysis: list) -> str:
    """
    构建持仓ETF分析卡片文本（简洁版）。

    Args:
        etf_analysis: analyze_portfolio() 返回的分析结果列表

    Returns:
        飞书 lark_md 格式的文本
    """
    if not etf_analysis:
        return "暂无持仓ETF数据"

    lines = []

    # 汇总统计
    total = len(etf_analysis)
    good_pattern = [e for e in etf_analysis if e.get("pattern_score", 0) >= 60]
    bullish = [e for e in etf_analysis if "多头排列" in e.get("position", "")]
    buy_signals = [e for e in etf_analysis if e.get("signal") == "BUY"]
    avg_score = sum(e.get("pattern_score", 0) for e in etf_analysis) / total if total else 0

    # 汇总行
    summary_parts = []
    if bullish:
        summary_parts.append(f"🟢多头{len(bullish)}只")
    if buy_signals:
        summary_parts.append(f"🟢买入{len(buy_signals)}只")
    if good_pattern:
        summary_parts.append(f"✅好形态{len(good_pattern)}只")
    summary_parts.append(f"📊均分{avg_score:.0f}")
    lines.append("**" + " | ".join(summary_parts) + "**")
    lines.append("")

    # 按评分排序
    sorted_etfs = sorted(etf_analysis, key=lambda x: x.get("pattern_score", 0), reverse=True)

    # 表格头部
    lines.append("| ETF | 指数 | 信号 | 评分 | 量价 | 位置 |")
    lines.append("|------|------|------|------|------|------|")

    # 每行数据
    for e in sorted_etfs:
        etf_name = e.get("etf_name", "")[:8]
        index_name = e.get("index_code", "")[:6]

        # 信号图标
        signal = e.get("signal", "")
        position = e.get("position", "")
        if signal == "BUY":
            sig_icon = "🟢买入"
        elif "多头排列" in position:
            sig_icon = "🟢多头"
        elif "空头排列" in position:
            sig_icon = "🔴空头"
        elif signal == "HOLD_BULL":
            sig_icon = "🟡持多"
        elif signal == "HOLD_BEAR":
            sig_icon = "🟠持空"
        else:
            sig_icon = "⚪观望"

        # 评分
        score = e.get("pattern_score", 0)
        score_str = f"{score:.0f}" if score else "0"

        # 量价配合
        vol_match = e.get("volume_price_match_detail", False)
        vol_ratio = e.get("volume_ratio", 1)
        if vol_match:
            vol_str = f"✅{vol_ratio:.1f}x"
        elif vol_ratio > 1.5:
            vol_str = f"📈{vol_ratio:.1f}x"
        elif vol_ratio < 0.7:
            vol_str = f"📉缩量"
        else:
            vol_str = "➡️正常"

        # 价格位置
        price_pos = e.get("price_position_60d", 50)
        if price_pos < 20:
            pos_str = "🔴低位"
        elif price_pos < 40:
            pos_str = "🟠偏下"
        elif price_pos > 80:
            pos_str = "🟢高位"
        elif price_pos > 60:
            pos_str = "🟡偏上"
        else:
            pos_str = "⚪中性"

        lines.append(f"| {etf_name} | {index_name} | {sig_icon} | {score_str} | {vol_str} | {pos_str} |")

    # 异常信号提示
    abnormal_etfs = [e for e in sorted_etfs if e.get("abnormal_signals")]
    if abnormal_etfs:
        lines.append("")
        lines.append("**⚠️ 异常量能**")
        for e in abnormal_etfs[:3]:  # 最多显示3个
            for sig in e.get("abnormal_signals", [])[:1]:  # 每个ETF最多显示1个信号
                sig_type = sig.get("type", "")
                desc = sig.get("description", "")[:20]
                etf_name = e.get("etf_name", "")[:6]
                emoji = "🔴" if sig.get("severity") == "danger" else "🟡"
                lines.append(f"- {emoji}{etf_name}: {sig_type}")

    return "\n".join(lines)


def build_portfolio_etf_card(etf_analysis: list) -> dict:
    """
    构建持仓ETF分析卡片。

    Args:
        etf_analysis: 持仓ETF分析结果列表

    Returns:
        飞书卡片 dict
    """
    content = _portfolio_etf_card_text(etf_analysis)

    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": "📈 持仓ETF分析"},
                "template": "purple"
            },
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": content}}
            ]
        }
    }


def generate_portfolio_etf_md(etf_analysis: list, output_path: str = None) -> str:
    """
    生成美观的持仓ETF分析 Markdown 报告。

    Args:
        etf_analysis: 持仓ETF分析结果列表
        output_path: 可选，保存到的文件路径

    Returns:
        Markdown 格式的报告文本
    """
    if not etf_analysis:
        md = "# 📊 持仓ETF分析报告\n\n暂无持仓数据\n"
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(md)
        return md

    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 汇总统计
    total = len(etf_analysis)
    avg_score = sum(e.get("pattern_score", 0) for e in etf_analysis) / total if total else 0
    bullish = [e for e in etf_analysis if "多头排列" in e.get("position", "")]
    buy_signals = [e for e in etf_analysis if e.get("signal") == "BUY"]
    good_pattern = [e for e in etf_analysis if e.get("pattern_score", 0) >= 60]

    # 按评分排序
    sorted_etfs = sorted(etf_analysis, key=lambda x: x.get("pattern_score", 0), reverse=True)

    # 构建 Markdown
    lines = []
    lines.append("# 📊 持仓ETF分析报告")
    lines.append(f"\n**生成时间**: {now}\n")
    lines.append("---\n")

    # 概览表格
    lines.append("## 📈 持仓概览\n")
    lines.append("| 指标 | 数值 |")
    lines.append("|:-----|:-----|")
    lines.append(f"| 持仓数量 | {total} 只 |")
    lines.append(f"| 平均评分 | {avg_score:.0f}/100 |")
    lines.append(f"| 多头排列 | {len(bullish)} 只 |")
    lines.append(f"| 买入信号 | {len(buy_signals)} 只 |")
    lines.append(f"| 好形态 | {len(good_pattern)} 只 |\n")

    # 持仓详情表格
    lines.append("## 🔍 持仓详情\n")
    lines.append("| ETF | 跟踪指数 | 信号 | 评分 | 量价 | 位置 | RSI |")
    lines.append("|:----|:--------|:-----|:----:|:----:|:----:|:---:|")

    for e in sorted_etfs:
        etf_name = e.get("etf_name", "")[:10]
        index_name = e.get("index_code", "")[:8]
        signal = e.get("signal", "")
        position = e.get("position", "")

        # 信号图标
        if signal == "BUY":
            sig_icon = "🟢买入"
        elif "多头排列" in position:
            sig_icon = "🟢多头"
        elif "空头排列" in position:
            sig_icon = "🔴空头"
        elif signal == "HOLD_BULL":
            sig_icon = "🟡持多"
        elif signal == "HOLD_BEAR":
            sig_icon = "🟠持空"
        else:
            sig_icon = "⚪观望"

        # 评分
        score = e.get("pattern_score", 0)
        score_str = f"{score:.0f}"

        # 量价
        vol_ratio = e.get("volume_ratio", 1)
        vol_match = e.get("volume_price_match_detail", False)
        if vol_match:
            vol_str = f"✅{vol_ratio:.1f}x"
        elif vol_ratio > 1.5:
            vol_str = f"📈{vol_ratio:.1f}x"
        elif vol_ratio < 0.7:
            vol_str = f"📉缩"
        else:
            vol_str = "➡️正常"

        # 价格位置
        price_pos = e.get("price_position_60d", 50)
        if price_pos < 20:
            pos_str = "🔴低位"
        elif price_pos < 40:
            pos_str = "🟠偏下"
        elif price_pos > 80:
            pos_str = "🟢高位"
        elif price_pos > 60:
            pos_str = "🟡偏上"
        else:
            pos_str = "⚪中性"

        # RSI
        rsi = e.get("rsi14", 50)
        if rsi < 30:
            rsi_str = f"🔴{rsi:.0f}"
        elif rsi > 70:
            rsi_str = f"🟢{rsi:.0f}"
        else:
            rsi_str = f"{rsi:.0f}"

        lines.append(f"| {etf_name} | {index_name} | {sig_icon} | {score_str} | {vol_str} | {pos_str} | {rsi_str} |")

    lines.append("")

    # 异常量能提示
    abnormal_etfs = [e for e in sorted_etfs if e.get("abnormal_signals")]
    if abnormal_etfs:
        lines.append("## ⚠️ 异常量能提示\n")
        for e in abnormal_etfs:
            etf_name = e.get("etf_name", "")[:8]
            for sig in e.get("abnormal_signals", []):
                sig_type = sig.get("type", "")
                desc = sig.get("description", "")
                severity = sig.get("severity", "")
                emoji = "🔴" if severity == "danger" else "🟡" if severity == "warning" else "🟢"
                lines.append(f"- {emoji} **{etf_name}**: {sig_type} - {desc}")
        lines.append("")

    # 操作建议
    lines.append("## 📝 操作建议\n")
    if buy_signals:
        lines.append("- 🟢 **可关注**: 存在买入信号，建议关注")
    elif bullish:
        lines.append("- 🟡 **持有**: 多头排列中，维持现有仓位")
    elif avg_score < 20:
        lines.append("- 🔴 **谨慎**: 整体偏弱，控制仓位")
    else:
        lines.append("- ⚪ **观望**: 等待明确信号")

    lines.append("\n---\n")
    lines.append("*本报告仅供参考，不构成投资建议*")

    md = "\n".join(lines)

    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(md)

    return md


def send_portfolio_etf_md(etf_analysis: list, webhook: str = FEISHU_WEBHOOK) -> bool:
    """
    发送持仓ETF分析 Markdown 报告到飞书。

    Args:
        etf_analysis: 持仓ETF分析结果列表
        webhook: 飞书 Webhook 地址

    Returns:
        发送是否成功
    """
    md_content = generate_portfolio_etf_md(etf_analysis)

    # 飞书 text 消息类型支持简单的文本，可以将 md 内容作为 text 发送
    # 或者使用 post 类型支持富文本
    payload = {
        "msg_type": "text",
        "content": {
            "text": md_content
        }
    }

    try:
        import requests
        r = requests.post(webhook, json=payload, timeout=15)
        resp = r.json()
        if resp.get("code") == 0 or resp.get("StatusCode") == 0:
            print("  ✓ 持仓ETF分析 Markdown 已发送")
            return True
        print(f"  ✗ 发送失败: {resp}")
        return False
    except Exception as e:
        print(f"  ✗ 发送异常: {e}")
        return False


def build_selector_card(selector_report: dict) -> dict:
    """构建选股建议卡片"""
    content = _selector_card_text(selector_report)
    
    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": "📊 知行趋势线选股建议"},
                "template": "purple"
            },
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": content}}
            ]
        }
    }


# ─────────────────────────────────────────────────────────────
# 主函数：构建飞书卡片
# ─────────────────────────────────────────────────────────────

def build_card(report_data: dict) -> dict:
    """
    构建飞书交互式卡片（单卡片版本，保持向后兼容）。

    Args:
        report_data: signal.build_report() 返回的完整报告字典。

    Returns:
        飞书消息 payload dict。
    """
    # 使用多卡片版本
    cards = build_cards(report_data)
    if cards:
        return cards[0]  # 返回第一张卡片（主卡片）
    return {"msg_type": "text", "content": {"text": "报告生成失败"}}


def build_cards(report_data: dict) -> list:
    """
    构建飞书多卡片消息（多卡片版本）。

    Args:
        report_data: signal.build_report() 返回的完整报告字典。

    Returns:
        多张卡片的消息 payload 列表。
    """
    now = report_data.get("generated_at", "?")
    
    cards = []

    cap_dim = report_data.get("capital",     {})
    fun_dim = report_data.get("fundamental", {})
    pol_dim = report_data.get("policy",      {})
    glb_dim = report_data.get("global",      {})
    comp    = report_data.get("composite",   {})

    cap_s  = cap_dim.get("score", 0.0)
    fun_s  = fun_dim.get("score", 0.0)
    pol_s  = pol_dim.get("score", 0.0)
    glb_s  = glb_dim.get("score", 0.0)
    comp_s = comp.get("score", 0.0)
    comp_l = comp.get("label", "N/A")

    # 指南针信号（用于仓位建议）- 使用最近明显信号，避免追涨杀跌
    cap_data_raw = cap_dim.get("data", {})
    znz = cap_data_raw.get("znz_active_cap", {})
    znz_signal = znz.get("last_clear_signal") if znz and znz.get("error") is None else None

    pos_range, pos_reason = _score_to_position(comp_s, znz_signal, cap_s, fun_s, pol_s, glb_s)
    risks    = _collect_risks(report_data)
    watchlist = _collect_watchlist(report_data)

    cap_summ = _cap_summary(cap_dim)
    fun_summ = _fun_summary(fun_dim)
    # 政策面：从monetary数据获取
    pol_data = pol_dim.get("data", {})
    monetary = pol_data.get("monetary", {})
    if monetary and monetary.get("error") is None:
        signal = monetary.get("signal", "🟡 货币中性")
        bond = monetary.get("bond_10y")
        # MLF无数据时不展示
        mlf = monetary.get("mlf_1y")
        if mlf and bond:
            pol_summ = f"{signal} MLF {mlf}% 国债 {bond}%"
        elif bond:
            pol_summ = f"{signal} 国债 {bond}%"
        else:
            pol_summ = signal
    else:
        pol_summ = "政策数据待接入"
    glb_summ = _glb_summary(glb_dim)

    # =====================
    # 卡片1: 交易决策区
    # =====================
    elements1 = []
    decision_lines = [
        "**综合结论**",
        "",
        f"资金面(30%) {_score_icon(cap_s)} **{cap_s:+.2f}** {cap_summ}",
        f"基本面(40%) {_score_icon(fun_s)} **{fun_s:+.2f}** {fun_summ}",
        f"政策面(10%) {_score_icon(pol_s)} **{pol_s:+.2f}** {pol_summ}",
        f"全球市场(20%) {_score_icon(glb_s)} **{glb_s:+.2f}** {glb_summ}",
        f"**综合加权 {_score_icon(comp_s)} {comp_s:+.2f} · {comp_l}**",
        "",
        "---",
        "",
        f"**建议仓位：{pos_range}**",
        f"*{pos_reason}*",
    ]
    elements1.append({"tag": "div", "text": {"tag": "lark_md", "content": "\n".join(decision_lines)}})

    # 风险点
    if risks:
        risk_lines = ["**⚠️ 主要风险点**", ""]
        for r in risks:
            risk_lines.append(f"- {r}")
        elements1.append({"tag": "div", "text": {"tag": "lark_md", "content": "\n".join(risk_lines)}})

    # 关注事项
    if watchlist:
        watch_lines = ["**📌 近期关注事项**", ""]
        for w in watchlist:
            watch_lines.append(f"- {w}")
        elements1.append({"tag": "div", "text": {"tag": "lark_md", "content": "\n".join(watch_lines)}})

    # 卡片1: 交易决策区
    cards.append({
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": f"📋 交易决策  {now}"}, "template": "indigo"},
            "elements": elements1,
        }
    })

    # =====================
    # 卡片2: 资金面详情
    # =====================
    elements2 = []
    cap_block_text = _cap_kpi_block(cap_dim)
    elements2.append({"tag": "div", "text": {"tag": "lark_md", "content": cap_block_text}})

    cards.append({
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": f"🏦 资金面详情  {now}"}, "template": "green"},
            "elements": elements2,
        }
    })

    # =====================
    # 卡片3: 基本面详情
    # =====================
    elements3 = []
    fun_block_text = _fun_kpi_block(fun_dim)
    elements3.append({"tag": "div", "text": {"tag": "lark_md", "content": fun_block_text}})

    cards.append({
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": f"📊 基本面详情  {now}"}, "template": "green"},
            "elements": elements3,
        }
    })

    # =====================
    # 卡片4: 政策面详情
    # =====================
    elements4 = []
    pol_block_text = _policy_kpi_block(pol_dim)
    elements4.append({"tag": "div", "text": {"tag": "lark_md", "content": pol_block_text}})

    cards.append({
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": f"🗄️ 政策面详情  {now}"}, "template": "blue"},
            "elements": elements4,
        }
    })

    # =====================
    # 卡片5: 全球市场 + 图片
    # =====================
    elements5 = []
    glb_block_text, glb_img_key = _glb_kpi_block(glb_dim)
    elements5.append({"tag": "div", "text": {"tag": "lark_md", "content": glb_block_text}})
    # 如果有图片，添加飞书卡片图片元素
    if glb_img_key:
        elements5.append({"tag": "img", "img_key": glb_img_key})

    cards.append({
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": f"🌏 全球估值  {now}"}, "template": "orange"},
            "elements": elements5,
        }
    })

    # =====================
    # 卡片6: 持仓监控
    # =====================
    # 从 report_data 中获取持仓报告（由 main.py 在 report_data 中传入）
    position_report = report_data.get("position_report")
    if position_report:
        position_card = build_position_card(position_report)
        cards.append(position_card)

    # =====================
    # 卡片7: 选股建议
    # =====================
    # 从 report_data 中获取选股报告（由 main.py 在 report_data 中传入）
    selector_report = report_data.get("selector_report")
    if selector_report:
        selector_card = build_selector_card(selector_report)
        cards.append(selector_card)

    return cards


def send(payload: dict, webhook: str = FEISHU_WEBHOOK) -> bool:
    """发送飞书消息，成功返回 True。"""
    try:
        r    = requests.post(webhook, json=payload, timeout=15)
        resp = r.json()
        if resp.get("code") == 0 or resp.get("StatusCode") == 0:
            return True
        print(f"  飞书返回异常: {resp}")
        return False
    except Exception as e:
        print(f"  飞书推送失败: {e}")
        return False


def send_cards(cards: list, webhook: str = FEISHU_WEBHOOK) -> bool:
    """发送多张飞书卡片消息，成功返回 True。"""
    try:
        for i, card in enumerate(cards):
            r = requests.post(webhook, json=card, timeout=15)
            resp = r.json()
            if resp.get("code") != 0 and resp.get("StatusCode") != 0:
                print(f"  卡片{i+1}发送异常: {resp}")
                return False
        return True
    except Exception as e:
        print(f"  飞书推送失败: {e}")
        return False
