"""
CPI/PPI 解读模块。

数据来源：国家统计局官方解读（网页抓取），CSV缓存兜底。
"""

import csv
import os
from datetime import datetime
from typing import Dict, Any, Optional

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_CPI_PPI_INTERP_CSV = os.path.join(_DATA_DIR, "cpi_ppi_interpretation.csv")


def _read_cpi_ppi_interp_csv() -> dict:
    """读取CPI/PPI解读CSV缓存，返回{period: row_dict}，取最新期。"""
    if not os.path.isfile(_CPI_PPI_INTERP_CSV):
        return {}
    result = {}
    with open(_CPI_PPI_INTERP_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            p = row.get("period", "").strip()
            if not p:
                continue
            result[p] = {
                "period":         p,
                "publish_date":   row.get("publish_date", ""),
                "cpi_yoy":       _safe_float(row.get("cpi_yoy")),
                "cpi_mom":       _safe_float(row.get("cpi_mom")),
                "ppi_yoy":       _safe_float(row.get("ppi_yoy")),
                "ppi_mom":       _safe_float(row.get("ppi_mom")),
                "title":         row.get("title", ""),
                "author":        row.get("author", ""),
                "summary":       row.get("summary", ""),
                "key_points":    row.get("key_points", ""),
                "source_url":    row.get("source_url", ""),
            }
    return result


def _safe_float(value) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def fetch_cpi_ppi_with_interpretation(timeout: int = 15) -> Dict[str, Any]:
    """
    获取 CPI/PPI 数据及官方解读。

    优先从本地CSV缓存读取（缓存由网页抓取任务维护）。
    """
    try:
        cached = _read_cpi_ppi_interp_csv()
        if cached:
            latest_period = sorted(cached.keys())[-1]
            rec = cached[latest_period].copy()
            # 返回符合预期的格式
            return {
                "period": rec["period"],
                "publish_date": rec.get("publish_date"),
                "cpi_yoy": rec.get("cpi_yoy"),
                "cpi_mom": rec.get("cpi_mom"),
                "ppi_yoy": rec.get("ppi_yoy"),
                "ppi_mom": rec.get("ppi_mom"),
                "interpretation": {
                    "author": rec.get("author"),
                    "summary": rec.get("summary"),
                    "key_points": rec.get("key_points"),
                    "source_url": rec.get("source_url"),
                },
                "source": "csv_cache",
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
    except Exception as e:
        pass

    return {
        "data": None,
        "error": f"CPI/PPI解读数据获取失败：{e}",
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
