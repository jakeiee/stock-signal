"""
找到居民人均可支配收入"累计增长(%)"的具体 valuecode。
方法：直接查国家统计局页面源码中的指标tree，或者用 getTree 查 A0501 的子叶。
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
    "Referer": "https://data.stats.gov.cn/easyquery.htm?cn=B01",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "X-Requested-With": "XMLHttpRequest",
}

# getTree 对 A0501（全国居民人均收入情况）展开子节点
ts = int(time.time() * 1000)
url = f"https://data.stats.gov.cn/easyquery.htm?m=getTree&dbcode=hgjd&wdcode=zb&id=A0501&k1={ts}"
print(f"[接口URL] {url}")
req = urllib.request.Request(url, headers=HEADERS)
with urllib.request.urlopen(req, timeout=12, context=ssl_ctx) as resp:
    raw = resp.read().decode("utf-8")
data = json.loads(raw)
print(f"[原始数据] {json.dumps(data, ensure_ascii=False)}")
print("\nA0501 叶子节点（具体指标）:")
for item in data:
    id_ = item.get("id")
    name = item.get("name", "")
    print(f"  id={id_}  name={name}  isParent={item.get('isParent')}")

# 找到"累计增长"相关的 code
print()
growth_codes = []
for item in data:
    name = item.get("name", "")
    id_ = item.get("id")
    if any(k in name for k in ["增长", "增速", "同比", "%", "增"]):
        print(f"★ 增速相关: id={id_}  name={name}")
        growth_codes.append(id_)

# 用找到的增速code查询数据
if growth_codes:
    print("\n=== 用增速指标code查询数据 ===")
    for code in growth_codes[:3]:
        ts = int(time.time() * 1000)
        import urllib.parse
        wds = urllib.parse.quote(json.dumps([{"wdcode": "zb", "valuecode": code}]))
        dfwds = urllib.parse.quote(json.dumps([{"wdcode": "sj", "valuecode": "LAST8"}]))
        url2 = (
            f"https://data.stats.gov.cn/easyquery.htm"
            f"?m=QueryData&dbcode=hgjd&rowcode=sj&colcode=zb"
            f"&wds={wds}&dfwds={dfwds}&k1={ts}"
        )
        print(f"\n[接口URL] code={code}: {url2}")
        req2 = urllib.request.Request(url2, headers=HEADERS)
        with urllib.request.urlopen(req2, timeout=12, context=ssl_ctx) as resp2:
            raw2 = resp2.read().decode("utf-8")
        d2 = json.loads(raw2)
        nodes2 = d2.get("returndata", {}).get("datanodes", [])
        print(f"  datanodes数={len(nodes2)}")
        for n in nodes2[:6]:
            print(f"  code={n.get('code')}  data={n.get('data',{}).get('data')}")
        time.sleep(0.3)
