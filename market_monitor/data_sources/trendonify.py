"""
全球主要市场估值数据源。

数据来源（优先级从高到低）：
  1. WorldPERatio (worldperatio.com) - 主要指数PE及历史偏离度
     - 美股：S&P 500
     - 日股：MSCI Japan
     - A股：FTSE China 50
  2. 港股专用数据源 (eniu.com) - 恒生指数 PE
  3. 乐咕乐股 (legulegu.com) - 标普500、恒生指数 PE
  4. Wind MAGS/TECHK - 美股/港股科技指数
  5. 东方财富K线 - 日经225、KOSPI 估算

估值等级划分：
  - 0-20%：🟢🟢 有吸引力
  - 21-40%：🟢 低估
  - 41-60%：🟡 合理
  - 61-80%：🟠 高估
  - 81-100%：🔴 昂贵
"""

import json
import ssl
import urllib.request
from datetime import datetime
from typing import Dict, Any, Optional

from .global_mkt import fetch_mags_valuation, fetch_techk_valuation, _fetch_kline, _SECID
from .worldperatio import fetch_worldperatio_valuation
from .hk_valuation import fetch_hk_valuation

# SSL 上下文
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

# 乐咕乐股 API 基础配置
_LEGULEGU_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://www.legulegu.com/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}


def _fetch_legulegu_pe(market_code: str) -> Dict[str, Any]:
    """
    从乐咕乐股获取指数PE数据。
    
    Args:
        market_code: 市场代码，如 "sp500", "hsi"
    
    Returns:
        {"pe": float, "date": str, "error": str|None}
    """
    url = f"https://www.legulegu.com/api/stockdata/market/{market_code}/pe"
    req = urllib.request.Request(url, headers=_LEGULEGU_HEADERS)
    
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        
        # 解析最新PE数据
        latest = data.get("data", [{}])[-1] if data.get("data") else {}
        pe = latest.get("pe")
        date_str = latest.get("date", "")
        
        return {
            "pe": round(pe, 2) if pe else None,
            "date": date_str,
            "error": None,
        }
    except Exception as e:
        return {"pe": None, "date": "", "error": str(e)}


def _calc_pe_percentile(pe: float, historical_pe_range: tuple) -> Optional[float]:
    """
    基于历史PE区间估算百分位。
    
    Args:
        pe: 当前PE
        historical_pe_range: (min_pe, max_pe, avg_pe) 历史最小、最大、平均PE
    
    Returns:
        估算的百分位 (0-100)
    """
    if pe is None or not historical_pe_range:
        return None
    
    min_pe, max_pe, avg_pe = historical_pe_range
    if max_pe <= min_pe:
        return 50.0
    
    # 使用对数正态分布近似
    import math
    log_pe = math.log(pe)
    log_min = math.log(min_pe)
    log_max = math.log(max_pe)
    
    percentile = (log_pe - log_min) / (log_max - log_min) * 100
    return round(max(0, min(100, percentile)), 1)


