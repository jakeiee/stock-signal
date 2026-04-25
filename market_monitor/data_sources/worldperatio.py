"""
WorldPERatio 全球市场估值数据源。

数据来源：
  - https://worldperatio.com/major-stock-index-pe-ratios/
  - 提供全球主要市场PE估值及历史偏离度数据

覆盖市场：
  - 美股：S&P 500, Nasdaq 100, Dow Jones, Russell 2000
  - 港股：FTSE China 50 (FXI)
  - 日股：MSCI Japan
  - 韩股：MSCI South Korea
  - 其他：MSCI World, MSCI Emerging Markets等

数据字段：
  - PE Ratio: 当前市盈率
  - P/E Evaluation: 5年/10年/20年估值评估 (Fair/Overvalued/Expensive)
  - Deviation vs Avg: 相对于历史均值的标准差偏离
  - Trend Margin: 相对于200日均线的偏离
"""

import re
import ssl
import urllib.request
from datetime import datetime
from typing import Dict, Any, List, Optional

# SSL 上下文
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

# 请求头
_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://worldperatio.com/",
}

# 主要指数映射（从截图中提取）
INDEX_MAPPING = {
    "QQQ": {"name": "Nasdaq 100", "country": "US", "type": "tech"},
    "SPY": {"name": "S&P 500", "country": "US", "type": "broad"},
    "URTH": {"name": "MSCI World", "country": "Global", "type": "global"},
    "VT": {"name": "FTSE Global All Cap", "country": "Global", "type": "global"},
    "DIA": {"name": "Dow Jones", "country": "US", "type": "broad"},
    "INDA": {"name": "MSCI India", "country": "IN", "type": "emerging"},
    "VGK": {"name": "FTSE Europe", "country": "EU", "type": "developed"},
    "EWA": {"name": "MSCI Australia", "country": "AU", "type": "developed"},
    "EWC": {"name": "MSCI Canada", "country": "CA", "type": "developed"},
    "IWM": {"name": "Russell 2000", "country": "US", "type": "small_cap"},
    "EFA": {"name": "MSCI EAFE", "country": "Developed", "type": "developed"},
    "EWU": {"name": "MSCI United Kingdom", "country": "UK", "type": "developed"},
    "EWQ": {"name": "MSCI France", "country": "FR", "type": "developed"},
    "EWJ": {"name": "MSCI Japan", "country": "JP", "type": "developed"},
    "EWG": {"name": "MSCI Germany", "country": "DE", "type": "developed"},
    "EEM": {"name": "MSCI Emerging Markets", "country": "EM", "type": "emerging"},
    "EWI": {"name": "MSCI Italy", "country": "IT", "type": "developed"},
    "EWZ": {"name": "MSCI Brazil", "country": "BR", "type": "emerging"},
    "FXI": {"name": "FTSE China 50", "country": "CN", "type": "emerging"},
}


def _parse_evaluation_to_percentile(evaluation: str) -> Optional[float]:
    """
    将估值评估转换为估算百分位。
    
    Args:
        evaluation: 估值评估字符串 (Fair/Overvalued/Expensive)
    
    Returns:
        估算的百分位 (0-100)
    """
    mapping = {
        "Cheap": 10.0,
        "Fair": 35.0,
        "Overvalued": 65.0,
        "Expensive": 85.0,
    }
    return mapping.get(evaluation, None)


def _parse_deviation_to_percentile(deviation_str: str) -> Optional[float]:
    """
    将标准差偏离转换为估算百分位。
    
    基于正态分布：
    - -2σ ≈ 2.3% 百分位
    - -1σ ≈ 15.9% 百分位
    - 0σ ≈ 50% 百分位
    - +1σ ≈ 84.1% 百分位
    - +2σ ≈ 97.7% 百分位
    
    Args:
        deviation_str: 标准差偏离字符串，如 "+2.54σ" 或 "-0.78σ"
    
    Returns:
        估算的百分位 (0-100)
    """
    import math
    
    if not deviation_str or "σ" not in deviation_str:
        return None
    
    try:
        # 提取数值
        deviation = float(deviation_str.replace("σ", "").replace("+", "").strip())
        # 使用正态分布CDF转换
        # CDF(x) = 0.5 * (1 + erf(x / sqrt(2)))
        percentile = 0.5 * (1 + math.erf(deviation / math.sqrt(2))) * 100
        return round(percentile, 1)
    except (ValueError, TypeError):
        return None


