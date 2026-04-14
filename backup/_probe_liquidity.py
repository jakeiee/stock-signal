"""探测 M2 + 社融 + 10年国债收益率 接口字段"""
import json, ssl, time, urllib.request, re

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

_HEADERS = {
    "Accept": "*/*",
    "Referer": "https://data.eastmoney.com/",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}

def fetch(url):
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as r:
        raw = r.read().decode("utf-8")
    m = re.match(r"^\w+\((.*)\)\s*;?\s*$", raw.strip(), re.DOTALL)
    if m:
        raw = m.group(1)
    return json.loads(raw)

ts = int(time.time() * 1000)

print("=== M2 货币供应量 (RPT_ECONOMY_CURRENCY_SUPPLY) ===")
d = fetch(f"https://datacenter-web.eastmoney.com/api/data/v1/get?columns=REPORT_DATE%2CTIME%2CBASIC_CURRENCY%2CBASIC_CURRENCY_SAME%2CBASIC_CURRENCY_SEQUENTIAL%2CCURRENCY%2CCURRENCY_SAME%2CCURRENCY_SEQUENTIAL%2CFREE_CASH%2CFREE_CASH_SAME%2CFREE_CASH_SEQUENTIAL&pageNumber=1&pageSize=3&sortColumns=REPORT_DATE&sortTypes=-1&source=WEB&client=WEB&reportName=RPT_ECONOMY_CURRENCY_SUPPLY&_={ts}")
rows = d.get("result", {}).get("data", [])
for r in rows:
    print(json.dumps(r, ensure_ascii=False))

print("\n=== 尝试社融 RPT_ECONOMY_SOCIAL_FINANCING ===")
try:
    d2 = fetch(f"https://datacenter-web.eastmoney.com/api/data/v1/get?columns=ALL&pageNumber=1&pageSize=3&sortColumns=REPORT_DATE&sortTypes=-1&source=WEB&client=WEB&reportName=RPT_ECONOMY_SOCIAL_FINANCING&_={ts}")
    rows2 = d2.get("result", {}).get("data", [])
    print(f"records={len(rows2)}")
    for r in rows2[:2]:
        print(json.dumps(r, ensure_ascii=False))
except Exception as e:
    print(f"  失败: {e}")

print("\n=== 尝试社融 RPT_MACRO_SOCIAL_FINANCING ===")
try:
    d3 = fetch(f"https://datacenter-web.eastmoney.com/api/data/v1/get?columns=ALL&pageNumber=1&pageSize=3&sortColumns=REPORT_DATE&sortTypes=-1&source=WEB&client=WEB&reportName=RPT_MACRO_SOCIAL_FINANCING&_={ts}")
    rows3 = d3.get("result", {}).get("data", [])
    print(f"records={len(rows3)}")
    for r in rows3[:2]:
        print(json.dumps(r, ensure_ascii=False))
except Exception as e:
    print(f"  失败: {e}")

print("\n=== 尝试社融 RPT_ECONOMY_SOCIALFINANCING ===")
try:
    d4 = fetch(f"https://datacenter-web.eastmoney.com/api/data/v1/get?columns=ALL&pageNumber=1&pageSize=3&sortColumns=REPORT_DATE&sortTypes=-1&source=WEB&client=WEB&reportName=RPT_ECONOMY_SOCIALFINANCING&_={ts}")
    rows4 = d4.get("result", {}).get("data", [])
    print(f"records={len(rows4)}")
    for r in rows4[:2]:
        print(json.dumps(r, ensure_ascii=False))
except Exception as e:
    print(f"  失败: {e}")

print("\n=== 尝试社融 RPT_ECONOMY_CREDIT ===")
try:
    d5 = fetch(f"https://datacenter-web.eastmoney.com/api/data/v1/get?columns=ALL&pageNumber=1&pageSize=3&sortColumns=REPORT_DATE&sortTypes=-1&source=WEB&client=WEB&reportName=RPT_ECONOMY_CREDIT&_={ts}")
    rows5 = d5.get("result", {}).get("data", [])
    print(f"records={len(rows5)}")
    for r in rows5[:2]:
        print(json.dumps(r, ensure_ascii=False))
except Exception as e:
    print(f"  失败: {e}")

print("\n=== 10年国债收益率 (push2行情) ===")
# 10年国债: 债券代码 sh019728 -> secid=1.019728 / 或用 IRS 接口
try:
    bond_url = "https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2&invt=2&fields=f2,f3,f4,f12,f14&secids=1.019547,1.019595,1.019696"
    req = urllib.request.Request(bond_url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as r:
        raw = r.read().decode("utf-8")
    data = json.loads(raw)
    print(json.dumps(data, ensure_ascii=False, indent=2))
except Exception as e:
    print(f"  失败: {e}")

print("\n=== 10年国债 eastmoney 宏观接口 ===")
try:
    bond2 = fetch(f"https://datacenter-web.eastmoney.com/api/data/v1/get?columns=ALL&pageNumber=1&pageSize=3&sortColumns=REPORT_DATE&sortTypes=-1&source=WEB&client=WEB&reportName=RPT_BOND_CBRATE&_={ts}")
    rows_b = bond2.get("result", {}).get("data", [])
    print(f"records={len(rows_b)}")
    for r in rows_b[:2]:
        print(json.dumps(r, ensure_ascii=False))
except Exception as e:
    print(f"  失败: {e}")
