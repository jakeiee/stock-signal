#!/usr/bin/env python3
"""
选股持仓管理一条龙流水线。

完整流程：
  Phase 1: 东方财富ETF初筛（KDJ<0, 规模>5000万, 五大类ETF）
  Phase 2: 知行趋势线二次分析（综合评分）
  Phase 3: 买入标的筛选（BUY/HOLD_BULL + score>=40）
  Phase 4: 止损规则绑定（亏损5%/10%/15%/20%）
  Phase 5: 飞书报告输出（结构化报告 + 卡片消息推送）

使用方法：
    python3 -m market_monitor.portfolio_selection_workflow            # 终端输出
    python3 -m market_monitor.portfolio_selection_workflow --feishu  # 推送到飞书
    python3 -m market_monitor.portfolio_selection_workflow --debug   # 调试模式
"""

import argparse
import json
import os
import random
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── 核心模块导入 ────────────────────────────────────────────────────────────────

from market_monitor.data_sources.etf_selector import ETFFilter, get_selection_etfs
from market_monitor.analysis.zhixing import (
    comprehensive_score,
    fetch_etf_history, fetch_stock_history,
    fetch_index_history_xalpha,
    get_trend_status, calculate_kdj,
)
from market_monitor.analysis.position_manager import (
    PositionManager, Market, TrendDirection, DEFAULT_STOP_LOSS_RULES
)
from market_monitor.analysis.stock_selector import StockSelector


# ── 配置 ────────────────────────────────────────────────────────────────────────

# 选股五大ETF类型
SELECTION_ETF_TYPES = ["行业主题", "宽基指数", "风格策略", "外盘ETF", "黄金ETF"]

# 规模门槛（万元）
SELECTION_SCALE_MIN = 5000

# KDJ超卖阈值
SELECTION_KDJ_MAX = 0

# 综合评分买入阈值
BUY_SCORE_THRESHOLD = 40

# 最多分析ETF数量
MAX_ANALYZE_COUNT = 30

# ── ETF 跟踪指数 → xalpha 指数代码映射 ──────────────────────────────────────────
# 键：东方财富选股API返回的 INDEX_NAME_ABBR（跟踪标的简称）
# 值：xalpha indexinfo 可用的指数代码
# 
# xalpha 代码格式：
#   A股中证: ZZ+代码（如 ZZ930601）
#   港股: HK+代码（如 HKHSTECH, HKHSIII）
#   深证: SZ+代码（如 SZ399673）
#   上证: SH+代码（如 SH000688）
#   国证: GZ+代码（如 GZ987018）

ETF_INDEX_TO_XACODE: Dict[str, str] = {
    # ── 宽基指数 ──
    "创业板50": "SZ399673",
    "创业板人工智能": "ZZH20034",
    
    # ── 行业主题 ──
    "CS物联网": "ZZ930712",
    "SHS物联网": "ZZ931460",
    "电力指数": "ZZ399989",
    "绿色电力": "ZZH20033",
    "消费电子": "ZZ931494",
    "家电龙头": "ZZ931102",
    "全指公用": "ZZ000990",
    "中证VR": "ZZ930821",
    "中国互联网50人民币": "HKHSIII",
    "国新港股通央企红利": "ZZ931854",
    
    # ── 港股/外盘ETF ──
    "港股通互联网": "HKHSIII",
    "恒生港股通中国科技指数": "HKHSTECH",
    "恒生港股通科技主题指数": "HKHSTECH",
    "港股通科技主题": "HKHSTECH",
    "港股通信息C人民币": "HKHSIII",
    "港股通信息C港元": "HKHSIII",
    
    # ── MSCI USA 等海外指数 xalpha 不支持，跳过 ──
}

# 止损规则（复用 PositionManager 默认规则）
# 亏损5% → 预警观察
# 亏损10% → 减仓50%
# 亏损15% → 强制止损
# 亏损20% → 完全离场


# ── Phase 1: ETF初筛 ───────────────────────────────────────────────────────────

