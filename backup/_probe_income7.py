"""
用 A0501（全国居民人均收入情况）查询数据，找到"累计增长(%)"字段。
"""
import urllib.request
import json
import ssl
import time
import urllib.parse

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://data.stats.gov.cn/easyquery.htm?cn=B01",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "X-Requested-With": "XMLHttpRequest",
}

ts = int(time.time() * 1000)

# 用 wds 限定 zb=A0501（全国居民人均收入情况），查询最近10季度
wds = urllib.parse.quote(json.dumps([{"wdcode": "zb", "valuecode": "A0501"}]))
dfwds = urllib.parse.quote(json.dumps([{"wdcode": "sj", "valuecode": "LAST10"}]))

url = (
    f"https://data.stats.gov.cn/easyquery.htm"
    f"?m=QueryData&dbcode=hgjd&rowcode=zb&colcode=sj"
    f"&wds={wds}"
    f"&dfwds={dfwds}"
    f"&k1={ts}"
)

print(f"[接口URL] {url}")

req = urllib.request.Request(url, headers=HEADERS)
with urllib.request.urlopen(req, timeout=15, context=ssl_ctx) as resp:
    raw = resp.read().decode("utf-8")
data = json.loads(raw)

print(f"[原始数据] {json.dumps(data, ensure_ascii=False)[:1000]}")
print()

returndata = data.get("returndata", {})
wdnodes = returndata.get("wdnodes", [])
datanodes = returndata.get("datanodes", [])

# 打印全部指标
print("=== A0501 全部指标 ===")
nodes = wdnodes[0].get("nodes", []) if wdnodes else []
for n in nodes:
    print(f"  code={n.get('code')}  unit={n.get('unit')}  name={n.get('name')}")

print(f"\n=== datanodes 共 {len(datanodes)} 条 ===")
print("=== 全部数据（2025年各季度）===")
for node in datanodes:
    code = node.get("code", "")
    val = node.get("data", {}).get("data")
    sval = node.get("data", {}).get("strdata")
    if "2025" in code:
        print(f"  code={code}  data={val}  strdata={sval}")

print("\n=== 可能是同比增速的数据（0-15范围）===")
for node in datanodes:
    code = node.get("code", "")
    val = node.get("data", {}).get("data")
    if val is not None and 0 < float(val) < 15:
        print(f"  code={code}  data={val}")

# 打印所有有效数据
print("\n=== 全部有效数据（前50条）===")
valid = [(n.get("code"), n.get("data", {}).get("data")) for n in datanodes if n.get("data", {}).get("hasdata")]
for code, val in valid[:50]:
    print(f"  code={code}  data={val}")
