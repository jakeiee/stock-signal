"""
终端报告输出（stock_monitor）。

输出格式：
  ══════════════════════════
  📡 股市交易分析监控  |  YYYY-MM-DD HH:MM
  ══════════════════════════

  ▌ 资金面   [░░░┼░░░░░░░] 0.0  N/A
     ↘ 两融回落，杠杆降温  ← 趋势概括

  ▌ 基本面   [░░░┼░░░░░░░] 0.0  N/A
     ↘ 经济放缓 估值偏高  ← 趋势概括

  ▌ 政策面   [░░░┼░░░░░░░] 0.0  N/A

  ▌ 全球市场 [░░░┼░░░░░░░] 0.0  N/A

  ──────────────────────────
  综合信号   [░░░┼░░░░░░░] 0.0  中性
  权重：资金30% 基本面40% 政策10% 全球20%
  ══════════════════════════
"""
from .feishu import _cap_summary, _fun_summary, _glb_summary


def _score_bar(score: float) -> str:
    """将 -2~+2 得分渲染为 11 格字符进度条，中心为 0。"""
    width  = 11
    center = 5
    offset = round(score / 2 * center)
    bar    = list("░" * width)
    bar[center] = "┼"
    if offset > 0:
        for i in range(center + 1, min(center + offset + 1, width)):
            bar[i] = "█"
    elif offset < 0:
        for i in range(max(0, center + offset), center):
            bar[i] = "█"
    return "[" + "".join(bar) + f"] {score:+.1f}"


