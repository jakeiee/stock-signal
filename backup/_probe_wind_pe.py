"""
探查万得全A(除金融、石油石化)估值接口
接口: https://indexapi.wind.com.cn/indicesWebsite/api/indexValuation?indexid=a49479f7cc5cc9cab3c7a7d55803bc9e
"""
import json
import ssl
import time
import urllib.request

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

HEADERS = {
    "Accept": "application/json",
    "Referer": "https://www.windindices.com/",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}

def fetch_wind_pe():
    url = (
        "https://indexapi.wind.com.cn/indicesWebsite/api/indexValuation"
        "?indexid=a49479f7cc5cc9cab3c7a7d55803bc9e"
        "&limit=false"
        "&lan=cn"
    )
    
    print(f"[接口URL] {url}")
    
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15, context=ssl_ctx) as resp:
        raw = resp.read().decode("utf-8")
    
    data = json.loads(raw)
    print(f"[原始数据] {json.dumps(data, ensure_ascii=False)[:1000]}")
    
    # 解析数据
    # peValue 应该是市盈率
    # 需要找到历史数据来计算百分位
    
    # 解析数据
    result_list = data.get("Result", [])
    print(f"\n[数据解析] 共 {len(result_list)} 条历史数据")
    
    # 最新数据
    if result_list:
        latest = result_list[-1]
        from datetime import datetime
        latest_date = datetime.fromtimestamp(latest["tradeDate"] / 1000)
        print(f"[最新数据] 日期: {latest_date.strftime('%Y-%m-%d')}, PE: {latest['peValue']}, PB: {latest['pbValue']}")
        
        # 最早的
        earliest = result_list[0]
        earliest_date = datetime.fromtimestamp(earliest["tradeDate"] / 1000)
        print(f"[最早数据] 日期: {earliest_date.strftime('%Y-%m-%d')}, PE: {earliest['peValue']}")
    
    return data

if __name__ == "__main__":
    result = fetch_wind_pe()
