"""
综合信号汇总：将五个维度的数据聚合为结构化报告字典。
"""

from typing import Dict, Any


def build_report(
    capital_data: Dict,
    fundamental_data: Dict,
    valuation_data: Dict,
    policy_data: Dict,
    global_data: Dict,
) -> Dict[str, Any]:
    """
    聚合各维度数据为结构化报告。

    Returns:
        包含各维度数据的汇总字典
    """
    return {
        "capital":     capital_data,
        "fundamental": fundamental_data,
        "valuation":   valuation_data,
        "policy":      policy_data,
        "global":      global_data,
    }