def fetch_worldperatio_major_indexes() -> Dict[str, Any]:
    """
    从 WorldPERatio 获取主要指数PE数据。
    
    Returns:
        {
            "data": [
                {
                    "symbol": str,          # 指数代码
                    "name": str,            # 指数名称
                    "country": str,         # 国家/地区
                    "pe": float,            # 当前PE
                    "evaluation_5y": str,   # 5年评估
                    "evaluation_10y": str,  # 10年评估
                    "evaluation_20y": str,  # 20年评估
                    "avg_5y": float,        # 5年平均PE
                    "avg_10y": float,       # 10年平均PE
                    "avg_20y": float,       # 20年平均PE
                    "dev_5y": str,          # 5年标准差偏离
                    "dev_10y": str,         # 10年标准差偏离
                    "dev_20y": str,         # 20年标准差偏离
                    "trend_margin": str,    # 相对于200日均线
                    "date": str,            # 数据日期
                },
                ...
            ],
            "last_update": str,  # 页面最后更新时间
            "error": str|None,
        }
    """
    url = "https://worldperatio.com/major-stock-index-pe-ratios/"
    
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=30, context=_SSL_CTX) as resp:
            html = resp.read().decode("utf-8")
        
        result = {
            "data": [],
            "last_update": "",
            "error": None,
        }
        
        # 提取最后更新时间
        update_match = re.search(r'Last Update:\s*([\d\s\w,]+)', html, re.IGNORECASE)
        if update_match:
            result["last_update"] = update_match.group(1).strip()
        
        # 提取表格数据
        # 表格结构：第0列(空) | Symbol | Name | PE | 5Y评估 | 10Y评估 | 20Y评估 | 5Y平均 | 10Y平均 | 20Y平均 | 5Y偏离 | 10Y偏离 | 20Y偏离 | Trend | Date
        tables = re.findall(r'<table[^>]*>(.*?)</table>', html, re.DOTALL | re.IGNORECASE)
        if not tables:
            return {"data": [], "last_update": "", "error": "无法找到表格数据"}
        
        table_html = tables[0]
        
        # 提取所有行
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', table_html, re.DOTALL)
        
        for row in rows:
            # 提取单元格 - 支持td和th
            cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row, re.DOTALL)
            if len(cells) < 10:
                continue
            
            # 清理HTML标签
            def clean_cell(cell):
                text = re.sub(r'<[^>]+>', ' ', cell).strip()
                text = re.sub(r'\s+', ' ', text)
                # 移除排序箭头
                text = re.sub(r'[▾▴]', '', text).strip()
                return text
            
            cells = [clean_cell(c) for c in cells]
            
            # 数据行结构：第0列(空) | Symbol | Name | PE | 5Y评估 | 10Y评估 | 20Y评估 | 5Y平均 | 10Y平均 | 20Y平均 | 5Y偏离 | 10Y偏离 | 20Y偏离 | Trend | Date
            symbol = cells[1] if len(cells) > 1 else ""
            name = cells[2] if len(cells) > 2 else ""
            
            # 提取PE值
            pe_str = cells[3] if len(cells) > 3 else ""
            try:
                pe = float(pe_str) if pe_str else None
            except ValueError:
                pe = None
            
            # 提取评估
            eval_5y = cells[4] if len(cells) > 4 else ""
            eval_10y = cells[5] if len(cells) > 5 else ""
            eval_20y = cells[6] if len(cells) > 6 else ""
            
            # 提取历史平均
            avg_5y_str = cells[7] if len(cells) > 7 else ""
            avg_10y_str = cells[8] if len(cells) > 8 else ""
            avg_20y_str = cells[9] if len(cells) > 9 else ""
            
            try:
                avg_5y = float(avg_5y_str) if avg_5y_str else None
                avg_10y = float(avg_10y_str) if avg_10y_str else None
                avg_20y = float(avg_20y_str) if avg_20y_str else None
            except ValueError:
                avg_5y = avg_10y = avg_20y = None
            
            # 提取偏离度
            dev_5y = cells[10] if len(cells) > 10 else ""
            dev_10y = cells[11] if len(cells) > 11 else ""
            dev_20y = cells[12] if len(cells) > 12 else ""
            
            # 提取趋势边际
            trend_margin = cells[13] if len(cells) > 13 else ""
            
            # 提取日期
            date_str = cells[14] if len(cells) > 14 else ""
            
            # 获取国家信息
            country_info = INDEX_MAPPING.get(symbol, {})
            
            if symbol and pe is not None:
                result["data"].append({
                    "symbol": symbol,
                    "name": name or country_info.get("name", ""),
                    "country": country_info.get("country", ""),
                    "type": country_info.get("type", ""),
                    "pe": pe,
                    "evaluation_5y": eval_5y,
                    "evaluation_10y": eval_10y,
                    "evaluation_20y": eval_20y,
                    "avg_5y": avg_5y,
                    "avg_10y": avg_10y,
                    "avg_20y": avg_20y,
                    "dev_5y": dev_5y,
                    "dev_10y": dev_10y,
                    "dev_20y": dev_20y,
                    "trend_margin": trend_margin,
                    "date": date_str,
                })
        
        return result
        
    except Exception as e:
        return {
            "data": [],
            "last_update": "",
            "error": str(e),
        }