def _print_capital_sub(capital_data: dict) -> None:
    """
    在资金面区块下方逐行打印各子指标接入状态。
    已接入的指标显示实际数值，待接入的显示占位提示。
    """
    # ① 新开户数
    na = capital_data.get("new_accounts", {})
    if "error" not in na and "new_accounts" in na:
        period  = na.get("period", "?")
        val     = na["new_accounts"]
        mom     = na.get("mom_pct")
        yoy     = na.get("yoy_pct")
        src     = na.get("source", "")
        mom_str = f"  环比 {mom:+.1f}%" if mom is not None else ""
        yoy_str = f"  同比 {yoy:+.1f}%" if yoy is not None else ""
        # 缓存回退时加注提示，让用户知道数据非实时
        src_tag = "  ⚠ 离线缓存" if src == "csv_cache" else ""
        print(f"      ├ 新开户数  [{period}]  {val:,.0f} 万户/月{mom_str}{yoy_str}{src_tag}")
    else:
        print( "      ├ 新开户数  — 待录入")

    # ② 融资融券
    mg = capital_data.get("margin", {})
    if "error" not in mg and mg.get("total_bal") is not None:
        mg_date    = mg.get("date", "?")
        mg_bal     = mg["total_bal"]
        mg_chg     = mg.get("bal_chg")
        mg_chgpct  = mg.get("bal_chg_pct")
        mg_rzmr    = mg.get("rz_mktcap_ratio")   # 融资余额/流通市值（RZYEZB）
        mg_balmr   = mg.get("bal_mktcap_ratio")   # 两融余额/流通市值（自算）
        mg_rz      = mg.get("rz_bal")
        mg_rq      = mg.get("rq_bal")
        mg_rzbuy   = mg.get("rz_buy")
        mg_rqsell  = mg.get("rq_sell")
        mg_mktto   = mg.get("mkt_turnover")
        mg_sh      = mg.get("sh_turnover")
        mg_sz      = mg.get("sz_turnover")
        mg_bj      = mg.get("bj_turnover")
        mg_tratio  = mg.get("turnover_ratio")
        mg_src     = mg.get("source", "")

        chg_str    = f"  {mg_chg:+.2f}亿（{mg_chgpct:+.2f}%）" if mg_chg is not None else ""
        cache_tag  = "  ⚠ 离线缓存" if mg_src == "csv_cache" else ""
        print(f"      ├ 两融余额  [{mg_date}]  {mg_bal:,.2f} 亿元{chg_str}{cache_tag}")

        # 融资/融券余额 & 占比
        rz_str  = f"融资 {mg_rz:,.2f}亿" if mg_rz is not None else ""
        rq_str  = f"融券 {mg_rq:,.2f}亿" if mg_rq is not None else ""
        rzmr_str  = f"  融资/流通市值 {mg_rzmr:.4f}%" if mg_rzmr is not None else ""
        balmr_str = f"  两融/流通市值 {mg_balmr:.4f}%" if mg_balmr is not None else ""
        print(f"      │   {rz_str}  {rq_str}{rzmr_str}{balmr_str}")

        # 全市场成交额（沪+深+京）及两融交易占比
        if mg_mktto is not None:
            sh_str = f"沪 {mg_sh:,.2f}" if mg_sh is not None else ""
            sz_str = f"深 {mg_sz:,.2f}" if mg_sz is not None else ""
            bj_str = f"京 {mg_bj:,.2f}" if mg_bj is not None else ""
            parts  = "  ".join(s for s in [sh_str, sz_str, bj_str] if s)
            # 两融交易 = 融资买入 + 融券卖出
            if mg_rzbuy is not None and mg_rqsell is not None:
                margin_trade = mg_rzbuy + mg_rqsell
                margin_trade_str = f"  两融交易 {margin_trade:,.2f}亿（融资买入 {mg_rzbuy:,.2f}  融券卖出 {mg_rqsell:,.2f}）"
            elif mg_rzbuy is not None:
                margin_trade_str = f"  融资买入 {mg_rzbuy:,.2f}亿"
            else:
                margin_trade_str = ""
            tratio_str = f"  两融交易/成交额 {mg_tratio:.2f}%" if mg_tratio is not None else ""
            print(f"      │   全市场成交 {mg_mktto:,.2f}亿（{parts}）{margin_trade_str}{tratio_str}")

        # 趋势警示
        try:
            from ..data_sources.capital import fetch_margin_history, analyze_margin_trend
            history = fetch_margin_history(n=20)
            trend = analyze_margin_trend(history, window=10)
            if trend.get("warning"):
                print(f"      │   ⚠ 趋势警示：{trend['warning_reason']}")
            else:
                tr_peak = trend.get("tr_ratio_peak")
                tr_now  = trend.get("tr_ratio_latest")
                tr_drop = trend.get("tr_ratio_drop_pct")
                if tr_peak and tr_now is not None:
                    drop_info = f"  较峰值 {tr_peak:.2f}% 回落 {tr_drop:.2f}pp" if tr_drop else ""
                    print(f"      │   两融交易/成交额趋势：当前 {tr_now:.2f}%{drop_info}")
        except Exception:
            pass
    else:
        print( "      ├ 两融余额  — 待录入")

    # ③ 成交额（TODO）
    print( "      ├ 全市场成交额  — 待接入")

    # ④ 北向资金（TODO）
    print( "      └ 北向资金净流入  — 待接入")


