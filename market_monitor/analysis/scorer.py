"""
各维度信号评分模块。

每个 score_* 函数将原始数据字典转换为标准评分元组：
    (score: float, label: str, detail: str)

score 范围：-2（强空头信号）到 +2（强多头信号）

当前实现状态：
    score_capital()    资金面评分   ——已实现：A股月度新开户数、融资融券（含趋势警示）
    score_valuation()  基本面评分   ——待实现（占位返回中性）
    score_policy()     政策面评分   ——待实现（占位返回中性）
    score_global()     全球市场评分 ——待实现（占位返回中性）
"""

from typing import Optional


# ── 新开户数评分阈值（单位：万户/月）──────────────────────────────────────────
_NA_HOT2  = 600   # ≥ 600 → 顶部/极热 → 强空头
_NA_HOT1  = 400   # 400–599 → 偏热
_NA_NORM  = 200   # 200–399 → 正常
_NA_COLD1 = 100   # 100–199 → 偏冷
# < 100   → 极冷 → 强多头

# ── 融资融券评分阈值（bal_mktcap_ratio：两融余额/A股流通市值，单位：%）──────────
# 历史参考：A股两融余额/流通市值 2015年顶部约4%，底部约1.3%，常态2%~2.5%
_MG_HOT2  = 3.5   # ≥ 3.5% → 极热 → 强空头
_MG_HOT1  = 3.0   # 3.0–3.5% → 偏热
_MG_NORM  = 2.0   # 2.0–3.0% → 正常
_MG_COLD1 = 1.5   # 1.5–2.0% → 偏冷
# < 1.5%  → 极冷 → 强多头

# ── 趋势警示参数 ─────────────────────────────────────────────────────────────
# 余额占比超过此阈值时启用交易额占比趋势监控
_MG_TREND_BAL_THRESHOLD = 3.0   # %
# 交易额占比从峰值下降超过此比例视为"快速下降"
_MG_TREND_DROP_RATIO    = 0.15  # 15%
# 触发趋势警示时的额外惩罚分
_MG_TREND_PENALTY       = -0.5


def _score_new_accounts(na: float) -> tuple:
    """
    根据月度新开户数（万户）计算子评分。

    阈值（用户定义）：
        ≥ 600 万户 → 极热 -2（顶部区间，历史高位，散户蜂拥入场）
        400–599   → 偏热 -1
        200–399   → 正常  0
        100–199   → 偏冷 +1
        <  100    → 极冷 +2（散户极度悲观，历史底部区域）
    """
    if na >= _NA_HOT2:
        return -2.0, "极热", f"新开户 {na:.0f} 万户（≥{_NA_HOT2}万，顶部区间）"
    if na >= _NA_HOT1:
        return -1.0, "偏热", f"新开户 {na:.0f} 万户（{_NA_HOT1}–{_NA_HOT2-1}万，偏热）"
    if na >= _NA_NORM:
        return  0.0, "正常", f"新开户 {na:.0f} 万户（{_NA_NORM}–{_NA_HOT1-1}万，正常）"
    if na >= _NA_COLD1:
        return +1.0, "偏冷", f"新开户 {na:.0f} 万户（{_NA_COLD1}–{_NA_NORM-1}万，偏冷）"
    return +2.0, "极冷", f"新开户 {na:.0f} 万户（<{_NA_COLD1}万，极度低迷）"


