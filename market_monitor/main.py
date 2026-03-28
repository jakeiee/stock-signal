"""
股市交易分析监控 —— 主入口。

执行流程：
  Step 1  采集资金面数据（新开户数 / 融资融券 / 成交额 / 北向资金）
  Step 2  采集基本面数据
          ① 经济总量/结构：GDP 同比增速、三产结构（东方财富 RPT_ECONOMY_GDP）
          ② 宏观供需关系：PMI / CPI / PPI / 工业增加值（待接入）
          ③ 宏观流动性：M2 / 社融 / 国债利率 / LPR（待接入）
  Step 3  采集政策面数据（近期重大政策事件）
  Step 4  采集全球市场数据（美股 / VIX / 商品 / 汇率）
  Step 5  聚合信号，生成报告
  Step 6  终端输出
  Step 7  可选：推送飞书

用法：
    python3 -m market_monitor
    python3 -m market_monitor --new-accounts 450
    python3 -m market_monitor --margin "2026-03-13,26517.11,..."
    python3 -m market_monitor --znz "2026-03-23,186349.4,-2.94"

参数说明：
    --new-accounts <万户>
        手动覆盖新开户数，单位万户。
        不传时通过上交所接口自动拉取，本地 CSV 缓存兜底。

    --margin <逗号分隔，顺序固定>
        手动录入两融数据（逗号分隔，顺序固定）：
          date             - 日期 YYYY-MM-DD
          total_bal        - 两融余额（亿元）
          bal_chg          - 两融余额日变动（亿元）
          bal_chg_pct      - 两融余额日变动幅度（%）
          rz_mktcap_ratio  - 融资余额/流通市值（%）
          bal_mktcap_ratio - 两融余额/流通市值（%）
          rz_bal           - 融资余额（亿元）
          rq_bal           - 融券余额（亿元）
          rz_buy           - 融资买入额（亿元）
          rq_sell          - 融券卖出额（亿元）
          rz_repay         - 融资偿还额（亿元）
          rz_net           - 融资净买入额（亿元）
          mkt_turnover     - 全市场成交额（亿元，沪+深+京）
          sh_turnover      - 沪市成交额（亿元）
          sz_turnover      - 深市成交额（亿元）
          bj_turnover      - 京市（北交所）成交额（亿元）
          turnover_ratio   - 两融交易/全市场成交额（%，两融交易=融资买入+融券卖出）
        不传时通过东方财富接口自动拉取，本地 CSV 缓存兜底。

    --znz <逗号分隔>
        手动录入指南针活跃市值数据（决定动态仓位 0-40%）：
          date       - 日期 YYYY-MM-DD
          active_cap - 活跃市值（亿元）
          chg_pct    - 日变动幅度（%，可选）
        信号判断：
          单日涨幅 ≥ +4%  → 🟢 增量资金入场信号 → 建议仓位 40%
          单日跌幅 ≤ -2.3% → 🔴 资金离场警示信号 → 建议仓位 0-10%
          其他             → 🟡 观望 → 建议仓位 20%

    --feishu
        推送报告到飞书机器人

    --macro
        生成 HTML 格式的宏观交易分析报告并保存到本地
        文件保存位置：market_monitor/data/macro_report_YYYY-MM-DD.html
"""

import sys
from typing import Optional

from .data_sources import capital, valuation, policy, global_mkt, fundamental as fundamental_mod
from .analysis import signal as signal_mod
from .report import terminal, feishu as feishu_mod, macro_report


