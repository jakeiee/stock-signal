"""
10 年期国债收益率（CN10Y）实时获取。

链路优先级：
  1. push2.eastmoney.com 实时行情接口（f43 字段，存储值 ÷ 10000 = 收益率%）
  2. push2his.eastmoney.com 历史 K 线（主链路失败时备用）
  3. 保底值 BOND_FALLBACK（两条链路均失败时兜底）
"""

import json
import subprocess
import requests
from datetime import datetime, timedelta, date

from ..config import BOND_FALLBACK


def fetch() -> tuple[float, str]:
    """
    获取中国10年期国债(CN10Y)收益率。

    Returns:
        (rate_percent, date_str)
        成功时 date_str 为 "YYYY-MM-DD" 或 "实时"；
        失败时返回 (BOND_FALLBACK, "fallback")。
    """
    # ── 主链路：push2 实时接口 ─────────────────────────────────────────────────
    try:
        r = requests.get(
            "https://push2.eastmoney.com/api/qt/stock/get",
            params={"secid": "171.CN10Y", "fields": "f43,f86"},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=8,
        )
        d = r.json().get("data") or {}
        if d.get("f43") and d["f43"] > 0:
            rate = d["f43"] / 10000   # 18316 → 1.8316%
            ts   = (
                datetime.fromtimestamp(d["f86"]).strftime("%Y-%m-%d")
                if d.get("f86") else "实时"
            )
            return rate, ts
    except Exception:
        pass

    # ── 备用：push2his 历史 K 线 ──────────────────────────────────────────────
    try:
        today = date.today()
        beg   = (today - timedelta(days=7)).strftime("%Y%m%d")
        end   = today.strftime("%Y%m%d")
        result = subprocess.run(
            [
                "curl", "-s", "--max-time", "10",
                "-H", "User-Agent: Mozilla/5.0",
                (
                    "https://push2his.eastmoney.com/api/qt/stock/kline/get"
                    f"?secid=171.CN10Y&klt=101&fqt=1"
                    f"&fields1=f1,f2,f3,f4&fields2=f51,f52,f53,f54,f55"
                    f"&beg={beg}&end={end}"
                ),
            ],
            capture_output=True, text=True, timeout=15,
        )
        data   = json.loads(result.stdout)
        klines = data.get("data", {}).get("klines", [])
        if klines:
            latest = klines[-1].split(",")
            return float(latest[2]), latest[0]
    except Exception:
        pass

    return BOND_FALLBACK, "fallback"
