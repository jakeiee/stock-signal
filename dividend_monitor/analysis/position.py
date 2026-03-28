"""
动态仓位建议计算模块。

综合三类信号得出建议仓位区间（0%–100%）：

  ① 市场温度（全市场成交额）—— 市场热度过高时降仓，低迷时加仓
  ② 估值信号（股息率百分位）—— 股息率历史高位时加仓，低位时减仓
  ③ 技术信号（周线 KDJ J 值）—— 超卖时加仓，超买时降仓

每个维度产出 -2~+2 的得分，三维度加权合并后映射至仓位区间。

市场温度数据来源：中证全指（000985）历史成交额。

仓位档位（供参考，最终由投资者自行决策）：
  满仓  90–100%
  重仓  70–90%
  标配  50–70%
  轻仓  30–50%
  低配  10–30%
  空仓  0–10%
"""

from typing import Optional, List


# ── 维度权重 ───────────────────────────────────────────────────────────────────#
# 估值信号权重最高，市场温度次之，KDJ 辅助
_W_VALUATION = 0.50   # 估值维度权重
_W_MARKET    = 0.30   # 市场活跃度维度权重
_W_KDJ       = 0.20   # 技术指标维度权重


# ────────────────────────────────────────────────────────────────────────────────
# 1. 市场温度评分
# ────────────────────────────────────────────────────────────────────────────────

def score_market(
    active_rate: Optional[float],
    active_mv: Optional[float] = None,
    turnover: Optional[float] = None,
) -> tuple:
    """
    根据全市场成交额评分。

    市场过热 → 做空压力 → 降仓（负分）；市场低迷 → 安全边际高 → 加仓（正分）。

    成交额阈值（中证全指口径，千亿级）：
        > 25000亿 → 极热 -2
        > 15000亿 → 偏热 -1
        >  8000亿 → 正常  0
        >  5000亿 → 偏冷 +1
        ≤  5000亿 → 极冷 +2

    Args:
        active_rate: 保留参数（暂不使用）。
        active_mv:   保留参数（暂不使用）。
        turnover:    全市场成交额（亿元，中证全指口径）。

    Returns:
        (score: float, label: str, detail: str)
    """
    if turnover is not None:
        if turnover > 25000:
            return -2.0, "极热", f"成交额 {turnover:,.0f}亿（>25000亿），市场极度过热"
        if turnover > 15000:
            return -1.0, "偏热", f"成交额 {turnover:,.0f}亿（>15000亿），市场偏热"
        if turnover > 8000:
            return  0.0, "正常", f"成交额 {turnover:,.0f}亿（8000–15000亿），市场正常"
        if turnover > 5000:
            return +1.0, "偏冷", f"成交额 {turnover:,.0f}亿（5000–8000亿），市场偏冷"
        return +2.0, "极冷", f"成交额 {turnover:,.0f}亿（≤5000亿），市场极度低迷"

    return 0.0, "N/A", "市场数据缺失，跳过此维度"


# ────────────────────────────────────────────────────────────────────────────────
# 2. 估值评分（跨指数取均值）
# ────────────────────────────────────────────────────────────────────────────────

def score_valuation(val_results: list) -> tuple:
    """
    根据各指数股息率百分位和 PE 百分位综合评分。

    股息率越高（百分位高）→ 越便宜 → 加仓（正分）
    PE 越低（百分位低）→ 越便宜 → 加仓（正分）

    五档分位映射：
        div_pct > 80  → +2   极高股息，极具吸引力
        div_pct > 60  → +1   偏高股息，性价比良好
        div_pct 40-60 → 0    中等
        div_pct 20-40 → -1   偏低股息，需谨慎
        div_pct < 20  → -2   极低股息，过热

    PE 同理（取反方向）。最终本维度得分 = (div_score + pe_score) / 2 的跨指数均值。

    Args:
        val_results: 与 INDEXES 对应的估值结果列表。

    Returns:
        (score: float, label: str, detail: str)
    """
    scores = []
    details_list = []

    for res in val_results:
        if "error" in res or "div_pct" not in res:
            continue

        div_pct = res.get("div_pct")
        pe_pct  = res.get("pe_pct")

        # 百分位为 None 表示数据不足（< MIN_HIST_DAYS），跳过此指数的估值评分
        if div_pct is None or pe_pct is None:
            continue

        # 股息率评分（高分位 → 高估值吸引力 → 正分）
        if div_pct > 80:
            ds = +2.0
        elif div_pct > 60:
            ds = +1.0
        elif div_pct > 40:
            ds =  0.0
        elif div_pct > 20:
            ds = -1.0
        else:
            ds = -2.0

        # PE 评分（低分位 → 便宜 → 正分）
        pe_pct_inv = 100 - pe_pct
        if pe_pct_inv > 80:
            ps = +2.0
        elif pe_pct_inv > 60:
            ps = +1.0
        elif pe_pct_inv > 40:
            ps =  0.0
        elif pe_pct_inv > 20:
            ps = -1.0
        else:
            ps = -2.0

        avg = (ds + ps) / 2
        scores.append(avg)

        name = res.get("source", "?")   # 备用，终端不使用此字段
        details_list.append(
            f"股息率{div_pct:.0f}%位({ds:+.0f}) PE{pe_pct:.0f}%位({ps:+.0f})"
        )

    if not scores:
        return 0.0, "N/A", "估值数据全部缺失，跳过此维度"

    avg_score = sum(scores) / len(scores)
    label = _score_to_label(avg_score)
    detail = "；".join(details_list)
    return round(avg_score, 2), label, detail


