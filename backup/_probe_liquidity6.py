"""寻找社融存量同比和10年国债收益率的可用接口"""
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

# ── 方案A: 东财专门的社融接口（可能在 datacenter2） ──
print("=== 社融 datacenter2 ===")
for host in ["datacenter-web.eastmoney.com", "datacenter2.eastmoney.com"]:
    for name in ["RPT_ECONOMY_RZMB", "RPT_ECONOMY_SHRONGRONG", "SHRONGRONG_ALL"]:
        try:
            url = f"https://{host}/api/data/v1/get?columns=ALL&pageNumber=1&pageSize=1&sortColumns=REPORT_DATE&sortTypes=-1&source=WEB&client=WEB&reportName={name}&_={ts}"
            d = fetch_json(url)
            rows = (d.get("result") or {}).get("data") or []
            if rows:
                print(f"  FOUND: {host}/{name}")
                print(json.dumps(rows[0], ensure_ascii=False)[:300])
            else:
                code = d.get("code")
                if code not in (None, 0, "0"):
                    print(f"  {host}/{name}: code={code}")
        except Exception as e:
            if "404" not in str(e):
                print(f"  {host}/{name}: {e}")

# ── 方案B: M2 接口中直接有社融相关字段 ──
print("\n=== M2 接口字段完整版 ===")
d = fetch_json(f"https://datacenter-web.eastmoney.com/api/data/v1/get?columns=ALL&pageNumber=1&pageSize=2&sortColumns=REPORT_DATE&sortTypes=-1&source=WEB&client=WEB&reportName=RPT_ECONOMY_CURRENCY_SUPPLY&_={ts}")
rows = (d.get("result") or {}).get("data") or []
for r in rows[:1]:
    print(json.dumps(r, ensure_ascii=False, indent=2))

# ── 方案C: 国债期货行情接口（有实时价格和隐含收益率）──
print("\n=== 东财 10年国债收益率 (行情快照) ===")
# 10年国债期货主力：T 合约
for sid in ["113.T2506", "113.T2503", "113.TF2506"]:
    try:
        url = f"https://push2.eastmoney.com/api/qt/stock/get?fltt=2&invt=2&fields=f2,f3,f4,f5,f6,f12,f14,f15,f16,f17,f18,f23&secid={sid}"
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10, context=_SSL_CTX) as r:
            data = json.loads(r.read().decode("utf-8"))
        if data.get("data"):
            print(f"  {sid}: {data['data']}")
    except Exception as e:
        print(f"  {sid}: {e}")

# ── 方案D: 中债官方信息网 - 国债收益率 HTML 解析 ──
print("\n=== 中债官网国债收益率 ===")
# 中债信息网提供公开的收益率曲线数据（HTML表格），可以爬取解析
try:
    req = urllib.request.Request(
        "https://yield.chinabond.com.cn/cbweb-czb-web/czb/showDetailGjqxInfo?locale=zh_CN",
        headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://yield.chinabond.com.cn/",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        }
    )
    with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as r:
        raw = r.read().decode("utf-8")
    # 提取表格数据
    rows_html = re.findall(r'<tr[^>]*>(.*?)</tr>', raw, re.DOTALL)
    for tr in rows_html[:8]:
        cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', tr, re.DOTALL)
        cleaned = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
        if any(cleaned):
            print(f"  {cleaned}")
except Exception as e:
    print(f"  中债收益率: {e}")

# ── 方案E: 东财 bonds datacenter 新接口 ──
print("\n=== 东财债券收益率曲线 ===")
try:
    # 东财债券行情收益率，有专门的接口
    url = f"https://datacenter-web.eastmoney.com/api/data/v1/get?columns=ALL&pageNumber=1&pageSize=5&sortColumns=DATES&sortTypes=-1&source=WEB&client=WEB&reportName=RPT_CNBD_YLDCVR&_={ts}"
    d = fetch_json(url)
    rows = (d.get("result") or {}).get("data") or []
    if rows:
        print("  FOUND RPT_CNBD_YLDCVR")
        print(json.dumps(rows[0], ensure_ascii=False)[:400])
    else:
        print(f"  RPT_CNBD_YLDCVR: code={d.get('code')}")
except Exception as e:
    print(f"  RPT_CNBD_YLDCVR: {e}")

# ── 方案F: 通过东财 bonds 页面找社融 ──
print("\n=== 东财债券/利率接口 ===")
for name in ["RPT_CNBD_CURVE", "RPTA_CNBD_SPOT_RATE",
             "RPT_CNBD_INTEREST_RATE", "RPT_CNBD_CURVE_HIST"]:
    try:
        url = f"https://datacenter-web.eastmoney.com/api/data/v1/get?columns=ALL&pageNumber=1&pageSize=2&sortColumns=REPORT_DATE&sortTypes=-1&source=WEB&client=WEB&reportName={name}&_={ts}"
        d = fetch_json(url)
        rows = (d.get("result") or {}).get("data") or []
        if rows:
            print(f"  FOUND: {name}")
            print(json.dumps(rows[0], ensure_ascii=False)[:400])
    except:
        pass
