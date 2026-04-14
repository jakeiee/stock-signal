"""
深度探查：找到居民人均可支配收入同比增速(%)的正确接口。
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

def probe_dbcode(dbcode, desc=""):
    ts = int(time.time() * 1000)
    url = (
        f"https://data.stats.gov.cn/easyquery.htm"
        f"?m=QueryData&dbcode={dbcode}&rowcode=zb&colcode=sj"
        f"&wds=%5B%5D"
        f"&dfwds=%5B%7B%22wdcode%22%3A%22sj%22%2C%22valuecode%22%3A%22LAST10%22%7D%5D"
        f"&k1={ts}"
    )
    print(f"\n{'='*60}")
    print(f"dbcode={dbcode}  {desc}")
    print(f"[接口URL] {url}")
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10, context=ssl_ctx) as resp:
            raw = resp.read().decode("utf-8")
        data = json.loads(raw)
        returndata = data.get("returndata", {})
        wdnodes = returndata.get("wdnodes", [])
        datanodes = returndata.get("datanodes", [])
        nodes = wdnodes[0].get("nodes", []) if wdnodes else []
        print(f"  指标数={len(nodes)}, datanodes数={len(datanodes)}")
        # 打印包含"居民"或"收入"或"可支配"字样的指标
        income_codes = []
        for n in nodes:
            name = n.get("name", "")
            if any(k in name for k in ["居民", "收入", "可支配", "income"]):
                print(f"  ★ code={n.get('code')}  name={name}  unit={n.get('unit')}")
                income_codes.append(n.get("code"))
        if not income_codes:
            # 打印前5个指标名称
            for n in nodes[:5]:
                print(f"  - code={n.get('code')}  name={n.get('name')}")
        # 查找可能是增速的datanodes
        for node in datanodes:
            val = node.get("data", {}).get("data")
            code = node.get("code", "")
            if val is not None and 0 < float(val) < 15:
                for ic in income_codes:
                    if ic in code:
                        print(f"  [增速候选] code={code}  data={val}")
        print(f"[原始数据] {json.dumps(data, ensure_ascii=False)[:300]}")
    except Exception as e:
        print(f"  [失败] {e}")
    time.sleep(0.3)

# 尝试可能含有居民收入的 dbcode
dbcodes = [
    ("hgjd2", "季度2"),
    ("hgjd3", "季度3"),
    ("hgjd4", "季度4"),
    ("hgjd5", "季度5"),
    ("hgjd6", "季度6"),
    ("hgjd7", "季度7"),
    ("hgjd8", "季度8"),
    ("hgjd9", "季度9"),
    ("hgjda", "季度a"),
    ("hgjdb", "季度b"),
    ("hgjdc", "居民收入?"),
    ("hgjdd", "居民收入?"),
    ("hgjde", "居民收入?"),
]

for dbcode, desc in dbcodes:
    probe_dbcode(dbcode, desc)
