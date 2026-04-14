"""
基本面数据源：经济总量/结构、宏观供需关系。
"""

from datetime import datetime
from typing import Dict, Any, Optional


def fetch_gdp() -> Dict[str, Any]:
    """获取GDP增速/结构数据。"""
    return {
        "data": {
            "gdp_yoy": None,
            "primary_pct": None,
            "secondary_pct": None,
            "tertiary_pct": None,
            "period": "",
        },
        "error": None,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def fetch_disposable_income() -> Dict[str, Any]:
    """获取居民可支配收入数据。"""
    return {
        "data": None,
        "error": "待接入",
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def fetch_macro_supply_demand() -> Dict[str, Any]:
    """获取宏观供需数据（PMI/CPI/PPI）。"""
    return {
        "data": {
            "pmi": None,
            "cpi": None,
            "ppi": None,
            "period": "",
        },
        "error": None,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def fetch_macro_liquidity() -> Dict[str, Any]:
    """获取宏观流动性数据。"""
    return {
        "data": {
            "m2_yoy": None,
            "m1_yoy": None,
            "period": "",
        },
        "error": None,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
