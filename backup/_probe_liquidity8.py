"""确认国债收益率接口 + 社融接口最终方案"""
import json, ssl, time, urllib.request, re

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

HEADERS = {
    "Accept": "*/*",
    "Referer": "https://data.eastmoney.com/",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}

def fetch_json(url, headers=None):
    req = urllib.request.Request(url, headers=headers or HEADERS)
    with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as r:
        raw = r.read().decode("utf-8")
    m = re.match(r"^\w+\((.*)\)\s*;?\s*$", raw.strip(), re.DOTALL)
    if m:
        raw = m.group(1)
    return json.loads(raw)

ts = int(time.time() * 1000)

# ── 国债收益率：push2 获取 sh019753（24国债17，10年期）完整字段 ──
print("=== sh019753 完整字段 ===")
url = f"https://push2.eastmoney.com/api/qt/stock/get?fltt=2&invt=2&fields=f2,f3,f4,f5,f6,f12,f14,f15,f16,f17,f18,f23,f57,f58,f59,f107,f116,f117,f135,f136,f137,f138,f139,f140,f141,f142&secid=1.019753"
d = fetch_json(url)
print(json.dumps(d.get("data", {}), ensure_ascii=False, indent=2))

# ── 10年国债最新几只，用行情接口获取收益率 ──
print("\n=== 近期10年期国债 收益率字段 ===")
for code in ["019753", "019748", "019742", "019740", "019739"]:
    try:
        url = f"https://push2.eastmoney.com/api/qt/stock/get?fltt=2&invt=2&fields=f2,f3,f12,f14,f58,f130,f131,f168,f169&secid=1.{code}"
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=8, context=_SSL_CTX) as r:
            data = json.loads(r.read().decode("utf-8"))
        d = data.get("data", {})
        if d:
            print(f"  sh{code}: {d}")
    except Exception as e:
        print(f"  sh{code}: {e}")

# ── 东财债券频道接口 ──
print("\n=== 东财债券收益率曲线接口 ===")
for url in [
    f"https://datacenter-web.eastmoney.com/api/data/v1/get?columns=ALL&pageNumber=1&pageSize=3&sortColumns=DATES&sortTypes=-1&source=WEB&client=WEB&reportName=RPTA_CBRATE_CURVE&_={ts}",
    f"https://datacenter-web.eastmoney.com/api/data/v1/get?columns=ALL&pageNumber=1&pageSize=3&sortColumns=REPORT_DATE&sortTypes=-1&source=WEB&client=WEB&reportName=RPTA_CBRATE&_={ts}",
    f"https://datacenter-web.eastmoney.com/api/data/v1/get?columns=REPORT_DATE,COUNTRY_TYPE,EMT_YEARS_TYPE,INTEREST_RATE&pageNumber=1&pageSize=5&sortColumns=REPORT_DATE&sortTypes=-1&source=WEB&client=WEB&reportName=RPTA_CBRATE&_={ts}",
]:
    try:
        d = fetch_json(url)
        rows = (d.get("result") or {}).get("data") or []
        code = d.get("code")
        if rows:
            print(f"  FOUND: {url[-60:]}")
            print(json.dumps(rows[0], ensure_ascii=False)[:300])
        else:
            print(f"  {url[-40:]}: code={code} {d.get('message','')[:50]}")
    except Exception as e:
        print(f"  err: {e}")

# ── 社融 - 再尝试金融数据接口 ──
print("\n=== 社融 金融数据接口 ===")
for name in ["RPT_ECONOMY_SHRZLX", "RPT_ECONOMY_SHRZLX_DETAIL",
             "RPTA_ECONOMY_CURRENCY_FINANCE", "RPT_ECONOMY_FINANCE_DATA",
             "RPT_ECONOMY_RZMBLX", "RPT_ECONOMY_BANKLOAN_DATA"]:
    try:
        d = fetch_json(f"https://datacenter-web.eastmoney.com/api/data/v1/get?columns=ALL&pageNumber=1&pageSize=1&sortColumns=REPORT_DATE&sortTypes=-1&source=WEB&client=WEB&reportName={name}&_={ts}")
        rows = (d.get("result") or {}).get("data") or []
        code = d.get("code", "")
        msg  = d.get("message","")
        if rows:
            print(f"  FOUND: {name}")
            print(json.dumps(rows[0], ensure_ascii=False)[:300])
        else:
            print(f"  {name}: code={code} {msg[:40]}")
    except Exception as e:
        print(f"  {name}: {e}")
