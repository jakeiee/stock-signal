"""
探查国家统计局居民人均可支配收入的正确接口。
目标：找到"居民人均可支配收入累计增长(%)"字段，即图中的5.0%/5.2%等。
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

def probe(dbcode, desc):
    ts = int(time.time() * 1000)
    url = (
        f"https://data.stats.gov.cn/easyquery.htm"
        f"?m=QueryData&dbcode={dbcode}&rowcode=zb&colcode=sj"
        f"&wds=%5B%5D"
        f"&dfwds=%5B%7B%22wdcode%22%3A%22sj%22%2C%22valuecode%22%3A%22LAST12%22%7D%5D"
        f"&k1={ts}"
    )
    print(f"\n{'='*60}")
    print(f"[{desc}] dbcode={dbcode}")
    print(f"[接口URL] {url}")
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=12, context=ssl_ctx) as resp:
            raw = resp.read().decode("utf-8")
        data = json.loads(raw)
        print(f"[原始数据] {json.dumps(data, ensure_ascii=False)[:400]}")
        print()
        returndata = data.get("returndata", {})
        wdnodes = returndata.get("wdnodes", [])
        datanodes = returndata.get("datanodes", [])
        # 打印指标列表
        nodes = wdnodes[0].get("nodes", []) if wdnodes else []
        print(f"  指标数={len(nodes)}, datanodes数={len(datanodes)}")
        for n in nodes[:15]:
            print(f"    code={n.get('code')}  name={n.get('name')}  unit={n.get('unit')}")
        # 找到0-20范围内的值（可能是增速%）
        print(f"  [可能的增速字段]")
        for node in datanodes:
            val = node.get("data", {}).get("data")
            if val is not None and 0 < float(val) < 20:
                print(f"    code={node.get('code')}  data={val}")
    except Exception as e:
        print(f"  [失败] {e}")

# 尝试各种 dbcode
probe("hgjd", "季度数据-居民收入/GDP")    # 季度基础
probe("hgyd", "月度数据")                   # 月度
probe("hgnd", "年度数据")                   # 年度
probe("fsyd", "分省月度")                   # 分省月度
