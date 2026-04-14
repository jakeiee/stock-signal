"""
政策面数据源：央行政策事件。
"""

from datetime import datetime
from typing import Dict, Any


def fetch() -> Dict[str, Any]:
    """获取政策事件。"""
    return {
        "data": [],
        "error": None,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def fetch_policy_events() -> Dict[str, Any]:
    """获取政策事件列表。"""
    return {
        "data": {
            "monetary": None,
            "events": [],
        },
        "error": None,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
