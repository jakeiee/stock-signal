"""
动态仓位建议计算模块。

基于估值百分位、KDJ 技术信号、市场成交额三个维度计算建议仓位。
"""

import sys
import os
from typing import Optional, List, Dict, Tuple

# 处理导入：支持直接执行和模块执行
if __package__:
    from ..config import INDEXES
else:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def calc_position(
    val_results: List[dict],
    kdj_data: Dict[str, List],
    active_rate: Optional[float] = None,
    active_mv: Optional[float] = None,
    turnover: Optional[float] = None,
) -> dict:
    """
    计算综合仓位建议。

    Args:
        val_results:  估值结果列表（与 INDEXES 等长）
        kdj_data:     {index_code: [kdj_row, ...]}
        active_rate:  主动管理比例（可选，0-1）
        active_mv:    主动管理规模（亿元，可选）
        turnover:     全市场成交额（亿元，可选）

    Returns:
        {
            "val_score": float,       # 估值维度得分 (-2 ~ +2)
            "val_label": str,          # 估值标签
            "mkt_score": float,        # 市场维度得分
            "mkt_label": str,          # 市场标签
            "kdj_score": float,        # 技术维度得分
            "kdj_label": str,          # 技术标签
            "composite_score": float,  # 综合得分
            "position_pct": float,     # 中枢仓位（%）
            "position_range": Tuple[int, int],  # 建议区间
            "position_label": str,    # 仓位标签
        }
    """
    # ── 1. 估值维度 ──────────────────────────────────────────────────────
    val_score, val_label = _calc_val_score(val_results)

    # ── 2. 市场维度 ──────────────────────────────────────────────────────
    mkt_score, mkt_label = _calc_mkt_score(turnover)

    # ── 3. 技术维度 ──────────────────────────────────────────────────────
    kdj_score, kdj_label = _calc_kdj_score(kdj_data)

    # ── 4. 综合得分（估值50% 市场30% 技术20%） ───────────────────────────
    composite = val_score * 0.5 + mkt_score * 0.3 + kdj_score * 0.2

    # ── 5. 映射到仓位区间 ────────────────────────────────────────────────
    position_pct, position_range, position_label = _map_to_position(composite)

    return {
        "val_score": round(val_score, 2),
        "val_label": val_label,
        "mkt_score": round(mkt_score, 2),
        "mkt_label": mkt_label,
        "kdj_score": round(kdj_score, 2),
        "kdj_label": kdj_label,
        "composite_score": round(composite, 2),
        "position_pct": position_pct,
        "position_range": position_range,
        "position_label": position_label,
    }


def _calc_val_score(val_results: List[dict]) -> Tuple[float, str]:
    """
    估值维度得分：平均股息率百分位和 PE 百分位（PE越低越好，取反）。

    得分范围：-2 (极贵) ~ +2 (极便宜)
    """
    scores = []
    for res in val_results:
        if "error" in res:
            continue
        div_pct = res.get("div_pct")   # 股息率百分位，越高越好
        pe_pct  = res.get("pe_pct")    # PE 百分位，越低越好

        s = 0.0
        cnt = 0
        if div_pct is not None:
            # 股息率%位越高越好 → 线性映射到 [-1, +1]
            s += (div_pct - 50) / 50   # 0%→-1, 50%→0, 100%→+1
            cnt += 1
        if pe_pct is not None:
            # PE%位越低越好 → 取反
            pe_score = -(pe_pct - 50) / 50   # 0%→+1, 50%→0, 100%→-1
            s += pe_score
            cnt += 1

        if cnt > 0:
            scores.append(s / cnt)

    if not scores:
        return 0.0, "估值数据不足"

    avg = sum(scores) / len(scores)
    label = "极便宜" if avg >= 1.5 else (
        "便宜" if avg >= 0.5 else (
        "适中" if avg >= -0.5 else (
        "偏贵" if avg >= -1.5 else "极贵"
    )))
    return avg, label


def _calc_mkt_score(turnover: Optional[float]) -> Tuple[float, str]:
    """
    市场维度得分：基于全市场成交额判断市场活跃度。

    成交额越高，市场越活跃 → 可以承担更高风险 → 仓位可略高
    """
    if turnover is None:
        return 0.0, "成交额数据缺失"

    # 经验阈值（亿元）
    # 低于 5000 亿：低迷 → 低仓位
    # 5000-8000 亿：正常
    # 8000-12000 亿：活跃 → 可略高
    # 高于 12000 亿：过热 → 降低
    if turnover < 5000:
        score = -1.0
        label = "低迷"
    elif turnover < 8000:
        score = 0.0
        label = "正常"
    elif turnover < 12000:
        score = 0.5
        label = "活跃"
    else:
        score = -0.5   # 过热提示风险
        label = "过热"

    return score, label


def _calc_kdj_score(kdj_data: Dict[str, List]) -> Tuple[float, str]:
    """
    技术维度得分：基于 KDJ 判断超买/超卖。

    KDJ > 80：超买 → 低仓位
    KDJ < 20：超卖 → 高仓位
    金叉：买入信号
    死叉：卖出信号
    """
    scores = []
    for code, rows in kdj_data.items():
        if not rows:
            continue
        row = rows[0]
        k, d, j = row.get("K"), row.get("D"), row.get("J")
        if k is None or d is None or j is None:
            continue

        s = 0.0
        # J 值超买/超卖
        if j > 100:
            s -= 1.5   # 极度超买
        elif j > 80:
            s -= 0.5   # 超买
        elif j < 0:
            s += 1.5   # 极度超卖
        elif j < 20:
            s += 0.5   # 超卖

        # 金叉/死叉
        if len(rows) >= 2:
            prev = rows[1]
            pk, pd = prev.get("K"), prev.get("D")
            if pk is not None and pd is not None:
                if pk < pd and k > d:
                    s += 0.5   # 金叉
                elif pk > pd and k < d:
                    s -= 0.5   # 死叉

        scores.append(s)

    if not scores:
        return 0.0, "KDJ 数据不足"

    avg = sum(scores) / len(scores)

    label = "强买入" if avg >= 1.5 else (
        "弱买入" if avg >= 0.5 else (
        "中性" if avg >= -0.5 else (
        "弱卖出" if avg >= -1.5 else "强卖出"
    )))
    return avg, label


def _map_to_position(composite: float) -> Tuple[float, Tuple[int, int], str]:
    """
    将综合得分映射到仓位区间。

    综合得分范围：-2 ~ +2
    仓位范围：10% ~ 90%
    """
    # 线性映射
    pct = 50 + composite * 20   # -2→10%, -1→30%, 0→50%, 1→70%, 2→90%
    pct = max(10, min(90, pct))   # 限制在 10-90%

    # 区间：中枢 ±10%
    lo = max(0, int(pct - 10))
    hi = min(100, int(pct + 10))

    # 标签
    if pct >= 70:
        label = "重仓"
    elif pct >= 50:
        label = "适中"
    elif pct >= 30:
        label = "轻仓"
    else:
        label = "空仓"

    return round(pct, 0), (lo, hi), label