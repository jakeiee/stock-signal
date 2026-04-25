"""
Shiller 免费 API 数据源。

数据来源：
  - https://posix4e.github.io/shiller_wrapper_data/
  - 提供 S&P 500 的 CAPE 比率（席勒市盈率）历史数据
  - 数据从 1871 年至今

数据字段：
  - CAPE: 周期调整市盈率（使用过去10年平均盈利计算）
  - SP500: 标普500指数
  - Dividend: 股息率
  - Earnings: 每股收益
  - CPI: 消费者物价指数
"""

import json
import ssl
import urllib.request
from datetime import datetime
from typing import Dict, Any, Optional, List

# SSL 上下文
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

# API 端点
SHILLER_API_BASE = "https://posix4e.github.io/shiller_wrapper_data"


def fetch_shiller_stock_data() -> Dict[str, Any]:
    """
    获取 Shiller 股票市场完整历史数据。
    
    Returns:
        {
            "data": [
                {
                    "date": str,           # 日期 YYYY-MM-DD
                    "sp500": float,        # 标普500指数
                    "cape": float,         # CAPE 比率
                    "dividend": float,     # 股息率
                    "earnings": float,     # 每股收益
                    "cpi": float,          # CPI
                    "real_price": float,   # 通胀调整后股价
                },
                ...
            ],
            "latest": dict,       # 最新数据点
            "error": str|None,
        }
    """
    url = f"{SHILLER_API_BASE}/data/stock_market_data.json"
    
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        })
        
        with urllib.request.urlopen(req, timeout=30, context=_SSL_CTX) as resp:
            raw_data = json.loads(resp.read().decode("utf-8"))
        
        # 获取实际数据列表
        data = raw_data.get("data", []) if isinstance(raw_data, dict) else raw_data
        
        # 处理数据
        processed_data = []
        for item in data:
            if isinstance(item, dict):
                processed_data.append({
                    "date": item.get("date_string", ""),
                    "sp500": item.get("sp500"),
                    "cape": item.get("cape"),
                    "dividend": item.get("dividend"),
                    "earnings": item.get("earnings"),
                    "cpi": item.get("cpi"),
                    "real_price": item.get("real_price"),
                    "real_dividend": item.get("real_dividend"),
                    "real_earnings": item.get("real_earnings"),
                    "long_interest_rate": item.get("long_interest_rate"),
                })
        
        # 获取最新数据
        latest = processed_data[-1] if processed_data else None
        
        return {
            "data": processed_data,
            "latest": latest,
            "error": None,
        }
        
    except Exception as e:
        return {
            "data": [],
            "latest": None,
            "error": str(e),
        }


def calculate_cape_percentile(data: List[Dict], years: int = 10) -> Optional[float]:
    """
    计算当前 CAPE 在给定时间周期内的百分位。
    
    Args:
        data: Shiller 历史数据列表
        years: 计算百分位的时间周期（年）
    
    Returns:
        百分位 (0-100)，失败返回 None
    """
    if not data or len(data) < 12:
        return None
    
    try:
        # 获取最新 CAPE
        current_cape = data[-1].get("cape")
        if current_cape is None:
            return None
        
        # 计算需要回溯的数据点数（月数据）
        months_back = years * 12
        
        # 获取过去 N 年的 CAPE 数据
        if len(data) <= months_back:
            historical_capes = [d.get("cape") for d in data[:-1] if d.get("cape") is not None]
        else:
            historical_capes = [d.get("cape") for d in data[-months_back-1:-1] if d.get("cape") is not None]
        
        if not historical_capes:
            return None
        
        # 计算百分位：小于当前值的占比
        count_below = sum(1 for cape in historical_capes if cape < current_cape)
        percentile = (count_below / len(historical_capes)) * 100
        
        return round(percentile, 1)
        
    except Exception:
        return None


