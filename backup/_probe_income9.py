"""
用不同方式查询 A0501（全国居民人均收入情况）的数据，找到增速字段。
关键：rowcode和colcode的排列方式影响返回的wdnodes中的指标列表。
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

def query(wds_list, dfwds_list, rowcode="zb", colcode="sj", dbcode="hgjd"):
    ts = int(time.time() * 1000)
    wds = urllib.parse.quote(json.dumps(wds_list))
    dfwds = urllib.parse.quote(json.dumps(dfwds_list))
    url = (
        f"https://data.stats.gov.cn/easyquery.htm"
        f"?m=QueryData&dbcode={dbcode}&rowcode={rowcode}&colcode={colcode}"
        f"&wds={wds}&dfwds={dfwds}&k1={ts}"
    )
    print(f"\n[接口URL] {url}")
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=12, context=ssl_ctx) as resp:
        raw = resp.read().decode("utf-8")
    data = json.loads(raw)
    returndata = data.get("returndata", {})
    wdnodes = returndata.get("wdnodes", [])
    datanodes = returndata.get("datanodes", [])
    nodes = wdnodes[0].get("nodes", []) if wdnodes else []
    print(f"[原始数据片段] {json.dumps(data, ensure_ascii=False)[:500]}")
    print(f"  指标数={len(nodes)}, datanodes数={len(datanodes)}")
    for n in nodes:
        name = n.get("name", "")
        code = n.get("code", "")
        unit = n.get("unit", "")
        if any(k in name for k in ["居民", "收入", "可支配", "人均", "增长", "增速", "同比"]):
            print(f"  ★ code={code}  unit={unit}  name={name}")
        else:
            print(f"    code={code}  unit={unit}  name={name}")
    # 打印0-15范围内的datanodes
    for node in datanodes:
        val = node.get("data", {}).get("data")
        code = node.get("code", "")
        if val is not None and 0 < float(val) < 15:
            print(f"  [增速候选] code={code}  data={val}")
    time.sleep(0.3)
    return datanodes

# 方式1: wds=A0501，dfwds=LAST10，按 zb 为行
print("=== 方式1: rowcode=sj, colcode=zb, wds=A0501 ===")
query(
    wds_list=[],
    dfwds_list=[{"wdcode": "zb", "valuecode": "A0501"}, {"wdcode": "sj", "valuecode": "LAST10"}],
    rowcode="sj",
    colcode="zb",
)

# 方式2: wds=[A0501的父级], dfwds=time
print("\n=== 方式2: 用 A0501 作为 dfwds ===")
query(
    wds_list=[{"wdcode": "sj", "valuecode": "2025D"}],
    dfwds_list=[{"wdcode": "zb", "valuecode": "A0501"}],
    rowcode="zb",
    colcode="sj",
)

# 方式3: 通过查询 hgjd 并限定 A05（人民生活）
print("\n=== 方式3: 限定 A05 查 hgjd ===")
query(
    wds_list=[],
    dfwds_list=[{"wdcode": "zb", "valuecode": "A05"}, {"wdcode": "sj", "valuecode": "LAST8"}],
    rowcode="zb",
    colcode="sj",
)