def phase1_etf_prescreen(
    etf_types: List[str] = None,
    scale_min: float = SELECTION_SCALE_MIN,
    kdj_max: float = SELECTION_KDJ_MAX,
    track_target: str = None,
) -> Dict:
    """
    Phase 1: 东方财富ETF初筛。
    
    Returns:
        {
            "success": bool,
            "total": int,
            "etfs": [{code, name, type, scale, kdj_value, premium, change_pct, track_target}, ...],
            "error": str|None
        }
    """
    print("[Phase 1] ETF初筛...")
    print(f"         条件: KDJ<{kdj_max}, 规模>{scale_min}万, 类型={etf_types or SELECTION_ETF_TYPES}")
    
    result = get_selection_etfs(
        etf_types=etf_types or SELECTION_ETF_TYPES,
        scale_min=scale_min,
        track_target=track_target,
    )
    
    if not result.get("success"):
        print(f"         ❌ 初筛失败: {result.get('error')}")
        return result
    
    etfs = result.get("etfs", [])
    print(f"         ✅ 初筛得到 {len(etfs)} 只ETF")
    
    # 打印前5只概览
    if etfs:
        print(f"         {'代码':<8} {'名称':<18} {'KDJ':>8} {'溢价%':>8} {'规模(万)':>12} {'类型':<10}")
        for etf in etfs[:5]:
            print(
                f"         {etf['code']:<8} {etf['name']:<18} "
                f"{etf.get('kdj_value', 0):>8.2f} {etf.get('premium', 0):>8.2f} "
                f"{etf.get('scale', 0):>12.1f} {etf.get('type', ''):<10}"
            )
        if len(etfs) > 5:
            print(f"         ... 还有 {len(etfs)-5} 只")
    
    return result


# ── Phase 2: 知行趋势线分析 ─────────────────────────────────────────────────────

def phase2_zhixing_analysis(etfs: List[Dict], max_analyze: int = MAX_ANALYZE_COUNT) -> List[Dict]:
    """
    Phase 2: 对初筛ETF逐一进行知行趋势线分析和综合评分。
    
    Returns:
        包含知行分析和综合评分的ETF列表
    """
    print(f"\n[Phase 2] 知行趋势线分析（最多 {max_analyze} 只）...")
    
    etfs_to_analyze = etfs[:max_analyze]
    results = []
    error_count = 0
    
    for i, etf in enumerate(etfs_to_analyze):
        code = etf["code"]
        name = etf["name"]
        print(f"         [{i+1}/{len(etfs_to_analyze)}] {code} {name}...", end=" ", flush=True)
        
        # 请求间隔：避免被数据源限流（1.0~2.0s 随机延迟）
        if i > 0:
            delay = 1.0 + random.random()
            time.sleep(delay)
        
        try:
            # 优先使用指数数据（xalpha，数据更完整）
            # 1. 查找 ETF 跟踪指数 → xalpha 代码
            track_target = etf.get("track_target", "")
            xa_code = ETF_INDEX_TO_XACODE.get(track_target)
            
            if xa_code:
                # 用 xalpha 获取指数历史数据
                df = fetch_index_history_xalpha(xa_code)
                if df is not None and not df.empty and len(df) >= 20:
                    print(f"[指数{xa_code}]", end=" ", flush=True)
                else:
                    # xalpha 失败，回退到 ETF 数据
                    xa_code = None
            
            if not xa_code:
                # 回退：用 akshare 获取 ETF 历史数据
                is_etf = code.startswith(("51", "15", "16", "50", "56"))
                if is_etf:
                    df = fetch_etf_history(code)
                else:
                    df = fetch_stock_history(code)
            
            if df is None or df.empty:
                print("❌ 数据获取失败")
                error_count += 1
                continue
            
            if len(df) < 20:
                print("❌ 数据不足")
                error_count += 1
                continue
            
            # 用 get_trend_status 直接分析（不重复请求）
            analysis = get_trend_status(df)
            if "error" in analysis:
                print(f"❌ {analysis['error']}")
                error_count += 1
                continue
            
            analysis["code"] = code
            analysis["name"] = name
            analysis["is_etf"] = True
            analysis["is_index_based"] = bool(xa_code)
            if xa_code:
                analysis["xa_code"] = xa_code
            
            # 生成综合评分
            score = comprehensive_score(df)
            analysis.update(score)
            
            # 合并ETF信息
            analysis["etf_type"] = etf.get("type", "")
            analysis["scale"] = etf.get("scale", 0)
            analysis["premium"] = etf.get("premium", 0)
            analysis["track_target"] = etf.get("track_target", "")
            analysis["price"] = etf.get("price", 0)
            analysis["pre_kdj"] = etf.get("kdj_value", 0)
            analysis["pre_scale"] = etf.get("scale", 0)
            analysis["pre_premium"] = etf.get("premium", 0)
            analysis["pre_change_pct"] = etf.get("change_pct", 0)
            
            results.append(analysis)
            
            # 简洁状态输出
            signal_icon = {"BUY": "🟢", "HOLD_BULL": "🟡", "HOLD_NEUTRAL": "⚪", "HOLD_BEAR": "🔴", "SELL": "🔴"}.get(analysis.get("signal", ""), "⚪")
            print(f"{signal_icon} {analysis.get('signal','?')} | {analysis.get('position','?')} | 评分:{analysis.get('total_score',0):.0f} | J:{analysis.get('kdj_j',0):.1f}")
            
        except Exception as e:
            print(f"❌ {str(e)[:50]}")
            error_count += 1
    
    print(f"         ✅ 分析完成: {len(results)} 只有效, {error_count} 只失败")
    
    return results


