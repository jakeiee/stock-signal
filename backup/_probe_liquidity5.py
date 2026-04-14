"""通过抓取实际页面 HTML 找社融接口 + 中债收益率 JSON 接口"""
import json, ssl, time, urllib.request, re

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

def fetch_raw(url, headers=None):
    h = headers or {
        "Accept": "*/*",
        "Referer": "https://data.eastmoney.com/",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    }
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as r:
        return r.read().decode("utf-8")

ts = int(time.time() * 1000)

# 1. 东财社融页面（实际社融数据页面是 sfrz.html）
print("=== 东财社融页面 sfrz ===")
try:
    raw = fetch_raw("https://data.eastmoney.com/cjsj/sfrz.html")
    names = re.findall(r"reportName['\"]?\s*[=:]\s*['\"]([A-Z_]+)['\"]", raw)
    print("reportName:", set(names))
    # 找 datacenter 接口 URL
    urls = re.findall(r"datacenter-web\.eastmoney\.com/api/data/v1/get[^'\"\\s]*", raw)
    print("datacenter URLs:", urls[:5])
    # 找 callback 名/report
    snippets = re.findall(r".{0,100}RPT[A-Z_]+.{0,100}", raw)
    for s in snippets[:5]:
        print(s)
except Exception as e:
    print(f"  {e}")

# 2. 东财社融专项 JS
print("\n=== cjsj JS 列表 ===")
try:
    raw = fetch_raw("https://data.eastmoney.com/cjsj/sfrz.html")
    # 找所有 js 引用
    scripts = re.findall(r'src=["\']([^"\']+\.js[^"\']*)["\']', raw)
    for s in scripts:
        if "cjsj" in s or "eastmoney" in s:
            print(f"  {s}")
except Exception as e:
    print(f"  {e}")

# 3. 中债收益率 - queryGjqx 接口（需要 session，直接请求）
print("\n=== 中债收益率 API ===")
try:
    # 中债官方 QueryGjqx（国债期限结构数据）
    raw = fetch_raw(
        "https://yield.chinabond.com.cn/cbweb-czb-web/czb/queryGjqxInfo?workTime=2026-03-14&locale=zh_CN",
        headers={
            "Accept": "text/javascript, application/javascript, application/ecmascript, application/x-ecmascript, */*; q=0.01",
            "Referer": "https://yield.chinabond.com.cn/cbweb-czb-web/czb/showDetailGjqxInfo?locale=zh_CN",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "X-Requested-With": "XMLHttpRequest",
        }
    )
    print(f"  原始响应({len(raw)}字节):", raw[:500])
except Exception as e:
    print(f"  中债 queryGjqxInfo: {e}")

# 4. 国家统计局直接接口
print("\n=== 国家统计局社融相关 ===")
try:
    # NBS开放API，社融存量同比
    raw = fetch_raw(
        "https://data.stats.gov.cn/easyquery.htm?cn=A01&zb=A070O&sj=202601&m=queryData",
        headers={
            "Referer": "https://data.stats.gov.cn/",
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
        }
    )
    print(f"  NBS响应:", raw[:300])
except Exception as e:
    print(f"  NBS: {e}")

# 5. 东财社融 - 另一个可能的 URL
print("\n=== 尝试东财 sfrz JS ===")
for js_url in [
    "https://data.eastmoney.com/newstatic/js/cjsj/cn/sfrz.js",
    "https://data.eastmoney.com/newstatic/js/cjsj/sfrz.js",
]:
    try:
        raw = fetch_raw(js_url)
        names = re.findall(r"reportName['\"]?\s*[=:]\s*['\"]([A-Z_]+)['\"]", raw)
        api_parts = re.findall(r"RPT[A-Z_]+", raw)
        if names or api_parts:
            print(f"  {js_url}: reportNames={set(names)}, RPT words={set(api_parts[:10])}")
    except Exception as e:
        print(f"  {js_url}: {e}")
