"""
基本面数据源：全市场 PE/PB/股息率 及其历史百分位。

数据来源：
  - 万得全A（除金融石油石化）：wind_a_pe_history.csv（Wind API + 手动维护百分位）
  - 其他指数：Wind APP 手动记录数据（wind_app_recorded_data/*.json）

返回格式统一为 {"data": ..., "error": str|None, "updated_at": str}。
"""

import os
import json
import re
import csv
from datetime import datetime
from typing import Dict, Any, Optional, List

# Wind APP数据目录
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WIND_APP_DATA_DIR = os.path.join(_PROJECT_ROOT, "wind_app_recorded_data")

# 万得全A历史数据CSV路径
_WA_CSV_PATH = os.path.join(_PROJECT_ROOT, "data", "wind_a_pe_history.csv")


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


def _load_wa_csv() -> tuple:
    """
    加载万得全A历史数据CSV。

    Returns:
        (rows: list, latest_pe_pct: float|None, last_updated: str|None)
        rows: 按日期升序排列的字典列表
        latest_pe_pct: 最新一行的pe_pct（手动维护）
        last_updated: 最新一行的last_updated日期（手动维护）
    """
    if not os.path.exists(_WA_CSV_PATH):
        return [], None, None

    rows = []
    latest_pe_pct = None
    latest_updated = None

    try:
        with open(_WA_CSV_PATH, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
                if row.get("pe_pct"):
                    latest_pe_pct = float(row["pe_pct"])
                    latest_updated = row.get("last_updated", "")
    except Exception:
        pass

    return rows, latest_pe_pct, latest_updated


def _calc_percentile(pe_values: List[float], current_pe: float) -> Optional[float]:
    """计算PE历史百分位"""
    if not pe_values or current_pe is None:
        return None
    valid_values = [v for v in pe_values if v is not None and v != ""]
    if not valid_values:
        return None
    count = sum(1 for v in valid_values if v <= current_pe)
    return round(count / len(valid_values) * 100, 1)


def _extract_launch_date(historical_period: str) -> str:
    """从 historical_period 字段提取发布日"""
    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", historical_period)
    return date_match.group(1) if date_match else ""


def fetch_market_valuation() -> Dict[str, Any]:
    """
    获取全市场估值数据。

    数据来源：
    - 优先从 wind_a_pe_history.csv 获取（万得全A除金融石油石化）
    - 如果 CSV 数据不是最新，调用 Wind API 补充新数据

    Returns:
        {
            "data": {
                "pe": float,           # 市盈率
                "pb": float,           # 市净率
                "div_yield": float,    # 股息率
                "pe_pct": float,       # PE历史百分位（手动维护）
                "pb_pct": float,       # PB历史百分位
                "div_pct": float,      # 股息率历史百分位
                "date": str,
                "last_updated": str,   # 百分位最后手动更新日期
            },
            "error": None,
            "updated_at": str,
        }
    """
    # 加载 CSV 数据
    rows, csv_pe_pct, last_updated = _load_wa_csv()

    if not rows:
        # CSV 为空，尝试调用 Wind API
        return _fetch_wa_from_api()

    # 获取最新一条数据
    latest = rows[-1]
    current_date = latest["trade_date"]

    # 注意：Wind API indexid 指向了错误的指数（PE=23），暂时禁用自动更新
    # 如需更新数据，请手动从 Wind APP 获取并添加到 CSV
    need_update = False  # 禁用自动 API 更新

    # 计算 PB 历史百分位（基于 CSV 数据）
    pb_values = []
    for row in rows:
        try:
            if row.get("pb"):
                pb_values.append(float(row["pb"]))
        except (ValueError, TypeError):
            pass
    current_pb = float(latest["pb"]) if latest.get("pb") else None
    pb_pct = _calc_percentile(pb_values, current_pb) if pb_values else None

    return {
        "data": {
            "pe": float(latest["pe"]) if latest.get("pe") else None,
            "pb": float(latest["pb"]) if latest.get("pb") else None,
            "div_yield": float(latest["div_yield"]) if latest.get("div_yield") else None,
            "pe_pct": csv_pe_pct,  # 手动维护
            "pb_pct": pb_pct,
            "div_pct": None,
            "date": current_date,
            "last_updated": last_updated,
            "source": "wa_csv",
            "need_update": need_update,
        },
        "error": None,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def _fetch_wa_from_api() -> Dict[str, Any]:
    """从 Wind API 获取万得全A数据（当 CSV 为空时使用）"""
    from .global_mkt import fetch_wa_valuation

    result = fetch_wa_valuation()
    if "error" in result:
        return {
            "data": None,
            "error": result["error"],
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }

    return {
        "data": {
            "pe": result["pe"],
            "pb": result["pb"],
            "div_yield": result["div_yield"],
            "pe_pct": None,  # CSV 为空，无法获取百分位
            "pb_pct": None,
            "div_pct": None,
            "date": result["date"],
            "last_updated": None,
            "source": "wind_api",
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

    从 CSV 读取，百分位手动维护。
    """
    # 加载 CSV 数据
    rows, csv_pe_pct, last_updated = _load_wa_csv()

    if not rows:
        # CSV 为空，尝试调用 Wind API
        return _fetch_wa_from_api()

    # 获取最新一条数据
    latest = rows[-1]
    current_date = latest["trade_date"]

    # 注意：Wind API indexid 指向了错误的指数（PE=23），暂时禁用自动更新
    # 如需更新数据，请手动从 Wind APP 获取并添加到 CSV
    need_update = False  # 禁用自动 API 更新

    # 计算 PB 历史百分位（基于 CSV 数据）
    pb_values = []
    for row in rows:
        try:
            if row.get("pb"):
                pb_values.append(float(row["pb"]))
        except (ValueError, TypeError):
            pass
    current_pb = float(latest["pb"]) if latest.get("pb") else None
    pb_pct = _calc_percentile(pb_values, current_pb) if pb_values else None

    return {
        "data": {
            "pe": float(latest["pe"]) if latest.get("pe") else None,
            "pb": float(latest["pb"]) if latest.get("pb") else None,
            "div_yield": float(latest["div_yield"]) if latest.get("div_yield") else None,
            "pe_pct": csv_pe_pct,  # 手动维护
            "pb_pct": pb_pct,
            "div_pct": None,
            "risk_premium": None,
            "date": current_date,
            "last_updated": last_updated,
            "source": "wa_csv",
            "need_update": need_update,
        },
        "error": None,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
