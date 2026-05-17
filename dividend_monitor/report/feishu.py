"""
飞书机器人推送：卡片构建与发送。
"""

from typing import Optional
import requests

# 处理导入：支持直接执行和模块执行
if __package__:
    from ..config import INDEXES, FEISHU_WEBHOOK
    from ..analysis import kdj as kdj_mod
else:
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from dividend_monitor.config import INDEXES, FEISHU_WEBHOOK
    from dividend_monitor.analysis import kdj as kdj_mod


def _pct_label(pct: Optional[float]) -> str:
    """
    将百分位数值映射为五档文字描述。
    pct 为 None 时返回 "待接入"（数据不足，暂不显示）。
    """
    if pct is None:
        return "待接入"
    if pct >= 80:
        return "极高"
    if pct >= 60:
        return "偏高"
    if pct >= 40:
        return "适中"
    if pct >= 20:
        return "偏低"
    return "极低"


def _score_icon(score: float) -> str:
    """得分图标：强多/弱多/中性/弱空/强空。"""
    if score >= 1.5:
        return "🟢🟢"
    if score >= 0.5:
        return "🟢"
    if score >= -0.5:
        return "🟡"
    if score >= -1.5:
        return "🔴"
    return "🔴🔴"


def _pm_market_icon(market_id: str) -> str:
    """仓位管理市场图标。"""
    icons = {
        "a_stock": "🇨🇳",
        "hk_stock": "🇭🇰",
        "us_stock": "🇺🇸",
    }
    return icons.get(market_id, "🌐")


def _pm_style_icon(style_id: str) -> str:
    """仓位管理风格图标。"""
    icons = {
        "high_elasticity": "🚀",
        "high_dividend": "💰",
        "balanced": "⚖️",
    }
    return icons.get(style_id, "📊")


def _pm_action_icon(action: str) -> str:
    """调仓动作图标。"""
    icons = {
        "buy": "📈",
        "sell": "📉",
        "hold": "➡️",
        "reduce": "⬇️",
        "quit": "❌",
        "watch": "👀",
    }
    return icons.get(action, "➡️")


def _build_position_manager_block(pm_result: dict) -> str:
    """
    构建仓位管理区块文本。

    Args:
        pm_result: PositionManager.get_market_allocation() 返回的结果

    Returns:
        格式化的 Markdown 文本
    """
    if not pm_result or "error" in pm_result:
        return ""

    blocks = []

    # 标题
    blocks.append("**📊 仓位管理建议**")

    # 权益/现金比例
    total_equity = pm_result.get("total_equity_ratio", 0) * 100
    cash_ratio = pm_result.get("cash_ratio", 0) * 100
    blocks.append(f"　⚖️ 权益仓位 **{total_equity:.0f}%**　💵 现金/债券 **{cash_ratio:.0f}%**")

    # 市场配置
    market_alloc = pm_result.get("market_allocations", {})
    if market_alloc:
        blocks.append("")
        blocks.append("**🌏 市场配置（权益仓位内部分布）**")
        for market_id, data in market_alloc.items():
            icon = _pm_market_icon(market_id)
            name = data.get("name", market_id)
            ratio = data.get("raw_weight", 0) * 100
            # 获取估值水平
            val_level_map = {
                "extremely_low": "极度低估",
                "low": "低估",
                "fair": "合理",
                "high": "偏高",
                "extremely_high": "极度偏高",
            }
            val_level = data.get("valuation_level", "")
            val_label = val_level_map.get(val_level, val_level) if val_level else "未知"
            # 趋势图标
            trend_map = {
                "bullish": "🟢",
                "bearish": "🔴",
                "neutral": "🟡",
            }
            trend = data.get("trend", "neutral")
            trend_icon = trend_map.get(trend, "🟡")

            blocks.append(
                f"　{icon} {name}\n"
                f"　　占比 {ratio:.1f}%　{trend_icon}趋势 {val_label}"
            )

    # 风格配置
    style_alloc = pm_result.get("style_allocations", {})
    if style_alloc:
        blocks.append("")
        blocks.append("**🎯 风格配置（权益仓位内部分布）**")
        for style_id, data in style_alloc.items():
            icon = _pm_style_icon(style_id)
            name = data.get("name", style_id)
            target = data.get("target_weight", 0) * 100
            current = data.get("current_weight", 0) * 100
            if current > 0:
                blocks.append(f"　{icon} {name} 目标 **{target:.0f}%**")
            else:
                blocks.append(f"　{icon} {name} 目标 **{target:.0f}%**")

    # 调仓建议摘要
    rebalance_items = pm_result.get("rebalance_items", [])
    if rebalance_items:
        blocks.append("")
        blocks.append("**⚠️ 调仓建议**")

        # 只显示调整幅度最大的前3个
        top_adjustments = sorted(
            rebalance_items,
            key=lambda x: abs(x.get("adjustment", 0)),
            reverse=True
        )[:3]

        for item in top_adjustments:
            code = item.get("code", "")
            name = item.get("name", "")[:8]
            current = item.get("current_weight", 0) * 100
            target = item.get("target_weight", 0) * 100
            adj = item.get("adjustment", 0) * 100
            action = item.get("stop_loss_action", "hold")
            action_icon = _pm_action_icon(action)

            adj_str = f"+{adj:.1f}%" if adj >= 0 else f"{adj:.1f}%"
            if abs(adj) < 0.5:
                adj_str = "—"

            blocks.append(
                f"　{action_icon} {code} {name}\n"
                f"　　{current:.1f}% → {target:.1f}% ({adj_str})"
            )

    return "\n".join(blocks)


