"""
港股估值数据源。

数据来源：
  - 亿牛网 (eniu.com) - 恒生指数 PE、股息率、历史百分位
  - HKCoding (hkcoding.com) - 恒生指数 PE 历史数据

覆盖指数：
  - 恒生指数 (HSI) - 港股主要大盘指数
  - 恒生科技指数 - 港股科技板块
"""

import re
import ssl
import urllib.request
from datetime import datetime
from typing import Dict, Any, Optional

# SSL 上下文
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

# 请求头 - 模拟浏览器请求
_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    "cache-control": "max-age=0",
    "priority": "u=0, i",
    "sec-ch-ua": "\"Chromium\";v=\"146\", \"Not-A.Brand\";v=\"24\", \"Microsoft Edge\";v=\"146\"",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "\"macOS\"",
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "none",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0"
    ),
}


def fetch_eniu_hsi() -> Dict[str, Any]:
    """
    从亿牛网获取恒生指数估值数据。
    
    Returns:
        {
            "pe": float,            # 当前PE
            "dividend_yield": float, # 股息率(%)
            "pe_avg": float,        # 历史平均PE
            "pe_max": float,        # 历史最高PE
            "pe_min": float,        # 历史最低PE
            "percentile_3y": float, # 近3年百分位
            "percentile_5y": float, # 近5年百分位
            "percentile_10y": float, # 近10年百分位
            "percentile_all": float, # 历史百分位
            "date": str,            # 数据日期
            "source": str,          # 数据来源
            "error": str|None,
        }
    """
    url = "https://eniu.com/gu/hkhsi"
    
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            html = resp.read().decode("utf-8")
        
        result = {
            "pe": None,
            "dividend_yield": None,
            "pe_avg": None,
            "pe_max": None,
            "pe_min": None,
            "percentile_3y": None,
            "percentile_5y": None,
            "percentile_10y": None,
            "percentile_all": None,
            "date": "",
            "source": "eniu",
            "error": None,
        }
        
        # 提取当前PE和股息率 - 从页面头部链接
        # 格式: 市盈率" target="_self">13.98
        pe_match = re.search(r'市盈率"[^>]*>([0-9.]+)', html)
        if pe_match:
            result["pe"] = float(pe_match.group(1))
        
        dy_match = re.search(r'股息率"[^>]*>([0-9.]+)', html)
        if dy_match:
            result["dividend_yield"] = float(dy_match.group(1))
        
        # 备用：从文本中提取
        if result["pe"] is None:
            pe_dy_match = re.search(r'市盈率[:：]\s*([0-9.]+)', html)
            if pe_dy_match:
                result["pe"] = float(pe_dy_match.group(1))
        
        if result["dividend_yield"] is None:
            dy_match2 = re.search(r'股息率[:：]\s*([0-9.]+)', html)
            if dy_match2:
                result["dividend_yield"] = float(dy_match2.group(1))
        
        # 提取历史统计
        stats_match = re.search(r'当前市盈率\s*([0-9.]+).*?历史平均\s*([0-9.]+).*?历史最高\s*([0-9.]+).*?历史最低\s*([0-9.]+)', html)
        if stats_match:
            if result["pe"] is None:
                result["pe"] = float(stats_match.group(1))
            result["pe_avg"] = float(stats_match.group(2))
            result["pe_max"] = float(stats_match.group(3))
            result["pe_min"] = float(stats_match.group(4))
        
        # 提取百分位 - 专门查找"当前市盈率百分位"区域
        # 查找包含"当前市盈率百分位"的panel
        percentile_section = re.search(r'当前市盈率百分位(.*?)(?=<h2|<div class="panel|</div>\s*</div>\s*$)', html, re.DOTALL)
        if percentile_section:
            section_text = percentile_section.group(1)
            # 清理HTML标签但保留结构
            section_text = re.sub(r'<[^>]+>', ' ', section_text)
            section_text = re.sub(r'\s+', ' ', section_text).strip()
            
            # 提取各时间段百分位
            p3y = re.search(r'近3年[:：]\s*([0-9.]+)%', section_text)
            if p3y:
                result["percentile_3y"] = float(p3y.group(1))
            
            p5y = re.search(r'近5年[:：]\s*([0-9.]+)%', section_text)
            if p5y:
                result["percentile_5y"] = float(p5y.group(1))
            
            p10y = re.search(r'近10年[:：]\s*([0-9.]+)%', section_text)
            if p10y:
                result["percentile_10y"] = float(p10y.group(1))
            
            pall = re.search(r'所有时间[:：]\s*([0-9.]+)%', section_text)
            if pall:
                result["percentile_all"] = float(pall.group(1))
        
        # 备用：在整个页面中查找百分位数据
        if result["percentile_3y"] is None:
            p3y = re.search(r'近3年[:：]\s*([0-9.]+)%', html)
            if p3y:
                result["percentile_3y"] = float(p3y.group(1))
        
        if result["percentile_5y"] is None:
            p5y = re.search(r'近5年[:：]\s*([0-9.]+)%', html)
            if p5y:
                result["percentile_5y"] = float(p5y.group(1))
        
        if result["percentile_10y"] is None:
            p10y = re.search(r'近10年[:：]\s*([0-9.]+)%', html)
            if p10y:
                result["percentile_10y"] = float(p10y.group(1))
        
        if result["percentile_all"] is None:
            pall = re.search(r'所有时间[:：]\s*([0-9.]+)%', html)
            if pall:
                result["percentile_all"] = float(pall.group(1))
        
        # 设置日期
        result["date"] = datetime.now().strftime("%Y-%m-%d")
        
        return result
        
    except Exception as e:
        return {
            "pe": None,
            "dividend_yield": None,
            "pe_avg": None,
            "pe_max": None,
            "pe_min": None,
            "percentile_3y": None,
            "percentile_5y": None,
            "percentile_10y": None,
            "percentile_all": None,
            "date": "",
            "source": "eniu",
            "error": str(e),
        }


