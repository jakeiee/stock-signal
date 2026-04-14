"""
探查国家统计局社融数据接口
接口URL: https://data.stats.gov.cn/easyquery.htm?m=QueryData&dbcode=hgnd&rowcode=zb&colcode=sj&wds=[]&dfwds=[{"wdcode":"sj","valuecode":"LAST20"}]
"""
import json
import ssl
import time
import urllib.parse
import urllib.request

# SSL 配置
ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://data.stats.gov.cn/easyquery.htm?cn=C01",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "X-Requested-With": "XMLHttpRequest",
}

def fetch_social_finance():
    ts = int(time.time() * 1000)
    dfwds = urllib.parse.quote(json.dumps([{"wdcode": "sj", "valuecode": "LAST20"}]))
    url = (
        f"https://data.stats.gov.cn/easyquery.htm"
        f"?m=QueryData&dbcode=hgnd&rowcode=zb&colcode=sj"
        f"&wds=%5B%5D&dfwds={dfwds}&k1={ts}"
    )
    
    print(f"[接口URL] {url}")
    
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15, context=ssl_ctx) as resp:
        raw = resp.read().decode("utf-8")
    
    data = json.loads(raw)
    print(f"[原始数据] {json.dumps(data, ensure_ascii=False)[:800]}")
    
    returndata = data.get("returndata", {})
    wdnodes = returndata.get("wdnodes", [])
    datanodes = returndata.get("datanodes", [])
    
    # 打印指标信息
    print(f"\n[指标列表]")
    for wd in wdnodes:
        nodes = wd.get("nodes", [])
        for n in nodes:
            print(f"  code={n.get('code')} name={n.get('name')} unit={n.get('unit')}")
    
    # 查找社融数据（社会融资规模）
    print(f"\n[数据节点] 共 {len(datanodes)} 条")
    sf_data = {}
    for node in datanodes:
        code = node.get("code", "")
        val = node.get("data", {}).get("data")
        hasdata = node.get("data", {}).get("hasdata", False)
        
        # 打印所有数据节点（用于定位社融字段）
        if val and hasdata:
            print(f"  code={code} val={val}")
            # 社融指标代码通常是 A0L08 或类似
            if "A0L08" in code or "SOCIAL" in code.upper() or "FINANCE" in code.upper():
                # 提取年份: zb.A0L08_sj.2025 -> 2025
                year = code.split(".")[-1]
                sf_data[year] = val
                print(f"    ★ 社融数据: {year}年 = {val}亿元")
    
    return sf_data

if __name__ == "__main__":
    result = fetch_social_finance()
    print(f"\n[最终结果] 社融年度数据: {result}")