def _score_margin(bal_ratio: float) -> tuple:
    """
    根据两融余额/流通市值比例（%）计算子评分。

    阈值：
        ≥ 3.5% → 极热 -2（杠杆资金极度堆积，历史顶部特征）
        3.0–3.5% → 偏热 -1
        2.0–3.0% → 正常  0
        1.5–2.0% → 偏冷 +1
        <  1.5%  → 极冷 +2（去杠杆深度，历史底部区域）
    """
    if bal_ratio >= _MG_HOT2:
        return -2.0, "极热", f"两融余额占比 {bal_ratio:.2f}%（≥{_MG_HOT2}%，杠杆极度堆积）"
    if bal_ratio >= _MG_HOT1:
        return -1.0, "偏热", f"两融余额占比 {bal_ratio:.2f}%（{_MG_HOT1}–{_MG_HOT2}%，偏热）"
    if bal_ratio >= _MG_NORM:
        return  0.0, "正常", f"两融余额占比 {bal_ratio:.2f}%（{_MG_NORM}–{_MG_HOT1}%，正常）"
    if bal_ratio >= _MG_COLD1:
        return +1.0, "偏冷", f"两融余额占比 {bal_ratio:.2f}%（{_MG_COLD1}–{_MG_NORM}%，偏冷）"
    return +2.0, "极冷", f"两融余额占比 {bal_ratio:.2f}%（<{_MG_COLD1}%，去杠杆深度）"


def score_capital(capital_data: dict) -> tuple:
    """
    资金面评分。

    当前接入指标：
      ① A股月度新开户数（散户资金情绪）—— 权重 60%
      ② 融资融券（杠杆资金热度）         —— 权重 40%
      仅有一项时临时权重100%，两项均无则返回 N/A。

    趋势警示（叠加惩罚）：
      当两融余额/流通市值 >= 3.0% 且融资买入额/成交额从近期峰值快速下降（>15%），
      在加权得分基础上额外 -0.5 分并标注警示信息。
      逻辑：余额占比高说明杠杆已积累，交易额占比快速回落意味着买盘萎缩、
            往往是市场顶部信号（2015年顶部的典型特征）。

    待接入指标（TODO）：
      - 全市场成交额
      - 北向资金净流入

    Args:
        capital_data: capital.py 各函数返回值的聚合字典，结构：
            {
                "new_accounts": {"period": str, "new_accounts": float, ...} | {"error": str},
                "margin":       {"date": str, "total_bal": float, ...}      | {"error": str},
                "turnover":     {...} | {"error": str},
                "northbound":   {...} | {"error": str},
            }

    Returns:
        (score: float, label: str, detail: str)
    """
    from ..data_sources.capital import fetch_margin_history, analyze_margin_trend

    scores  = []
    details = []

    # ① 新开户数
    na_data = capital_data.get("new_accounts", {})
    if "error" not in na_data and "new_accounts" in na_data:
        na_val  = na_data["new_accounts"]
        period  = na_data.get("period", "?")
        s, _, d = _score_new_accounts(na_val)
        scores.append((s, 0.6))
        details.append(f"[{period}] {d}")

    # ② 融资融券
    mg_data = capital_data.get("margin", {})
    trend_result = {}
    if "error" not in mg_data and mg_data.get("bal_mktcap_ratio") is not None:
        mg_ratio = mg_data["bal_mktcap_ratio"]
        mg_date  = mg_data.get("date", "?")
        s, _, d  = _score_margin(mg_ratio)
        scores.append((s, 0.4))
        details.append(f"[{mg_date}] {d}")

        # 趋势分析：获取近30日历史做趋势判断
        try:
            history = fetch_margin_history(n=30)
            trend_result = analyze_margin_trend(history, window=10)
        except Exception:
            trend_result = {}

    # ③ 印花税/券商佣金率政策
    fund_policy = capital_data.get("fund_policy", {})
    fund_score = 0.0
    fund_detail = ""
    if fund_policy.get("available"):
        fund_score = fund_policy.get("score", 0.0)
        fund_detail = f"印花税/佣金 {fund_policy.get('label','N/A')}"

    if not scores and fund_score == 0.0:
        return 0.0, "N/A", "资金面数据待接入"

    # 调整权重：新增开户数50% + 两融35% + 政策15%
    total_base_w = sum(w for _, w in scores)
    if fund_score != 0.0 and total_base_w > 0:
        # 三项都有
        weights = [(s, w * 0.5) for s, w in scores]  # 新开户和两融各占 50%*权重比例
        weights.append((fund_score, 0.15))  # 政策占 15%
        # 调整基础权重总和为 85%
        scores.extend([(fund_score, 0.15)])
        total_w = sum(w for _, w in scores)
    elif fund_score != 0.0:
        scores.append((fund_score, 1.0))
        total_w = 1.0
    else:
        total_w = total_base_w if total_base_w > 0 else 1.0

    # 加权平均
    final = sum(s * w for s, w in scores) / total_w if total_w > 0 else 0.0

    # 趋势警示惩罚
    warning_note = ""
    if trend_result.get("warning"):
        final = max(final + _MG_TREND_PENALTY, -2.0)
        warning_note = f"；⚠ {trend_result['warning_reason']}"

    # 政策消息补充
    policy_note = f"；{fund_detail}" if fund_detail else ""

    label = _score_to_label(final)
    detail_str = "；".join(details) + warning_note + policy_note

    return round(final, 2), label, detail_str