# ── Phase 3: 买入标的筛选 ───────────────────────────────────────────────────────

def phase3_filter_buy(analyses: List[Dict], score_threshold: int = BUY_SCORE_THRESHOLD) -> Dict:
    """
    Phase 3: 筛选买入标的。
    
    筛选条件：
    - 知行信号为 BUY 或 HOLD_BULL
    - 综合评分 >= 40
    - 优先选择多头排列
    
    Returns:
        {
            "buy_candidates": [...],  # 强烈推荐（BUY + score>=40）
            "watch_candidates": [...], # 关注列表（HOLD_BULL + score>=40）
            "all_candidates": [...],   # 全部通过初筛的标的（按评分排序）
        }
    """
    print(f"\n[Phase 3] 买入标的筛选（评分>= {score_threshold}）...")
    
    # 按评分排序
    sorted_analyses = sorted(analyses, key=lambda x: x.get("total_score", 0), reverse=True)
    
    # 强烈推荐: BUY信号 + 评分达标
    buy_candidates = [
        a for a in sorted_analyses
        if a.get("signal") == "BUY" and a.get("total_score", 0) >= score_threshold
    ]
    
    # 关注列表: HOLD_BULL信号 + 评分达标
    watch_candidates = [
        a for a in sorted_analyses
        if a.get("signal") == "HOLD_BULL" and a.get("total_score", 0) >= score_threshold
    ]
    
    # 全部标的（通过评分的）
    all_passed = [a for a in sorted_analyses if a.get("total_score", 0) >= score_threshold]
    
    print(f"         🟢 强烈推荐(BUY): {len(buy_candidates)} 只")
    print(f"         🟡 关注列表(HOLD_BULL): {len(watch_candidates)} 只")
    print(f"         📋 评分达标总计: {len(all_passed)} 只")
    
    if buy_candidates:
        print(f"         {'代码':<8} {'名称':<18} {'评分':>5} {'信号':>10} {'排列':>8} {'KDJ_J':>7} {'类型':<10}")
        for b in buy_candidates:
            print(
                f"         {b.get('code',''):<8} {b.get('name',''):<18} "
                f"{b.get('total_score',0):>5.0f} {b.get('signal',''):>10} "
                f"{b.get('position',''):>8} {b.get('kdj_j',0):>7.1f} "
                f"{b.get('etf_type',''):<10}"
            )
    
    if watch_candidates:
        print(f"\n         关注列表:")
        print(f"         {'代码':<8} {'名称':<18} {'评分':>5} {'信号':>10} {'排列':>8} {'KDJ_J':>7} {'类型':<10}")
        for w in watch_candidates[:5]:
            print(
                f"         {w.get('code',''):<8} {w.get('name',''):<18} "
                f"{w.get('total_score',0):>5.0f} {w.get('signal',''):>10} "
                f"{w.get('position',''):>8} {w.get('kdj_j',0):>7.1f} "
                f"{w.get('etf_type',''):<10}"
            )
    
    return {
        "buy_candidates": buy_candidates,
        "watch_candidates": watch_candidates,
        "all_candidates": all_passed,
    }


# ── Phase 4: 止损绑定 ──────────────────────────────────────────────────────────

