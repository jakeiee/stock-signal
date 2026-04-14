"""
终端报告输出。
"""

from typing import Optional

# 处理导入：支持直接执行和模块执行
if __package__:
    from ..config import INDEXES
    from ..analysis import kdj as kdj_mod
else:
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from dividend_monitor.config import INDEXES
    from dividend_monitor.analysis import kdj as kdj_mod


def _pct_bar(pct: Optional[float], width: int = 10) -> str:
    """
    渲染字符进度条，如 [████░░░░░░] 40.0%。
    pct 为 None 时返回 "[??????????] N/A（数据不足）"。
    """
    if pct is None:
        return "[" + "?" * width + "] N/A（数据不足）"
    filled = round(pct / 100 * width)
    return "[" + "█" * filled + "░" * (width - filled) + f"] {pct:.1f}%"


def _score_bar(score: float) -> str:
    """将 -2~+2 得分渲染为 11 格进度条，中心为 0。"""
    width   = 11
    center  = 5
    offset  = round(score / 2 * center)
    filled  = center + offset
    filled  = max(0, min(width, filled))
    bar     = "░" * width
    bar_lst = list(bar)
    bar_lst[center] = "┼"   # 中心基准线
    if offset > 0:
        for i in range(center + 1, center + offset + 1):
            if 0 <= i < width:
                bar_lst[i] = "█"
    elif offset < 0:
        for i in range(center + offset, center):
            if 0 <= i < width:
                bar_lst[i] = "█"
    return "[" + "".join(bar_lst) + f"] {score:+.1f}"


def print_report(
    val_results: list,
    kdj_data: dict,
    risk_free_rate: float,
    rf_date: str,
    now: str,
    mkt_result: Optional[dict] = None,
    pos_result: Optional[dict] = None,
) -> None:
    """
    将监控结果打印到终端。

    Args:
        val_results:    与 INDEXES 等长的估值结果列表，每项为 dict。
        kdj_data:       {index_code: [kdj_row, ...]} 映射。
        risk_free_rate: 无风险利率（%）。
        rf_date:        无风险利率对应日期字符串或 "fallback"。
        now:            报告生成时间字符串。
        mkt_result:     全市场成交额结果字典（可选）。
        pos_result:     动态仓位建议字典（可选）。
    """
    W      = 68
    rf_src = f"实时 CN10Y ({rf_date})" if rf_date != "fallback" else "保底默认值"

    print(f"\n{'═' * W}")
    print(f"  📊 红利指数监控  |  {now}")
    print(f"  无风险利率: {risk_free_rate:.4f}%（{rf_src}）")
    print(f"{'═' * W}")

    for idx, res in zip(INDEXES, val_results):
        print(f"\n  ▌ {idx['name']}（{idx['code']}）", end="")

        if "error" in res:
            print(f"  ✗ {res['error']}")
        else:
            src_tag = "  [Wind APP缓存]"
            print(f"  数据日期: {res['date']}{src_tag}")

            # 发布年限不足警告
            launch_date  = res.get("launch_date", "")
            launch_years = res.get("launch_years")
            launch_short = res.get("launch_short_history", False)
            if launch_short and launch_years is not None:
                print(f"    ⚠ 指数发布日期 {launch_date}（约 {launch_years:.1f} 年），历史不足10年，百分位仅供参考")

            # 历史数据区间说明 - 显示发布日至数据日期
            data_date = res.get("date", "")
            launch_date = res.get("launch_date", "")
            hist_years = res.get("hist_years", 0)
            
            if launch_date and data_date:
                print(f"    历史区间  {launch_date} 至 {data_date}（约 {hist_years:.1f} 年完整发布历史）")
            elif launch_date:
                print(f"    历史区间  {launch_date} 至今（约 {hist_years:.1f} 年完整发布历史）")

            rp = f"{res['risk_premium']:+.2f}%" if res["risk_premium"] is not None else "N/A"
            print(f"    股息率  {res['div']:.3f}%  {_pct_bar(res['div_pct'])}")
            print(f"    市盈率  {res['pe']:.2f}    {_pct_bar(res['pe_pct'])}")
            print(f"    风险溢价  {rp}")

        rows = kdj_data.get(idx["code"], [])
        if rows:
            r       = rows[0]
            k_s     = f"{r['K']:.1f}" if r["K"] is not None else "N/A"
            d_s     = f"{r['D']:.1f}" if r["D"] is not None else "N/A"
            j_s     = f"{r['J']:.1f}" if r["J"] is not None else "N/A"
            sig     = kdj_mod.signal(r, rows[1] if len(rows) > 1 else None)
            sig_str = f"  {sig}" if sig else ""
            kdj_tag = "  ⚠ 妙想降级" if r.get("source") == "mx" else ""
            print(f"    周KDJ  K={k_s}  D={d_s}  J={j_s}{sig_str}  （{r['date']}）{kdj_tag}")
        else:
            print("    周KDJ  暂无数据")

    # ── 动态仓位建议区块 ──────────────────────────────────────────────────────
    if pos_result:
        print(f"\n{'─' * W}")
        print("  💡 动态仓位建议")
        print(f"{'─' * W}")

        # 市场成交额行
        if mkt_result and "error" not in mkt_result:
            tv      = mkt_result.get("turnover")
            chg     = mkt_result.get("turnover_chg_pct")
            tv_prev = mkt_result.get("turnover_prev")
            dt      = mkt_result.get("data_date", "?")
            tv_str  = f"成交额 {tv:,.0f}亿" if tv is not None else ""
            if chg is not None and tv_prev is not None:
                chg_str = f"  较前日 {chg:+.2f}%（前日 {tv_prev:,.0f}亿）"
            elif chg is not None:
                chg_str = f"  较前日 {chg:+.2f}%"
            else:
                chg_str = ""
            print(f"  市场成交额  {tv_str}{chg_str}  截至 {dt}")
        else:
            err = (mkt_result or {}).get("error", "数据缺失")
            print(f"  市场成交额  ✗ {err}")

        print(f"\n  评分维度（-2 空头 ←→ +2 多头）：")
        print(f"    估值信号  {_score_bar(pos_result['val_score'])}  {pos_result['val_label']}")
        print(f"    市场温度  {_score_bar(pos_result['mkt_score'])}  {pos_result['mkt_label']}")
        print(f"    技术信号  {_score_bar(pos_result['kdj_score'])}  {pos_result['kdj_label']}")
        print(f"    综合得分  {_score_bar(pos_result['composite_score'])}")

        lo, hi = pos_result["position_range"]
        label  = pos_result["position_label"]
        pct    = pos_result["position_pct"]
        print(f"\n  ▶ 建议仓位  {lo}%–{hi}%（中枢 {pct}%）  【{label}】")
        print(f"\n  ─ 权重：估值50%  市场温度30%  KDJ技术20%")
        print(f"  ─ 本建议仅供参考，不构成投资建议")

    print(f"\n{'═' * W}")
    print(f"  ─ 百分位说明：基于Wind APP完整发布历史计算（发布日至数据日期）；PE%位越低越便宜；股息率%位越高越丰厚")
    print(f"  ─ N/A（数据不足）表示有效历史 < 240 个交易日，百分位不可信，暂空置待接入新数据源")
    print(f"  ─ 风险溢价 = 1/PE×100% − {risk_free_rate:.4f}%（无风险利率）")
    print(f"{'═' * W}\n")
