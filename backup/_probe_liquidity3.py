"""探测社融+国债收益率正确接口"""
import json, ssl, time, urllib.request, re

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

_HEADERS = {
    "Accept": "*/*",
    "Referer": "https://data.eastmoney.com/",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}

def fetch_raw(url):
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as r:
        return r.read().decode("utf-8")

def fetch_json(url):
    raw = fetch_raw(url)
    m = re.match(r"^\w+\((.*)\)\s*;?\s*$", raw.strip(), re.DOTALL)
    if m:
        raw = m.group(1)
    return json.loads(raw)

ts = int(time.time() * 1000)

# 社融 — 尝试新闻找关键字
print("=== 社融 RPT_ECONOMY_RZMB ===")
for name in ["RPT_ECONOMY_RZMB", "RPT_ECONOMY_FINANCE_INCREMENT",
             "RPT_MACRO_MONEY_SUPPLY", "RPT_ECONOMY_LOAN", "RPT_ECONOMY_BANKLOAN"]:
    try:
        d = fetch_json(f"https://datacenter-web.eastmoney.com/api/data/v1/get?columns=ALL&pageNumber=1&pageSize=1&sortColumns=REPORT_DATE&sortTypes=-1&source=WEB&client=WEB&reportName={name}&_={ts}")
        rows = (d.get("result") or {}).get("data") or []
        if rows:
            print(f"  FOUND: {name}")
            print(json.dumps(rows[0], ensure_ascii=False)[:300])
        else:
            print(f"  {name}: 空")
    except Exception as e:
        print(f"  {name}: {e}")

# 东方财富社融增量数据接口（从页面html获取关键字）
print("\n=== 社融页面探测 ===")
try:
    raw = fetch_raw("https://data.eastmoney.com/cjsj/hjzz.html")
    # 找 reportName
    names = re.findall(r"reportName['\"]?\s*[=:]\s*['\"]([A-Z_]+)['\"]", raw)
    print("找到reportName:", set(names))
except Exception as e:
    print(f"  {e}")

print("\n=== 国债收益率 — 东财债券收益率接口 ===")
# 东财行情 bonds.eastmoney.com 利率债接口
for name in ["RPT_BOND_CBRATE_DAILY", "RPT_ZQSJ_BOND_YIELD",
             "RPT_BOND_YIELD", "RPTA_BOND_CURVE_SPOT",
             "RPT_BOND_SPOTRATECURVE"]:
    try:
        d = fetch_json(f"https://datacenter-web.eastmoney.com/api/data/v1/get?columns=ALL&pageNumber=1&pageSize=1&sortColumns=REPORT_DATE&sortTypes=-1&source=WEB&client=WEB&reportName={name}&_={ts}")
        rows = (d.get("result") or {}).get("data") or []
        if rows:
            print(f"  FOUND: {name}")
            print(json.dumps(rows[0], ensure_ascii=False)[:400])
        else:
            print(f"  {name}: 空")
    except Exception as e:
        print(f"  {name}: {e}")

# 用 push2 行情获取国债期货 T 主力合约，或直接找 10 年国债关键字
print("\n=== push2 国债期货主力合约 ===")
# T 10年期国债期货主力 secid=113.T主
for sid in ["113.T2506", "113.TL2506", "113.T2503"]:
    try:
        url = f"https://push2.eastmoney.com/api/qt/stock/get?fltt=2&invt=2&fields=f2,f3,f4,f12,f14&secid={sid}"
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=10, context=_SSL_CTX) as r:
            data = json.loads(r.read().decode("utf-8"))
        print(f"  {sid}: {data.get('data')}")
    except Exception as e:
        print(f"  {sid}: {e}")

# 中债官方API
print("\n=== 中债 chinabond 官方接口（免费公开）===")
try:
    # 中债官方收益率曲线（免登录公开）
    url_cb = "https://www.chinabond.com.cn/svr/singleQryYld.do?zqdm=0200004&frqType=DAILY&pageIndex=1&pageSize=5&token=&_={}".format(ts)
    req = urllib.request.Request(url_cb, headers={
        "Referer": "https://www.chinabond.com.cn/",
        "User-Agent": "Mozilla/5.0",
        "Accept": "*/*",
    })
    with urllib.request.urlopen(req, timeout=10, context=_SSL_CTX) as r:
        raw = r.read().decode("utf-8")
    print("中债收益率:", raw[:500])
except Exception as e:
    print(f"  失败: {e}")