def build_card(
    val_results: list,
    kdj_data: dict,
    risk_free_rate: float,
    rf_date: str,
    now: str,
    mkt_result: Optional[dict] = None,
    pos_result: Optional[dict] = None,
    pm_result: Optional[dict] = None,
) -> dict:
    """
    构建飞书交互式卡片消息体。

    Args:
        val_results:    与 INDEXES 等长的估值结果列表。
        kdj_data:       {index_code: [kdj_row, ...]} 映射。
        risk_free_rate: 无风险利率（%）。
        rf_date:        无风险利率对应日期字符串或 "fallback"。
        now:            报告生成时间字符串。
        mkt_result:     全市场成交额结果字典（可选）。
        pos_result:     动态仓位建议字典（可选）。
        pm_result:      仓位管理建议字典（可选，来自 PositionManager）。

    Returns:
        可直接传入 requests.post(json=...) 的飞书消息字典。
    """
    rf_src = f"实时 ({rf_date})" if rf_date != "fallback" else "保底默认"

    index_blocks = []
    for idx, res in zip(INDEXES, val_results):
        name = idx["name"]
        code = idx["code"]

        rows = kdj_data.get(code, [])
        if rows:
            r         = rows[0]
            k_s       = f"{r['K']:.1f}" if r["K"] is not None else "-"
            d_s       = f"{r['D']:.1f}" if r["D"] is not None else "-"
            j_s       = f"{r['J']:.1f}" if r["J"] is not None else "-"
            sig       = kdj_mod.signal(r, rows[1] if len(rows) > 1 else None)
            kdj_label = "妙想⚠" if r.get("source") == "mx" else "中证自算"
            kdj_str   = f"K={k_s} D={d_s} J={j_s}" + (f" *{sig}*" if sig else "")
            kdj_date  = r["date"]
        else:
            kdj_str   = "暂无数据"
            kdj_label = "-"
            kdj_date  = "-"

        if "error" in res:
            block = (
                f"**{name}**（{code}）　❌ 估值数据：{res['error']}\n"
                f"　📈 周KDJ（{kdj_date}，{kdj_label}）{kdj_str}"
            )
            index_blocks.append(block)
            continue

        rp      = f"{res['risk_premium']:+.2f}%" if res["risk_premium"] is not None else "N/A"
        div_pct = res.get("div_pct")   # 可能为 None
        pe_pct  = res.get("pe_pct")    # 可能为 None
        div_lv  = _pct_label(div_pct)
        pe_lv   = _pct_label(pe_pct)

        # 百分位有效时才显示颜色图标，无效时统一用灰色占位
        # 股息率：百分位越低=历史上大部分时间更低=现在股息率更高=便宜=绿色
        if div_pct is not None:
            div_icon = "🟢" if div_pct < 30 else ("🔴" if div_pct > 70 else "🟡")
        else:
            div_icon = "⚪"
        # 市盈率：百分位越低=历史上大部分时间更低=现在PE更低=便宜=绿色
        if pe_pct is not None:
            pe_icon = "🟢" if pe_pct < 30 else ("🔴" if pe_pct > 70 else "🟡")
        else:
            pe_icon = "⚪"
        rp_icon  = "🟢" if (res["risk_premium"] or 0) > 3 else (
            "🔴" if (res["risk_premium"] or 0) < 1 else "🟡"
        )
        val_note = " *Wind APP数据*" if res.get("source") == "wind_app" else " *缓存*"

        # 百分位展示字符串
        div_pct_str = f"{div_pct:.1f}% *{div_lv}*" if div_pct is not None else "*待接入（数据不足）*"
        pe_pct_str  = f"{pe_pct:.1f}% *{pe_lv}*"  if pe_pct  is not None else "*待接入（数据不足）*"

        # 发布年限提示
        launch_short = res.get("launch_short_history", False)
        launch_date  = res.get("launch_date", "")
        launch_years = res.get("launch_years")
        launch_note  = ""
        if launch_short and launch_years is not None:
            launch_note = f"\n　⚠ 指数发布 {launch_date}（约 {launch_years:.1f} 年），历史不足10年，百分位仅供参考"

        # 历史区间行 - 显示发布日至数据日期
        data_date = res.get("date", "")
        launch_date = res.get("launch_date", "")
        hist_years = res.get("hist_years", 0)
        hist_note = ""
        
        if launch_date and data_date:
            hist_note = f"\n　📅 数据区间 {launch_date} 至 {data_date}（约 {hist_years:.1f} 年完整发布历史）"
        elif launch_date:
            hist_note = f"\n　📅 数据区间 {launch_date} 至今（约 {hist_years:.1f} 年完整发布历史）"

        block = (
            f"**{name}**（{code}）　数据日期：{res['date']}{val_note}{launch_note}{hist_note}\n"
            f"　{div_icon} 股息率 **{res['div']:.3f}%**　百分位 {div_pct_str}\n"
            f"　{pe_icon} 市盈率 **{res['pe']:.2f}**　百分位 {pe_pct_str}\n"
            f"　{rp_icon} 风险溢价 **{rp}**\n"
            f"　📈 周KDJ（{kdj_date}，{kdj_label}）{kdj_str}"
        )
        index_blocks.append(block)

    percent_note = "百分位基于Wind APP完整发布历史计算（发布日至数据日期） · PE%位越低越便宜 · 股息率%位越高越丰厚"
    
    note = (
        f"无风险利率 **{risk_free_rate:.4f}%**（10年期国债 CN10Y，{rf_src}）\n"
        f"{percent_note}\n"
        "⚪ 待接入 = 有效历史 < 240 交易日，百分位暂空置，后续接入新数据源后补充\n"
        f"风险溢价 = 1/PE×100% − {risk_free_rate:.4f}%"
    )

    elements = [
        {"tag": "div", "text": {"tag": "lark_md", "content": note}},
        {"tag": "hr"},
    ]
    for i, block_text in enumerate(index_blocks):
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": block_text}})
        if i < len(index_blocks) - 1:
            elements.append({"tag": "hr"})

    # ── 动态仓位建议区块 ──────────────────────────────────────────────────────
    if pos_result:
        elements.append({"tag": "hr"})

        if mkt_result and "error" not in mkt_result:
            tv      = mkt_result.get("turnover")
            chg     = mkt_result.get("turnover_chg_pct")
            tv_prev = mkt_result.get("turnover_prev")
            dt      = mkt_result.get("data_date", "?")
            tv_str  = f"成交额 **{tv:,.0f}亿**" if tv is not None else ""
            if chg is not None and tv_prev is not None:
                chg_icon = "📈" if chg >= 0 else "📉"
                chg_str  = f"  {chg_icon} 较前日 **{chg:+.2f}%**（前日 {tv_prev:,.0f}亿）"
            elif chg is not None:
                chg_icon = "📈" if chg >= 0 else "📉"
                chg_str  = f"  {chg_icon} 较前日 **{chg:+.2f}%**"
            else:
                chg_str  = ""
            mkt_line = f"📡 {tv_str}{chg_str}  截至 {dt}"
        else:
            err = (mkt_result or {}).get("error", "数据缺失")
            mkt_line = f"📡 全市场成交额 ❌ {err}"

        lo, hi = pos_result["position_range"]
        label  = pos_result["position_label"]
        pct    = pos_result["position_pct"]
        cs     = pos_result["composite_score"]

        pos_block = (
            f"**💡 动态仓位建议**\n"
            f"　{mkt_line}\n\n"
            f"　{_score_icon(pos_result['val_score'])} 估值　{pos_result['val_score']:+.1f} *{pos_result['val_label']}*\n"
            f"　{_score_icon(pos_result['mkt_score'])} 市场 {pos_result['mkt_score']:+.1f} *{pos_result['mkt_label']}*\n"
            f"　{_score_icon(pos_result['kdj_score'])} 技术 {pos_result['kdj_score']:+.1f} *{pos_result['kdj_label']}*\n"
            f"　综合 **{cs:+.2f}**（估值50% 市场30% 技术20%）\n\n"
            f"　▶ 建议 **{lo}%–{hi}%**（中枢{pct}%） **【{label}】**\n\n"
            f"　*不构成投资建议*"
        )
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": pos_block}})

    # ── 仓位管理区块 ──────────────────────────────────────────────────────────
    if pm_result and "error" not in pm_result:
        elements.append({"tag": "hr"})
        pm_block = _build_position_manager_block(pm_result)
        if pm_block:
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": pm_block}})

    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title":    {"tag": "plain_text", "content": f"📊 红利指数监控  {now}"},
                "template": "blue",
            },
            "elements": elements,
        },
    }


def send(payload: dict, webhook: str = FEISHU_WEBHOOK) -> bool:
    """
    发送飞书消息。

    Args:
        payload: build_card() 返回的消息体。
        webhook: 飞书机器人 Webhook 地址。

    Returns:
        True 表示发送成功，False 表示失败。
    """
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
