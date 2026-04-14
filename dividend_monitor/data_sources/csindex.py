"""
中证指数官网数据源。

用于在妙想 API 不可用时获取 OHLCV 日线数据，自算 KDJ。
"""

import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional


def fetch_daily_chg(csindex_code: str, days: int = 300) -> List[Dict]:
    """
    从中证指数官网获取日线数据（含成交额）。

    Args:
        csindex_code: 中证指数代码，如 "000985"（中证全指）
        days: 获取最近 N 天数据

    Returns:
        [{"date": "2026-04-10", "turnover": 9800.0, "cons_number": 5200, ...}, ...]
        空列表表示请求失败或无数据
    """
    start = (datetime.now() - timedelta(days=days + 30)).strftime("%Y%m%d")
    end = datetime.now().strftime("%Y%m%d")

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://www.csindex.com.cn/",
        "Accept": "application/json",
    }

    try:
        resp = requests.get(
            "https://www.csindex.com.cn/csindex-home/perf/index-perf",
            params={"indexCode": csindex_code, "startDate": start, "endDate": end},
            headers=headers,
            timeout=20,
        )
        records = resp.json().get("data", [])
        if not records:
            return []

        result = []
        for r in records:
            # 跳过无效行
            close = r.get("close") or r.get("closePri")
            if not close or float(close) <= 0:
                continue

            result.append({
                "date":         r.get("tradeDate", ""),
                "open":         float(r.get("open", 0)),
                "high":         float(r.get("high", 0)),
                "low":          float(r.get("low", 0)),
                "close":        float(close),
                "volume":       float(r.get("tradingVol", 0)),
                "turnover":     float(r.get("tradingValue", 0)) / 100000000,  # 转换为亿元
                "cons_number":  int(r.get("consNumber", 0)),  # 成分股数量
            })

        return result

    except Exception:
        return []