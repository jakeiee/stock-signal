"""
探查社融数据 - 使用 A0L08 指标代码
用户截图URL: https://data.stats.gov.cn/easyquery.htm?cn=C01&zb=A0L08&sj=2025
"""
import json
import ssl
import time
import urllib.parse
import urllib.request

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://data.stats.gov.cn/easyquery.htm?cn=C01&zb=A0L08&sj=2025",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "X-Requested-With": "XMLHttpRequest",
}

# 尝试不同的 dbcode
DB_CODES = ["hgnd", "hgjd", "fsnd"]  # 年度数据、季度数据、季度累计

def query_db(dbcode):
    ts = int(time.time() * 1000)
    dfwds = urllib.parse.quote(json.dumps([
        {"wdcode": "zb", "valuecode": "A0L08"},  # 社会融资规模
        {"wdcode": "sj", "valuecode": "LAST20"}
    ]))
    url = (
        f"https://data.stats.gov.cn/easyquery.htm"
        f"?m=QueryData&dbcode={dbcode}&rowcode=zb&colcode=sj"
        f"&wds=%5B%5D&dfwds={dfwds}&k1={ts}"
    )
    print(f"\n=== dbcode={dbcode} ===")
    print(f"[接口URL] {url}")
    
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=12, context=ssl_ctx) as resp:
            raw = resp.read().decode("utf-8")
        
        data = json.loads(raw)
        returndata = data.get("returndata", {})
        wdnodes = returndata.get("wdnodes", [])
        datanodes = returndata.get("datanodes", [])
        
        # 打印指标列表
        print(f"[指标列表]")
        for wd in wdnodes:
            nodes = wd.get("nodes", [])
            for n in nodes:
                code = n.get("code", "")
                name = n.get("name", "")
                unit = n.get("unit", "")
                if "A0L" in code:
                    print(f"  ★ {code} {name} ({unit})")
                else:
                    print(f"    {code} {name} ({unit})")
        
        # 打印社融数据
        print(f"[数据节点] 共 {len(datanodes)} 条")
        sf_data = {}
        for node in datanodes:
            code = node.get("code", "")
            val = node.get("data", {}).get("data")
            hasdata = node.get("data", {}).get("hasdata", False)
            
            if val is not None and hasdata and float(val) > 1000:  # 社融是千亿级别
                # 提取年份
                parts = code.split(".")
                if len(parts) >= 3:
                    year = parts[-1]
                    sf_data[year] = val
                    print(f"  ★ {year}年: {val}亿元")
        
        if sf_data:
            print(f"[成功] 找到社融数据: {sf_data}")
            return sf_data
        else:
            print(f"[无数据] 未找到社融数据")
            # 打印所有数据节点看看有什么
            for node in datanodes[:10]:
                code = node.get("code", "")
                val = node.get("data", {}).get("data")
                hasdata = node.get("data", {}).get("hasdata", False)
                if val is not None and hasdata:
                    print(f"    {code} = {val}")
            return None
            
    except Exception as e:
        print(f"[错误] {e}")
        return None

if __name__ == "__main__":
    for db in DB_CODES:
        result = query_db(db)
        if result:
            print(f"\n使用 dbcode={db} 成功获取社融数据!")
            break
        time.sleep(0.5)
