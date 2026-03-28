"""
飞书机器人推送：卡片构建与发送。

卡片格式：交互式卡片（msg_type=interactive），蓝色标题栏。
各指数块包含：估值指标（股息率/PE/风险溢价）+ 周 KDJ。
估值数据缺失时仅展示 KDJ，两个数据模块完全解耦。
卡片末尾附动态仓位建议区块（市场成交额 + 三维度得分 + 仓位结论）。
"""

from typing import Optional

from typing import Optional

import requests

from ..config import INDEXES, FEISHU_WEBHOOK
from ..analysis import kdj as kdj_mod


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


def build_card(
    val_results: list,
    kdj_data: dict,
    risk_free_rate: float,
    rf_date: str,
    now: str,
    mkt_result: Optional[dict] = None,
    pos_result: Optional[dict] = None,
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
        if div_pct is not None:
            div_icon = "🔴" if div_pct > 70 else ("🟢" if div_pct < 30 else "🟡")
        else:
            div_icon = "⚪"
        if pe_pct is not None:
            pe_icon = "🟢" if pe_pct < 20 else ("🔴" if pe_pct > 80 else "🟡")
        else:
            pe_icon = "⚪"
        rp_icon  = "🟢" if (res["risk_premium"] or 0) > 3 else (
            "🔴" if (res["risk_premium"] or 0) < 1 else "🟡"
        )
        val_note = " ⚠*妙想实时*" if res.get("source") == "mx" else ""

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

        # 历史区间行
        hist_start = res.get("hist_start", "")
        hist_n     = res.get("div_hist_n", 0)
        hist_years = res.get("hist_years")
        hist_note  = ""
        if hist_start:
            hist_note = f"\n　📅 数据区间 {hist_start} 至今"
            hist_note += f"（约 {hist_years:.1f} 年，{hist_n} 交易日）" if hist_years else f"（{hist_n} 交易日）"

        block = (
            f"**{name}**（{code}）　数据日期：{res['date']}{val_note}{launch_note}{hist_note}\n"
            f"　{div_icon} 股息率 **{res['div']:.3f}%**　百分位 {div_pct_str}\n"
            f"　{pe_icon} 市盈率 **{res['pe']:.2f}**　百分位 {pe_pct_str}\n"
            f"　{rp_icon} 风险溢价 **{rp}**\n"
            f"　📈 周KDJ（{kdj_date}，{kdj_label}）{kdj_str}"
        )
        index_blocks.append(block)

    note = (
        f"无风险利率 **{risk_free_rate:.4f}%**（10年期国债 CN10Y，{rf_src}）\n"
        "百分位基于妙想API返回历史区间计算 · PE%位越低越便宜 · 股息率%位越高越丰厚\n"
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