def _score_gdp(gdp_yoy: float, p3_pct_delta: Optional[float] = None) -> tuple:
    """
    根据 GDP 累计同比增速（%）和第三产业占比变化计算基础评分。

    阈值：
        ≥ 5.5% → 强劲 +2
        5.0–5.5% → 良好 +1
        4.0–5.0% → 正常  0
        3.0–4.0% → 偏弱 -1
        < 3.0%  → 偏差 -2

    第三产业占比同比变化附加分（±0.5）：
        ≥ +0.5pp → 消费/服务结构改善 +0.5
        ≤ -0.5pp → 内需结构偏弱     -0.5
    """
    if gdp_yoy >= 5.5:
        s, lbl = +2.0, "强劲"
    elif gdp_yoy >= 5.0:
        s, lbl = +1.0, "良好"
    elif gdp_yoy >= 4.0:
        s, lbl =  0.0, "正常"
    elif gdp_yoy >= 3.0:
        s, lbl = -1.0, "偏弱"
    else:
        s, lbl = -2.0, "偏差"

    d = f"GDP同比 {gdp_yoy:.1f}%（{lbl}）"

    if p3_pct_delta is not None:
        if p3_pct_delta >= 0.5:
            s   = min(s + 0.5, +2.0)
            d  += f"；第三产业占比较去年同期 +{p3_pct_delta:.2f}pp（消费/服务结构改善）"
        elif p3_pct_delta <= -0.5:
            s   = max(s - 0.5, -2.0)
            d  += f"；第三产业占比较去年同期 {p3_pct_delta:.2f}pp（内需结构偏弱）"

    return s, lbl, d


