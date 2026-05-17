"""
主入口：协调各模块完成数据采集、计算和报告输出。

执行流程：
  Step 0  实时获取10年期国债收益率（CN10Y）
  Step 1  获取估值数据（妙想API → 本地缓存降级）
  Step 2  获取周线KDJ（妙想API → 中证官网自算降级）
  Step 3  获取全市场成交额（中证全指历史），计算动态仓位建议
  Step 4  计算仓位管理建议（基于 PositionManager）
  Step 5  终端输出报告
  Step 6  可选：推送飞书机器人

集成了自我改进学习系统：自动记录执行错误和学习点
"""

import sys
import time
from datetime import datetime

# 处理导入：支持直接执行和模块执行两种方式
if __package__:
    from .config import INDEXES
    from . import cache
    from .data_sources import bond
    from .data_sources.csindex import fetch_daily_chg
    from .analysis import valuation, kdj, position
    from .report import terminal, feishu
    # 仓位管理模块
    from market_monitor.analysis.position_manager import PositionManager, Market, TrendDirection
    from market_monitor.data_sources import valuation as market_valuation
else:
    # 直接执行时 (python dividend_monitor/main.py)
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from dividend_monitor.config import INDEXES
    from dividend_monitor import cache
    from dividend_monitor.data_sources import bond
    from dividend_monitor.data_sources.csindex import fetch_daily_chg
    from dividend_monitor.analysis import valuation, kdj, position
    from dividend_monitor.report import terminal, feishu
    # 仓位管理模块
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from market_monitor.analysis.position_manager import PositionManager, Market, TrendDirection
    from market_monitor.data_sources import valuation as market_valuation

# 集成自我改进学习系统
_learning_system_enabled = False
try:
    import sys
    sys.path.insert(0, '.')
    from tools.self_improvement_integration import get_tracker
    _learning_system_enabled = True
