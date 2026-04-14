"""通过 JS 文件和中债官方API找社融/国债收益率正确接口"""
import json, ssl, time, urllib.request, re

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

_HEADERS = {
    "Accept": "*/*",
    "Referer": "https://data.eastmoney.com/",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}

def fetch_raw(url, headers=None):
    h = headers or _HEADERS
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as r:
        return r.read().decode("utf-8")

def fetch_json(url):
    raw = fetch_raw(url)
    m = re.match(r"^\w+\((.*)\)\s*;?\s*$", raw.strip(), re.DOTALL)
    if m:
        raw = m.group(1)
    return json.loads(raw)

ts = int(time.time() * 1000)

# 1. 抓取东财社融页面的JS
print("=== 从东财 hjzz.html 对应 JS 找接口名 ===")
try:
    raw = fetch_raw("https://data.eastmoney.com/newstatic/js/cjsj/cn/hjzz.js",
                    headers={**_HEADERS, "Referer": "https://data.eastmoney.com/cjsj/hjzz.html"})
    names = re.findall(r"reportName['\"]?\s*[=:]\s*['\"]([A-Z_]+)['\"]", raw)
    print("社融JS中找到:", set(names))
    # 打印JS内容片段
    idx = raw.find("reportName")
    if idx >= 0:
        print(raw[max(0,idx-100):idx+300])
except Exception as e:
    print(f"  失败: {e}")

# 2. 另找社融JS
print("\n=== 社融 JS (sherongrong.js) ===")
for js in ["shrongrong.js", "hjzz.js", "sfrz.js", "rzrq.js"]:
    try:
        raw = fetch_raw(f"https://data.eastmoney.com/newstatic/js/cjsj/cn/{js}")
        names = re.findall(r"reportName['\"]?\s*[=:]\s*['\"]([A-Z_]+)['\"]", raw)
        if names:
            print(f"  {js}: {set(names)}")
    except:
        pass

# 3. 中债官方收益率 - bond.chinabond.com.cn
print("\n=== 中债信息网 API ===")
for url in [
    "https://yield.chinabond.com.cn/cbweb-czb-web/czb/queryGjqxInfo?workTime=2026-03-14&locale=zh_CN",
    "https://yield.chinabond.com.cn/cbweb-mn-web/mn/queryGjzfsggInfo?workTime=2026-03-14",
]:
    try:
        raw = fetch_raw(url, headers={
            "Referer": "https://yield.chinabond.com.cn/",
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json,*/*",
        })
        print(f"  {url[:60]}:")
        print(f"  {raw[:300]}")
    except Exception as e:
        print(f"  {url[:60]}: {e}")

# 4. 东财固收行情-国债收益率（cnbd datacenter）
print("\n=== 东财 CNBD 国债收益率 ===")
for name in ["RPT_CNBD_CURVE_RATE", "RPTA_CNBD_CURVE_RATE",
             "RPT_BOND_SPOT_RATE", "RPT_MARKET_BOND_RATE"]:
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

# 5. 直接拉取社融增量/存量数据
print("\n=== 社融 sfrz 相关 ===")
for name in ["RPT_SHRONGRONG_SCALE", "RPT_SFRZ_TOTAL",
             "RPT_ECONOMY_SOCIAL_FINANCE_SCALE", "RPT_SHRONGRONG_BYYEAR"]:
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