def _score_supply_demand(sd: dict) -> tuple:
    """
    宏观供需关系评分（CPI / PPI / PMI 综合）。

    评分细则：
      PPI 同比（权重 35%）:
          > 0%    → +1（上游企业盈利改善）
          -2~0%   →  0（轻微通缩，偏弱）
          < -2%   → -1（明显通缩，上游利润压力）

      CPI 同比（权重 35%）:
          0–3%   → +0.5（温和通胀，消费企业定价能力增强）
          > 3%   → -0.5（通胀压力，企业成本上升）
          -0.5~0 →  0  （轻微通缩临界）
          < -0.5 → -1  （通缩，消费需求偏弱）

      PPI-CPI 剪刀差（附加分，±0.5）:
          > +2pp  → 上游盈利优于下游  附加 +0.5
          < -2pp  → 下游企业利润承压  附加 -0.5

      制造业 PMI（权重 30%）:
          > 50.5 → +1（景气扩张）
          49.5–50.5 → 0（荣枯线临界）
          < 49.5 → -1（收缩区间）
    """
    scores  = []
    details = []

    ppi_yoy   = sd.get("ppi_yoy")
    cpi_yoy   = sd.get("cpi_yoy")
    spread    = sd.get("ppi_cpi_spread")
    pmi_mfg   = sd.get("pmi_mfg")

    # PPI
    if ppi_yoy is not None:
        if ppi_yoy > 0:
            s_ppi, lbl_ppi = +1.0, "通胀改善"
        elif ppi_yoy >= -2.0:
            s_ppi, lbl_ppi =  0.0, "轻微通缩"
        else:
            s_ppi, lbl_ppi = -1.0, "明显通缩"
        scores.append((s_ppi, 0.35))
        details.append(f"PPI {ppi_yoy:+.1f}%（{lbl_ppi}）")

    # CPI
    if cpi_yoy is not None:
        if 0 <= cpi_yoy <= 3.0:
            s_cpi, lbl_cpi = +0.5, "温和通胀"
        elif cpi_yoy > 3.0:
            s_cpi, lbl_cpi = -0.5, "通胀压力"
        elif cpi_yoy >= -0.5:
            s_cpi, lbl_cpi =  0.0, "通缩临界"
        else:
            s_cpi, lbl_cpi = -1.0, "通缩偏弱"
        scores.append((s_cpi, 0.35))
        details.append(f"CPI {cpi_yoy:+.1f}%（{lbl_cpi}）")

    # PPI-CPI 剪刀差附加分
    if spread is not None:
        if spread > 2.0:
            extra_spread = +0.5
            details.append(f"PPI-CPI剪刀差 {spread:+.1f}pp（上游盈利优于下游）")
        elif spread < -2.0:
            extra_spread = -0.5
            details.append(f"PPI-CPI剪刀差 {spread:+.1f}pp（下游利润承压）")
        else:
            extra_spread = 0.0
            details.append(f"PPI-CPI剪刀差 {spread:+.1f}pp")
        # 附加分不计入权重，直接叠加到最终分
    else:
        extra_spread = 0.0

    # PMI 制造业
    if pmi_mfg is not None:
        if pmi_mfg > 50.5:
            s_pmi, lbl_pmi = +1.0, "扩张"
        elif pmi_mfg >= 49.5:
            s_pmi, lbl_pmi =  0.0, "临界"
        else:
            s_pmi, lbl_pmi = -1.0, "收缩"
        scores.append((s_pmi, 0.30))
        details.append(f"制造业PMI {pmi_mfg:.1f}（{lbl_pmi}）")

    if not scores:
        return 0.0, "N/A", "供需数据缺失"

    total_w = sum(w for _, w in scores)
    base    = sum(s * w for s, w in scores) / total_w
    final   = max(-2.0, min(2.0, base + extra_spread))
    label   = _score_to_label(final)
    return round(final, 2), label, "  ".join(details)


