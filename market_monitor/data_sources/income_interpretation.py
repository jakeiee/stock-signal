"""
收入解读模块。

人均可支配收入数据来源：东方财富数据中心（替代国家统计局API）。
"""

import csv
import os
import json
import re
import ssl
import time
import urllib.request
from datetime import datetime
from typing import Dict, Any, Optional

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

_EM_BASE_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
_EM_HEADERS = {
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://data.eastmoney.com/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}


def _safe_float(value) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _em_fetch_json(url: str, timeout: int = 15) -> dict:
    req = urllib.request.Request(url, headers=_EM_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:
        raw = resp.read().decode("utf-8")
    m = re.search(r"(?:datatable\w+|jQuery\w+)\((.+)\)\s*;?\s*$", raw, re.DOTALL)
    return json.loads(m.group(1) if m else raw)


def fetch_income_with_interpretation(timeout: int = 15) -> Dict[str, Any]:
    """
    获取居民人均可支配收入数据及解读。

    数据来源：东方财富 RPT_INCOMEDIFFUSION_PEOPLEINCOME（居民收入扩散指数）
    备用：本地CSV缓存

    Returns:
        {
            "period": str,        # 如 "2025Q4"
            "income_yoy": float,  # 人均可支配收入同比增速（%）
            "interpretation": {...},
            "source": str,
        }
    """
    # 尝试东方财富接口
    try:
        ts = int(time.time() * 1000)
        # 东方财富居民收入相关接口
        url = (
            f"{_EM_BASE_URL}"
            "?columns=REPORT_DATE%2CTIME%2CFIRST_SAME%2CSECOND_SAME%2CTHIRD_SAME"
            "%2CSUM_SAME"
            "&pageNumber=1&pageSize=4"
            "&sortColumns=REPORT_DATE&sortTypes=-1"
            f"&source=WEB&client=WEB&reportName=RPT_INCOMEDIFFUSION_PEOPLEINCOME&_={ts}"
        )
        data = _em_fetch_json(url, timeout=timeout)
        result = data.get("result") or {}
        rows = result.get("data") or []

        if rows:
            r = rows[0]
            period_str = str(r.get("TIME", "")).strip()
            # 解析季度：2025年第1-4季度 -> 2025Q4
            m = re.search(r"第1[-–~]?(\d)季度", period_str)
            if m:
                period = f"{period_str[:4]}Q{m.group(1)}"
            else:
                period = period_str

            income_yoy = _safe_float(r.get("SUM_SAME"))  # 累计口径同比

            if income_yoy is not None:
                return {
                    "period": period,
                    "income_yoy": income_yoy,
                    "interpretation": {
                        "author": None,
                        "summary": f"居民人均可支配收入同比{income_yoy:.1f}%",
                    },
                    "source": "eastmoney",
                    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                }
    except Exception as e:
        print(f"[收入解读] 东方财富接口失败: {e}")

    # 降级：读取CSV缓存
    csv_path = os.path.join(_DATA_DIR, "disposable_income.csv")
    if os.path.isfile(csv_path):
        try:
            cached = {}
            with open(csv_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    p = row.get("period", "").strip()
                    if p:
                        cached[p] = {
                            "period": p,
                            "income_yoy": _safe_float(row.get("income_yoy")),
                            "source": row.get("source", ""),
                        }
            if cached:
                latest = sorted(cached.keys())[-1]
                rec = cached[latest]
                return {
                    "period": rec["period"],
                    "income_yoy": rec["income_yoy"],
                    "interpretation": {
                        "author": None,
                        "summary": f"居民人均可支配收入同比{rec['income_yoy']:.1f}%（历史缓存）",
                    },
                    "source": "csv_cache",
                    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                }
        except Exception as e:
            print(f"[收入解读] CSV读取失败: {e}")

    return {
        "data": None,
        "error": "人均可支配收入数据获取失败（国家统计局API被拦截，东方财富无直接接口）",
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
