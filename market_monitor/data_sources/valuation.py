"""
估值数据源——市场整体估值指标。

已实现指标：
  - 万得全A(除金融、石油石化) PE/PB 及历史百分位
    数据来源：万得 Wind API
    指数代码：a49479f7cc5cc9cab3c7a7d55803bc9e
    指标：
      peValue - 市盈率
      pbValue - 市净率
      didValue - 股息率
      close - 收盘价

待实现指标：
  - 主要宽基指数 PE/PB 对比（沪深300 / 中证500 / 中证1000）
"""

import csv
import json
import os
import ssl
import time
import urllib.request
from datetime import datetime
from typing import Optional

# ── SSL / HTTP 配置 ───────────────────────────────────────────────────────
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

_WIND_BASE_URL = "https://indexapi.wind.com.cn/indicesWebsite/api/indexValuation"
_WIND_INDEX_ID = "a49479f7cc5cc9cab3c7a7d55803bc9e"  # 万得全A(除金融、石油石化)

_WIND_HEADERS = {
    "Accept": "application/json",
    "Referer": "https://www.windindices.com/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}

# CSV 缓存路径
_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
_VALUATION_CSV_PATH = os.path.join(_DATA_DIR, "wind_a_pe_history.csv")
_VALUATION_CSV_FIELDS = [
    "trade_date",  # 交易日期 YYYY-MM-DD
    "pe",          # 市盈率
    "pb",          # 市净率
    "div_yield",   # 股息率(%)
    "close",       # 收盘价
]


def _ensure_data_dir():
    os.makedirs(_DATA_DIR, exist_ok=True)


def _fetch_wind_pe_raw(timeout: int = 20) -> list:
    """
    从万得 API 获取原始估值数据。
    Returns: list of dict, each with tradeDate, peValue, pbValue, didValue, close
    """
    ts = int(time.time() * 1000)
    url = (
        f"{_WIND_BASE_URL}"
        f"?indexid={_WIND_INDEX_ID}"
        f"&limit=false"
        f"&lan=cn"
        f"&_={ts}"
    )
    print(f"[接口URL] {url}")
    
    req = urllib.request.Request(url, headers=_WIND_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:
        raw = resp.read().decode("utf-8")
    
    data = json.loads(raw)
    print(f"[原始数据] {json.dumps(data, ensure_ascii=False)[:300]}...")
    
    if not data.get("Success"):
        raise RuntimeError(f"万得API返回失败: {data.get('Message')}")
    
    result_list = data.get("Result", [])
    print(f"[计算步骤] 获取到 {len(result_list)} 条历史数据")
    
    return result_list


def _read_valuation_csv() -> dict:
    """读取历史估值 CSV，返回 {trade_date: row_dict}"""
    if not os.path.isfile(_VALUATION_CSV_PATH):
        return {}
    
    result = {}
    with open(_VALUATION_CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            td = row.get("trade_date", "").strip()
            if not td:
                continue
            result[td] = {
                "trade_date": td,
                "pe": float(row.get("pe") or 0),
                "pb": float(row.get("pb") or 0),
                "div_yield": float(row.get("div_yield") or 0),
                "close": float(row.get("close") or 0),
            }
    return result


def _write_valuation_csv(records: dict) -> None:
    """将 {trade_date: row_dict} 写入 CSV，按日期升序"""
    _ensure_data_dir()
    with open(_VALUATION_CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_VALUATION_CSV_FIELDS)
        writer.writeheader()
        for td in sorted(records.keys()):
            row = records[td]
            writer.writerow({
                "trade_date": td,
                "pe": f"{row['pe']:.4f}" if row['pe'] else "",
                "pb": f"{row['pb']:.4f}" if row['pb'] else "",
                "div_yield": f"{row['div_yield']:.4f}" if row['div_yield'] else "",
                "close": f"{row['close']:.4f}" if row['close'] else "",
            })


def _calculate_percentile(value: float, history: list) -> float:
    """
    计算历史百分位。
    百分位 = 当前值在历史数据中排第百分之几（从小到大）。
    低于20%为低估，高于80%为高估。
    """
    if not history or len(history) < 10:
        return None
    
    sorted_history = sorted(history)
    # 找到 value 在 sorted_history 中的位置
    # 使用线性插值计算百分位
    n = len(sorted_history)
    # 计算有多少历史值 <= 当前值
    count_less_equal = sum(1 for v in sorted_history if v <= value)
    percentile = (count_less_equal / n) * 100
    return round(percentile, 1)


def fetch_market_valuation(timeout: int = 20) -> dict:
    """
    获取万得全A(除金融、石油石化)估值指标。

    Returns:
        {
            "date":        str,          # 数据日期 YYYY-MM-DD
            "pe":          float,        # 市盈率
            "pe_pct":      float,        # PE 历史百分位（0-100，越低越便宜）
            "pb":          float,        # 市净率
            "pb_pct":      float,        # PB 历史百分位
            "div_yield":   float,        # 股息率(%)
            "div_pct":     float,        # 股息率历史百分位
            "close":       float,        # 收盘价
            "source":      str,
        }
        失败时：{"error": str}

    百分位参考：
        PE/PB:
          < 20% → 低估（便宜）
          20-80% → 正常
          > 80% → 高估（贵）
        股息率：
          > 80% → 高股息（丰厚）
          20-80% → 正常
          < 20% → 低股息
    """
    try:
        # 1. 获取原始数据
        raw_data = _fetch_wind_pe_raw(timeout)
        
        if not raw_data:
            raise RuntimeError("万得API返回空数据")
        
        # 2. 解析并保存到 CSV
        parsed_data = {}  # {trade_date: row}
        for item in raw_data:
            ts_ms = item.get("tradeDate")
            if not ts_ms:
                continue
            # 转换时间戳
            dt = datetime.fromtimestamp(ts_ms / 1000)
            trade_date = dt.strftime("%Y-%m-%d")
            
            parsed_data[trade_date] = {
                "trade_date": trade_date,
                "pe": item.get("peValue", 0) or 0,
                "pb": item.get("pbValue", 0) or 0,
                "div_yield": item.get("didValue", 0) or 0,  # didValue 是股息率
                "close": item.get("close", 0) or 0,
            }
        
        print(f"[计算步骤] 解析到 {len(parsed_data)} 条数据")
        
        # 保存到 CSV
        _write_valuation_csv(parsed_data)
        print(f"[计算步骤] 已保存到 CSV: {_VALUATION_CSV_PATH}")
        
        # 3. 获取最新数据
        sorted_dates = sorted(parsed_data.keys(), reverse=True)
        latest_date = sorted_dates[0]
        latest = parsed_data[latest_date]
        
        # 4. 计算百分位
        # 收集所有历史 PE 值
        all_pe = [v["pe"] for v in parsed_data.values() if v["pe"] > 0]
        all_pb = [v["pb"] for v in parsed_data.values() if v["pb"] > 0]
        all_div = [v["div_yield"] for v in parsed_data.values() if v["div_yield"] > 0]
        
        pe_pct = _calculate_percentile(latest["pe"], all_pe)
        pb_pct = _calculate_percentile(latest["pb"], all_pb)
        div_pct = _calculate_percentile(latest["div_yield"], all_div)
        
        print(f"[计算步骤] PE={latest['pe']:.2f}, 历史共{len(all_pe)}条, 百分位={pe_pct}%")
        print(f"[计算步骤] PB={latest['pb']:.2f}, 历史共{len(all_pb)}条, 百分位={pb_pct}%")
        print(f"[计算步骤] 股息率={latest['div_yield']:.2f}%, 历史共{len(all_div)}条, 百分位={div_pct}%")
        
        print(f"[最终结果] date={latest_date}, pe={latest['pe']:.2f}, pe_pct={pe_pct}%, "
              f"pb={latest['pb']:.2f}, pb_pct={pb_pct}%")
        
        return {
            "date": latest_date,
            "pe": round(latest["pe"], 2),
            "pe_pct": pe_pct,
            "pb": round(latest["pb"], 2),
            "pb_pct": pb_pct,
            "div_yield": round(latest["div_yield"], 2),
            "div_pct": div_pct,
            "close": round(latest["close"], 2),
            "source": "wind",
        }
        
    except Exception as e:
        # 降级：读取 CSV 缓存
        try:
            cached = _read_valuation_csv()
            if cached:
                sorted_dates = sorted(cached.keys(), reverse=True)
                latest_date = sorted_dates[0]
                latest = cached[latest_date]
                
                # 重新计算百分位
                all_pe = [v["pe"] for v in cached.values() if v["pe"] > 0]
                all_pb = [v["pb"] for v in cached.values() if v["pb"] > 0]
                all_div = [v["div_yield"] for v in cached.values() if v["div_yield"] > 0]
                
                pe_pct = _calculate_percentile(latest["pe"], all_pe)
                pb_pct = _calculate_percentile(latest["pb"], all_pb)
                div_pct = _calculate_percentile(latest["div_yield"], all_div)
                
                print(f"[降级] 使用CSV缓存: {latest_date}, pe={latest['pe']}")
                
                return {
                    "date": latest_date,
                    "pe": round(latest["pe"], 2),
                    "pe_pct": pe_pct,
                    "pb": round(latest["pb"], 2),
                    "pb_pct": pb_pct,
                    "div_yield": round(latest["div_yield"], 2),
                    "div_pct": div_pct,
                    "close": round(latest["close"], 2),
                    "source": "csv_cache",
                }
        except Exception:
            pass
        return {"error": f"估值数据获取失败：{e}"}


# 保留原有的待实现函数（兼容旧代码）
def fetch_index_valuation(index_code: str, timeout: int = 20) -> dict:
    """
    获取指定宽基指数的估值数据（待实现）。
    """
    return {"error": f"fetch_index_valuation({index_code!r}) 暂未实现，请使用 fetch_market_valuation() 获取全市场估值"}