def _score_liquidity(liq: dict) -> tuple:
    """
    宏观流动性评分（M2 / 10年国债收益率 / 社融）。

    评分细则：
      M2 同比（权重 40%）:
          ≥ 10%  → 货币宽松，流动性充裕   +1
          7–10%  → 正常                     0
          < 7%   → 货币偏紧               -1

      10年国债收益率（权重 30%）:
          < 2%   → 低利率，估值溢价增强    +1
          2–3%   → 利率正常                 0
          > 3%   → 高利率，估值承压        -1

      社融同比（权重 30%）:
          ≥ 12%  → 融资旺盛，经济增长动力强 +1
          8–12%  → 正常偏松                 0
          5–8%   → 偏弱，稳增长压力        -1
          < 5%   → 融资低迷                -2
    """
    scores  = []
    details = []

    m2_yoy   = liq.get("m2_yoy")
    bond_10y = liq.get("bond_10y")
    sf_yoy   = liq.get("social_fin_yoy")

    # M2
    if m2_yoy is not None:
        if m2_yoy >= 10.0:
            s_m2, lbl_m2 = +1.0, "宽松"
        elif m2_yoy >= 7.0:
            s_m2, lbl_m2 =  0.0, "正常"
        else:
            s_m2, lbl_m2 = -1.0, "偏紧"
        scores.append((s_m2, 0.40))
        details.append(f"M2同比 {m2_yoy:.1f}%（{lbl_m2}）")

    # 10年国债收益率
    if bond_10y is not None:
        if bond_10y < 2.0:
            s_b, lbl_b = +1.0, "低利率"
        elif bond_10y <= 3.0:
            s_b, lbl_b =  0.0, "利率正常"
        else:
            s_b, lbl_b = -1.0, "高利率"
        scores.append((s_b, 0.30))
        details.append(f"10年国债 {bond_10y:.2f}%（{lbl_b}）")

    # 社融
    if sf_yoy is not None:
        if sf_yoy >= 12.0:
            s_sf, lbl_sf = +1.0, "融资旺盛"
        elif sf_yoy >= 8.0:
            s_sf, lbl_sf =  0.0, "正常"
        elif sf_yoy >= 5.0:
            s_sf, lbl_sf = -1.0, "偏弱"
        else:
            s_sf, lbl_sf = -2.0, "融资低迷"
        scores.append((s_sf, 0.30))
        details.append(f"社融同比 {sf_yoy:.1f}%（{lbl_sf}）")

    if not scores:
        return 0.0, "N/A", "流动性数据缺失"

    total_w = sum(w for _, w in scores)
    final   = sum(s * w for s, w in scores) / total_w
    final   = max(-2.0, min(2.0, final))
    label   = _score_to_label(final)
    return round(final, 2), label, "  ".join(details)


def _score_disposable_income(di: dict) -> tuple:
    """
    居民人均可支配收入增速评分。

    评分细则：
        收入同比增速（使用实际增速或名义增速）：
            ≥ 6%  → 收入强劲增长，消费/可选板块预期改善  +1
            4–6%  → 正常                                    0
            2–4%  → 偏弱，可选消费谨慎                     -1
            < 2%  → 居民收入压力大，消费板块下行风险         -2
    """
    income_yoy = di.get("income_yoy")
    if income_yoy is None:
        return 0.0, "N/A", "人均收入数据缺失"

    if income_yoy >= 6.0:
        s, lbl = +1.0, "收入强劲"
    elif income_yoy >= 4.0:
        s, lbl =  0.0, "收入正常"
    elif income_yoy >= 2.0:
        s, lbl = -1.0, "收入偏弱"
    else:
        s, lbl = -2.0, "收入低迷"

    d = f"人均收入同比 {income_yoy:+.1f}%（{lbl}）"
    return s, lbl, d


