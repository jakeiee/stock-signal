#!/usr/bin/env python3
"""Search for correct East Money API for social finance."""
import urllib.request
import json
import ssl
import time
import re

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

headers = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}

ts = int(time.time() * 1000)

# 尝试从东方财富宏观数据页面获取社融数据
# 社融月报数据的正确接口可能是其他报表名称
# 尝试直接获取一些常见的宏观数据接口

print("=== 尝试常见宏观数据接口 ===")

# 尝试获取数据列表页面
urls_to_try = [
    # 社融 - 社会融资规模
    ("https://datacenter-web.eastmoney.com/api/data/v1/get?type=RPT_ECONOMY_SOCIAL_FINANCING&page=1&size=20", "RPT_ECONOMY_SOCIAL_FINANCING (alt)"),
    # 社融存量 - 可能的接口
    ("https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_ECONOMY_SOCIAL_FINANCING_STA&columns=ALL&pageNumber=1&pageSize=10", "RPT_ECONOMY_SOCIAL_FINANCING_STA"),
    # 另一个尝试
    ("https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_SOCIAL_FINANCING&columns=ALL&pageNumber=1&pageSize=10", "RPT_SOCIAL_FINANCING"),
]

for url, name in urls_to_try:
    print(f"\n尝试 {name}:")
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15, context=ssl_ctx) as r:
            raw = r.read().decode("utf-8")
        m = re.match(r"^\w+\((.*)\)\s*;?\s*$", raw.strip(), re.DOTALL)
        if m:
            raw = m.group(1)
        d = json.loads(raw)
        success = d.get("success", False)
        if success:
            rows = d.get("result", {}).get("data", [])
            print(f"  成功! 返回 {len(rows)} 条")
            if rows:
                print(f"  字段: {list(rows[0].keys())[:10]}")
        else:
            print(f"  失败: {d.get('message', 'unknown')[:80]}")
    except Exception as e:
        print(f"  异常: {e}")

# 如果以上都不行，尝试使用旧的可靠接口 - M2数据
print("\n=== 尝试 M2 货币供应量接口 (作为参考) ===")
url_m2 = "https://datacenter-web.eastmoney.com/api/data/v1/get?columns=REPORT_DATE%2CTIME%2CBASIC_CURRENCY%2CBASIC_CURRENCY_SAME%2CBASIC_CURRENCY_SEQUENTIAL%2CCURRENCY%2CCURRENCY_SAME%2CCURRENCY_SEQUENTIAL&pageNumber=1&pageSize=3&sortColumns=REPORT_DATE&sortTypes=-1&source=WEB&client=WEB&reportName=RPT_ECONOMY_CURRENCY_SUPPLY&_={ts}"
req = urllib.request.Request(url_m2, headers=headers)
with urllib.request.urlopen(req, timeout=15, context=ssl_ctx) as r:
    raw = r.read().decode("utf-8")
m = re.match(r"^\w+\((.*)\)\s*;?\s*$", raw.strip(), re.DOTALL)
if m:
    raw = m.group(1)
d = json.loads(raw)
rows = d.get("result", {}).get("data", [])
print(f"M2 数据返回 {len(rows)} 条:")
for r in rows[:2]:
    print(json.dumps(r, ensure_ascii=False))
