"""进一步探测社融接口 + 10年国债收益率"""
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

# 社融接口候选
names = [
    "RPT_ECONOMY_FINANCE_SCALE",
    "RPT_ECONOMY_SOCIAL_FINANCE",
    "RPT_ECONOMY_NEWFINANCE",
    "RPT_MONETARY_FINANCE",
    "RPT_ECONOMY_TOTAL_FINANCE",
    "RPT_ECONOMY_RZ",
    "RPT_ECONOMY_AGGREGATE_FINANCE",
    "RPT_MACRO_FINANCE",
]
for n in names:
    try:
        d = fetch(f"https://datacenter-web.eastmoney.com/api/data/v1/get?columns=ALL&pageNumber=1&pageSize=1&sortColumns=REPORT_DATE&sortTypes=-1&source=WEB&client=WEB&reportName={n}&_={ts}")
        rows = d.get("result", {}).get("data", [])
        if rows:
            print(f"\n=== FOUND: {n} ===")
            print(json.dumps(rows[0], ensure_ascii=False))
        else:
            print(f"  {n}: 空数据")
    except Exception as e:
        print(f"  {n}: 失败 {e}")

print("\n=== 10年国债 - 用 secid=1.019668 (10年国债期货参考) ===")
# 尝试用东方财富债券行情接口查10年国债
# 当前10年期国债 sh019753 等
bond_ids = [
    "1.019753",  # 近期10年国债
    "1.019742",
    "1.019668",
    "1.019580",
]
for sid in bond_ids:
    try:
        url = f"https://push2.eastmoney.com/api/qt/stock/get?fltt=2&invt=2&fields=f2,f3,f4,f12,f14,f58&secid={sid}"
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=10, context=_SSL_CTX) as r:
            data = json.loads(r.read().decode("utf-8"))
        print(f"  {sid}: {data.get('data', {})}")
    except Exception as e:
        print(f"  {sid}: {e}")

print("\n=== 中债收益率曲线 - datacenter bonds ===")
# 中债国债收益率曲线，东方财富有专属接口
for name in ["RPT_BOND_SPOT_YIELD", "RPT_BOND_YIELD_CURVE", "RPT_BOND_CBRATE", "RPT_BONDS_YIELD"]:
    try:
        d = fetch(f"https://datacenter-web.eastmoney.com/api/data/v1/get?columns=ALL&pageNumber=1&pageSize=1&sortColumns=REPORT_DATE&sortTypes=-1&source=WEB&client=WEB&reportName={name}&_={ts}")
        rows = d.get("result", {}).get("data", [])
        if rows:
            print(f"\n  FOUND: {name}")
            print(json.dumps(rows[0], ensure_ascii=False))
        else:
            print(f"  {name}: 空")
    except Exception as e:
        print(f"  {name}: {e}")

print("\n=== push2 中债国债收益率 ===")
# 用 push2 获取 国债收益率指数，东财数据  sh000012 中债综合指数 / sh000013 中债国债
for sid in ["1.000012", "1.000013", "1.1000013"]:
    try:
        url = f"https://push2.eastmoney.com/api/qt/stock/get?fltt=2&invt=2&fields=f2,f3,f4,f12,f14&secid={sid}"
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=10, context=_SSL_CTX) as r:
            data = json.loads(r.read().decode("utf-8"))
        print(f"  {sid}: {data.get('data', {})}")
    except Exception as e:
        print(f"  {sid}: {e}")