def score_fundamental(fundamental_data: dict) -> tuple:
    """
    基本面（宏观经济）综合评分。

    子模块及权重（动态调整：有数据则参与加权，无数据则跳过）：
      ① 经济总量/结构：GDP 同比 + 第三产业占比变化   权重 0.35
          - 附加：人均可支配收入增速                   权重 0.10
      ② 宏观供需关系：CPI / PPI / PMI               权重 0.25
      ③ 宏观流动性：M2 同比 / 10年国债收益率 / 社融  权重 0.30

    Args:
        fundamental_data: main.py 聚合的基本面字典：
            {
                "gdp":              fetch_gdp() 返回值,
                "disposable_income":fetch_disposable_income() 返回值,
                "supply_demand":    fetch_macro_supply_demand() 返回值,
                "liquidity":        fetch_macro_liquidity() 返回值,
            }

    Returns:
        (score: float, label: str, detail: str)
    """
    scores  = []
    details = []

    # ① GDP / 经济结构  权重 0.35
    gdp = fundamental_data.get("gdp", {})
    if "error" not in gdp and gdp.get("gdp_yoy") is not None:
        s, _, d = _score_gdp(gdp["gdp_yoy"], gdp.get("p3_pct_yoy_delta"))
        scores.append((s, 0.35))
        period = gdp.get("period", "?")
        details.append(f"[{period}] {d}")

    # ①-2 居民人均可支配收入  权重 0.10
    di = fundamental_data.get("disposable_income", {})
    if "error" not in di and di.get("income_yoy") is not None:
        s_di, _, d_di = _score_disposable_income(di)
        scores.append((s_di, 0.10))
        period_di = di.get("period", "?")
        details.append(f"[{period_di}] {d_di}")

    # ② 宏观供需关系  权重 0.25
    sd = fundamental_data.get("supply_demand", {})
    if "error" not in sd and any(
        sd.get(k) is not None for k in ("cpi_yoy", "ppi_yoy", "pmi_mfg")
    ):
        s_sd, _, d_sd = _score_supply_demand(sd)
        scores.append((s_sd, 0.25))
        period_sd = sd.get("period", "?")
        details.append(f"[{period_sd}] {d_sd}")

    # ③ 宏观流动性  权重 0.30
    liq = fundamental_data.get("liquidity", {})
    if "error" not in liq and any(
        liq.get(k) is not None for k in ("m2_yoy", "bond_10y", "social_fin_yoy")
    ):
        s_liq, _, d_liq = _score_liquidity(liq)
        scores.append((s_liq, 0.30))
        period_liq = liq.get("period", "?")
        details.append(f"[{period_liq}] {d_liq}")

    if not scores:
        return 0.0, "N/A", "基本面数据待接入（所有接口失败）"

    total_w = sum(w for _, w in scores)
    final   = sum(s * w for s, w in scores) / total_w

    label = _score_to_label(final)
    return round(final, 2), label, "；".join(details)


def score_valuation(valuation_data: dict) -> tuple:
    """
    市场估值评分（万得全A除金融石油石化）。

    评分逻辑：
      - PE百分位 > 80% → 高估 -1分
      - PE百分位 < 20% → 低估 +1分
      - PB百分位 > 80% → 高估 -0.5分
      - PB百分位 < 20% → 低估 +0.5分
      - 股息率百分位 > 80% → 高股息 +0.5分
      - 股息率百分位 < 20% → 低股息 -0.5分

    Args:
        valuation_data: valuation.py fetch_market_valuation() 返回值。

    Returns:
        (score: float, label: str, detail: str)
    """
    if not valuation_data or "error" in valuation_data:
        return 0.0, "N/A", "市场估值数据获取失败"
    
    pe_pct = valuation_data.get("pe_pct")
    pb_pct = valuation_data.get("pb_pct")
    div_pct = valuation_data.get("div_pct")
    pe = valuation_data.get("pe", 0)
    pb = valuation_data.get("pb", 0)
    div_yield = valuation_data.get("div_yield", 0)
    date = valuation_data.get("date", "?")
    
    if pe_pct is None:
        return 0.0, "N/A", "PE百分位数据缺失"
    
    score = 0.0
    details = []
    
    # PE 百分位评分
    if pe_pct > 80:
        score -= 1.0
        details.append(f"PE第{pe_pct:.0f}%(高估)")
    elif pe_pct < 20:
        score += 1.0
        details.append(f"PE第{pe_pct:.0f}%(低估)")
    else:
        details.append(f"PE第{pe_pct:.0f}%")
    
    # PB 百分位评分
    if pb_pct is not None:
        if pb_pct > 80:
            score -= 0.5
            details.append(f"PB第{pb_pct:.0f}%(高估)")
        elif pb_pct < 20:
            score += 0.5
            details.append(f"PB第{pb_pct:.0f}%(低估)")
        else:
            details.append(f"PB第{pb_pct:.0f}%")
    
    # 股息率百分位评分
    if div_pct is not None:
        if div_pct > 80:
            score += 0.5
            details.append(f"股息第{div_pct:.0f}%(高)")
        elif div_pct < 20:
            score -= 0.5
            details.append(f"股息第{div_pct:.0f}%(低)")
        else:
            details.append(f"股息第{div_pct:.0f}%")
    
    # 转换分数到标签
    if score >= 1.0:
        label = "低估"
    elif score >= 0.5:
        label = "偏低"
    elif score >= -0.5:
        label = "正常"
    elif score >= -1.0:
        label = "偏高"
    else:
        label = "高估"
    
    detail_str = f"[{date}] PE{pe:.1f} {details[0]} PB{pb:.2f} 股息{div_yield:.2f}%"
    
    return round(score, 2), label, detail_str