def _print_fundamental_sub(fundamental_data: dict) -> None:
    """
    在基本面区块下方逐行打印三个子模块的接入状态。
    已接入的指标显示实际数值，待接入的显示占位提示。
    """
    # ─── 子模块一：经济总量/结构 ──────────────────────────────────────────────
    gdp = fundamental_data.get("gdp", {})
    if "error" not in gdp and gdp.get("gdp_yoy") is not None:
        period   = gdp.get("period", "?")
        gdp_yoy  = gdp["gdp_yoy"]
        p1_yoy   = gdp.get("p1_yoy")
        p2_yoy   = gdp.get("p2_yoy")
        p3_yoy   = gdp.get("p3_yoy")
        p1_pct   = gdp.get("p1_pct")
        p2_pct   = gdp.get("p2_pct")
        p3_pct   = gdp.get("p3_pct")
        p3_delta = gdp.get("p3_pct_yoy_delta")

        print(f"      ├ 经济总量/结构  [{period}]  GDP同比 {gdp_yoy:.1f}%")

        # 三产同比增速
        yoy_parts = []
        if p1_yoy is not None:
            yoy_parts.append(f"一产 {p1_yoy:.1f}%")
        if p2_yoy is not None:
            yoy_parts.append(f"二产 {p2_yoy:.1f}%")
        if p3_yoy is not None:
            yoy_parts.append(f"三产 {p3_yoy:.1f}%")
        if yoy_parts:
            print(f"      │   分产业同比：{'  '.join(yoy_parts)}")

        # 三产结构占比
        pct_parts = []
        if p1_pct is not None:
            pct_parts.append(f"一产 {p1_pct:.1f}%")
        if p2_pct is not None:
            pct_parts.append(f"二产 {p2_pct:.1f}%")
        if p3_pct is not None:
            delta_str = f"（较去年同期 {p3_delta:+.2f}pp）" if p3_delta is not None else ""
            pct_parts.append(f"三产 {p3_pct:.1f}%{delta_str}")
        if pct_parts:
            print(f"      │   结构占比：{'  '.join(pct_parts)}")
    else:
        err = gdp.get("error", "")
        print(f"      ├ 经济总量/结构  — 待接入{('  (' + err + ')') if err else ''}")

    # ─── 人均可支配收入 ───────────────────────────────────────────────────────
    di = fundamental_data.get("disposable_income", {})
    if "error" not in di and di.get("income_yoy") is not None:
        period2   = di.get("period", "?")
        inc_yoy   = di["income_yoy"]
        real_yoy  = di.get("real_yoy")
        real_str  = f"  实际增速 {real_yoy:.1f}%" if real_yoy is not None else ""
        print(f"      │   人均可支配收入  [{period2}]  名义增速 {inc_yoy:.1f}%{real_str}")
    else:
        print("      │   人均可支配收入  — 待录入")

    # ─── 子模块二：宏观供需关系 ───────────────────────────────────────────────
    sd = fundamental_data.get("supply_demand", {})
    if "error" not in sd and any(sd.get(k) is not None for k in ("pmi_mfg", "cpi_yoy", "ppi_yoy")):
        period3 = sd.get("period", "?")
        # 第一行：CPI / PPI / 剪刀差
        price_parts = []
        if sd.get("cpi_yoy") is not None:
            price_parts.append(f"CPI {sd['cpi_yoy']:+.2f}%")
        if sd.get("ppi_yoy") is not None:
            price_parts.append(f"PPI {sd['ppi_yoy']:+.2f}%")
        if sd.get("ppi_cpi_spread") is not None:
            spread_val = sd["ppi_cpi_spread"]
            spread_tag = "↑上游占优" if spread_val > 2 else ("↓下游承压" if spread_val < -2 else "")
            price_parts.append(f"PPI-CPI剪刀差 {spread_val:+.2f}pp{(' ' + spread_tag) if spread_tag else ''}")
        # 第二行：PMI
        pmi_parts = []
        if sd.get("pmi_mfg") is not None:
            pmi_mfg_val = sd["pmi_mfg"]
            pmi_mfg_tag = "扩张" if pmi_mfg_val > 50.5 else ("临界" if pmi_mfg_val >= 49.5 else "收缩")
            pmi_parts.append(f"制造业PMI {pmi_mfg_val:.1f}（{pmi_mfg_tag}）")
        if sd.get("pmi_svc") is not None:
            pmi_svc_val = sd["pmi_svc"]
            pmi_svc_tag = "扩张" if pmi_svc_val > 50.5 else ("临界" if pmi_svc_val >= 49.5 else "收缩")
            pmi_parts.append(f"非制造业PMI {pmi_svc_val:.1f}（{pmi_svc_tag}）")
        print(f"      ├ 宏观供需关系   [{period3}]  {'  '.join(price_parts)}")
        if pmi_parts:
            print(f"      │               {'  '.join(pmi_parts)}")
        # 累计值（辅助参考）
        accum_parts = []
        if sd.get("cpi_accum") is not None:
            accum_parts.append(f"CPI累计 {sd['cpi_accum']:+.2f}%")
        if sd.get("ppi_accum") is not None:
            accum_parts.append(f"PPI累计 {sd['ppi_accum']:+.2f}%")
        if accum_parts:
            print(f"      │               {'  '.join(accum_parts)}")
    else:
        print("      ├ 宏观供需关系   — 待接入（CPI / PPI / PPI-CPI剪刀差 / PMI）")

    # ─── 子模块三：宏观流动性 ─────────────────────────────────────────────────
    liq = fundamental_data.get("liquidity", {})
    if "error" not in liq and any(liq.get(k) is not None for k in ("m2_yoy", "bond_10y")):
        period4 = liq.get("period", "?")
        liq_parts = []
        if liq.get("m2_yoy") is not None:
            m2_v = liq["m2_yoy"]
            m2_tag = "宽松" if m2_v >= 10 else ("正常" if m2_v >= 7 else "偏紧")
            liq_parts.append(f"M2同比 {m2_v:.1f}%（{m2_tag}）")
        if liq.get("m1_yoy") is not None:
            liq_parts.append(f"M1同比 {liq['m1_yoy']:.1f}%")
        if liq.get("bond_10y") is not None:
            b10y = liq["bond_10y"]
            b_tag = "低利率" if b10y < 2.0 else ("正常" if b10y <= 3.0 else "高利率")
            code_str = f"（{liq.get('bond_10y_code', '')}）" if liq.get("bond_10y_code") else ""
            liq_parts.append(f"10年国债 {b10y:.2f}%{code_str}（{b_tag}）")
        # 社融
        if liq.get("social_fin_yoy") is not None:
            liq_parts.append(f"社融存量 {liq['social_fin_yoy']:.1f}%")
        print(f"      └ 宏观流动性     [{period4}]  {'  '.join(liq_parts)}")
        if liq.get("social_fin_yoy") is None:
            print("                         社融存量同比  — 待接入（接口未公开）")
    else:
        print("      └ 宏观流动性     — 待接入（M2 / 社融 / 国债利率 / LPR）")