def fetch_worldperatio_valuation() -> Dict[str, Any]:
    """
    获取全球主要市场估值数据（适配现有接口）。
    
    Returns:
        {
            "US": {"pe": float, "pct_10y": float, "date": str, "source": str, "dev_10y": str},
            "HK": {"pe": float, "pct_10y": float, "date": str, "source": str, "dev_10y": str},
            "JP": {"pe": float, "pct_10y": float, "date": str, "source": str, "dev_10y": str},
            "KR": {"pe": float, "pct_10y": float, "date": str, "source": str, "dev_10y": str},
            "CN": {"pe": float, "pct_10y": float, "date": str, "source": str, "dev_10y": str},
            "date": str,
            "note": str,
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
    
    print("  [全球估值] 从 WorldPERatio 获取数据...", end=" ", flush=True)
    
    data = fetch_worldperatio_major_indexes()
    
    if data.get("error"):
        print(f"✗ {data['error']}")
        result["note"] = f"WorldPERatio 获取失败: {data['error']}"
        return result
    
    if not data.get("data"):
        print("✗ 无数据")
        result["note"] = "WorldPERatio 返回空数据"
        return result
    
    print(f"✓ 获取到 {len(data['data'])} 个指数")
    
    # 映射到目标市场
    for item in data["data"]:
        country = item.get("country", "")
        pe = item.get("pe")
        eval_10y = item.get("evaluation_10y", "")
        dev_10y = item.get("dev_10y", "")
        date_str = item.get("date", "")
        
        # 估算百分位
        pct_10y = _parse_evaluation_to_percentile(eval_10y)
        
        market_data = {
            "pe": pe,
            "pct_10y": pct_10y,
            "date": date_str,
            "source": "worldperatio",
            "name": item.get("name", ""),
            "evaluation_5y": item.get("evaluation_5y", ""),
            "evaluation_10y": eval_10y,
            "evaluation_20y": item.get("evaluation_20y", ""),
            "dev_5y": item.get("dev_5y", ""),
            "dev_10y": dev_10y,
            "dev_20y": item.get("dev_20y", ""),
            "avg_10y": item.get("avg_10y"),
            "trend_margin": item.get("trend_margin", ""),
        }
        
        if country == "US":
            # 优先使用 S&P 500
            if item.get("symbol") == "SPY":
                result["US"] = market_data
            elif not result["US"]:
                result["US"] = market_data
        elif country == "CN":
            result["CN"] = market_data
        elif country == "JP":
            result["JP"] = market_data
        elif country == "KR":
            # 从 MSCI Emerging Markets 或查找韩国相关
            pass  # 当前页面没有单独的韩国指数
    
    # 使用 MSCI Emerging Markets 作为港股参考（FXI是中国50）
    for item in data["data"]:
        if item.get("symbol") == "FXI":
            result["HK"] = {
                "pe": item.get("pe"),
                "pct_10y": _parse_evaluation_to_percentile(item.get("evaluation_10y", "")),
                "date": item.get("date", ""),
                "source": "worldperatio",
                "name": item.get("name", ""),
                "dev_10y": item.get("dev_10y", ""),
                "note": "FTSE China 50 作为港股参考",
            }
            break
    
    # 使用 MSCI Emerging Markets 估算韩股
    for item in data["data"]:
        if item.get("symbol") == "EEM":
            # 新兴市场整体PE作为参考
            result["KR"] = {
                "pe": item.get("pe"),
                "pct_10y": _parse_evaluation_to_percentile(item.get("evaluation_10y", "")),
                "date": item.get("date", ""),
                "source": "worldperatio",
                "name": "MSCI Emerging Markets (参考)",
                "dev_10y": item.get("dev_10y", ""),
                "note": "新兴市场整体作为韩股参考",
            }
            break
    
    result["date"] = data.get("last_update", "")
    result["note"] = f"数据来源: WorldPERatio ({data.get('last_update', '')})"
    
    return result


if __name__ == "__main__":
    # 测试
    print("=" * 70)
    print("WorldPERatio 全球市场估值数据测试")
    print("=" * 70)
    
    print("\n1. 获取主要指数数据:")
    print("-" * 70)
    
    data = fetch_worldperatio_major_indexes()
    
    if data.get("error"):
        print(f"错误: {data['error']}")
    else:
        print(f"最后更新: {data.get('last_update', 'N/A')}")
        print(f"获取到 {len(data.get('data', []))} 个指数")
        print()
        
        # 打印表格
        print(f"{'Symbol':<8} {'Name':<25} {'PE':<8} {'10Y评估':<12} {'10Y偏离':<12} {'Trend':<10}")
        print("-" * 90)
        
        for item in data.get("data", []):
            print(f"{item.get('symbol', ''):<8} "
                  f"{item.get('name', '')[:24]:<25} "
                  f"{item.get('pe', ''):<8} "
                  f"{item.get('evaluation_10y', ''):<12} "
                  f"{item.get('dev_10y', ''):<12} "
                  f"{item.get('trend_margin', ''):<10}")
    
    print("\n" + "=" * 70)
    print("2. 获取适配格式的估值数据:")
    print("-" * 70)
    
    valuation = fetch_worldperatio_valuation()
    
    for market in ["US", "CN", "HK", "JP", "KR"]:
        data = valuation.get(market, {})
        if data:
            print(f"{market}: PE={data.get('pe')}, 百分位={data.get('pct_10y')}%, "
                  f"10Y偏离={data.get('dev_10y')}, 评估={data.get('evaluation_10y')}")
    
    print(f"\n数据日期: {valuation.get('date', 'N/A')}")
    print(f"说明: {valuation.get('note', 'N/A')}")