def score_policy(policy_data: dict) -> tuple:
    """
    政策面评分。

    评分维度：
      - 近期货币政策方向（宽松 → 正分，收紧 → 负分）
      - 近期重大监管政策情绪（利好 → 正分，利空 → 负分）

    Args:
        policy_data: policy.py fetch_policy_events() 返回值。

    Returns:
        (score: float, label: str, detail: str)
    """
    # 1. 货币政策评分
    monetary = policy_data.get("monetary", {})
    
    if monetary and "error" not in monetary:
        signal = monetary.get("signal", "🟡 货币中性")
        
        # 解析信号
        if "🟢" in signal and "宽松" in signal:
            score = 0.5
            label = "货币宽松"
        elif "🔴" in signal or "收紧" in signal:
            score = -0.5
            label = "货币收紧"
        else:
            score = 0.0
            label = "货币中性"
        
        # 详情
        mlf = monetary.get("mlf_1y", "N/A")
        bond = monetary.get("bond_10y", "N/A")
        detail = f"MLF {mlf}% 国债 {bond}%"
        
        return score, label, detail
    
    # 默认返回
    return 0.0, "N/A", "政策面数据待接入"


def score_global(global_data: dict) -> tuple:
    """
    全球市场评分。

    评分维度及权重：
      ① 美股趋势（标普500近5日涨跌幅）          权重 50%
            > +3%  → 强势，风险偏好高           +1
            -3%~+3% → 震荡                         0
            < -3%  → 弱势，风险偏好回落          -1
         附加：标普500在200日均线上方            +0.5
               标普500在200日均线下方            -0.5

      ② 亚太市场（恒生+日经近5日均涨跌幅）       权重 30%
            > +2%  → 亚太风险偏好正面             +1
            -2%~+2% → 震荡                          0
            < -2%  → 亚太市场拖累                 -1

      ③ 美元指数（DXY近5日涨跌幅）               权重 20%
            > +1.5% → 美元走强，新兴市场压力      -1
            -1.5%~+1.5% → 稳定                      0
            < -1.5% → 美元走弱，资金回流新兴市场  +1

    附加信号（不计入权重，直接叠加，上限±0.5）：
      - 港股近5日涨幅 > 5% → 外资流入明显         +0.3
      - 港股近5日跌幅 > 5% → 外资撤离              -0.3

    Args:
        global_data: {
            "us":          fetch_us_market() 返回值,
            "commodities": fetch_commodities() 返回值,
            "forex":       fetch_forex() 返回值,
            "asia":        fetch_asia_market() 返回值,
        }

    Returns:
        (score: float, label: str, detail: str)
    """
    scores  = []
    details = []
    extra   = 0.0

    # ① 美股（标普500 近5日）权重 0.50 ─────────────────────────────────────
    us = global_data.get("us", {})
    if "error" not in us:
        spx = us.get("SPX", {})
        ndx = us.get("NDX", {})
        spx_chg5 = spx.get("chg5d_pct")
        spx_price = spx.get("price")
        ndx_chg5 = ndx.get("chg5d_pct")
        above_ma  = us.get("spx_above_ma200")

        if spx_chg5 is not None:
            if spx_chg5 > 3.0:
                s_us, lbl_us = +1.0, "强势"
            elif spx_chg5 >= -3.0:
                s_us, lbl_us =  0.0, "震荡"
            else:
                s_us, lbl_us = -1.0, "弱势"
            scores.append((s_us, 0.50))
            ndx_str = f"  纳斯达克100 5日 {ndx_chg5:+.2f}%" if ndx_chg5 is not None else ""
            details.append(f"标普500 5日 {spx_chg5:+.2f}%（{lbl_us}）{ndx_str}")

            # MA200 附加
            if above_ma is True:
                extra += 0.3
                details.append("标普在200日均线上方（趋势多头）")
            elif above_ma is False:
                extra -= 0.3
                details.append("标普在200日均线下方（趋势空头）")

    # ② 亚太（恒生+日经均值）权重 0.30 ─────────────────────────────────────
    asia = global_data.get("asia", {})
    if "error" not in asia:
        hsi_chg5  = (asia.get("HSI") or {}).get("chg5d_pct")
        n225_chg5 = (asia.get("N225") or {}).get("chg5d_pct")

        asia_chgs = [v for v in (hsi_chg5, n225_chg5) if v is not None]
        if asia_chgs:
            avg_asia = sum(asia_chgs) / len(asia_chgs)
            if avg_asia > 2.0:
                s_asia, lbl_asia = +1.0, "偏多"
            elif avg_asia >= -2.0:
                s_asia, lbl_asia =  0.0, "震荡"
            else:
                s_asia, lbl_asia = -1.0, "偏弱"
            scores.append((s_asia, 0.30))
            parts_asia = []
            if hsi_chg5 is not None:
                parts_asia.append(f"恒生 5日 {hsi_chg5:+.2f}%")
            if n225_chg5 is not None:
                parts_asia.append(f"日经 5日 {n225_chg5:+.2f}%")
            details.append("  ".join(parts_asia) + f"（亚太{lbl_asia}）")

            # 港股特别附加（强势/弱势信号）
            if hsi_chg5 is not None:
                if hsi_chg5 > 5.0:
                    extra = min(extra + 0.3, 0.5)
                    details.append(f"港股强势（5日 {hsi_chg5:+.2f}%，外资流入信号）")
                elif hsi_chg5 < -5.0:
                    extra = max(extra - 0.3, -0.5)
                    details.append(f"港股弱势（5日 {hsi_chg5:+.2f}%，外资撤离信号）")

    # ③ 美元指数（DXY 近5日）权重 0.20 ──────────────────────────────────────
    forex = global_data.get("forex", {})
    if "error" not in forex:
        dxy       = forex.get("DXY", {}) or {}
        usdcny    = forex.get("USDCNY", {}) or {}
        dxy_chg5  = dxy.get("chg5d_pct")
        cny_chg5  = usdcny.get("chg5d_pct")

        if dxy_chg5 is not None:
            if dxy_chg5 > 1.5:
                s_fx, lbl_fx = -1.0, "美元走强"
            elif dxy_chg5 >= -1.5:
                s_fx, lbl_fx =  0.0, "美元稳定"
            else:
                s_fx, lbl_fx = +1.0, "美元走弱"
            scores.append((s_fx, 0.20))
            cny_str = f"  美元/人民币 5日 {cny_chg5:+.4f}%" if cny_chg5 is not None else ""
            details.append(f"美元指数 5日 {dxy_chg5:+.2f}%（{lbl_fx}）{cny_str}")

    if not scores:
        return 0.0, "N/A", "全球市场数据获取失败"

    total_w = sum(w for _, w in scores)
    base    = sum(s * w for s, w in scores) / total_w
    final   = max(-2.0, min(2.0, base + extra))
    label   = _score_to_label(final)
    return round(final, 2), label, "；".join(details)


def _score_to_label(score: float) -> str:
    """将得分映射为文字描述。"""
    if score >= 1.5:
        return "强多头"
    if score >= 0.5:
        return "偏多"
    if score >= -0.5:
        return "中性"
    if score >= -1.5:
        return "偏空"
    return "强空头"
