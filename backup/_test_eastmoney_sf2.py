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
    print(f"Raw response (first 500 chars): {raw[:500]}")
    m = re.match(r"^\w+\((.*)\)\s*;?\s*$", raw.strip(), re.DOTALL)
    if m:
        raw = m.group(1)
    return json.loads(raw)

ts = int(time.time() * 1000)

# 尝试东方财富社融数据接口
print("=== 东方财富 社融数据 ===")

# 社融存量（通过搜索找到的正确接口）
url = f"https://datacenter-web.eastmoney.com/api/data/v1/get?columns=ALL&pageNumber=1&pageSize=20&sortColumns=REPORT_DATE&sortTypes=-1&source=WEB&client=WEB&reportName=RPT_ECONOMY_SOCIAL_FINANCING&_={ts}"
d = fetch(url)
print(f"Full response: {json.dumps(d, ensure_ascii=False)[:1000]}")