def phase4_stop_loss(candidates: List[Dict], position_manager: PositionManager = None) -> List[Dict]:
    """
    Phase 4: 为入选标的绑定止损规则。
    
    基于当前价格计算止损价格线：
    - 亏损5%：预警观察
    - 亏损10%：减仓50%
    - 亏损15%：强制止损
    - 亏损20%：完全离场
    """
    print(f"\n[Phase 4] 止损规则绑定...")
    
    pm = position_manager or PositionManager()
    
    for cand in candidates:
        price = cand.get("price", 0)
        if price <= 0:
            cand["stop_loss"] = {}
            continue
        
        # 计算各档位止损价格
        stop_loss_info = {}
        for rule in pm.stop_loss_rules:
            loss_pct = rule.loss_pct
            stop_price = price * (1 - loss_pct)
            stop_loss_info[f"loss_{int(loss_pct*100)}pct"] = {
                "threshold": f"亏损{loss_pct*100:.0f}%",
                "stop_price": round(stop_price, 3),
                "action": rule.action,
                "action_desc": {
                    "watch": "⚠️ 预警观察",
                    "reduce": "🔻 减仓50%",
                    "quit": "🛑 强制止损",
                }.get(rule.action, rule.description),
            }
        
        cand["stop_loss"] = stop_loss_info
    
    print(f"         ✅ 已完成 {len(candidates)} 只标的止损绑定")
    
    # 打印示范
    if candidates:
        sample = candidates[0]
        print(f"         示例 ({sample.get('code','')} {sample.get('name','')} @ {sample.get('price',0):.3f})：")
        for key, info in sample["stop_loss"].items():
            print(f"           {info['threshold']} → 止损价 ¥{info['stop_price']:.3f} ({info['action_desc']})")
    
    return candidates


# ── Phase 5: 报告生成 ──────────────────────────────────────────────────────────

