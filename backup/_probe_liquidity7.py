"""最终确认可用接口：国债收益率 + 社融"""
import json, ssl, time, urllib.request, re

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

HEADERS = {
    "Accept": "*/*",
    "Referer": "https://data.eastmoney.com/",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}

def fetch_raw(url, headers=None):
    req = urllib.request.Request(url, headers=headers or HEADERS)
    with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as r:
        return r.read().decode("utf-8")

def fetch_json(url, headers=None):
    raw = fetch_raw(url, headers)
    m = re.match(r"^\w+\((.*)\)\s*;?\s*$", raw.strip(), re.DOTALL)
    if m:
        raw = m.group(1)
    return json.loads(raw)

ts = int(time.time() * 1000)

# ── 方案1: push2 行情获取国债现货价格/收益率 ──
# 10年国债代码：sh019757（2026年新发行），sh019753(2025年)等
# 但更可靠的方式：搜索代码包含 "019" 的上海债券
print("=== push2 上海国债搜索 ===")
try:
    # 按关键字搜索
    url = "https://searchapi.eastmoney.com/api/suggest/get?input=10年国债&type=8&token=REMADE&count=5"
    d = fetch_json(url)
    print(json.dumps(d, ensure_ascii=False, indent=2)[:600])
except Exception as e:
    print(f"  搜索: {e}")

# ── 方案2: 东财 债券行情 - 利率债列表 ──
print("\n=== 东财利率债列表 ===")
try:
    url = f"https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=5&po=1&np=1&fltt=2&invt=2&fid=f3&fs=b:MK0354&fields=f2,f3,f12,f14,f15,f23&_={ts}"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=10, context=_SSL_CTX) as r:
        data = json.loads(r.read().decode("utf-8"))
    items = (data.get("data") or {}).get("diff") or []
    for item in items[:5]:
        print(f"  {item}")
except Exception as e:
    print(f"  利率债: {e}")

# ── 方案3: 直接用中债国债收益率公开查询 ──
# 中债信息网开放了公开查询接口
print("\n=== 中债收益率 JSON 接口 ===")
for path in [
    "/cbweb-czb-web/czb/queryGjqxInfo?workTime=2026-03-14&locale=zh_CN",
    "/cbweb-pbc-web/pbc/queryBuyBackInfo?workTime=2026-03-14&locale=zh_CN",
]:
    try:
        raw = fetch_raw(
            f"https://yield.chinabond.com.cn{path}",
            headers={
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Referer": "https://yield.chinabond.com.cn/cbweb-czb-web/czb/showDetailGjqxInfo?locale=zh_CN",
                "User-Agent": "Mozilla/5.0",
                "X-Requested-With": "XMLHttpRequest",
            }
        )
        print(f"  {path}: {raw[:300]}")
    except Exception as e:
        print(f"  {path}: {e}")

# ── 方案4: 东财 iFind 接口（万得 wind 数据源）──
print("\n=== 东财另类接口 - 国债 ===")
# 搜索有没有宏观数据接口
for name in ["RPT_MACRO_LEND_RATE", "RPT_ECONOMY_INTEREST_RATE",
             "RPTA_MACRO_LEND_RATE", "RPT_ECONOMY_LPR"]:
    try:
        d = fetch_json(f"https://datacenter-web.eastmoney.com/api/data/v1/get?columns=ALL&pageNumber=1&pageSize=2&sortColumns=REPORT_DATE&sortTypes=-1&source=WEB&client=WEB&reportName={name}&_={ts}")
        rows = (d.get("result") or {}).get("data") or []
        if rows:
            print(f"  FOUND: {name}")
            print(json.dumps(rows[0], ensure_ascii=False)[:400])
        else:
            code = d.get("code")
            msg  = d.get("message","")
            print(f"  {name}: code={code} {msg}")
    except Exception as e:
        print(f"  {name}: {e}")

# ── 方案5: 用 push2 获取 国债期货结算价换算收益率 ──
print("\n=== push2 债券期货/现券行情 ===")
# T 10年国债期货2506合约
for sid in ["113.T2506", "113.T2503", "1.019747", "1.019748", "1.019749",
            "1.019750", "1.019751", "1.019752", "1.019753"]:
    try:
        url = f"https://push2.eastmoney.com/api/qt/stock/get?fltt=2&invt=2&fields=f2,f3,f4,f12,f14,f58&secid={sid}"
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=8, context=_SSL_CTX) as r:
            data = json.loads(r.read().decode("utf-8"))
        d = data.get("data")
        if d and d.get("f14"):
            print(f"  {sid}: name={d.get('f14')} price={d.get('f2')} chg%={d.get('f3')}")
    except Exception as e:
        print(f"  {sid}: {e}")

# ── 方案6: 专门找10年国债代码 ──
print("\n=== 专项搜索10年国债 ===")
try:
    url = "https://searchapi.eastmoney.com/api/suggest/get?input=019753&type=8,0&token=REMADE&count=3"
    d = fetch_json(url)
    print(json.dumps(d, ensure_ascii=False)[:400])
except Exception as e:
    print(f"  {e}")
