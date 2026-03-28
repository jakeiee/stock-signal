"""
政策面数据源。

已实现指标：
  - 货币政策（MLF/降准/逆回购/LPR/国债收益率）
  - 重大监管政策公告（IPO 节奏、再融资政策等）- 待实现
  - 财政政策信号（专项债、财政赤字等）- 待实现
  - 经济数据发布日历（CPI/PPI/PMI/GDP 等）- 待实现

数据来源：
  - 货币政策：预设基准值 + Web Search动态发现
  - 其他政策：Web Search / 东方财富财经日历

注意：政策面数据高度依赖非结构化文本，
结合 LLM 做政策语义解析和情绪评分。
"""

from datetime import datetime
from typing import Optional, Dict, List


def fetch_policy_events(days: int = 30, timeout: int = 20) -> dict:
    """
    获取近 N 日重大货币/财政政策事件。
    现在包含货币政策数据。

    Returns:
        {
            "monetary": {...},  # 货币政策数据
            "events": [...],     # 政策事件列表（待实现）
            "calendar": [...],  # 经济日历（待实现）
            "source": str,
        }
    """
    # 1. 获取货币政策数据
    try:
        from .monetary_policy import fetch_monetary_policy
        monetary_data = fetch_monetary_policy()
    except Exception as e:
        monetary_data = {"error": str(e)}
    
    # 2. 政策事件列表（待实现）
    events = []
    
    # 3. 经济日历（待实现）
    calendar = []
    
    return {
        "monetary": monetary_data,
        "events": events,
        "calendar": calendar,
        "source": "monetary_policy + (待实现)",
    }


def fetch_econ_calendar(timeout: int = 20) -> dict:
    """
    获取未来两周经济数据发布日历（CPI、PPI、PMI、GDP等）。

    Returns:
        {
            "calendar": [...],
            "source": str,
        }
        失败时：{"error": str}
    """
    # TODO: 对接财经日历接口
    return {"error": "待实现（TODO: fetch_econ_calendar）"}
