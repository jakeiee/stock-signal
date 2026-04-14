"""
尝试国家统计局居民人均可支配收入页面使用的真实参数。
图中显示的是"居民人均可支配收入累计值(元)"和"累计增长(%)"，
这是季度数据库中的两个不同指标。
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

def probe_with_wds(dbcode, zb_code, desc):
    """用具体的指标代码查询"""
    ts = int(time.time() * 1000)
    # 查询特定指标的历史数据
    import urllib.parse
    wds_param = urllib.parse.quote(json.dumps([{"wdcode": "zb", "valuecode": zb_code}]))
    dfwds_param = urllib.parse.quote(json.dumps([{"wdcode": "sj", "valuecode": "LAST10"}]))
    url = (
        f"https://data.stats.gov.cn/easyquery.htm"
        f"?m=QueryData&dbcode={dbcode}&rowcode=sj&colcode=zb"
        f"&wds={wds_param}"
        f"&dfwds={dfwds_param}"
        f"&k1={ts}"
    )
    print(f"\n{'='*60}")
    print(f"[{desc}] dbcode={dbcode}, code={zb_code}")
    print(f"[接口URL] {url}")
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10, context=ssl_ctx) as resp:
            raw = resp.read().decode("utf-8")
        data = json.loads(raw)
        returndata = data.get("returndata", {})
        datanodes = returndata.get("datanodes", [])
        print(f"  datanodes数={len(datanodes)}")
        for node in datanodes[:8]:
            code = node.get("code", "")
            val = node.get("data", {}).get("data")
            print(f"  code={code}  data={val}")
    except Exception as e:
        print(f"  [失败] {e}")
    time.sleep(0.3)

# hgjd 数据库中，根据wdnodes全部列表，找跟居民收入相关的code
# 先把hgjd全部指标代码打出来
ts = int(time.time() * 1000)
url_all = (
    f"https://data.stats.gov.cn/easyquery.htm"
    f"?m=QueryData&dbcode=hgjd&rowcode=zb&colcode=sj"
    f"&wds=%5B%5D"
    f"&dfwds=%5B%7B%22wdcode%22%3A%22sj%22%2C%22valuecode%22%3A%22LAST6%22%7D%5D"
    f"&k1={ts}"
)
print(f"[接口URL hgjd全部指标] {url_all}")
req = urllib.request.Request(url_all, headers=HEADERS)
with urllib.request.urlopen(req, timeout=15, context=ssl_ctx) as resp:
    raw = resp.read().decode("utf-8")
data = json.loads(raw)
returndata = data.get("returndata", {})
wdnodes = returndata.get("wdnodes", [])
nodes = wdnodes[0].get("nodes", []) if wdnodes else []
print(f"\nhgjd 全部 {len(nodes)} 个指标:")
for n in nodes:
    name = n.get("name", "")
    code = n.get("code", "")
    unit = n.get("unit", "")
    print(f"  code={code}  unit={unit}  name={name}")

# 找出所有 datanodes 里值在 0-20 范围内的
datanodes = returndata.get("datanodes", [])
print(f"\n[可能是增速的数据节点 (0<val<20)]:")
for node in datanodes:
    val = node.get("data", {}).get("data")
    code = node.get("code", "")
    if val is not None and 0 < float(val) < 20:
        print(f"  code={code}  data={val}")