def _parse_args() -> dict:
    """解析命令行参数，返回配置字典。"""
    args = sys.argv[1:]
    cfg: dict = {
        "feishu":          False,
        "macro":           False,  # 生成宏观交易分析报告（HTML）
        "new_accounts":    None,   # float|None
        "margin_override": None,   # dict|None
        "znz_override":    None,   # dict|None
    }
    i = 0
    while i < len(args):
        if args[i] == "--feishu":
            cfg["feishu"] = True
        elif args[i] == "--new-accounts" and i + 1 < len(args):
            try:
                cfg["new_accounts"] = float(args[i + 1])
            except ValueError:
                print(f"  ⚠  --new-accounts 参数无效：{args[i+1]}，将自动获取")
            i += 1
        elif args[i] == "--margin" and i + 1 < len(args):
            try:
                parts = [p.strip() for p in args[i + 1].split(",")]
                keys  = [
                    "date", "total_bal", "bal_chg", "bal_chg_pct",
                    "rz_mktcap_ratio", "bal_mktcap_ratio",
                    "rz_bal", "rq_bal", "rz_buy", "rq_sell",
                    "rz_repay", "rz_net",
                    "mkt_turnover", "sh_turnover", "sz_turnover", "bj_turnover",
                    "turnover_ratio",
                ]
                override = {}
                for j, key in enumerate(keys):
                    if j < len(parts) and parts[j] not in ("", "-"):
                        override[key] = parts[j] if key == "date" else float(parts[j])
                cfg["margin_override"] = override
            except Exception as ex:
                print(f"  ⚠  --margin 参数解析失败：{ex}，将自动获取")
            i += 1
        elif args[i] == "--znz" and i + 1 < len(args):
            try:
                parts = [p.strip() for p in args[i + 1].split(",")]
                if len(parts) >= 2:
                    znz_override = {
                        "date": parts[0],
                        "active_cap": float(parts[1]),
                    }
                    if len(parts) >= 3 and parts[2] not in ("", "-"):
                        znz_override["chg_pct"] = float(parts[2])
                    cfg["znz_override"] = znz_override
            except Exception as ex:
                print(f"  ⚠  --znz 参数解析失败：{ex}，将自动获取")
            i += 1
        elif args[i] == "--macro":
            cfg["macro"] = True
        i += 1
    return cfg


