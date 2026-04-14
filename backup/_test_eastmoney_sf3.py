#!/usr/bin/env python3
"""Test East Money API for social finance data."""
import urllib.request
import json
import ssl
import time
import re

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

headers = {
    "Accept": "*/*",
    "Referer": "https://data.eastmoney.com/",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}

def fetch(url):
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15, context=ssl_ctx) as r:
        raw = r.read().decode("utf-8")
    m = re.match(r"^\w+\((.*)\)\s*;?\s*$", raw.strip(), re.DOTALL)
    if m:
        raw = m.group(1)
    return json.loads(raw)

ts = int(time.time() * 1000)

# 尝试不同的报表名称
report_names = [
    "RPT_MACRO_SOCIAL_FINANCING",
    "RPT_ECONOMY_SOCIALFINANCING",
    "RPT_ECONOMY_CREDIT",
    "RPT_ECONOMY_FINANCIAL",
    "RPT_MACRO_SOCIALFIN",
]

for report_name in report_names:
    print(f"\n=== 尝试 {report_name} ===")
    url = f"https://datacenter-web.eastmoney.com/api/data/v1/get?columns=ALL&pageNumber=1&pageSize=5&sortColumns=REPORT_DATE&sortTypes=-1&source=WEB&client=WEB&reportName={report_name}&_={ts}"
    try:
        d = fetch(url)
        success = d.get("success", False)
        if success:
            rows = d.get("result", {}).get("data", [])
            print(f"成功! 返回 {len(rows)} 条数据")
            if rows:
                print(f"字段: {list(rows[0].keys())}")
                # 打印前几条的关键字段
                for r in rows[:2]:
                    print(json.dumps(r, ensure_ascii=False, indent=2))
        else:
            msg = d.get("message", "")
            print(f"失败: {msg}")
    except Exception as e:
        print(f"异常: {e}")
