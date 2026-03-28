"""
主入口：协调各模块完成数据采集、计算和报告输出。

执行流程：
  Step 0  实时获取10年期国债收益率（CN10Y）
  Step 1  获取估值数据（妙想API → 本地缓存降级）
  Step 2  获取周线KDJ（妙想API → 中证官网自算降级）
  Step 3  获取全市场成交额（中证全指历史），计算动态仓位建议
  Step 4  终端输出报告
  Step 5  可选：推送飞书机器人
"""

import sys
import time
from datetime import datetime

from .config import INDEXES
from . import cache
from .data_sources import bond
from .data_sources.csindex import fetch_daily_chg
from .analysis import valuation, kdj, position
from .report import terminal, feishu


def _fetch_market_turnover() -> dict:
    """
    从中证全指历史接口获取最近两个交易日成交额，计算日环比。

    Returns:
        成功时：{"turnover": float, "turnover_prev": float|None,
                 "turnover_chg_pct": float|None, "data_date": str,
                 "stock_count": int, "source": "csindex"}
        失败时：{"error": str}
    """
    rows = fetch_daily_chg("000985", days=15)
    if not rows:
        return {"error": "中证全指接口无数据"}

    latest = rows[-1]
    result = {
        "turnover":         latest["turnover"],
        "data_date":        latest["date"],
        "stock_count":      latest["cons_number"],
        "turnover_prev":    None,
        "turnover_chg_pct": None,
        "source":           "csindex",
    }
    if len(rows) >= 2:
        prev_tv = rows[-2]["turnover"]
        if prev_tv and prev_tv > 0:
            result["turnover_prev"]    = prev_tv
            result["turnover_chg_pct"] = round(
                (latest["turnover"] - prev_tv) / prev_tv * 100, 2
            )
    return result


def main() -> None:
    send_to_feishu = "--feishu" in sys.argv
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # ── Step 0: 无风险利率 ────────────────────────────────────────────────────
    print("→ 获取10年期国债收益率(CN10Y)...", end=" ", flush=True)
    risk_free_rate, rf_date = bond.fetch()
    if rf_date == "fallback":
        print(f"✗ 获取失败，使用保底值 {risk_free_rate}%")
    else:
        print(f"✓ {risk_free_rate:.4f}%（{rf_date}）")

    # ── Step 1: 估值数据 ──────────────────────────────────────────────────────
    print("\n[1/3] 获取估值数据...")
    val_cache       = cache.load()
    val_results     = []
    cache_updated   = False
    quota_exhausted = False

    for i, idx in enumerate(INDEXES):
        if i > 0:
            time.sleep(3)
        print(f"  → {idx['name']}...", end=" ", flush=True)

        cached = val_cache.get(idx["code"])
        if cached:
            pe = cached.get("pe")
            cached["risk_premium"] = (1 / pe * 100) - risk_free_rate if pe else None
            cached["source"] = "cache"
            val_results.append(cached)
            print(f"✓  [缓存 {cached.get('date','?')}]")
            continue

        try:
            if quota_exhausted:
                raise RuntimeError("妙想API今日配额已用尽（status=113）")

            res = valuation.fetch(idx, risk_free_rate)

            if res.get("error_type") == "quota":
                quota_exhausted = True
                raise RuntimeError(res["error"])

            if "error" not in res:
                val_cache[idx["code"]] = res
                cache_updated = True
                val_results.append(res)
                print("✓  [妙想]")
            else:
                val_results.append({"error": res.get("error", "未知错误")})
                print(f"✗ {res.get('error','?')}  [无缓存]")

        except Exception as e:
            err_msg = str(e)
            label = "配额用尽" if "113" in err_msg or "配额" in err_msg else err_msg[:40]
            val_results.append({"error": err_msg})
            print(f"✗ {label}  [无缓存]")

    if cache_updated:
        cache.save(val_cache)
        from .config import VAL_CACHE_FILE
        print(f"  ✓ 估值缓存已更新 → {VAL_CACHE_FILE}")

    # ── Step 2: 周线 KDJ ─────────────────────────────────────────────────────
    print("\n[2/3] 获取周线 KDJ...")
    kdj_data = {}
    for i, idx in enumerate(INDEXES):
        if i > 0:
            time.sleep(3)
        print(f"  → {idx['name']}...", end=" ", flush=True)
        try:
            rows = kdj.fetch(idx)
            kdj_data[idx["code"]] = rows
            if rows:
                src_label = "妙想（降级）" if rows[0].get("source") == "mx" else "中证官网自算"
                print(f"✓  [{src_label}]")
            else:
                print("✗ 无数据")
        except Exception as e:
            kdj_data[idx["code"]] = []
            print(f"✗ {e}")

    # ── Step 3: 全市场成交额 + 动态仓位建议 ──────────────────────────────────
    print("\n[3/3] 获取全市场成交额（中证全指）...", end=" ", flush=True)
    mkt_result = _fetch_market_turnover()
    if "error" in mkt_result:
        print(f"✗ {mkt_result['error']}")
        turnover = None
    else:
        tv      = mkt_result.get("turnover")
        chg     = mkt_result.get("turnover_chg_pct")
        dt_tag  = mkt_result.get("data_date", "?")
        tv_str  = f"成交额 {tv:,.0f}亿" if tv is not None else ""
        chg_str = f"  日环比 {chg:+.2f}%" if chg is not None else ""
        print(f"✓  {tv_str}{chg_str}  [{dt_tag}]")
        turnover = tv

    pos_result = position.calc_position(
        val_results, kdj_data,
        active_rate=None,
        active_mv=None,
        turnover=turnover,
    )

    # ── Step 4: 终端报告 ──────────────────────────────────────────────────────
    terminal.print_report(
        val_results, kdj_data, risk_free_rate, rf_date, now,
        mkt_result=mkt_result, pos_result=pos_result,
    )

    # ── Step 5: 飞书推送 ──────────────────────────────────────────────────────
    if send_to_feishu:
        print("→ 推送飞书...", end=" ", flush=True)
        card = feishu.build_card(
            val_results, kdj_data, risk_free_rate, rf_date, now,
            mkt_result=mkt_result, pos_result=pos_result,
        )
        ok = feishu.send(card)
        print("✓ 已发送" if ok else "✗ 发送失败")
    else:
        print("  提示：添加 --feishu 参数可将报告推送到飞书机器人")


if __name__ == "__main__":
    main()
