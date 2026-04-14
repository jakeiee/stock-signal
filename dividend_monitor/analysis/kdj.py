"""
KDJ 技术指标计算模块。

数据源策略：
  优先：妙想API（标注 source='mx'）
  降级：中证官网 OHLCV 自算（标注 source='csindex'）
"""

import sys
import os
from typing import Optional, List, Dict

# 处理导入：支持直接执行和模块执行
if __package__:
    from ..config import INDEXES
else:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from dividend_monitor.config import INDEXES


# ─────────────────────────── 妙想API封装 ───────────────────────────

API_BASE = "https://mkapi2.dfcfs.com/finskillshub/api/claw"
APIKEY   = os.environ.get("MX_APIKEY", "mkt_HeEVfE9lWxYWMJpYsdLfU4-rWvXyKj5xU0mvS0giDOA")
MX_HEADERS = {"Content-Type": "application/json", "apikey": APIKEY}


def mx_query(question: str, timeout: int = 30) -> list:
    """
    调用妙想 API 查询自然语言问题。

    Returns:
        items: API 返回的 table 数据列表

    Raises:
        RuntimeError: 配额用尽（status=113）或其他致命错误
    """
    import requests, json

    payload = {
        "question": question,
        "api_type": "stock",
        "req_num": 10,
    }

    try:
        resp = requests.post(API_BASE, headers=MX_HEADERS, json=payload, timeout=timeout)
        data = resp.json()

        status = data.get("status", "")
        if status == "113":
            raise RuntimeError("妙想API今日配额已用尽（status=113）")

        if status != "000":
            raise RuntimeError(f"妙想API错误: status={status}, msg={data.get('msg', '')}")

        results = data.get("results", [])
        if not results:
            raise RuntimeError("妙想API返回空结果")

        return results

    except requests.exceptions.Timeout:
        raise RuntimeError("妙想API请求超时")
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"妙想API网络错误: {e}")


def parse_float(v: any) -> Optional[float]:
    """解析任意值类型为浮点数，失败返回 None。"""
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def extract_weekly(heads: List[str], k_list: List, d_list: List, j_list: List) -> List[Dict]:
    """
    从妙想API返回的列表中解析出周线数据行。

    Args:
        heads:  列名列表（用于定位日期列）
        k_list: K 值列表
        d_list: D 值列表
        j_list: J 值列表

    Returns:
        [{"date": "2026-01-03", "v0": K, "v1": D, "v2": J}, ...]
    """
    rows = []
    # 找到日期列（通常是最后一列或 named "date"）
    date_idx = -1
    for i, h in enumerate(heads):
        if h and ("date" in h.lower() or "时间" in h or "周期" in h):
            date_idx = i
            break
    if date_idx < 0:
        date_idx = len(heads) - 1   # 默认最后一列

    # 长度对齐
    n = min(len(k_list), len(d_list), len(j_list))
    for i in range(n):
        v0 = parse_float(k_list[i])
        v1 = parse_float(d_list[i])
        v2 = parse_float(j_list[i])
        # 日期列
        if date_idx < len(heads):
            date_str = str(k_list[i]) if False else ""   # 占位，下面补全
        # 日期可能混在 k_list 同位置，取同索引
        rows.append({"v0": v0, "v1": v1, "v2": v2})

    # 重新用原始返回值取日期
    # 妙想返回的 table 中，日期列在 table[heads[date_idx]]
    return rows


# ─────────────────────────── 中证官网数据源 ───────────────────────────

def _csindex_ohlcv(csindex_code: str, days: int = 300):
    """
    从中证官网获取指数日线 OHLCV 数据（pandas DataFrame）。
    列：date, open, high, low, close, volume
    """
    # 使用已验证的 csindex.fetch_daily_chg 获取原始数据
    if __package__:
        from dividend_monitor.data_sources.csindex import fetch_daily_chg
    else:
        from data_sources.csindex import fetch_daily_chg

    rows = fetch_daily_chg(csindex_code, days=days)
    if not rows:
        raise RuntimeError(f"中证官网返回空数据: {csindex_code}")

    import pandas as pd
    df = pd.DataFrame(rows)
    # 过滤无效行
    df = df[df["close"] > 0]
    df["date"] = pd.to_datetime(df["date"], format="%Y%m%d").dt.strftime("%Y-%m-%d")
    df = df[["date", "open", "high", "low", "close", "volume"]].copy()
    df = df.sort_values("date").reset_index(drop=True)
    return df


