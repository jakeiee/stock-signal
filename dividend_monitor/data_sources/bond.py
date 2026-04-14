"""
10年期国债收益率数据源。

数据源：
  优先：东方财富 push2 实时行情接口
  备用：东方财富 push2his 历史K线
"""

import json
import subprocess
from datetime import datetime, date, timedelta
from typing import Tuple, Optional
import requests


# 保底默认值（无法获取实时数据时使用）
BOND_FALLBACK = 1.70  # %


def fetch() -> Tuple[float, str]:
    """
    实时获取中国10年期国债(CN10Y)收益率。

    Returns:
        (收益率%, 日期字符串)
        失败时返回 (BOND_FALLBACK, "fallback")
    """
    # ── 优先：push2 实时接口 ──
    try:
        r = requests.get(
            "https://push2.eastmoney.com/api/qt/stock/get",
            params={"secid": "171.CN10Y", "fields": "f43,f86"},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=8,
        )
        d = r.json().get("data") or {}
        if d.get("f43") and d["f43"] > 0:
            rate = d["f43"] / 10000       # 18316 → 1.8316
            ts = datetime.fromtimestamp(d["f86"]).strftime("%Y-%m-%d") if d.get("f86") else "实时"
            return rate, ts
    except Exception:
        pass

    # ── 备用：push2his 历史K线 ──
    try:
        today = date.today()
        beg = (today - timedelta(days=7)).strftime("%Y%m%d")
        end = today.strftime("%Y%m%d")
        result = subprocess.run(
            ["curl", "-s", "--max-time", "10",
             "-H", "User-Agent: Mozilla/5.0",
             f"https://push2his.eastmoney.com/api/qt/stock/kline/get"
             f"?secid=171.CN10Y&klt=101&fqt=1"
             f"&fields1=f1,f2,f3,f4&fields2=f51,f52,f53,f54,f55"
             f"&beg={beg}&end={end}"],
            capture_output=True, text=True, timeout=15,
        )
        data = json.loads(result.stdout)
        klines = data.get("data", {}).get("klines", [])
        if klines:
            latest = klines[-1].split(",")
            return float(latest[2]), latest[0]
    except Exception:
        pass

    return BOND_FALLBACK, "fallback"