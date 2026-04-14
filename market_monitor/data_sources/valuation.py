"""
基本面数据源：全市场 PE/PB/股息率 及其历史百分位。

数据来源：
  - Wind APP 手动记录数据（wind_app_recorded_data/*.json）
  - 妙想 API 估值接口（备用）

返回格式统一为 {"data": ..., "error": str|None, "updated_at": str}。
"""

import os
import json
import re
from datetime import datetime
from typing import Dict, Any, Optional

# Wind APP数据目录
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WIND_APP_DATA_DIR = os.path.join(_PROJECT_ROOT, "wind_app_recorded_data")


def _load_wind_app_data() -> Dict[str, Dict[str, Any]]:
    """加载所有Wind APP记录的估值数据"""
    result = {}

    if not os.path.exists(WIND_APP_DATA_DIR):
        return result

    try:
        for filename in os.listdir(WIND_APP_DATA_DIR):
            if filename.endswith(".json"):
                filepath = os.path.join(WIND_APP_DATA_DIR, filename)
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                index_code = data.get("index_code")
                if index_code:
                    result[index_code] = data
    except Exception:
        pass

    return result


def _extract_launch_date(historical_period: str) -> str:
    """从 historical_period 字段提取发布日"""
    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", historical_period)
    return date_match.group(1) if date_match else ""


def fetch_market_valuation() -> Dict[str, Any]:
    """
    获取全市场估值数据。

    Returns:
        {
            "data": {
                "pe": float,           # 市盈率
                "pb": float,           # 市净率
                "div_yield": float,    # 股息率
                "pe_pct": float,       # PE历史百分位
                "pb_pct": float,       # PB历史百分位
                "div_pct": float,      # 股息率历史百分位
                "date": str,
            },
            "error": None,
            "updated_at": str,
        }
    """
    wind_data = _load_wind_app_data()

    if not wind_data:
        return {
            "data": None,
            "error": "Wind APP数据目录为空",
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }

    # 使用中证全指的Wind APP数据
    index_code = "000985"
    if index_code in wind_data:
        data = wind_data[index_code]
    else:
        # 尝试大小写不敏感匹配
        for key, value in wind_data.items():
            if key.lower() == index_code.lower():
                data = value
                break
        else:
            # 使用第一个可用数据
            data = list(wind_data.values())[0]

    valuation_data = data.get("valuation_data", {})
    pe_data = valuation_data.get("PE_TTM", {})
    div_data = valuation_data.get("dividend_yield", {})

    return {
        "data": {
            "pe": pe_data.get("value"),
            "pe_pct": pe_data.get("percentile"),
            "div_yield": div_data.get("value"),
            "div_pct": div_data.get("percentile"),
            "pb": None,
            "pb_pct": None,
            "date": data.get("record_date", ""),
        },
        "error": None,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def fetch_index_valuation(index_code: str) -> Dict[str, Any]:
    """
    获取指定指数的估值数据。

    Args:
        index_code: 指数代码，如 "H30269", "000985"

    Returns:
        {
            "data": {
                "pe": float,
                "pb": float,
                "div_yield": float,
                "pe_pct": float,
                "pb_pct": float,
                "div_pct": float,
                "risk_premium": float,
                "date": str,
            },
            "error": None,
            "updated_at": str,
        }
    """
    wind_data = _load_wind_app_data()

    # 尝试大小写敏感和不敏感匹配
    data = wind_data.get(index_code)
    if data is None:
        index_lower = index_code.lower()
        for key, value in wind_data.items():
            if key.lower() == index_lower:
                data = value
                break

    if data is None:
        return {
            "data": None,
            "error": f"未找到指数 {index_code} 的Wind APP数据",
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }

    valuation_data = data.get("valuation_data", {})
    pe_data = valuation_data.get("PE_TTM", {})
    div_data = valuation_data.get("dividend_yield", {})
    risk_data = valuation_data.get("risk_premium", {})
    quality = data.get("data_quality_check", {})
    historical_period = data.get("historical_period", "")
    hist_years = float(quality.get("historical_period_years", 0))

    return {
        "data": {
            "pe": pe_data.get("value"),
            "pe_pct": pe_data.get("percentile"),
            "div_yield": div_data.get("value"),
            "div_pct": div_data.get("percentile"),
            "pb": None,
            "pb_pct": None,
            "risk_premium": risk_data.get("value"),
            "date": data.get("record_date", ""),
            "launch_date": _extract_launch_date(historical_period),
            "hist_years": hist_years,
            "source": "wind_app",
        },
        "error": None,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
