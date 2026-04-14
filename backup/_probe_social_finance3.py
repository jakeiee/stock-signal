"""
获取社融年度数据并计算同比
- 指标 A0L0801 = 社会融资规模 (亿元)
- 计算同比增速
"""
import csv
import json
import os
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

CSV_PATH = "/Users/liuyi/WorkBuddy/20260314145315/market_monitor/data/social_finance.csv"

def fetch_social_finance_data():
    """获取社会融资规模年度数据"""
    ts = int(time.time() * 1000)
    dfwds = urllib.parse.quote(json.dumps([
        {"wdcode": "zb", "valuecode": "A0L0801"},  # 社会融资规模
        {"wdcode": "sj", "valuecode": "LAST20"}
    ]))
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
    print(f"[原始数据] {json.dumps(data, ensure_ascii=False)[:500]}")
    
    returndata = data.get("returndata", {})
    datanodes = returndata.get("datanodes", [])
    
    # 只取 A0L0801 的数据
    sf_data = {}  # {年份: 社融存量(亿元)}
    for node in datanodes:
        code = node.get("code", "")
        val = node.get("data", {}).get("data")
        hasdata = node.get("data", {}).get("hasdata", False)
        
        # 只取 A0L0801 的数据
        if "A0L0801" in code and hasdata and val is not None and val > 100000:
            # 提取年份: zb.A0L0801_sj.2025 -> 2025
            year = code.split(".")[-1]
            sf_data[year] = val
            print(f"[数据节点] {year}年: {val}亿元")
    
    print(f"[计算步骤] 获取到 {len(sf_data)} 年数据: {sorted(sf_data.keys(), reverse=True)[:5]}")
    return sf_data

def calculate_yoy(sf_data):
    """计算同比增速"""
    # 按年份排序
    sorted_years = sorted(sf_data.keys(), reverse=True)
    
    results = []  # [(年份, 社融存量, 同比)]
    for i, year in enumerate(sorted_years):
        current_val = sf_data[year]
        
        # 找上一年
        prev_year = str(int(year) - 1)
        if prev_year in sf_data:
            prev_val = sf_data[prev_year]
            yoy = (current_val / prev_val - 1) * 100
            print(f"[计算步骤] {year}年: {current_val}亿 vs {prev_year}年: {prev_val}亿 → 同比={yoy:.2f}%")
        else:
            yoy = None
            print(f"[计算步骤] {year}年: {current_val}亿 (无去年数据)")
        
        results.append((year, current_val, yoy))
    
    return results

def save_to_csv(results):
    """保存到CSV文件"""
    # 写入CSV
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["period", "sf_bal", "sf_yoy", "source"])
        for year, bal, yoy in results:
            yoy_str = f"{yoy:.1f}" if yoy is not None else ""
            writer.writerow([year, f"{bal:.0f}", yoy_str, "stats.gov.cn"])
    
    print(f"[最终结果] 已保存到 {CSV_PATH}")
    
    # 打印最新数据
    if results:
        latest = results[0]
        print(f"  最新: {latest[0]}年, 社融存量={latest[1]:.0f}亿元, 同比={latest[2]:.1f}%" if latest[2] else "")

if __name__ == "__main__":
    # 1. 获取数据
    sf_data = fetch_social_finance_data()
    
    if not sf_data:
        print("[错误] 未获取到社融数据")
        exit(1)
    
    # 2. 计算同比
    results = calculate_yoy(sf_data)
    
    # 3. 保存CSV
    save_to_csv(results)