def _calc_kdj_from_df(df, n: int = 9) -> Optional[dict]:
    """
    从日线 DataFrame 重采样为周线后计算 KDJ。
    返回最新周 {date, K, D, J}，数据不足时返回 None。
    """
    import pandas as pd

    if df.empty or len(df) < n:
        return None

    # 重采样为周线（每周五收盘）
    df2 = df.copy()
    df2["date"] = pd.to_datetime(df2["date"])
    df2 = df2.set_index("date")
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    weekly = df2.resample("W-FRI").agg(agg).dropna().reset_index()
    weekly["date"] = weekly["date"].dt.strftime("%Y-%m-%d")

    if len(weekly) < n:
        return None

    # 计算 RSV
    low_min  = weekly["low"].rolling(window=n, min_periods=n).min()
    high_max = weekly["high"].rolling(window=n, min_periods=n).max()
    denom = high_max - low_min
    rsv = ((weekly["close"] - low_min) / denom.where(denom != 0, 1) * 100)

    # 平滑计算 K / D（初值50，权重2/3）
    def _smooth(series: pd.Series, init: float = 50.0) -> List[float]:
        result: List[float] = []
        prev = init
        for val in series:
            if pd.isna(val):
                result.append(float("nan"))
            else:
                prev = 2 / 3 * prev + 1 / 3 * val
                result.append(prev)
        return result

    k_vals = _smooth(rsv)
    d_vals = _smooth(pd.Series(k_vals))
    j_vals = [3 * k - 2 * d for k, d in zip(k_vals, d_vals)]

    weekly["k"] = k_vals
    weekly["d"] = d_vals
    weekly["j"] = j_vals

    # 取最后一个有效行
    valid = weekly.dropna(subset=["k"])
    if valid.empty:
        return None

    last = valid.iloc[-1]
    return {
        "date": last["date"],
        "K":    round(float(last["k"]), 2),
        "D":    round(float(last["d"]), 2),
        "J":    round(float(last["j"]), 2),
        "source": "csindex",
    }


def fetch(idx: dict) -> list:
    """
    获取最新一周周线KDJ。
    优先：妙想API（标注 source='mx'）
    降级：中证官网 OHLCV 自算（标注 source='csindex'）
    """
    # ── 优先：妙想 API ──
    try:
        items = mx_query(f"{idx['query_name']}最近30天周线KDJ指标")
        if items:
            item  = items[0]
            table = item.get("table", {})
            io    = item.get("indicatorOrder", [])
            heads = table.get("headName", [])
            k_key = io[0] if io else None
            if not k_key or k_key not in table:
                raise RuntimeError("妙想API返回值格式异常")

            d_key = f"KDJSJZBD_{k_key}"
            j_key = f"KDJSJZBJ_{k_key}"

            k_list = [parse_float(v) for v in table.get(k_key, [])]
            d_list = [parse_float(v) for v in table.get(d_key, [])]
            j_list = [parse_float(v) for v in table.get(j_key, [])]

            # 取前1条
            n = 1
            if len(k_list) >= n:
                result = []
                for i in range(n):
                    result.append({
                        "date": "",  # 妙想API返回不含日期列，用空
                        "K": k_list[i] if i < len(k_list) else None,
                        "D": d_list[i] if i < len(d_list) else None,
                        "J": j_list[i] if i < len(j_list) else None,
                        "source": "mx"
                    })
                if result and result[0]["K"] is not None:
                    return result
    except RuntimeError:
        pass
    except Exception:
        pass

    # ── 降级：中证官网 OHLCV 自算 ──
    csindex_code = idx.get("csindex_code")
    if not csindex_code:
        return []
    try:
        df = _csindex_ohlcv(csindex_code, days=300)
        kdj = _calc_kdj_from_df(df)
        if kdj:
            return [kdj]
    except Exception:
        pass

    return []


def signal(row: dict, prev_row: Optional[dict]) -> str:
    """KDJ 信号判断。"""
    k, d, j = row.get("K"), row.get("D"), row.get("J")
    if k is None or d is None or j is None:
        return ""
    if j < 0:
        return "⚠ J<0 极度超卖"
    if j > 100:
        return "⚠ J>100 超买"
    if prev_row and prev_row.get("K") is not None and prev_row.get("D") is not None:
        pk, pd_k = prev_row["K"], prev_row["D"]
        if pk < pd_k and k > d:
            return "✦ 金叉"
        if pk > pd_k and k < d:
            return "↓ 死叉"
    if k > 80 and d > 80:
        return "高位"
    if k < 20 and d < 20:
        return "低位"
    return ""