def phase5_generate_report(
    pre_result: Dict,
    zhixing_results: List[Dict],
    filter_result: Dict,
    generated_at: str,
) -> str:
    """
    Phase 5: 生成结构化Markdown报告（用于飞书文档和终端输出）。
    """
    lines = []
    
    # 标题
    lines.append(f"# 📊 选股持仓分析报告")
    lines.append(f"**生成时间**: {generated_at}")
    lines.append(f"**选股策略**: KDJ超卖 + 知行趋势线综合评分")
    lines.append("")
    
    # ── 初筛汇总 ──
    lines.append("## 📈 ETF初筛结果")
    lines.append("")
    
    etfs = pre_result.get("etfs", [])
    lines.append(f"- 选股条件: KDJ<0, 资产规模>5000万")
    lines.append(f"- ETF类型: 行业主题 | 宽基指数 | 风格策略 | 外盘ETF | 黄金ETF")
    lines.append(f"- 初筛结果: **{pre_result.get('total', 0)}** 只")
    lines.append(f"- 进入知行分析: **{len(zhixing_results)}** 只")
    lines.append("")
    
    # 类型分布
    type_dist = {}
    for a in zhixing_results:
        t = a.get("etf_type", "未知")
        type_dist[t] = type_dist.get(t, 0) + 1
    if type_dist:
        lines.append("**ETF类型分布**:")
        for t, c in sorted(type_dist.items(), key=lambda x: -x[1]):
            lines.append(f"- {t}: {c} 只")
    lines.append("")
    
    # ── 信号分布 ──
    lines.append("## 📉 知行信号分布")
    lines.append("")
    
    signal_dist = {}
    position_dist = {}
    for a in zhixing_results:
        sig = a.get("signal", "UNKNOWN")
        signal_dist[sig] = signal_dist.get(sig, 0) + 1
        pos = a.get("position", "未知")
        position_dist[pos] = position_dist.get(pos, 0) + 1
    
    lines.append("| 信号 | 数量 | 说明 |")
    lines.append("|---|---|---|")
    signal_desc = {
        "BUY": "🟢 金叉买入",
        "HOLD_BULL": "🟡 多头持有",
        "HOLD_NEUTRAL": "⚪ 中性观望",
        "HOLD_BEAR": "🔴 空头排列",
        "SELL": "🛑 死叉卖出",
    }
    for sig in ["BUY", "HOLD_BULL", "HOLD_NEUTRAL", "HOLD_BEAR", "SELL"]:
        if sig in signal_dist:
            lines.append(f"| {sig} | {signal_dist[sig]} | {signal_desc.get(sig, '')} |")
    lines.append("")
    
    # ── 买入推荐 ──
    buy_candidates = filter_result.get("buy_candidates", [])
    watch_candidates = filter_result.get("watch_candidates", [])
    
    if buy_candidates:
        lines.append("## 🟢 买入推荐（金叉信号 + 评分>=40）")
        lines.append("")
        lines.append("| 代码 | 名称 | 类型 | 评分 | 排列 | KDJ_J | 趋势差值% | 溢价% | 规模(万) |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for b in buy_candidates:
            lines.append(
                f"| {b.get('code','')} | {b.get('name','')} | {b.get('etf_type','')} | "
                f"{b.get('total_score',0):.0f} | {b.get('position','')} | "
                f"{b.get('kdj_j',0):.1f} | {b.get('trend_diff_pct',0):.1f}% | "
                f"{b.get('pre_premium',0):.2f}% | {b.get('pre_scale',0):.1f} |"
            )
        lines.append("")
    
    if watch_candidates:
        lines.append("## 🟡 关注列表（多头发力 + 评分>=40）")
        lines.append("")
        lines.append("| 代码 | 名称 | 类型 | 评分 | 排列 | KDJ_J | 趋势差值% | 溢价% | 规模(万) |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for w in watch_candidates[:10]:
            lines.append(
                f"| {w.get('code','')} | {w.get('name','')} | {w.get('etf_type','')} | "
                f"{w.get('total_score',0):.0f} | {w.get('position','')} | "
                f"{w.get('kdj_j',0):.1f} | {w.get('trend_diff_pct',0):.1f}% | "
                f"{w.get('pre_premium',0):.2f}% | {w.get('pre_scale',0):.1f} |"
            )
        lines.append("")
    
    # ── 止损规则 ──
    lines.append("## 🛑 止损规则")
    lines.append("")
    lines.append("| 亏损幅度 | 动作 | 止损后仓位 |")
    lines.append("|---|---|---|")
    lines.append("| 5% | ⚠️ 预警观察 | 不变 |")
    lines.append("| 10% | 🔻 减仓50% | 原仓位×50% |")
    lines.append("| 15% | 🛑 强制止损 | 清仓 |")
    lines.append("| 20% | 🛑 完全离场 | 清仓 |")
    lines.append("")
    
    # ── 全部分析结果明细 ──
    # 始终展示所有进入知行分析的ETF明细，方便查看每只ETF的具体信号和指标
    if zhixing_results:
        lines.append("## 📊 知行分析明细")
        lines.append("")
        lines.append("| 代码 | 名称 | 类型 | 评分 | 信号 | 排列 | KDJ_J | KDJ_K | KDJ_D | 趋势差值% |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|")
        # 按评分降序排列
        sorted_all = sorted(zhixing_results, key=lambda x: x.get("total_score", 0), reverse=True)
        for a in sorted_all[:30]:
            signal_icon = {"BUY": "🟢", "HOLD_BULL": "🟡", "HOLD_NEUTRAL": "⚪", "HOLD_BEAR": "🔴", "SELL": "🛑"}.get(a.get("signal", ""), "⚪")
            lines.append(
                f"| {a.get('code','')} | {a.get('name','')} | {a.get('etf_type','')} | "
                f"{a.get('total_score',0):.0f} | {signal_icon} {a.get('signal','')} | "
                f"{a.get('position','')} | {a.get('kdj_j',0):.1f} | "
                f"{a.get('kdj_k',0):.1f} | {a.get('kdj_d',0):.1f} | "
                f"{a.get('trend_diff_pct',0):.1f}% |"
            )
        if len(zhixing_results) > 30:
            lines.append(f"| ... | 还有 {len(zhixing_results) - 30} 只 | ... |")
        lines.append("")
    
    # ── 全部分析结果（仅达标） ──
    all_candidates = filter_result.get("all_candidates", [])
    if all_candidates:
        lines.append("## 📊 全部达标标的（按评分排序）")
        lines.append("")
        lines.append("| 代码 | 名称 | 类型 | 评分 | 信号 | 排列 | KDJ_J | KDJ_K | KDJ_D | 趋势差值% |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|")
        for a in all_candidates[:20]:
            signal_icon = {"BUY": "🟢", "HOLD_BULL": "🟡", "HOLD_NEUTRAL": "⚪", "HOLD_BEAR": "🔴", "SELL": "🛑"}.get(a.get("signal", ""), "⚪")
            lines.append(
                f"| {a.get('code','')} | {a.get('name','')} | {a.get('etf_type','')} | "
                f"{a.get('total_score',0):.0f} | {signal_icon} {a.get('signal','')} | "
                f"{a.get('position','')} | {a.get('kdj_j',0):.1f} | "
                f"{a.get('kdj_k',0):.1f} | {a.get('kdj_d',0):.1f} | "
                f"{a.get('trend_diff_pct',0):.1f}% |"
            )
        lines.append("")
    else:
        lines.append("> ⚠️ 当前无评分≥40的达标标的。可通过降低评分阈值或等待行情回暖来获取更多候选。")
        lines.append("")
    
    # ── 风险提示 ──
    lines.append("## ⚠️ 风险提示")
    lines.append("")
    lines.append("- 以上选股基于技术指标（知行趋势线 + KDJ），仅供参考，不构成投资建议")
    lines.append("- 买入前请确认ETF溢价率在合理范围（建议 < 3%）")
    lines.append("- 严格执行止损纪律，控制单只ETF最大仓位 < 15%")
    lines.append("- 关注季报、宏观数据等基本面变化，技术信号可能滞后")
    lines.append("")
    lines.append(f"---")
    lines.append(f"*报告由选股持仓管理系统自动生成*")
    
    return "\n".join(lines)


# ── 飞书推送 ───────────────────────────────────────────────────────────────────

def push_to_feishu(report_text: str) -> bool:
    """通过飞书Webhook推送卡片消息"""
    try:
        from market_monitor.config import FEISHU_WEBHOOK
        import requests
        
        if not FEISHU_WEBHOOK:
            print("⚠ 飞书 Webhook 未配置，仅输出终端报告")
            return False
        
        # 构建飞书卡片
        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": "📊 选股持仓分析报告"},
                    "template": "blue"
                },
                "elements": [
                    {
                        "tag": "markdown",
                        "content": report_text[:15000]  # 飞书卡片有长度限制
                    },
                    {
                        "tag": "hr"
                    },
                    {
                        "tag": "note",
                        "elements": [
                            {"tag": "plain_text", "content": f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')} | 自动选股系统"}
                        ]
                    }
                ]
            }
        }
        
        response = requests.post(
            FEISHU_WEBHOOK,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        result = response.json()
        if result.get('code') == 0 or result.get('StatusCode') == 0:
            print("✅ 飞书卡片消息已发送")
            return True
        else:
            print(f"⚠ 飞书发送失败: {result}")
            return False
            
    except ImportError:
        print("⚠ 飞书配置模块未找到")
        return False
    except Exception as e:
        print(f"⚠ 发送到飞书失败: {e}")
        return False


def push_to_feishu_docx(report_text: str) -> Optional[str]:
    """通过飞书API创建云文档推送报告"""
    try:
        import urllib.request
        import ssl
        
        # 获取飞书tenant_access_token
        app_id = os.environ.get("FEISHU_APP_ID", "")
        app_secret = os.environ.get("FEISHU_APP_SECRET", "")
        
        if not app_id or not app_secret:
            print("⚠ 飞书APP_ID/APP_SECRET未配置，跳过文档创建")
            return None
        
        # 获取token
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        
        token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        token_body = json.dumps({"app_id": app_id, "app_secret": app_secret}).encode("utf-8")
        token_req = urllib.request.Request(token_url, data=token_body, method="POST")
        token_req.add_header("Content-Type", "application/json")
        
        with urllib.request.urlopen(token_req, context=ssl_ctx, timeout=10) as resp:
            token_data = json.loads(resp.read().decode("utf-8"))
        
        token = token_data.get("tenant_access_token", "")
        if not token:
            print("⚠ 获取飞书token失败")
            return None
        
        # 创建文档
        doc_title = f"选股持仓报告_{datetime.now().strftime('%Y%m%d')}"
        doc_url = "https://open.feishu.cn/open-apis/docx/v1/documents"
        doc_body = json.dumps({"title": doc_title}).encode("utf-8")
        doc_req = urllib.request.Request(doc_url, data=doc_body, method="POST")
        doc_req.add_header("Content-Type", "application/json")
        doc_req.add_header("Authorization", f"Bearer {token}")
        
        try:
            with urllib.request.urlopen(doc_req, context=ssl_ctx, timeout=10) as resp:
                doc_data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print(f"⚠ 创建飞书文档失败: {e}")
            return None
        
        doc_id = doc_data.get("data", {}).get("document", {}).get("document_id", "")
        if not doc_id:
            print(f"⚠ 文档创建响应异常: {doc_data}")
            return None
        
        # 写入内容（将markdown转换为飞书文档块）
        blocks = _markdown_to_feishu_blocks(report_text)
        
        write_url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children"
        write_body = json.dumps({
            "children": blocks[:50],  # 飞书限制一次最多50个block
            "index": 0
        }).encode("utf-8")
        
        write_req = urllib.request.Request(write_url, data=write_body, method="POST")
        write_req.add_header("Content-Type", "application/json")
        write_req.add_header("Authorization", f"Bearer {token}")
        
        try:
            with urllib.request.urlopen(write_req, context=ssl_ctx, timeout=30) as resp:
                write_data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print(f"⚠ 文档写入失败: {e}")
        
        doc_link = f"https://bytedance.feishu.cn/docx/{doc_id}"
        print(f"✅ 飞书文档已创建: {doc_link}")
        return doc_link
        
    except Exception as e:
        print(f"⚠ 飞书文档推送失败: {e}")
        return None


def _markdown_to_feishu_blocks(md_text: str) -> List[Dict]:
    """将Markdown文本转换为飞书文档块（简化版）"""
    blocks = []
    lines = md_text.split("\n")
    
    for line in lines[:100]:  # 限制行数
        line = line.strip()
        if not line:
            continue
        
        if line.startswith("# "):
            blocks.append({
                "block_type": 3,  # heading1
                "heading1": {
                    "elements": [{"text_run": {"content": line[2:]}}]
                }
            })
        elif line.startswith("## "):
            blocks.append({
                "block_type": 4,  # heading2
                "heading2": {
                    "elements": [{"text_run": {"content": line[3:]}}]
                }
            })
        elif line.startswith("**") and line.endswith("**"):
            blocks.append({
                "block_type": 2,  # text
                "text": {
                    "elements": [{"text_run": {"content": line.strip("*"), "text_element_style": {"bold": True}}}]
                }
            })
        elif line.startswith("- "):
            blocks.append({
                "block_type": 2,  # text
                "text": {
                    "elements": [{"text_run": {"content": line}}]
                }
            })
        elif line.startswith("|"):
            # 跳过表格行（简化处理，实际应转为飞书表格block）
            pass
        elif line == "---":
            blocks.append({
                "block_type": 10,  # divider
                "divider": {}
            })
        else:
            blocks.append({
                "block_type": 2,  # text
                "text": {
                    "elements": [{"text_run": {"content": line}}]
                }
            })
    
    return blocks


# ── 主编排 ─────────────────────────────────────────────────────────────────────

def run_workflow(
    etf_types: List[str] = None,
    scale_min: float = SELECTION_SCALE_MIN,
    kdj_max: float = SELECTION_KDJ_MAX,
    score_threshold: int = BUY_SCORE_THRESHOLD,
    max_analyze: int = MAX_ANALYZE_COUNT,
    track_target: str = None,
    push_feishu: bool = False,
    debug: bool = False,
) -> Dict:
    """
    执行完整的选股持仓管理一条龙流程。
    
    Args:
        etf_types: ETF类型列表
        scale_min: 最小规模（万元）
        kdj_max: KDJ最大值
        score_threshold: 综合评分阈值
        max_analyze: 最多分析数量
        track_target: 跟踪标的筛选
        push_feishu: 是否推送飞书
        debug: 调试模式
    
    Returns:
        完整工作流结果
    """
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    print("=" * 70)
    print("📊 选股持仓管理一条龙系统")
    print(f"   启动时间: {generated_at}")
    print("=" * 70)
    
    # Phase 1: ETF初筛
    pre_result = phase1_etf_prescreen(
        etf_types=etf_types,
        scale_min=scale_min,
        kdj_max=kdj_max,
        track_target=track_target,
    )
    
    if not pre_result.get("success"):
        return {"success": False, "error": pre_result.get("error")}
    
    etfs = pre_result.get("etfs", [])
    if not etfs:
        print("\n⚠ 无符合条件的ETF，结束流程")
        return {"success": True, "etf_count": 0, "message": "无符合条件的ETF"}
    
    # Phase 2: 知行分析
    zhixing_results = phase2_zhixing_analysis(etfs, max_analyze=max_analyze)
    
    if not zhixing_results:
        print("\n⚠ 知行分析无有效结果")
        return {"success": True, "etf_count": len(etfs), "zhixing_count": 0}
    
    # Phase 3: 买入筛选
    filter_result = phase3_filter_buy(zhixing_results, score_threshold=score_threshold)
    
    all_candidates = filter_result.get("all_candidates", [])
    
    # Phase 4: 止损绑定（仅对推荐标的）
    pm = PositionManager()
    if all_candidates:
        all_candidates = phase4_stop_loss(all_candidates, position_manager=pm)
    
    # Phase 5: 生成报告
    print(f"\n[Phase 5] 生成报告...")
    report_text = phase5_generate_report(
        pre_result=pre_result,
        zhixing_results=zhixing_results,
        filter_result=filter_result,
        generated_at=generated_at,
    )
    print(f"         ✅ 报告已生成 ({len(report_text)} 字符)")
    
    # 终端输出（调试模式输出完整报告）
    if debug:
        print("\n" + "=" * 70)
        print(report_text)
        print("=" * 70)
    else:
        print("\n" + "-" * 70)
        # 输出摘要
        print(f"📊 初筛: {pre_result.get('total', 0)} 只 → 分析: {len(zhixing_results)} 只 → 推荐: {len(all_candidates)} 只")
        print(f"   🟢 强烈推荐: {len(filter_result.get('buy_candidates', []))} 只")
        print(f"   🟡 关注列表: {len(filter_result.get('watch_candidates', []))} 只")
        print("-" * 70)
    
    # 飞书推送
    doc_url = None
    if push_feishu:
        print("\n→ 推送飞书...")
        doc_url = push_to_feishu_docx(report_text)
        push_to_feishu(report_text)
    
    # 保存本地报告
    report_path = f"portfolio_report_{datetime.now().strftime('%Y-%m-%d')}.md"
    try:
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_text)
        print(f"\n💾 本地报告已保存: {report_path}")
    except Exception as e:
        print(f"\n⚠ 报告保存失败: {e}")
    
    print(f"\n{'=' * 70}")
    print("✅ 选股持仓管理流程完成")
    print(f"{'=' * 70}\n")
    
    return {
        "success": True,
        "generated_at": generated_at,
        "pre_result": pre_result,
        "zhixing_count": len(zhixing_results),
        "filter_result": filter_result,
        "report_text": report_text,
        "report_path": report_path,
        "doc_url": doc_url,
    }