# ────────────────────────────────────────────────────────────────────────────────
# 3. KDJ 技术评分（跨指数取均值）
# ────────────────────────────────────────────────────────────────────────────────

def score_kdj(kdj_data: dict) -> tuple:
    """
    根据各指数最新周 KDJ 的 J 值评分。

    J 值是 KDJ 中最敏感的指标：
        J < 10  → 超卖区 → +2（强烈加仓信号）
        J < 20  → 超卖区 → +1
        J 20-80 → 中性区 →  0
        J > 80  → 超买区 → -1
        J > 100 → 极度超买 → -2

    Args:
        kdj_data: {index_code: [kdj_row, ...]} 映射。

    Returns:
        (score: float, label: str, detail: str)
    """
    scores = []
    details_list = []

    for code, rows in kdj_data.items():
        if not rows:
            continue
        r = rows[0]
        j = r.get("J")
        if j is None:
            continue

        if j < 10:
            s = +2.0
        elif j < 20:
            s = +1.0
        elif j <= 80:
            s =  0.0
        elif j <= 100:
            s = -1.0
        else:
            s = -2.0

        scores.append(s)
        details_list.append(f"{code} J={j:.1f}({s:+.0f})")

    if not scores:
        return 0.0, "N/A", "KDJ 数据全部缺失，跳过此维度"

    avg = sum(scores) / len(scores)
    label = _score_to_label(avg)
    detail = "；".join(details_list)
    return round(avg, 2), label, detail


# ────────────────────────────────────────────────────────────────────────────────
# 4. 综合仓位建议
# ────────────────────────────────────────────────────────────────────────────────

def calc_position(
    val_results: list,
    kdj_data: dict,
    active_rate: Optional[float],
    active_mv: Optional[float] = None,
    turnover: Optional[float] = None,
) -> dict:
    """
    综合三维度评分，输出建议仓位区间。

    综合得分范围：-2 ~ +2。
    仓位映射（线性插值）：
        -2.0 → 10%   （市场极热/估值极贵/技术超买，空仓保守）
        -1.0 → 30%   （偏空）
         0.0 → 55%   （中性，标配）
        +1.0 → 75%   （偏多）
        +2.0 → 95%   （极度低估+冷市，重仓）

    Args:
        val_results: 估值结果列表。
        kdj_data:    周线 KDJ 数据映射。
        active_rate: 活跃率（%），实时链路提供。
        active_mv:   活跃市值（亿），有成交股票流通市值之和，实时链路提供。
        turnover:    成交额（亿），两条链路均提供。

    Returns:
        {
            "composite_score":  float,     # 综合加权得分 (-2~+2)
            "position_pct":     float,     # 建议仓位中枢（%）
            "position_range":   (int,int), # 建议仓位区间（%）
            "position_label":   str,       # 仓位档位文字
            "mkt_score":        float,
            "mkt_label":        str,
            "mkt_detail":       str,
            "val_score":        float,
            "val_label":        str,
            "val_detail":       str,
            "kdj_score":        float,
            "kdj_label":        str,
            "kdj_detail":       str,
        }
    """
    mkt_score, mkt_label, mkt_detail = score_market(active_rate, active_mv, turnover)
    val_score, val_label, val_detail = score_valuation(val_results)
    kdj_score, kdj_label, kdj_detail = score_kdj(kdj_data)

    # 加权合并（权重之和 = 1.0）
    composite = (
        val_score * _W_VALUATION
        + mkt_score * _W_MARKET
        + kdj_score * _W_KDJ
    )

    # 线性插值映射到仓位中枢（-2→10%, 0→55%, +2→95%）
    position_pct = _score_to_position(composite)
    # ±10% 区间
    lo = max(0,   round(position_pct - 10))
    hi = min(100, round(position_pct + 10))

    return {
        "composite_score": round(composite, 2),
        "position_pct":    round(position_pct, 1),
        "position_range":  (lo, hi),
        "position_label":  _position_label(position_pct),
        "mkt_score":       mkt_score,
        "mkt_label":       mkt_label,
        "mkt_detail":      mkt_detail,
        "val_score":       val_score,
        "val_label":       val_label,
        "val_detail":      val_detail,
        "kdj_score":       kdj_score,
        "kdj_label":       kdj_label,
        "kdj_detail":      kdj_detail,
    }


# ────────────────────────────────────────────────────────────────────────────────
# 辅助函数
# ────────────────────────────────────────────────────────────────────────────────

def _score_to_position(score: float) -> float:
    """将综合得分(-2~+2)线性映射为仓位百分比(10~95)。"""
    # 分段插值：-2→10, 0→55, +2→95
    if score <= 0:
        return 55 + score * (55 - 10) / 2   # -2→10, 0→55
    else:
        return 55 + score * (95 - 55) / 2   # 0→55, +2→95


def _score_to_label(score: float) -> str:
    """将得分映射为文字描述。"""
    if score >= 1.5:
        return "极度低估/超卖"
    if score >= 0.5:
        return "低估/偏冷"
    if score >= -0.5:
        return "中性"
    if score >= -1.5:
        return "高估/偏热"
    return "极度高估/超热"


def _position_label(pct: float) -> str:
    """仓位百分比 → 档位文字。"""
    if pct >= 85:
        return "满仓"
    if pct >= 70:
        return "重仓"
    if pct >= 50:
        return "标配"
    if pct >= 30:
        return "轻仓"
    if pct >= 10:
        return "低配"
    return "空仓"
