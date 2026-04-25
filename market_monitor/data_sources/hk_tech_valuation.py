"""
恒生科技指数估值数据源。

数据来源：
  - 雪球基金 (danjuanfunds.com) - 恒生科技指数 PE、PB、历史百分位

覆盖指数：
  - 恒生科技指数 (HKHSTECH) - 港股科技板块主要指数
"""

import json
import ssl
import urllib.request
from datetime import datetime
from typing import Dict, Any, Optional

# SSL 上下文
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

# 请求头
_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
    "sec-ch-ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Microsoft Edge";v="146"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0"
    ),
    "Referer": "https://danjuanfunds.com/dj-valuation-table-detail/HKHSTECH",
}


def fetch_hk_tech_valuation() -> Dict[str, Any]:
    """
    从雪球基金获取恒生科技指数估值数据。
    
    Returns:
        {
            "pe": float,              # 当前PE
            "pb": float,              # 当前PB
            "pe_percentile": float,   # PE历史百分位 (0-1)
            "pb_percentile": float,   # PB历史百分位 (0-1)
            "roe": float,             # ROE
            "yield": float,           # 股息率
            "eva_type": str,          # 估值类型 (high/low/normal)
            "date": str,              # 数据日期
            "source": str,            # 数据来源
            "error": str|None,
        }
    """
    url = "https://danjuanfunds.com/djapi/index_eva/detail/HKHSTECH"
    
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            response = json.loads(resp.read().decode("utf-8"))
        
        if response.get("result_code") != 0:
            return {
                "pe": None,
                "pb": None,
                "pe_percentile": None,
                "pb_percentile": None,
                "roe": None,
                "yield": None,
                "eva_type": None,
                "date": "",
                "source": "danjuan",
                "error": f"API返回错误: {response.get('result_code')}",
            }
        
        data = response.get("data", {})
        
        # 转换时间戳
        ts = data.get("ts", 0)
        if ts:
            date_str = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d")
        else:
            date_str = datetime.now().strftime("%Y-%m-%d")
        
        return {
            "pe": data.get("pe"),
            "pb": data.get("pb"),
            "pe_percentile": data.get("pe_percentile"),  # 0-1 范围
            "pb_percentile": data.get("pb_percentile"),  # 0-1 范围
            "roe": data.get("roe"),
            "yield": data.get("yeild"),
            "eva_type": data.get("eva_type"),  # high/low/normal
            "eva_type_int": data.get("eva_type_int"),
            "date": date_str,
            "source": "danjuan",
            "error": None,
        }
        
    except Exception as e:
        return {
            "pe": None,
            "pb": None,
            "pe_percentile": None,
            "pb_percentile": None,
            "roe": None,
            "yield": None,
            "eva_type": None,
            "date": "",
            "source": "danjuan",
            "error": str(e),
        }


def fetch_hk_tech_for_global() -> Dict[str, Any]:
    """
    获取恒生科技指数数据（适配全球估值接口）。
    
    Returns:
        {
            "pe": float,
            "pct_10y": float,  # 转换为0-100的百分位
            "date": str,
            "source": str,
            "name": str,
        }
    """
    print("  [港股科技] 从雪球基金获取恒生科技指数数据...", end=" ", flush=True)
    
    data = fetch_hk_tech_valuation()
    
    if data.get("error"):
        print(f"✗ {data['error']}")
        return {
            "pe": None,
            "pct_10y": None,
            "date": "",
            "source": "danjuan",
            "error": data["error"],
        }
    
    if not data.get("pe"):
        print("✗ 未获取到PE数据")
        return {
            "pe": None,
            "pct_10y": None,
            "date": "",
            "source": "danjuan",
            "error": "未获取到PE数据",
        }
    
    # 将0-1范围的百分位转换为0-100
    pe_percentile = data.get("pe_percentile")
    pct_10y = pe_percentile * 100 if pe_percentile is not None else None
    
    print(f"✓ PE={data['pe']:.2f}, 百分位={pct_10y:.1f}%")
    
    return {
        "pe": data.get("pe"),
        "pct_10y": pct_10y,
        "pb": data.get("pb"),
        "pb_percentile": data.get("pb_percentile"),
        "roe": data.get("roe"),
        "yield": data.get("yield"),
        "eva_type": data.get("eva_type"),
        "date": data.get("date"),
        "source": "danjuan",
        "name": "恒生科技指数 (HKHSTECH)",
    }


if __name__ == "__main__":
    # 测试
    print("=" * 70)
    print("恒生科技指数估值数据源测试")
    print("=" * 70)
    
    print("\n1. 获取原始数据:")
    print("-" * 70)
    
    data = fetch_hk_tech_valuation()
    
    if data.get("error"):
        print(f"错误: {data['error']}")
    else:
        print(f"当前PE: {data.get('pe')}")
        print(f"当前PB: {data.get('pb')}")
        print(f"PE百分位: {data.get('pe_percentile')}")
        print(f"PB百分位: {data.get('pb_percentile')}")
        print(f"ROE: {data.get('roe')}")
        print(f"股息率: {data.get('yield')}")
        print(f"估值类型: {data.get('eva_type')}")
        print(f"数据日期: {data.get('date')}")
    
    print("\n" + "=" * 70)
    print("2. 获取适配格式的数据:")
    print("-" * 70)
    
    hk_tech_data = fetch_hk_tech_for_global()
    print(f"\nPE: {hk_tech_data.get('pe')}")
    print(f"10年百分位: {hk_tech_data.get('pct_10y')}%")
    print(f"PB: {hk_tech_data.get('pb')}")
    print(f"来源: {hk_tech_data.get('name')}")
