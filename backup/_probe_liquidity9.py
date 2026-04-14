"""最终方案：国债收益率通过东财宏观数据/债券行情接口"""
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

# ── 方案1: 东财 bonds.eastmoney 利率债接口 ──
print("=== 东财债券频道 国债收益率 ===")
# 东方财富债券频道 bonds.eastmoney.com 有国债收益率走势，接口可能在 datacenter-web
for name in [
    "RPTA_WEB_TREASUYYIELD",
    "RPT_WEB_TREASUYYIELD",
    "RPT_BOND_TREASUYYIELD",
    "RPT_BOND_TREASURYYIELD",
    "RPT_TREASURY_YIELD",
    "RPTA_TREASURY_YIELD",
    "RPT_ECONOMY_TREASURY",
    "RPT_CN_TREASURYYIELD",
]:
    try:
        d = fetch_json(f"https://datacenter-web.eastmoney.com/api/data/v1/get?columns=ALL&pageNumber=1&pageSize=2&sortColumns=REPORT_DATE&sortTypes=-1&source=WEB&client=WEB&reportName={name}&_={ts}")
        rows = (d.get("result") or {}).get("data") or []
        if rows:
            print(f"\n  FOUND: {name}")
            print(json.dumps(rows[0], ensure_ascii=False)[:400])
        else:
            code = d.get("code","")
            msg = (d.get("message") or "")[:30]
            if str(code) != "9501":
                print(f"  {name}: code={code} {msg}")
    except Exception as e:
        if "9501" not in str(e):
            print(f"  {name}: {e}")

# ── 方案2: 东财 宏观-利率接口（LPR/基准利率）──
print("\n=== LPR 接口 ===")
for name in ["RPT_ECONOMY_LPR", "RPTA_ECONOMY_LPR", "RPT_ECONOMY_NEW_LPR",
             "RPT_MACRO_LPR", "RPT_ECONOMY_LPR_RATE"]:
    try:
        d = fetch_json(f"https://datacenter-web.eastmoney.com/api/data/v1/get?columns=ALL&pageNumber=1&pageSize=2&sortColumns=REPORT_DATE&sortTypes=-1&source=WEB&client=WEB&reportName={name}&_={ts}")
        rows = (d.get("result") or {}).get("data") or []
        code = d.get("code","")
        if rows:
            print(f"\n  FOUND: {name}")
            print(json.dumps(rows[0], ensure_ascii=False)[:400])
        elif str(code) != "9501":
            print(f"  {name}: code={code} {d.get('message','')[:50]}")
    except Exception as e:
        if "9501" not in str(e):
            print(f"  {name}: {e}")

# ── 方案3: 用 http 接口获取 10年期国债收益率历史 (通过行情接口) ──
print("\n=== push2 K线获取 019753 历史价格 ===")
try:
    # K线接口
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=1.019753&ut=fa5fd1943c7b386f172d6893dbfba10b&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&klt=101&fqt=1&beg=20260101&end=20261231&smplmt=460&lmt=1000000"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=10, context=_SSL_CTX) as r:
        data = json.loads(r.read().decode("utf-8"))
    klines = (data.get("data") or {}).get("klines") or []
    print(f"  K线条数: {len(klines)}")
    for k in klines[-3:]:
        print(f"  {k}")
except Exception as e:
    print(f"  K线: {e}")

# ── 方案4: 国债收益率=从东财 http/bonds 页面接口抓 ──
print("\n=== 东财 bonds 利率债接口 ===")
for url in [
    f"https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_YIELD_CURVE_DATA&columns=ALL&pageNumber=1&pageSize=3&sortColumns=REPORT_DATE&sortTypes=-1&_={ts}",
    f"https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_BOND_RATE&columns=ALL&pageNumber=1&pageSize=3&sortColumns=REPORT_DATE&sortTypes=-1&_={ts}",
    f"https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_BOND_INTEREST_RATE&columns=ALL&pageNumber=1&pageSize=3&sortColumns=REPORT_DATE&sortTypes=-1&_={ts}",
]:
    try:
        d = fetch_json(url)
        rows = (d.get("result") or {}).get("data") or []
        code = d.get("code","")
        if rows:
            name = re.search(r"reportName=(\w+)", url).group(1)
            print(f"\n  FOUND: {name}")
            print(json.dumps(rows[0], ensure_ascii=False)[:400])
        elif str(code) != "9501":
            print(f"  code={code}: {url[-60:]}")
    except Exception as e:
        if "9501" not in str(e):
            print(f"  err: {e}")
