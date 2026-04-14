"""
评分系统：各维度数据 → -2~+2 得分。
"""

from typing import Dict, Any


def score_capital(capital_data: Dict) -> Dict[str, Any]:
    """资金面评分。"""
    return {"score": 0, "label": "中性"}


def score_fundamental(fundamental_data: Dict) -> Dict[str, Any]:
    """基本面评分。"""
    return {"score": 0, "label": "中性"}


def score_valuation(valuation_data: Dict) -> Dict[str, Any]:
    """估值评分。"""
    return {"score": 0, "label": "中性"}


def score_policy(policy_data: Dict) -> Dict[str, Any]:
    """政策面评分。"""
    return {"score": 0, "label": "中性"}


def score_global(global_data: Dict) -> Dict[str, Any]:
    """全球市场评分。"""
    return {"score": 0, "label": "中性"}


def aggregate_score(scores: list) -> Dict[str, Any]:
    """综合评分。"""
    return {"score": 0, "label": "中性"}