# ── CLI入口 ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="选股持仓管理一条龙系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    # 终端输出
    python3 -m market_monitor.portfolio_selection_workflow
    
    # 推送到飞书
    python3 -m market_monitor.portfolio_selection_workflow --feishu
    
    # 指定ETF类型
    python3 -m market_monitor.portfolio_selection_workflow --types "行业主题,宽基指数"
    
    # 调试模式（打印完整报告）
    python3 -m market_monitor.portfolio_selection_workflow --debug
"""
    )
    parser.add_argument("--feishu", "-f", action="store_true", help="推送报告到飞书")
    parser.add_argument("--debug", "-d", action="store_true", help="调试模式（打印完整报告）")
    parser.add_argument("--types", default="", help="ETF类型，逗号分隔，默认全部五大类")
    parser.add_argument("--scale", type=float, default=SELECTION_SCALE_MIN, help=f"最小规模（万元），默认{SELECTION_SCALE_MIN}")
    parser.add_argument("--kdj", type=float, default=SELECTION_KDJ_MAX, help=f"KDJ最大值，默认{SELECTION_KDJ_MAX}")
    parser.add_argument("--score", type=int, default=BUY_SCORE_THRESHOLD, help=f"买入评分阈值，默认{BUY_SCORE_THRESHOLD}")
    parser.add_argument("--max", type=int, default=MAX_ANALYZE_COUNT, help=f"最多分析ETF数量，默认{MAX_ANALYZE_COUNT}")
    parser.add_argument("--track", default="", help="跟踪标的筛选（可选）")
    
    args = parser.parse_args()
    
    # 解析ETF类型
    etf_types = None
    if args.types:
        etf_types = [t.strip() for t in args.types.split(",") if t.strip()]
    
    # 执行工作流
    result = run_workflow(
        etf_types=etf_types,
        scale_min=args.scale,
        kdj_max=args.kdj,
        score_threshold=args.score,
        max_analyze=args.max,
        track_target=args.track or None,
        push_feishu=args.feishu,
        debug=args.debug,
    )
    
    if not result.get("success"):
        print(f"\n❌ 工作流执行失败: {result.get('error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