def _print_valuation_sub(valuation_data: dict) -> None:
    """
    在估值区块下方打印 PE/PB/股息率详情。
    数据来源：万得全A(除金融、石油石化)
    """
    if not valuation_data or "error" in valuation_data:
        print("      万得全A估值  — 待接入")
        return
    
    date = valuation_data.get("date", "?")
    pe = valuation_data.get("pe")
    pe_pct = valuation_data.get("pe_pct")
    pb = valuation_data.get("pb")
    pb_pct = valuation_data.get("pb_pct")
    div_yield = valuation_data.get("div_yield")
    div_pct = valuation_data.get("div_pct")
    
    # PE
    if pe is not None:
        pe_str = f"PE {pe:.1f}"
        if pe_pct is not None:
            pe_tag = "极低" if pe_pct < 10 else ("低估" if pe_pct < 20 else ("高估" if pe_pct > 80 else ("极高" if pe_pct > 90 else "")))
            pe_str += f" 第{pe_pct:.0f}%{pe_tag}"
    else:
        pe_str = "PE —"
    
    # PB
    if pb is not None:
        pb_str = f"PB {pb:.2f}"
        if pb_pct is not None:
            pb_tag = "低" if pb_pct < 20 else ("高" if pb_pct > 80 else "")
            pb_str += f" 第{pb_pct:.0f}%{pb_tag}"
    else:
        pb_str = "PB —"
    
    # 股息率
    if div_yield is not None:
        div_str = f"股息 {div_yield:.2f}%"
        if div_pct is not None:
            div_tag = "高" if div_pct > 80 else ("低" if div_pct < 20 else "")
            div_str += f" 第{div_pct:.0f}%{div_tag}"
    else:
        div_str = "股息 —"
    
    print(f"      万得全A(除金消/石化)  [{date}]")
    print(f"      └ {pe_str}  |  {pb_str}  |  {div_str}")