def fetch_hk_valuation() -> Dict[str, Any]:
    """
    获取港股估值数据（适配全球估值接口）。
    
    Returns:
        {
            "pe": float,
            "pct_10y": float,
            "date": str,
            "source": str,
            "name": str,
            "dividend_yield": float,
        }
    """
    print("  [港股估值] 从亿牛网获取恒生指数数据...", end=" ", flush=True)
    
    data = fetch_eniu_hsi()
    
    if data.get("error"):
        print(f"✗ {data['error']}")
        return {
            "pe": None,
            "pct_10y": None,
            "date": "",
            "source": "eniu",
            "error": data["error"],
        }
    
    if not data.get("pe"):
        print("✗ 未获取到PE数据")
        return {
            "pe": None,
            "pct_10y": None,
            "date": "",
            "source": "eniu",
            "error": "未获取到PE数据",
        }
    
    print(f"✓ PE={data['pe']}, 10年百分位={data.get('percentile_10y')}%")
    
    return {
        "pe": data.get("pe"),
        "pct_10y": data.get("percentile_10y"),
        "date": data.get("date"),
        "source": "eniu",
        "name": "恒生指数 (HSI)",
        "dividend_yield": data.get("dividend_yield"),
        "pe_avg": data.get("pe_avg"),
        "pe_max": data.get("pe_max"),
        "pe_min": data.get("pe_min"),
        "percentile_3y": data.get("percentile_3y"),
        "percentile_5y": data.get("percentile_5y"),
        "percentile_all": data.get("percentile_all"),
    }


if __name__ == "__main__":
    # 测试
    print("=" * 70)
    print("港股估值数据源测试")
    print("=" * 70)
    
    print("\n1. 获取亿牛网恒生指数详细数据:")
    print("-" * 70)
    
    data = fetch_eniu_hsi()
    
    if data.get("error"):
        print(f"错误: {data['error']}")
    else:
        print(f"当前PE: {data.get('pe')}")
        print(f"股息率: {data.get('dividend_yield')}%")
        print(f"历史平均PE: {data.get('pe_avg')}")
        print(f"历史最高PE: {data.get('pe_max')}")
        print(f"历史最低PE: {data.get('pe_min')}")
        print()
        print("百分位:")
        print(f"  近3年: {data.get('percentile_3y')}%")
        print(f"  近5年: {data.get('percentile_5y')}%")
        print(f"  近10年: {data.get('percentile_10y')}%")
        print(f"  所有时间: {data.get('percentile_all')}%")
    
    print("\n" + "=" * 70)
    print("2. 获取适配格式的港股估值数据:")
    print("-" * 70)
    
    hk_data = fetch_hk_valuation()
    print(f"\nPE: {hk_data.get('pe')}")
    print(f"10年百分位: {hk_data.get('pct_10y')}%")
    print(f"股息率: {hk_data.get('dividend_yield')}%")
    print(f"来源: {hk_data.get('name')}")