def fetch_trendonify_valuation() -> Dict[str, Any]:
    """
    获取全球主要市场估值数据。
    
    优先使用 WorldPERatio 数据，失败时回退到其他数据源。
    
    Returns:
        {
            "US": {"pe": float, "pct_10y": float, "date": str, "dev_10y": str},
            "HK": {"pe": float, "pct_10y": float, "date": str, "dev_10y": str},
            "JP": {"pe": float, "pct_10y": float, "date": str, "dev_10y": str},
            "KR": {"pe": float, "pct_10y": float, "date": str, "dev_10y": str},
            "CN": {"pe": float, "pct_10y": float, "date": str, "dev_10y": str},
            "date": str,  # 统一日期
            "note": str,  # 数据来源说明
        }
    """
    result = {
        "US": {},
        "HK": {},
        "JP": {},
        "KR": {},
        "CN": {},
        "date": "",
        "note": "",
    }
    
    errors = []
    
    # ─────────────────────────────────────────────────────
    # 1. 首先尝试从 WorldPERatio 获取数据
    # ─────────────────────────────────────────────────────
    print("  [全球估值] 尝试从 WorldPERatio 获取数据...")
    wp_data = fetch_worldperatio_valuation()
    
    if not wp_data.get("error") and wp_data.get("US"):
        # WorldPERatio 成功获取数据
        print("  [全球估值] ✓ WorldPERatio 数据获取成功")
        result["US"] = wp_data.get("US", {})
        result["CN"] = wp_data.get("CN", {})
        result["JP"] = wp_data.get("JP", {})
        result["KR"] = wp_data.get("KR", {})
        result["date"] = wp_data.get("date", "")
        result["note"] = wp_data.get("note", "")
        
        # ─────────────────────────────────────────────────────
        # 港股：使用专用数据源（亿牛网）
        # ─────────────────────────────────────────────────────
        hk_data = fetch_hk_valuation()
        if hk_data and hk_data.get("pe"):
            result["HK"] = {
                "pe": hk_data.get("pe"),
                "pct_10y": hk_data.get("pct_10y"),
                "date": hk_data.get("date"),
                "source": "eniu",
                "name": hk_data.get("name"),
                "dividend_yield": hk_data.get("dividend_yield"),
            }
        else:
            result["HK"] = wp_data.get("HK", {})
        
        # 打印获取结果
        for market in ["US", "CN", "HK", "JP", "KR"]:
            data = result.get(market, {})
            if data and data.get("pe"):
                print(f"    {market}: PE={data.get('pe')}, 10Y偏离={data.get('dev_10y', 'N/A')}")
        
        return result
    else:
        print(f"  [全球估值] ✗ WorldPERatio 获取失败，回退到备用数据源")
        if wp_data.get("error"):
            errors.append(f"WorldPERatio: {wp_data['error']}")
    
    # ─────────────────────────────────────────────────────
    # 2. 回退：美股 - 标普500 PE (乐咕乐股)
    # ─────────────────────────────────────────────────────
    print("  [全球估值] 获取标普500 PE...", end=" ", flush=True)
    sp500_data = _fetch_legulegu_pe("sp500")
    if sp500_data.get("error"):
        print(f"✗ {sp500_data['error']}")
        errors.append(f"标普500: {sp500_data['error']}")
        # 使用Wind MAGS作为备选
        mags = fetch_mags_valuation()
        if "error" not in mags:
            result["US"] = {
                "pe": mags.get("pe"),
                "pct_10y": mags.get("pe_pct"),
                "date": mags.get("date"),
                "source": "wind_mags",
            }
            result["date"] = mags.get("date", "")
    else:
        pe = sp500_data.get("pe")
        # 标普500历史PE区间参考 (近10年约15-30倍)
        pct = _calc_pe_percentile(pe, (15.0, 30.0, 20.0))
        result["US"] = {
            "pe": pe,
            "pct_10y": pct,
            "date": sp500_data.get("date"),
            "source": "legulegu",
        }
        result["date"] = sp500_data.get("date", "")
        print(f"✓ PE={pe}, 百分位={pct}%")
    
    # ─────────────────────────────────────────────────────
    # 3. 回退：港股 - 恒生指数 PE (乐咕乐股)
    # ─────────────────────────────────────────────────────
    print("  [全球估值] 获取恒生指数 PE...", end=" ", flush=True)
    hsi_data = _fetch_legulegu_pe("hsi")
    if hsi_data.get("error"):
        print(f"✗ {hsi_data['error']}")
        errors.append(f"恒生指数: {hsi_data['error']}")
        # 使用Wind TECHK作为备选
        techk = fetch_techk_valuation()
        if "error" not in techk:
            result["HK"] = {
                "pe": techk.get("pe"),
                "pct_10y": techk.get("pe_pct"),
                "date": techk.get("date"),
                "source": "wind_techk",
            }
            if not result["date"]:
                result["date"] = techk.get("date", "")
    else:
        pe = hsi_data.get("pe")
        # 恒生指数历史PE区间参考 (近10年约8-18倍)
        pct = _calc_pe_percentile(pe, (8.0, 18.0, 12.0))
        result["HK"] = {
            "pe": pe,
            "pct_10y": pct,
            "date": hsi_data.get("date"),
            "source": "legulegu",
        }
        if not result["date"]:
            result["date"] = hsi_data.get("date", "")
        print(f"✓ PE={pe}, 百分位={pct}%")
    
    # ─────────────────────────────────────────────────────
    # 4. 回退：日股 - 日经225 (东方财富K线估算)
    # ─────────────────────────────────────────────────────
    print("  [全球估值] 获取日经225数据...", end=" ", flush=True)
    try:
        n225_secid = _SECID.get("N225", ("100.N225", "日经225"))[0]
        n225_klines = _fetch_kline(n225_secid, n=60)
        if n225_klines:
            latest_price = n225_klines[-1][1] if n225_klines else None
            # 日经225近10年PE区间约12-25倍，当前约18-20倍
            # 基于价格趋势估算PE变化
            price_1y_ago = n225_klines[0][1] if len(n225_klines) > 0 else latest_price
            price_change = (latest_price / price_1y_ago - 1) * 100 if price_1y_ago else 0
            
            # 基准PE约19倍，根据价格变化调整
            base_pe = 19.0
            estimated_pe = base_pe * (1 + price_change / 100 * 0.5)  # 价格变化50%反映在PE上
            estimated_pe = max(12.0, min(25.0, estimated_pe))  # 限制在合理区间
            
            pct = _calc_pe_percentile(estimated_pe, (12.0, 25.0, 17.0))
            result["JP"] = {
                "pe": round(estimated_pe, 2),
                "pct_10y": pct,
                "date": n225_klines[-1][0] if n225_klines else "",
                "source": "estimated",
                "note": "基于行情数据估算",
            }
            print(f"✓ 估算PE={round(estimated_pe, 2)}, 百分位={pct}%")
        else:
            errors.append("日经225: 无法获取K线数据")
            print("✗ 无法获取K线数据")
    except Exception as e:
        errors.append(f"日经225: {e}")
        print(f"✗ {e}")
    
    # ─────────────────────────────────────────────────────
    # 5. 回退：韩股 - KOSPI (东方财富K线估算)
    # ─────────────────────────────────────────────────────
    print("  [全球估值] 获取KOSPI数据...", end=" ", flush=True)
    try:
        kospi_secid = _SECID.get("KOSPI", ("100.KS11", "韩国综合"))[0]
        kospi_klines = _fetch_kline(kospi_secid, n=60)
        if kospi_klines:
            latest_price = kospi_klines[-1][1] if kospi_klines else None
            # KOSPI近10年PE区间约8-20倍，当前约12-14倍
            base_pe = 13.0
            price_1y_ago = kospi_klines[0][1] if len(kospi_klines) > 0 else latest_price
            price_change = (latest_price / price_1y_ago - 1) * 100 if price_1y_ago else 0
            
            estimated_pe = base_pe * (1 + price_change / 100 * 0.5)
            estimated_pe = max(8.0, min(20.0, estimated_pe))
            
            pct = _calc_pe_percentile(estimated_pe, (8.0, 20.0, 12.0))
            result["KR"] = {
                "pe": round(estimated_pe, 2),
                "pct_10y": pct,
                "date": kospi_klines[-1][0] if kospi_klines else "",
                "source": "estimated",
                "note": "基于行情数据估算",
            }
            print(f"✓ 估算PE={round(estimated_pe, 2)}, 百分位={pct}%")
        else:
            errors.append("KOSPI: 无法获取K线数据")
            print("✗ 无法获取K线数据")
    except Exception as e:
        errors.append(f"KOSPI: {e}")
        print(f"✗ {e}")
    
    # 添加数据来源说明
    sources = []
    if result["US"].get("source"):
        sources.append(f"美股({result['US']['source']})")
    if result["HK"].get("source"):
        sources.append(f"港股({result['HK']['source']})")
    if result["JP"].get("source"):
        sources.append(f"日股({result['JP']['source']})")
    if result["KR"].get("source"):
        sources.append(f"韩股({result['KR']['source']})")
    
    result["note"] = "数据来源: " + ", ".join(sources) if sources else "数据获取失败"
    
    if errors:
        result["errors"] = errors
    
    return result


if __name__ == "__main__":
    # 测试
    print("=" * 60)
    print("全球主要市场估值数据测试")
    print("=" * 60)
    
    data = fetch_trendonify_valuation()
    
    print("\n" + "=" * 60)
    print("结果:")
    print("=" * 60)
    print(json.dumps(data, ensure_ascii=False, indent=2))