except ImportError:
    _learning_system_enabled = False
    get_tracker = None


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
    
    # ── 初始化自我改进跟踪器 ────────────────────────────────────────────────
    tracker = None
    if _learning_system_enabled and get_tracker:
        tracker = get_tracker("dividend_monitor")
        print("🧠 启用自我改进学习系统（自动记录错误和学习）")
    else:
        if not _learning_system_enabled:
            print("⚠ 自我改进学习系统未启用，请检查 tools/ 目录")
        elif not get_tracker:
            print("⚠ 无法导入 self_improvement_integration 模块")
    
    # ── 更新缓存：优先使用Wind APP数据 ────────────────────────────────────────
    try:
        from .data_sources import wind_app
        print("→ 检查Wind APP专业估值数据...", end=" ", flush=True)
        wind_app.update_valuation_cache()
    except Exception as e:
        print(f"⚠ Wind APP更新失败: {e}")
        # 记录错误到学习系统
        if tracker:
            tracker.log_error(
                error_summary="Wind APP专业估值数据更新失败",
                error_message=str(e),
                context="在 main() 函数开始时尝试更新Wind APP估值缓存",
                tool_name="wind_app.update_valuation_cache",
                priority="medium",
                fix_suggestion="检查网络连接或Wind APP数据源配置"
            )

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
                # 记录配额用尽的学习点
                if tracker:
                    tracker.log_learning(
                        summary="妙想API每日配额已用尽",
                        details=f"获取 {idx['name']} 估值数据时遇到配额限制。建议：1) 使用本地缓存降级 2) 切换数据源 3) 分布式API调用",
                        category="knowledge_gap",
                        priority="high",
                        related_files=["dividend_monitor/analysis/valuation.py"]
                    )
                raise RuntimeError(res["error"])

            if "error" not in res:
                val_cache[idx["code"]] = res
                cache_updated = True
                val_results.append(res)
                print("✓  [妙想]")
            else:
                val_results.append({"error": res.get("error", "未知错误")})
                print(f"✗ {res.get('error','?')}  [无缓存]")
                # 记录API错误
                if tracker:
                    tracker.log_error(
                        error_summary=f"获取 {idx['name']} 估值数据失败",
                        error_message=res.get("error", "未知错误"),
                        context=f"指数代码: {idx['code']}, 名称: {idx['name']}",
                        tool_name="valuation.fetch",
                        priority="medium",
                        fix_suggestion="检查妙想API配置或网络连接"
                    )

        except Exception as e:
            err_msg = str(e)
            label = "配额用尽" if "113" in err_msg or "配额" in err_msg else err_msg[:40]
            val_results.append({"error": err_msg})
            print(f"✗ {label}  [无缓存]")
            
            # 记录异常
            if tracker and "配额" not in err_msg:  # 配额错误已在上面记录
                tracker.log_error(
                    error_summary=f"获取 {idx['name']} 估值数据时发生异常",
                    error_message=err_msg,
                    context=f"指数代码: {idx['code']}, 风险免费率: {risk_free_rate}",
                    tool_name="valuation.fetch",
                    priority="high"
                )

    if cache_updated:
        cache.save(val_cache)
        from .config import VAL_CACHE_FILE
        print(f"  ✓ 估值缓存已更新 → {VAL_CACHE_FILE}")
        # 记录缓存成功更新
        if tracker:
            tracker.log_learning(
                summary="估值缓存成功更新",
                details=f"更新了 {len(INDEXES)} 个指数的估值缓存，缓存文件: {VAL_CACHE_FILE}",
                category="best_practice",
                priority="low",
                related_files=["dividend_monitor/cache.py"]
            )

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
                # 记录数据源降级情况
                if tracker and "降级" in src_label:
                    tracker.log_learning(
                        summary=f"KDJ数据源降级到备用方案",
                        details=f"获取 {idx['name']} KDJ数据时，妙想API降级到备用数据源。这可能是API配额不足或网络问题。",
                        category="knowledge_gap",
                        priority="medium"
                    )
            else:
                print("✗ 无数据")
                if tracker:
                    tracker.log_error(
                        error_summary=f"获取 {idx['name']} KDJ数据为空",
                        error_message="API返回空数据",
                        context=f"指数代码: {idx['code']}，KDJ数据源可能有问题",
                        tool_name="kdj.fetch",
                        priority="medium"
                    )
        except Exception as e:
            kdj_data[idx["code"]] = []
            print(f"✗ {e}")
            if tracker:
                tracker.log_error(
                    error_summary=f"获取 {idx['name']} KDJ数据失败",
                    error_message=str(e),
                    context=f"指数代码: {idx['code']}",
                    tool_name="kdj.fetch",
                    priority="high",
                    fix_suggestion="检查KDJ模块的数据源配置"
                )

    # ── Step 3: 全市场成交额 + 动态仓位建议 ──────────────────────────────────
    print("\n[3/3] 获取全市场成交额（中证全指）...", end=" ", flush=True)
    mkt_result = _fetch_market_turnover()
    if "error" in mkt_result:
        print(f"✗ {mkt_result['error']}")
        turnover = None
        # 记录成交额获取错误
        if tracker:
            tracker.log_error(
                error_summary="获取全市场成交额失败",
                error_message=mkt_result.get("error", "未知错误"),
                context="通过中证全指接口获取成交额数据",
                tool_name="_fetch_market_turnover",
                priority="medium",
                fix_suggestion="检查中证官网接口是否可用或网络连接"
            )
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

    # ── Step 4: 仓位管理建议 ──────────────────────────────────────────────────
    print("→ 计算仓位管理建议...", end=" ", flush=True)
    pm_result = None
    try:
        pm = PositionManager()

        # 构建估值字典 - 与 position_config.json 保持一致
        valuations = {}

        # A股估值：使用 Wind APP 数据（万得全A除金融石油石化 881003.WI）
        try:
            a_result = market_valuation.fetch_index_valuation("881003.WI")
            if a_result.get("data"):
                a_pe_pct = a_result["data"].get("pe_pct", 50)
                valuations[Market.A_STOCK] = 100 - a_pe_pct  # 转换为低估百分位
                print(f"  A股(万得全A除金融石油石化) PE百分位={a_pe_pct}%, 低估={100-a_pe_pct}%")
            else:
                valuations[Market.A_STOCK] = 50.0
                print(f"  ⚠ A股估值获取失败: {a_result.get('error', '未知错误')}")
        except Exception as e:
            print(f"⚠ A股估值获取失败: {e}")
            valuations[Market.A_STOCK] = 50.0

        # 港股估值：使用 Wind APP 数据（恒生科技 HSTECH）
        try:
            hk_result = market_valuation.fetch_index_valuation("HSTECH")
            if hk_result.get("data"):
                hk_pe_pct = hk_result["data"].get("pe_pct", 50)
                valuations[Market.HK_STOCK] = 100 - hk_pe_pct  # 转换为低估百分位
                print(f"  港股(恒生科技) PE百分位={hk_pe_pct}%, 低估={100-hk_pe_pct}%")
            else:
                valuations[Market.HK_STOCK] = 50.0
                print(f"  ⚠ 港股估值获取失败: {hk_result.get('error', '未知错误')}")
        except Exception as e:
            print(f"⚠ 港股估值获取失败: {e}")
            valuations[Market.HK_STOCK] = 50.0

        # 美股估值：使用 Wind APP 数据（标普500 SPX）
        try:
            us_result = market_valuation.fetch_index_valuation("SPX")
            if us_result.get("data"):
                us_pe_pct = us_result["data"].get("pe_pct", 50)
                valuations[Market.US_STOCK] = 100 - us_pe_pct  # 转换为低估百分位
                print(f"  美股(标普500) PE百分位={us_pe_pct}%, 低估={100-us_pe_pct}%")
            else:
                # 回退：使用 Shiller CAPE 数据
                try:
                    from market_monitor.data_sources.shiller_api import fetch_us_cape_valuation
                    cape_result = fetch_us_cape_valuation()
                    us_pe_pct = cape_result.get("pe_pct", 50)
                    valuations[Market.US_STOCK] = 100 - us_pe_pct
                    print(f"  美股(CAPE) PE百分位={us_pe_pct}%, 低估={100-us_pe_pct}%")
                except Exception:
                    valuations[Market.US_STOCK] = 50.0
                    print(f"  ⚠ 美股估值获取失败: {us_result.get('error', '未知错误')}")
        except Exception as e:
            print(f"⚠ 美股估值获取失败: {e}")
            valuations[Market.US_STOCK] = 50.0

        # 获取仓位管理建议
        pm_result = pm.get_market_allocation(valuations)
        print(f"✓ 权益仓位 {pm_result.get('total_equity_ratio', 0) * 100:.0f}%")

    except Exception as e:
        print(f"⚠ 仓位管理计算失败: {e}")
        if tracker:
            tracker.log_error(
                error_summary="仓位管理建议计算失败",
                error_message=str(e),
                context="调用 PositionManager.get_market_allocation()",
                tool_name="PositionManager",
                priority="medium",
                fix_suggestion="检查 PositionManager 模块和数据源"
            )

    # ── Step 5: 终端报告 ──────────────────────────────────────────────────────
    terminal.print_report(
        val_results, kdj_data, risk_free_rate, rf_date, now,
        mkt_result=mkt_result, pos_result=pos_result,
    )

    # ── Step 6: 飞书推送 ──────────────────────────────────────────────────────
    if send_to_feishu:
        print("→ 推送飞书...", end=" ", flush=True)
        try:
            card = feishu.build_card(
                val_results, kdj_data, risk_free_rate, rf_date, now,
                mkt_result=mkt_result, pos_result=pos_result,
                pm_result=pm_result,
            )
            ok = feishu.send(card)
            print("✓ 已发送" if ok else "✗ 发送失败")
            
            # 记录飞书推送结果
            if tracker:
                if ok:
                    tracker.log_learning(
                        summary="股息指数报告飞书推送成功",
                        details=f"股息指数报告已成功推送到飞书机器人，推送时间: {now}",
                        category="best_practice",
                        priority="low"
                    )
                else:
                    tracker.log_error(
                        error_summary="股息指数报告飞书推送失败",
                        error_message="飞书API调用失败",
                        context=f"推送时间: {now}",
                        tool_name="feishu.send",
                        priority="low",
                        fix_suggestion="检查飞书机器人配置和网络连接"
                    )
        except Exception as e:
            print(f"✗ 发送失败: {str(e)[:50]}")
            if tracker:
                tracker.log_error(
                    error_summary="股息指数报告飞书推送异常",
                    error_message=str(e),
                    context=f"推送时间: {now}",
                    tool_name="feishu.send",
                    priority="medium"
                )
    else:
        print("  提示：添加 --feishu 参数可将报告推送到飞书机器人")
    
    # ── 自我改进系统总结 ─────────────────────────────────────────────────────
    if tracker:
        try:
            tracker.print_summary()
        except Exception as e:
            print(f"⚠ 自我改进系统总结时出错: {str(e)[:50]}")


if __name__ == "__main__":
    main()