def _print_policy_sub(policy_data: dict) -> None:
    """
    打印政策面数据，重点显示货币政策。
    """
    # 货币政策数据
    monetary = policy_data.get("monetary", {})
    
    if monetary and "error" not in monetary:
        signal = monetary.get("signal", "🟡 货币中性")
        rules = monetary.get("signal_rules", [])
        
        print(f"      {signal}")
        # MLF利率（无数据时不展示）
        mlf = monetary.get('mlf_1y')
        if mlf:
            print(f"      ├ MLF利率 {mlf}%")
        # 存款准备金率
        rrr = monetary.get('rrr_large')
        if rrr:
            print(f"      ├ 存款准备金率 {rrr}%")
        # 10年国债收益率
        bond = monetary.get('bond_10y')
        if bond:
            print(f"      ├ 10年国债收益率 {bond}%")
        print(f"      └ LPR(1年/{monetary.get('lpr_1y', 'N/A')}%) LPR(5年/{monetary.get('lpr_5y', 'N/A')}%)")
        
        # 政策动态
        policy_change = monetary.get("policy_change", "")
        if policy_change and "无" not in policy_change:
            print(f"      {policy_change[:50]}...")
    else:
        print(f"      货币政策数据获取中...")


def _print_global_sub(global_data: dict) -> None:
    """
    在全球市场区块下方逐行打印四个子模块的接入状态。
    已接入的指标显示实际数值，待接入的显示占位提示。
    """
    # ─── 子模块一：美股市场 ──────────────────────────────────────────────────
    us = global_data.get("us", {})
    if "error" not in us and any(
        (us.get(sym) or {}).get("price") is not None for sym in ("DJIA", "SPX", "NDX")
    ):
        us_date = us.get("date", "?")
        parts_us = []
        for sym, label in (("DJIA", "道指"), ("SPX", "标普"), ("NDX", "纳指100")):
            info = us.get(sym) or {}
            price  = info.get("price")
            chg5d  = info.get("chg5d_pct")
            if price is not None:
                chg_str = f"（5日 {chg5d:+.2f}%）" if chg5d is not None else ""
                parts_us.append(f"{label} {price:,.2f}{chg_str}")
        print(f"      ├ 美股        [{us_date}]  {'  '.join(parts_us)}")
        above_ma = us.get("spx_above_ma200")
        if above_ma is not None:
            ma_tag = "200日均线上方（趋势多头）" if above_ma else "200日均线下方（趋势空头）"
            print(f"      │   标普500 {ma_tag}")
    else:
        err = (us.get("error") or "") if isinstance(us, dict) else ""
        print(f"      ├ 美股        — 待接入{('  (' + err + ')') if err else ''}")

    # ─── 子模块二：大宗商品 ──────────────────────────────────────────────────
    commod = global_data.get("commodities", {})
    if "error" not in commod and any(
        (commod.get(sym) or {}).get("price") is not None for sym in ("GOLD", "WTI", "BRENT")
    ):
        cm_date = commod.get("date", "?")
        parts_cm = []
        for sym, label in (("GOLD", "黄金"), ("WTI", "WTI原油"), ("BRENT", "布伦特")):
            info  = commod.get(sym) or {}
            price = info.get("price")
            chg5d = info.get("chg5d_pct")
            unit  = info.get("unit", "")
            if price is not None:
                chg_str = f"（5日 {chg5d:+.2f}%）" if chg5d is not None else ""
                parts_cm.append(f"{label} {price:,.1f}{chg_str}")
        print(f"      ├ 大宗商品    [{cm_date}]  {'  '.join(parts_cm)}")
    else:
        print("      ├ 大宗商品    — 待接入（黄金 / 原油）")

    # ─── 子模块三：外汇市场 ──────────────────────────────────────────────────
    forex = global_data.get("forex", {})
    if "error" not in forex and any(
        (forex.get(sym) or {}).get("price") is not None for sym in ("DXY", "USDCNY")
    ):
        fx_date = forex.get("date", "?")
        parts_fx = []
        for sym, label in (("DXY", "美元指数"), ("USDCNY", "美元/人民币")):
            info  = forex.get(sym) or {}
            price = info.get("price")
            chg5d = info.get("chg5d_pct")
            if price is not None:
                chg_str = f"（5日 {chg5d:+.2f}%）" if chg5d is not None else ""
                parts_fx.append(f"{label} {price:.2f}{chg_str}")
        print(f"      ├ 外汇        [{fx_date}]  {'  '.join(parts_fx)}")
    else:
        print("      ├ 外汇        — 待接入（美元指数 / 美元兑人民币）")

    # ─── 子模块四：亚太市场 ──────────────────────────────────────────────────
    asia = global_data.get("asia", {})
    if "error" not in asia and any(
        (asia.get(sym) or {}).get("price") is not None for sym in ("HSI", "N225")
    ):
        as_date = asia.get("date", "?")
        parts_as = []
        for sym, label in (("HSI", "恒生"), ("N225", "日经225")):
            info  = asia.get(sym) or {}
            price = info.get("price")
            chg5d = info.get("chg5d_pct")
            if price is not None:
                chg_str = f"（5日 {chg5d:+.2f}%）" if chg5d is not None else ""
                parts_as.append(f"{label} {price:,.2f}{chg_str}")
        print(f"      └ 亚太        [{as_date}]  {'  '.join(parts_as)}")
        print("                         VIX恐慌指数  — 待接入（CBOE接口未公开）")
    else:
        print("      └ 亚太        — 待接入（恒生指数 / 日经225）")


