"""
综合信号聚合模块。

将四个维度的原始数据和评分结果合并为统一的 report_data 字典，
供 report/ 层（terminal.py / feishu.py）直接消费。

report_data 结构：
    {
        "generated_at":   str,   # 生成时间 "YYYY-MM-DD HH:MM"
        "capital":      {"data": dict, "score": float, "label": str, "detail": str},
        "fundamental":  {"data": dict, "score": float, "label": str, "detail": str},
        "valuation":    {"data": dict, "score": float, "label": str, "detail": str},
        "policy":       {"data": dict, "score": float, "label": str, "detail": str},
        "global":       {"data": dict, "score": float, "label": str, "detail": str},
        "composite": {
            "score":  float,     # 加权综合得分（-2~+2）
            "label":  str,       # 文字描述
        },
    }

基本面维度拆分为三个子模块（合并进 fundamental 区块展示）：
    - 经济总量/结构（GDP / 三产结构 / 人均可支配收入）
    - 宏观供需关系（PMI / CPI / PPI / 工业产出）
    - 宏观流动性（M2 / 社融 / 国债利率 / LPR）

维度权重（初始默认，后续可配置）：
    资金面    30%
    基本面    40%  ← 包含经济总量/结构、供需关系、流动性
    政策面    10%
    全球市场  20%
"""

from datetime import datetime
from typing import Optional

from . import scorer


# ── 维度权重 ────────────────────────────────────────────────────────────────────
_W_CAPITAL       = 0.30
_W_FUNDAMENTAL   = 0.40
_W_POLICY        = 0.10
_W_GLOBAL        = 0.20


def build_report(
    capital_data:      dict,
    fundamental_data:  dict,
    valuation_data:    dict,
    policy_data:       dict,
    global_data:       dict,
) -> dict:
    """
    聚合五维度数据，生成完整报告字典。

    Args:
        capital_data:      资金面原始数据（capital.py 输出）。
        fundamental_data:  基本面原始数据（fundamental.py 三模块聚合字典）。
        valuation_data:    市场估值原始数据（valuation.py 输出，暂占位）。
        policy_data:       政策面原始数据（policy.py 输出）。
        global_data:       全球市场原始数据（global_mkt.py 输出）。

    Returns:
        统一结构的 report_data 字典（见模块说明）。
    """
    cap_s,  cap_l,  cap_d  = scorer.score_capital(capital_data)
    
    # 将估值数据合并到基本面数据中
    fundamental_with_val = {**fundamental_data, "valuation": valuation_data}
    fun_s,  fun_l,  fun_d  = scorer.score_fundamental(fundamental_with_val)
    
    # 估值评分合并到基本面评分中
    val_s,  val_l,  val_d  = scorer.score_valuation(valuation_data)
    fun_s_combined = fun_s + val_s  # 估值权重计入基本面
    if fun_s_combined > 2:
        fun_s_combined = 2.0
    elif fun_s_combined < -2:
        fun_s_combined = -2.0
    
    pol_s,  pol_l,  pol_d  = scorer.score_policy(policy_data)
    glb_s,  glb_l,  glb_d  = scorer.score_global(global_data)

    composite = (
        cap_s * _W_CAPITAL
        + fun_s_combined * _W_FUNDAMENTAL
        + pol_s * _W_POLICY
        + glb_s * _W_GLOBAL
    )

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "capital": {
            "data":   capital_data,
            "score":  cap_s,
            "label":  cap_l,
            "detail": cap_d,
        },
        "fundamental": {
            "data":   fundamental_with_val,
            "score":  fun_s_combined,
            "label":  fun_l,
            "detail": fun_d + " | " + val_d if fun_d and val_d else fun_d or val_d,
        },
        # valuation 已合并到 fundamental，不再作为独立维度
        "policy": {
            "data":   policy_data,
            "score":  pol_s,
            "label":  pol_l,
            "detail": pol_d,
        },
        "global": {
            "data":   global_data,
            "score":  glb_s,
            "label":  glb_l,
            "detail": glb_d,
        },
        "composite": {
            "score": round(composite, 2),
            "label": scorer._score_to_label(composite),
        },
    }
