"""
基本面数据源：全市场 PE/PB/股息率 及其历史百分位。

数据来源：
  - 万得全A（除金融石油石化）：market_monitor/data/wind_a_ex_fin_oil_pe.csv（Wind APP 手动记录）
  - 其他指数：Wind APP 手动记录数据（wind_app_recorded_data/*.json）

返回格式统一为 {"data": ..., "error": str|None, "updated_at": str}。
"""

import os
import json
import re
import csv
from datetime import datetime
from typing import Dict, Any, Optional, List

# 项目根目录
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Wind APP数据目录
WIND_APP_DATA_DIR = os.path.join(_PROJECT_ROOT, "wind_app_recorded_data")

# 万得全A（除金融石油石化）PE百分位CSV路径
_WA_PE_CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "wind_a_ex_fin_oil_pe.csv")


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


def _load_wa_pe_csv() -> tuple:
    """
    加载万得全A（除金融石油石化）PE百分位CSV。

    CSV格式: date,index_code,pe,max分位,source

    Returns:
        (rows: list, latest_pe: float, latest_pe_pct: float, last_updated: str|None)
        rows: 按日期升序排列的字典列表
        latest_pe: 最新一行的PE值
        latest_pe_pct: 最新一行的PE历史百分位
        last_updated: 最新一行的日期
    """
    if not os.path.exists(_WA_PE_CSV_PATH):
        return [], None, None, None

    rows = []
    latest_pe = None
    latest_pe_pct = None
    latest_updated = None

    try:
        with open(_WA_PE_CSV_PATH, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
                if row.get("pe") and row.get("max分位"):
                    latest_pe = float(row["pe"])
                    latest_pe_pct = float(row["max分位"])
                    latest_updated = row.get("date", "")
    except Exception as e:
        pass

    return rows, latest_pe, latest_pe_pct, latest_updated


def _extract_launch_date(historical_period: str) -> str:
    """从 historical_period 字段提取发布日"""
    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", historical_period)
    return date_match.group(1) if date_match else ""


def fetch_market_valuation() -> Dict[str, Any]:
    """
    获取全市场估值数据。

    数据来源：
    - 万得全A（除金融石油石化）：market_monitor/data/wind_a_ex_fin_oil_pe.csv（Wind APP 手动记录）

    Returns:
        {
            "data": {
                "pe": float,           # 市盈率
                "pb": float,           # 市净率（暂不支持）
                "div_yield": float,    # 股息率（暂不支持）
                "pe_pct": float,       # PE历史百分位
                "pb_pct": float,       # PB历史百分位（暂不支持）
                "div_pct": float,      # 股息率历史百分位（暂不支持）
                "date": str,
                "last_updated": str,   # 数据日期
            },
            "error": None,
            "updated_at": str,
        }
    """
    # 加载 PE 百分位 CSV 数据
    rows, pe, pe_pct, last_updated = _load_wa_pe_csv()

    if not rows or pe is None:
        return {
            "data": None,
            "error": f"无法读取 { _WA_PE_CSV_PATH }",
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }

    return {
        "data": {
            "pe": pe,
            "pb": None,  # wind_a_ex_fin_oil_pe.csv 不包含 PB 数据
            "div_yield": None,  # wind_a_ex_fin_oil_pe.csv 不包含股息率数据
            "pe_pct": pe_pct,
            "pb_pct": None,
            "div_pct": None,
            "date": last_updated,
            "last_updated": last_updated,
            "source": "wa_pe_csv",
        },
        "error": None,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def fetch_index_valuation(index_code: str) -> Dict[str, Any]:
    """
    获取指定指数的估值数据。

    Args:
        index_code: 指数代码，如 "H30269", "881003.WI"
        - 881003.WI: 万得全A（除金融石油石化），从 CSV 获取

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
    # 特殊处理 881003.WI：使用 CSV 数据
    if index_code.upper() in ("881003.WI", "881003"):
        return _fetch_wa_index_valuation()

    # 其他指数使用 Wind APP 数据
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


def _fetch_wa_index_valuation() -> Dict[str, Any]:
    """
    获取万得全A（除金融石油石化）的估值数据。

    从 wind_a_ex_fin_oil_pe.csv 读取（Wind APP 手动记录）。
    """
    # 加载 PE 百分位 CSV 数据
    rows, pe, pe_pct, last_updated = _load_wa_pe_csv()

    if not rows or pe is None:
        return {
            "data": None,
            "error": f"无法读取 { _WA_PE_CSV_PATH }",
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }

    return {
        "data": {
            "pe": pe,
            "pb": None,
            "div_yield": None,
            "pe_pct": pe_pct,
            "pb_pct": None,
            "div_pct": None,
            "risk_premium": None,
            "date": last_updated,
            "last_updated": last_updated,
            "source": "wa_pe_csv",
        },
        "error": None,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
