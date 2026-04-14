"""验证通过K线价格+面值计算YTM的可行性，同时探测社融另类接口"""
import json, ssl, time, urllib.request, re, math

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE
HEADERS = {"Accept": "*/*", "Referer": "https://data.eastmoney.com/", "User-Agent": "Mozilla/5.0"}

def fetch_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as r:
        raw = r.read().decode("utf-8")
    m = re.match(r"^\w+\((.*)\)\s*;?\s*$", raw.strip(), re.DOTALL)
    if m:
        raw = m.group(1)
    return json.loads(raw)

ts = int(time.time() * 1000)

# ── 方案：用 EMT 宏观利率接口 ──
print("=== 东财宏观 EMT 接口（加上 source=EMT）===")
for name in ["RPT_ECONOMY_INTEREST_RATE_EMT", "RPT_ECONOMY_LPR_EMT",
             "RPT_ECONOMY_TREASURY_YIELD", "RPT_ECONOMY_GOVERNMENT_BOND"]:
    try:
        d = fetch_json(f"https://datacenter-web.eastmoney.com/api/data/v1/get?columns=ALL&pageNumber=1&pageSize=2&sortColumns=REPORT_DATE&sortTypes=-1&source=EMT&client=WEB&reportName={name}&_={ts}")
        rows = (d.get("result") or {}).get("data") or []
        if rows:
            print(f"FOUND {name}: {json.dumps(rows[0], ensure_ascii=False)[:300]}")
        elif str(d.get("code")) != "9501":
            print(f"  {name}: code={d.get('code')} {d.get('message','')[:50]}")
    except Exception as e:
        pass

# ── 直接获取 24国债17 的债券信息（面值/票面利率/到期日）──
print("\n=== 24国债17 债券信息 ===")
try:
    url = f"https://datacenter-web.eastmoney.com/api/data/v1/get?columns=ALL&pageNumber=1&pageSize=1&filter=(SECUCODE=%22019753.SH%22)&source=WEB&client=WEB&reportName=RPT_BOND_BASIC_INFO&_={ts}"
    d = fetch_json(url)
    print(json.dumps(d, ensure_ascii=False)[:500])
except Exception as e:
    print(f"  {e}")

# ── 搜索债券基本信息 ──
print("\n=== 债券基本信息接口 ===")
for name in ["RPT_BOND_BASIC_INFO", "RPT_BOND_INFO", "RPT_ZQSJ_BOND_BASIC"]:
    try:
        d = fetch_json(f"https://datacenter-web.eastmoney.com/api/data/v1/get?columns=ALL&pageNumber=1&pageSize=1&filter=(SECUCODE=%22019753.SH%22)&source=WEB&client=WEB&reportName={name}&_={ts}")
        rows = (d.get("result") or {}).get("data") or []
        if rows:
            print(f"FOUND {name}")
            print(json.dumps(rows[0], ensure_ascii=False)[:400])
        elif str(d.get("code")) != "9501":
            print(f"  {name}: code={d.get('code')}")
    except Exception as e:
        pass

# ── 尝试用东财 f166 字段（债券收益率）在 push2 行情中获取 ──
print("\n=== push2 债券收益率字段探测（交易时间外）===")
# 债券收益率字段在东财 push2 中是 f166 (到期收益率), f168 (修正久期)
url = "https://push2.eastmoney.com/api/qt/stock/get?fltt=2&invt=2&fields=f2,f3,f4,f12,f14,f15,f16,f17,f18,f23,f57,f58,f59,f130,f131,f138,f160,f161,f162,f163,f164,f165,f166,f167,f168,f169&secid=1.019753"
d = fetch_json(url)
print(json.dumps(d.get("data", {}), ensure_ascii=False, indent=2))

# ── 中债官方网站直接查询 ──
print("\n=== 中债官方 yields API ===")
# 中债的实际 AJAX 接口
for url in [
    "https://yield.chinabond.com.cn/cbweb-czb-web/czb/queryGjqxInfoByParam.do?workTime=2026-03-14&locale=zh_CN",
    "https://yield.chinabond.com.cn/cbweb-czb-web/czb/queryGjqxInfo.do?workTime=2026-03-14&locale=zh_CN",
]:
    try:
        req = urllib.request.Request(url, headers={
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Referer": "https://yield.chinabond.com.cn/",
            "User-Agent": "Mozilla/5.0",
            "X-Requested-With": "XMLHttpRequest",
        })
        with urllib.request.urlopen(req, timeout=10, context=_SSL_CTX) as r:
            raw = r.read().decode("utf-8")
        print(f"  {url[-40:]}: {raw[:300]}")
    except Exception as e:
        print(f"  {url[-40:]}: {e}")
