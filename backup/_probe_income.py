"""
探查国家统计局居民人均可支配收入 API 的原始数据结构。
目标：找到"累计增长(%)"字段对应的 code，而非绝对金额。
"""
import urllib.request
import json
import ssl
import time

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://data.stats.gov.cn/",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "X-Requested-With": "XMLHttpRequest",
}

ts = int(time.time() * 1000)
url = (
    f"https://data.stats.gov.cn/easyquery.htm"
    f"?m=QueryData&dbcode=hgjd&rowcode=zb&colcode=sj"
    f"&wds=%5B%5D"
    f"&dfwds=%5B%7B%22wdcode%22%3A%22sj%22%2C%22valuecode%22%3A%22LAST18%22%7D%5D"
    f"&k1={ts}"
)

print(f"[接口URL] {url}")

req = urllib.request.Request(url, headers=HEADERS)
with urllib.request.urlopen(req, timeout=15, context=ssl_ctx) as resp:
    raw = resp.read().decode("utf-8")

data = json.loads(raw)
print(f"[原始数据] {json.dumps(data, ensure_ascii=False)[:800]}")
print()

returndata = data.get("returndata", {})
datanodes = returndata.get("datanodes", [])
wdnodes = returndata.get("wdnodes", [])

print("=== wdnodes（指标树）===")
print(json.dumps(wdnodes, ensure_ascii=False, indent=2)[:3000])
print()

print(f"=== datanodes 共 {len(datanodes)} 条 ===")
for i, node in enumerate(datanodes):
    code = node.get("code", "")
    val  = node.get("data", {}).get("data")
    sval = node.get("data", {}).get("strdata")
    # 只打印数值在 0-20 范围内的节点（可能是同比增速%）
    if val is not None and 0 < float(val) < 20:
        print(f"  [可能是增速] [{i}] code={code}  data={val}  strdata={sval}")

print()
print("=== 全部 datanodes（前30条）===")
for i, node in enumerate(datanodes[:30]):
    code = node.get("code", "")
    val  = node.get("data", {}).get("data")
    sval = node.get("data", {}).get("strdata")
    print(f"  [{i:02d}] code={code}  data={val}  strdata={sval}")
