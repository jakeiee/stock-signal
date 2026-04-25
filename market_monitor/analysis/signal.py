"""
综合信号汇总：将五个维度的数据聚合为结构化报告字典。
"""

from datetime import datetime
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

    数据结构统一为：
      fundamental["data"] = { gdp, disposable_income, supply_demand, liquidity, valuation, ... }
    这样飞书卡片的 _fun_kpi_block 可以直接从 fd 读取所有数据。
    """
    # 将所有基本面数据放入 fundamental["data"]
    fundamental = {"data": dict(fundamental_data)}  # 复制原始数据
    fundamental["data"]["valuation"] = valuation_data  # 添加估值数据

    return {
        "capital":     capital_data,
        "fundamental": fundamental,
        "valuation":   valuation_data,  # 保留顶层引用
        "policy":      policy_data,
        "global":      global_data,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