def print_report(report_data: dict) -> None:
    """
    将 signal.build_report() 生成的报告字典打印到终端。

    Args:
        report_data: signal.build_report() 返回的完整报告字典。
    """
    W   = 68
    now = report_data.get("generated_at", "?")

    print(f"\n{'═' * W}")
    print(f"  📡 股市交易分析监控  |  {now}")
    print(f"{'═' * W}")

    # ── 四维度区块 ────────────────────────────────────────────────────────────
    # 估值已合并到基本面维度中显示
    dimensions = [
        ("capital",      "资金面  "),
        ("fundamental",  "基本面  "),
        ("policy",       "政策面  "),
        ("global",       "全球市场"),
    ]

    for key, display_name in dimensions:
        dim = report_data.get(key, {})
        score  = dim.get("score",  0.0)
        label  = dim.get("label",  "N/A")
        # 趋势概括
        if key == "capital":
            summary = _cap_summary(dim)
        elif key == "fundamental":
            summary = _fun_summary(dim)
        elif key == "global":
            summary = _glb_summary(dim)
        else:
            summary = "数据获取中"
        print(f"\n  ▌ {display_name}  {_score_bar(score)}  {label}")
        if summary and summary != "数据获取中":
            print(f"      {summary}")
        # 资金面：展示各子指标接入状态
        if key == "capital":
            raw = dim.get("data", {})
            _print_capital_sub(raw)
        # 基本面：展示三模块接入状态 + 估值
        elif key == "fundamental":
            raw = dim.get("data", {})
            _print_fundamental_sub(raw)
            # 估值详情
            val_data = raw.get("valuation", {})
            if val_data and "error" not in val_data:
                _print_valuation_sub(val_data)
        # 全球市场：展示四子模块接入状态
        elif key == "global":
            raw = dim.get("data", {})
            _print_global_sub(raw)
        # 政策面：展示货币政策数据
        elif key == "policy":
            raw = dim.get("data", {})
            _print_policy_sub(raw)

    # ── 综合信号 ──────────────────────────────────────────────────────────────
    comp  = report_data.get("composite", {})
    cs    = comp.get("score", 0.0)
    cl    = comp.get("label", "中性")

    print(f"\n{'─' * W}")
    print(f"  综合信号  {_score_bar(cs)}  {cl}")
    print(f"  ─ 权重：资金面30%  基本面40%  政策面10%  全球市场20%")
    print(f"  ─ 本报告仅供参考，不构成投资建议")
    print(f"{'═' * W}\n")
