"""通过东财 bonds 频道页面找正确的收益率接口名"""
import json, ssl, time, urllib.request, re

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://bonds.eastmoney.com/",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}

def fetch_raw(url, h=None):
    req = urllib.request.Request(url, headers=h or HEADERS)
    with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as r:
        return r.read().decode("utf-8")

def fetch_json(url, h=None):
    raw = fetch_raw(url, h)
    m = re.match(r"^\w+\((.*)\)\s*;?\s*$", raw.strip(), re.DOTALL)
    if m:
        raw = m.group(1)
    return json.loads(raw)

ts = int(time.time() * 1000)

# 从 bonds.eastmoney.com 国债收益率页面找接口
print("=== bonds.eastmoney.com 国债收益率页面 ===")
try:
    raw = fetch_raw("https://bonds.eastmoney.com/guozhai.html")
    # 提取所有 datacenter API 调用
    apis = re.findall(r"reportName=([A-Z_]+)", raw)
    print("reportNames:", set(apis))
    # 提取 JS 文件路径
    scripts = re.findall(r'src=["\']([^"\']*\.js[^"\']*)["\']', raw)
    for s in scripts:
        if "bond" in s.lower() or "eastmoney" in s.lower():
            print(f"  JS: {s}")
except Exception as e:
    print(f"  {e}")

# 尝试 bonds 专用 JS
print("\n=== bonds JS 文件 ===")
for js in [
    "https://bonds.eastmoney.com/js/guozhai.js",
    "https://bonds.eastmoney.com/newstatic/js/guozhai.js",
    "https://bonds.eastmoney.com/static/js/guozhai.js",
]:
    try:
        raw = fetch_raw(js, h={"Accept": "*/*", "User-Agent": "Mozilla/5.0", "Referer": "https://bonds.eastmoney.com/"})
        apis = re.findall(r"reportName['\"]?\s*[=:]\s*['\"]([A-Z_]+)['\"]", raw)
        if apis:
            print(f"  {js}: {set(apis)}")
    except Exception as e:
        print(f"  {js}: {e}")

# 直接用东财宏观数据 JSON API 查询
print("\n=== 东财宏观利率 ===")
# 发现东财有一个专门的宏观利率接口
for name in [
    "RPT_ECONOMY_INTEREST",
    "RPT_ECONOMY_CB_RATE",
    "RPT_ECONOMYB_RATE",
    "RPTA_ECONOMY_INTEREST_RATE",
    "RPTA_ECONOMY_CB_RATE",
    "RPT_ECONOMY_BENCHMARK_RATE",
]:
    try:
        d = fetch_json(
            f"https://datacenter-web.eastmoney.com/api/data/v1/get?columns=ALL&pageNumber=1&pageSize=2&sortColumns=REPORT_DATE&sortTypes=-1&source=WEB&client=WEB&reportName={name}&_={ts}",
            h={"Accept": "*/*", "Referer": "https://data.eastmoney.com/", "User-Agent": "Mozilla/5.0"}
        )
        rows = (d.get("result") or {}).get("data") or []
        if rows:
            print(f"\n  FOUND: {name}")
            print(json.dumps(rows[0], ensure_ascii=False)[:400])
        elif str(d.get("code","")) != "9501":
            print(f"  {name}: {d}")
    except Exception as e:
        if "9501" not in str(e):
            print(f"  {name}: {e}")

# 社融 — 从人民银行数据发布获取
print("\n=== 人民银行公开数据 ===")
try:
    # PBOC 统计数据 - 社会融资规模
    raw = fetch_raw(
        "https://www.pbc.gov.cn/diaochatongji/116219/116225/116237/index.html",
        h={"Accept": "text/html", "User-Agent": "Mozilla/5.0", "Referer": "https://www.pbc.gov.cn/"}
    )
    print(f"  PBOC响应长度: {len(raw)}")
    links = re.findall(r'href=["\']([^"\']+社融[^"\']*)["\']', raw)
    print(f"  社融链接: {links[:3]}")
except Exception as e:
    print(f"  PBOC: {e}")

# 东财宏观 cjsj 数据接口（直接传入 sfrz 相关 URL 参数）
print("\n=== 东财社融增量数据接口 (具体参数) ===")
try:
    url = f"https://datacenter-web.eastmoney.com/api/data/v1/get?columns=REPORT_DATE%2CTIME%2CSCALE%2CSCALE_SAME%2CSCALE_SEQUENTIAL%2CTOTAL_SCALE%2CTOTAL_SAME&pageNumber=1&pageSize=3&sortColumns=REPORT_DATE&sortTypes=-1&source=WEB&client=WEB&reportName=RPT_ECONOMY_SHRONGRONG&_={ts}"
    d = fetch_json(url)
    print(f"  result: {d}")
except Exception as e:
    print(f"  {e}")