def calculate_cape_stats(data: List[Dict], years: int = 10) -> Dict[str, Any]:
    """
    计算 CAPE 在给定时间周期内的统计信息。
    
    Args:
        data: Shiller 历史数据列表
        years: 时间周期（年）
    
    Returns:
        {
            "current": float,      # 当前 CAPE
            "mean": float,         # 平均值
            "median": float,       # 中位数
            "min": float,          # 最小值
            "max": float,          # 最大值
            "percentile": float,   # 当前百分位
            "period": str,         # 统计周期描述
        }
    """
    if not data:
        return {"error": "无数据"}
    
    try:
        # 获取最新 CAPE
        current_cape = data[-1].get("cape")
        if current_cape is None:
            return {"error": "无法获取当前 CAPE"}
        
        # 计算需要回溯的数据点数
        months_back = years * 12
        
        # 获取过去 N 年的 CAPE 数据
        if len(data) <= months_back:
            historical_capes = [d.get("cape") for d in data[:-1] if d.get("cape") is not None]
        else:
            historical_capes = [d.get("cape") for d in data[-months_back-1:-1] if d.get("cape") is not None]
        
        if not historical_capes:
            return {"error": "历史数据不足"}
        
        # 计算统计值
        mean_cape = sum(historical_capes) / len(historical_capes)
        sorted_capes = sorted(historical_capes)
        median_cape = sorted_capes[len(sorted_capes) // 2]
        min_cape = min(historical_capes)
        max_cape = max(historical_capes)
        
        # 计算百分位
        count_below = sum(1 for cape in historical_capes if cape < current_cape)
        percentile = (count_below / len(historical_capes)) * 100
        
        return {
            "current": round(current_cape, 2),
            "mean": round(mean_cape, 2),
            "median": round(median_cape, 2),
            "min": round(min_cape, 2),
            "max": round(max_cape, 2),
            "percentile": round(percentile, 1),
            "period": f"近{years}年",
            "data_points": len(historical_capes),
        }
        
    except Exception as e:
        return {"error": str(e)}


def fetch_us_cape_valuation() -> Dict[str, Any]:
    """
    获取美股 CAPE 估值数据（适配全球估值接口）。
    
    Returns:
        {
            "cape": float,           # 当前 CAPE
            "cape_10y_pct": float,   # 近10年百分位
            "cape_max_pct": float,   # 历史百分位（全部数据）
            "mean_10y": float,       # 近10年均值
            "median_10y": float,     # 近10年中位数
            "date": str,             # 数据日期
            "source": str,           # 数据来源
            "error": str|None,
        }
    """
    print("  [美股CAPE] 从 Shiller API 获取数据...", end=" ", flush=True)
    
    result = fetch_shiller_stock_data()
    
    if result.get("error"):
        print(f"✗ {result['error']}")
        return {
            "cape": None,
            "cape_10y_pct": None,
            "cape_max_pct": None,
            "date": "",
            "source": "shiller",
            "error": result["error"],
        }
    
    data = result.get("data", [])
    latest = result.get("latest", {})
    
    if not latest:
        print("✗ 无最新数据")
        return {
            "cape": None,
            "cape_10y_pct": None,
            "cape_max_pct": None,
            "date": "",
            "source": "shiller",
            "error": "无最新数据",
        }
    
    # 计算10年统计
    stats_10y = calculate_cape_stats(data, years=10)
    
    # 计算历史统计（全部数据）
    stats_all = calculate_cape_stats(data, years=len(data)//12 + 1)
    
    cape = latest.get("cape")
    date_str = latest.get("date", "")
    
    print(f"✓ CAPE={cape:.2f}, 10年分位={stats_10y.get('percentile')}%")
    
    return {
        "cape": cape,
        "cape_10y_pct": stats_10y.get("percentile"),
        "cape_max_pct": stats_all.get("percentile"),
        "mean_10y": stats_10y.get("mean"),
        "median_10y": stats_10y.get("median"),
        "min_10y": stats_10y.get("min"),
        "max_10y": stats_10y.get("max"),
        "date": date_str,
        "source": "shiller",
        "error": None,
    }


if __name__ == "__main__":
    # 测试
    print("=" * 70)
    print("Shiller API 数据源测试")
    print("=" * 70)
    
    print("\n1. 获取美股 CAPE 估值数据:")
    print("-" * 70)
    
    result = fetch_us_cape_valuation()
    
    if result.get("error"):
        print(f"错误: {result['error']}")
    else:
        print(f"当前 CAPE: {result.get('cape')}")
        print(f"近10年分位: {result.get('cape_10y_pct')}%")
        print(f"历史分位: {result.get('cape_max_pct')}%")
        print(f"近10年均值: {result.get('mean_10y')}")
        print(f"近10年中位数: {result.get('median_10y')}")
        print(f"数据日期: {result.get('date')}")
    
    print("\n" + "=" * 70)
    print("2. 获取完整历史数据:")
    print("-" * 70)
    
    full_data = fetch_shiller_stock_data()
    
    if full_data.get("error"):
        print(f"错误: {full_data['error']}")
    else:
        data_list = full_data.get("data", [])
        print(f"数据点数: {len(data_list)}")
        
        if data_list:
            first = data_list[0]
            last = data_list[-1]
            print(f"最早数据: {first.get('date')} CAPE={first.get('cape')}")
            print(f"最新数据: {last.get('date')} CAPE={last.get('cape')}")
