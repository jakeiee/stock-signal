#!/usr/bin/env python3
"""Test PBC (央行) API for social finance."""
import urllib.request
import json
import ssl

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

headers = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}

# 尝试央行官方数据接口
print("=== 尝试央行 API ===")

# 社融数据可能从这个接口获取
urls = [
    "http://www.pbc.gov.cn/datainterface/datainterface/exportDataController/exportData",
    "http://www.pbc.gov.cn/dataorg/datainterface/interfaceListController/446023.html",
]

for url in urls:
    print(f"\n尝试: {url}")
    try:
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=10, context=ssl_ctx) as r:
            print(f"  状态: {r.status}")
            raw = r.read().decode("utf-8")
            print(f"  内容: {raw[:200]}")
    except Exception as e:
        print(f"  异常: {e}")

# 尝试使用简单的方式获取 - 直接计算
# M2 和社融通常相关性很高，可以考虑用M2作为近似
print("\n=== 使用 M2 数据作为社融的近似 ===")

# 重新测试 M2 接口是否正常
ts = 1773837895921
url_m2 = "https://datacenter-web.eastmoney.com/api/data/v1/get?columns=REPORT_DATE%2CTIME%2CBASIC_CURRENCY%2CBASIC_CURRENCY_SAME%2CBASIC_CURRENCY_SEQUENTIAL%2CCURRENCY%2CCURRENCY_SAME%2CCURRENCY_SEQUENTIAL&pageNumber=1&pageSize=3&sortColumns=REPORT_DATE&sortTypes=-1&source=WEB&client=WEB&reportName=RPT_ECONOMY_CURRENCY_SUPPLY&_={}".format(ts)

import re
req = urllib.request.Request(url_m2, headers=headers)
try:
    with urllib.request.urlopen(req, timeout=15, context=ssl_ctx) as r:
        raw = r.read().decode("utf-8")
    m = re.match(r"^\w+\((.*)\)\s*;?\s*$", raw.strip(), re.DOTALL)
    if m:
        raw = m.group(1)
    d = json.loads(raw)
    rows = d.get("result", {}).get("data", [])
    print(f"M2 数据: {len(rows)} 条")
    for r in rows:
        print(f"  {r.get('TIME')}: M2同比={r.get('BASIC_CURRENCY_SAME')}%")
except Exception as e:
    print(f"M2 接口异常: {e}")