def main() -> None:
    cfg = _parse_args()
    send_to_feishu = cfg["feishu"]

    print("\n⏳ 正在采集各维度数据...\n")

    # ── Step 1: 资金面 ────────────────────────────────────────────────────────
    print("  [1/4] 资金面...")

    # ① 指南针活跃市值：判断增量资金最有效指标，决定动态仓位 0-40%
    znz_override = cfg.get("znz_override")
    if znz_override is not None:
        print(f"        指南针活跃市值 ↩ 手动录入 {znz_override['active_cap']:.1f} 亿...", end=" ", flush=True)
        znz_result = capital.save_znz_active_cap(
            date=znz_override["date"],
            active_cap=znz_override["active_cap"],
            chg_pct=znz_override.get("chg_pct"),
        )
        # 重新获取以包含完整计算字段
        znz_result = capital.fetch_znz_active_cap()
    else:
        print("        指南针活跃市值 ⬇ 读取本地数据...", end=" ", flush=True)
        znz_result = capital.fetch_znz_active_cap()

    if "error" not in znz_result:
        znz_date = znz_result["date"]
        znz_cap = znz_result["active_cap"]
        znz_chg = znz_result.get("chg_pct")
        znz_signal = znz_result.get("signal_desc", "")
        znz_pos = znz_result.get("position_suggest", "")
        chg_str = f" {znz_chg:+.2f}%" if znz_chg is not None else ""
        print(f"✓  [{znz_date}] {znz_cap:,.1f}亿{chg_str} → {znz_signal} 建议仓位{znz_pos}")
    else:
        print(f"○ {znz_result['error']}")

    # ② 新开户数：优先命令行覆盖，否则上交所接口自动拉取（本地 CSV 缓存兜底）
    na_override = cfg["new_accounts"]
    if na_override is not None:
        print(f"        新开户数  ↩ 手动覆盖 {na_override:.0f} 万户", end=" ", flush=True)
    else:
        print("        新开户数  ⬇ 自动获取（上交所）...", end=" ", flush=True)

    na_result = capital.fetch_new_accounts(override=na_override)

    if "error" not in na_result:
        period  = na_result["period"]
        val     = na_result["new_accounts"]
        src     = na_result["source"]
        mom     = na_result.get("mom_pct")
        mom_str = f"  环比 {mom:+.1f}%" if mom is not None else ""
        # 友好显示数据来源
        src_label = {
            "sse(上交所)": "上交所",
            "csv_cache":   "本地缓存",
            "manual":      "手动录入",
        }.get(src, src)
        print(f"✓  [{period}] {val:.0f} 万户{mom_str}  来源：{src_label}")
    else:
        print(f"✗  {na_result['error']}")

    capital_data = {
        "znz_active_cap": znz_result,
        "new_accounts": na_result,
        "turnover":     capital.fetch_turnover(),
        "northbound":   capital.fetch_northbound(),
        "margin":       capital.fetch_margin(override=cfg.get("margin_override")),
    }

    # Step 1 补充：两融数据日志
    mg = capital_data["margin"]
    if "error" not in mg:
        mg_src     = {"manual": "手动录入", "eastmoney": "东方财富实时", "csv_cache": "本地缓存"}.get(mg.get("source", ""), mg.get("source", ""))
        mg_bal     = mg.get("total_bal")
        mg_chg     = mg.get("bal_chg")
        mg_rzmr    = mg.get("rz_mktcap_ratio")   # 融资余额/流通市值
        mg_balmr   = mg.get("bal_mktcap_ratio")   # 两融余额/流通市值
        mg_rzbuy   = mg.get("rz_buy")
        mg_rqsell  = mg.get("rq_sell")
        mg_mktto   = mg.get("mkt_turnover")
        mg_tratio  = mg.get("turnover_ratio")
        chg_str    = f"  变动 {mg_chg:+.2f}亿" if mg_chg is not None else ""
        rzmr_str   = f"  融资/流通市值 {mg_rzmr:.2f}%" if mg_rzmr is not None else ""
        balmr_str  = f"  两融/流通市值 {mg_balmr:.2f}%" if mg_balmr is not None else ""
        buy_str    = f"  融资买入 {mg_rzbuy:,.2f}亿" if mg_rzbuy is not None else ""
        sell_str   = f"  融券卖出 {mg_rqsell:,.2f}亿" if mg_rqsell is not None else ""
        mkt_str    = f"  全市场成交 {mg_mktto:,.2f}亿" if mg_mktto is not None else ""
        tr_str     = f"  两融交易/成交额 {mg_tratio:.2f}%" if mg_tratio is not None else ""
        print(f"        两融余额  ⬇ [{mg.get('date','?')}] {mg_bal:,.2f}亿{chg_str}{rzmr_str}{balmr_str}{buy_str}{sell_str}{mkt_str}{tr_str}  来源：{mg_src}")
    else:
        print(f"        两融余额  ✗  {mg['error']}")

    # ── Step 2: 基本面 ────────────────────────────────────────────────────────
    print("  [2/4] 基本面...")

    # ① 经济总量/结构：GDP
    print("        GDP增速/结构  ⬇ 自动获取（东方财富）...", end=" ", flush=True)
    gdp_result = fundamental_mod.fetch_gdp()
    if "error" not in gdp_result:
        period  = gdp_result.get("period", "?")
        yoy     = gdp_result.get("gdp_yoy")
        p3_pct  = gdp_result.get("p3_pct")
        p3_delta = gdp_result.get("p3_pct_yoy_delta")
        yoy_str  = f"同比 {yoy:.1f}%" if yoy is not None else "?"
        p3_str   = f"  三产占比 {p3_pct:.1f}%" if p3_pct is not None else ""
        delta_str = f"（较去年同期 {p3_delta:+.2f}pp）" if p3_delta is not None else ""
        print(f"✓  [{period}] {yoy_str}{p3_str}{delta_str}")
    else:
        print(f"✗  {gdp_result['error']}")

    # ② 人均可支配收入
    print("        人均收入增速  ⬇ 自动获取（国家统计局）...", end=" ", flush=True)
    di_result = fundamental_mod.fetch_disposable_income()
    if "error" not in di_result:
        period_di = di_result.get("period", "?")
        di_yoy = di_result.get("income_yoy")
        di_src = di_result.get("source", "")
        src_label_di = "本地缓存" if di_src == "csv_cache" else "国家统计局"
        if di_yoy is not None:
            print(f"✓  [{period_di}] 人均收入同比 {di_yoy:+.1f}%  来源：{src_label_di}")
        else:
            print(f"✗  人均收入数据缺失")
    else:
        print(f"✗  {di_result['error']}")

    # ③ 宏观供需关系：CPI / PPI / PMI
    print("        宏观供需关系  ⬇ 自动获取（东方财富 CPI/PPI/PMI）...", end=" ", flush=True)
    sd_result = fundamental_mod.fetch_macro_supply_demand()
    if "error" not in sd_result:
        sd_period = sd_result.get("period", "?")
        cpi_v = sd_result.get("cpi_yoy")
        ppi_v = sd_result.get("ppi_yoy")
        spr_v = sd_result.get("ppi_cpi_spread")
        pmi_v = sd_result.get("pmi_mfg")
        src_sd = sd_result.get("source", "")
        src_label_sd = "本地缓存" if src_sd == "csv_cache" else "东方财富实时"
        parts_sd = []
        if cpi_v is not None:
            parts_sd.append(f"CPI {cpi_v:+.2f}%")
        if ppi_v is not None:
            parts_sd.append(f"PPI {ppi_v:+.2f}%")
        if spr_v is not None:
            parts_sd.append(f"剪刀差 {spr_v:+.2f}pp")
        if pmi_v is not None:
            parts_sd.append(f"制造业PMI {pmi_v:.1f}")
        print(f"✓  [{sd_period}] {'  '.join(parts_sd)}  来源：{src_label_sd}")
    else:
        print(f"✗  {sd_result['error']}")

    # ④ 宏观流动性：M2 / 10年国债收益率（ChinaMoney API）
    print("        宏观流动性    ⬇ 自动获取（M2/社融/10年国债）...", end=" ", flush=True)
    liq_result = fundamental_mod.fetch_macro_liquidity()
    if "error" not in liq_result:
        liq_period = liq_result.get("period", "?")
        m2_v   = liq_result.get("m2_yoy")
        b10y_v = liq_result.get("bond_10y")
        src_liq = liq_result.get("source", "")
        src_label_liq = "本地缓存" if src_liq == "csv_cache" else "ChinaMoney实时"
        liq_parts = []
        if m2_v is not None:
            liq_parts.append(f"M2同比 {m2_v:.1f}%")
        if b10y_v is not None:
            bond_code = liq_result.get("bond_10y_code", "")
            liq_parts.append(f"10年国债YTM {b10y_v:.2f}%（{bond_code}）")
        print(f"✓  [{liq_period}] {'  '.join(liq_parts)}  来源：{src_label_liq}")
    else:
        print(f"✗  {liq_result['error']}")

    # 获取 PMI 官方解读（融合数据）
    print("        PMI官方解读  ⬇ 自动获取（国家统计局）...", end=" ", flush=True)
    from market_monitor.data_sources.pmi_interpretation import fetch_pmi_with_interpretation
    pmi_interp_result = fetch_pmi_with_interpretation()
    if "error" not in pmi_interp_result:
        interp_period = pmi_interp_result.get("period", "?")
        interp_author = pmi_interp_result.get("interpretation", {}).get("author", "")
        print(f"✓  [{interp_period}] 解读人：{interp_author}")
    else:
        print(f"✗  {pmi_interp_result.get('error', '获取失败')}")

    # 获取 CPI/PPI 官方解读（融合数据）
    print("        CPI/PPI解读   ⬇ 自动获取（国家统计局）...", end=" ", flush=True)
    from market_monitor.data_sources.cpi_ppi_interpretation import fetch_cpi_ppi_with_interpretation
    cpi_ppi_interp_result = fetch_cpi_ppi_with_interpretation()
    if "error" not in cpi_ppi_interp_result:
        interp_period = cpi_ppi_interp_result.get("period", "?")
        interp_summary = cpi_ppi_interp_result.get("interpretation", {}).get("summary", "")[:30] if cpi_ppi_interp_result.get("interpretation") else ""
        print(f"✓  [{interp_period}] {interp_summary}...")
    else:
        print(f"✗  {cpi_ppi_interp_result.get('error', '获取失败')}")

    # 获取 GDP 官方解读（季度数据）
    print("        GDP解读      ⬇ 自动获取（国家统计局）...", end=" ", flush=True)
    from market_monitor.data_sources.gdp_interpretation import fetch_gdp_with_interpretation
    gdp_interp_result = fetch_gdp_with_interpretation()
    if "error" not in gdp_interp_result:
        interp_period = gdp_interp_result.get("period", "?")
        interp_summary = gdp_interp_result.get("interpretation", {}).get("summary", "")[:30] if gdp_interp_result.get("interpretation") else ""
        print(f"✓  [{interp_period}] {interp_summary}...")
    else:
        print(f"✗  {gdp_interp_result.get('error', '获取失败')}")

    # 获取人均收入官方解读（季度数据）
    print("        收入解读     ⬇ 自动获取（国家统计局）...", end=" ", flush=True)
    from market_monitor.data_sources.income_interpretation import fetch_income_with_interpretation
    income_interp_result = fetch_income_with_interpretation()
    if "error" not in income_interp_result:
        interp_period = income_interp_result.get("period", "?")
        interp_summary = income_interp_result.get("interpretation", {}).get("summary", "")[:30] if income_interp_result.get("interpretation") else ""
        print(f"✓  [{interp_period}] {interp_summary}...")
    else:
        print(f"✗  {income_interp_result.get('error', '获取失败')}")

    fundamental_data = {
        "gdp":               gdp_result,
        "disposable_income": di_result,
        "supply_demand":     sd_result,
        "liquidity":         liq_result,
        "pmi_interpretation": pmi_interp_result if "error" not in pmi_interp_result else None,
        "cpi_ppi_interpretation": cpi_ppi_interp_result if "error" not in cpi_ppi_interp_result else None,
        "gdp_interpretation": gdp_interp_result if "error" not in gdp_interp_result else None,
        "income_interpretation": income_interp_result if "error" not in income_interp_result else None,
    }

    # ── Step 3: 政策面 ────────────────────────────────────────────────────────
    print("  [3/4] 政策面...", end=" ", flush=True)
    policy_data = policy.fetch_policy_events()
    print("完成（占位）")

    # ── Step 4: 全球市场 ──────────────────────────────────────────────────────
    print("  [4/4] 全球市场...")

    # ① 美股行情（道指/标普/纳指）
    print("        美股指数     ⬇ 自动获取（东方财富 DJIA/SPX/NDX K线）...", end=" ", flush=True)
    us_result = global_mkt.fetch_us_market()
    if "error" not in us_result:
        us_parts = []
        for sym, lbl in (("DJIA", "道指"), ("SPX", "标普"), ("NDX", "纳指")):
            info = us_result.get(sym) or {}
            price = info.get("price")
            chg5d = info.get("chg5d_pct")
            if price is not None:
                c = f" 5日{chg5d:+.2f}%" if chg5d is not None else ""
                us_parts.append(f"{lbl} {price:,.2f}{c}")
        print(f"✓  [{us_result.get('date','?')}] {'  '.join(us_parts)}")
    else:
        print(f"✗  {us_result['error']}")

    # ①-1 美国科技七巨头估值（MAGS.WI）
    print("        七巨头估值   ⬇ 自动获取（Wind MAGS.WI）...", end=" ", flush=True)
    mags_val_result = global_mkt.fetch_mags_valuation()
    if "error" not in mags_val_result:
        pe   = mags_val_result.get("pe")
        pe_p = mags_val_result.get("pe_pct")
        print(f"✓  [{mags_val_result.get('date','?')}] MAGS PE {pe:.1f} 第{pe_p:.0f}%")
    else:
        print(f"✗  {mags_val_result['error']}")

    # ② 大宗商品（黄金/原油）
    print("        大宗商品     ⬇ 自动获取（东方财富 黄金/WTI/布伦特 K线）...", end=" ", flush=True)
    commod_result = global_mkt.fetch_commodities()
    if "error" not in commod_result:
        cm_parts = []
        for sym, lbl, unit in (("GOLD","黄金","USD/oz"),("WTI","WTI","USD/bbl"),("BRENT","布伦特","USD/bbl")):
            info = commod_result.get(sym) or {}
            price = info.get("price")
            chg5d = info.get("chg5d_pct")
            if price is not None:
                c = f" 5日{chg5d:+.2f}%" if chg5d is not None else ""
                cm_parts.append(f"{lbl} {price:,.1f}{c}")
        print(f"✓  [{commod_result.get('date','?')}] {'  '.join(cm_parts)}")
    else:
        print(f"✗  {commod_result['error']}")

    # ③ 外汇（美元指数/美元兑人民币）
    print("        外汇行情     ⬇ 自动获取（东方财富 DXY/USDCNY K线）...", end=" ", flush=True)
    forex_result = global_mkt.fetch_forex()
    if "error" not in forex_result:
        fx_parts = []
        for sym, lbl in (("DXY","美元指数"),("USDCNY","美元/人民币")):
            info = forex_result.get(sym) or {}
            price = info.get("price")
            chg5d = info.get("chg5d_pct")
            if price is not None:
                c = f" 5日{chg5d:+.2f}%" if chg5d is not None else ""
                fx_parts.append(f"{lbl} {price:.4f}{c}")
        print(f"✓  [{forex_result.get('date','?')}] {'  '.join(fx_parts)}")
    else:
        print(f"✗  {forex_result['error']}")

    # ④ 亚太市场（港股/日经/韩国）
    print("        亚太市场     ⬇ 自动获取（东方财富 HSI/HSTECH/N225/KOSPI K线）...", end=" ", flush=True)
    asia_result = global_mkt.fetch_asia_market()
    if "error" not in asia_result:
        as_parts = []
        for sym, lbl in (("HSI","恒生"),("HSTECH","恒生科技"),("N225","日经"),("KOSPI","韩综")):
            info = asia_result.get(sym) or {}
            price = info.get("price")
            chg5d = info.get("chg5d_pct")
            if price is not None:
                c = f" 5日{chg5d:+.2f}%" if chg5d is not None else ""
                as_parts.append(f"{lbl} {price:,.2f}{c}")
        print(f"✓  [{asia_result.get('date','?')}] {'  '.join(as_parts)}")
    else:
        print(f"✗  {asia_result['error']}")

    # ④-1 港股中国科技龙头估值（TECHK.WI）
    print("        港科技估值   ⬇ 自动获取（Wind TECHK.WI）...", end=" ", flush=True)
    techk_val_result = global_mkt.fetch_techk_valuation()
    if "error" not in techk_val_result:
        pe_t  = techk_val_result.get("pe")
        pe_tp = techk_val_result.get("pe_pct")
        print(f"✓  [{techk_val_result.get('date','?')}] TECHK PE {pe_t:.1f} 第{pe_tp:.0f}%")
    else:
        print(f"✗  {techk_val_result['error']}")

    global_data = {
        "us":           us_result,
        "mags_val":     mags_val_result,    # 七巨头估值（替代旧的us_valuation）
        "commodities":  commod_result,
        "forex":        forex_result,
        "asia":         asia_result,
        "techk_val":    techk_val_result,   # 港股科技龙头估值
    }

    # ── Step 5: 聚合信号 ──────────────────────────────────────────────────────
    valuation_data = valuation.fetch_market_valuation()
    report_data = signal_mod.build_report(
        capital_data      = capital_data,
        fundamental_data  = fundamental_data,
        valuation_data    = valuation_data,
        policy_data       = policy_data,
        global_data       = global_data,
    )

    # ── Step 6: 终端输出 ──────────────────────────────────────────────────────
    terminal.print_report(report_data)

    # ── Step 7: 飞书推送 ──────────────────────────────────────────────────────
    if send_to_feishu:
        print("→ 推送飞书(多卡片)...", end=" ", flush=True)
        cards = feishu_mod.build_cards(report_data)
        ok = feishu_mod.send_cards(cards)
        print("✓ 已发送" if ok else "✗ 发送失败")
    else:
        print("  提示：添加 --feishu 参数可将报告推送到飞书机器人")

    # ── Step 8: 生成宏观交易分析报告 ───────────────────────────────────────────
    if cfg.get("macro"):
        print("\n→ 生成宏观交易分析报告（HTML）...", end=" ", flush=True)
        html_path = macro_report.generate_and_save(
            capital_data=capital_data,
            fundamental_data=fundamental_data,
            valuation_data=valuation_data,
            policy_data=policy_data,
            global_data=global_data,
        )
        print(f"✓ 已保存至 {html_path}")


if __name__ == "__main__":
    main()
