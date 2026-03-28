"""
中证指数官网（csindex.com.cn）数据源。

提供两个能力：
  1. fetch_ohlcv()  — 获取指定指数的日线 OHLCV DataFrame
  2. calc_kdj()     — 从日线 DataFrame 重采样为周线并计算 KDJ(9,3,3)

算法参考 kdj_calculator.py：
  - 周线采用 pandas resample('W-FRI')（每周五收盘作为周线 K 线）
  - RSV = (close - lowest_low_9w) / (highest_high_9w - lowest_low_9w) × 100
  - K / D 使用 EMA 平滑：prev × 2/3 + current × 1/3，初值均为 50
  - J = 3K − 2D
"""

from datetime import datetime, timedelta
from typing import Optional, List

import pandas as pd
import requests


def fetch_ohlcv(index_code: str, days: int = 300) -> pd.DataFrame:
    """
    从中证官网获取指数日线 OHLCV 数据。

    Args:
        index_code: 中证指数代码，如 "H30269"。
        days:       向前取数天数（接口端最多返回约 500 条）。

    Returns:
        包含 [date, open, high, low, close, volume] 列的 DataFrame，
        按日期升序排列；接口异常或无数据时返回空 DataFrame。
    """
    start = (datetime.now() - timedelta(days=days + 30)).strftime("%Y%m%d")
    end   = datetime.now().strftime("%Y%m%d")
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer":    "https://www.csindex.com.cn/",
    }
    resp = requests.get(
        "https://www.csindex.com.cn/csindex-home/perf/index-perf",
        params={"indexCode": index_code, "startDate": start, "endDate": end},
        headers=headers,
        timeout=20,
    )
    records = resp.json().get("data", [])
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df = df[df["open"] > 0].copy()
    df["date"] = pd.to_datetime(df["tradeDate"], format="%Y%m%d").dt.strftime("%Y-%m-%d")
    df = df.rename(columns={"tradingVol": "volume", "tradingValue": "amount"})
    df = df[["date", "open", "high", "low", "close", "volume"]]
    df = df.sort_values("date").reset_index(drop=True)
    return df


def fetch_daily_chg(index_code: str, days: int = 60) -> list:
    """
    从中证官网获取指数近 N 个自然日内的日线行情，返回涨跌幅、成交额列表。

    Returns:
        [{"date": "YYYY-MM-DD", "close": float, "change_pct": float,
          "turnover": float, "cons_number": int}, ...]
        按日期升序，接口失败返回空列表。
    """
    start = (datetime.now() - timedelta(days=days + 10)).strftime("%Y%m%d")
    end   = datetime.now().strftime("%Y%m%d")
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer":    "https://www.csindex.com.cn/",
    }
    try:
        resp = requests.get(
            "https://www.csindex.com.cn/csindex-home/perf/index-perf",
            params={"indexCode": index_code, "startDate": start, "endDate": end},
            headers=headers,
            timeout=20,
        )
        resp.raise_for_status()
        records = resp.json().get("data", [])
    except Exception:
        return []

    result = []
    for r in records:
        tv = r.get("tradingValue", 0)
        if not tv or float(tv) <= 0:
            continue
        raw_date = str(r.get("tradeDate", ""))
        try:
            date = datetime.strptime(raw_date, "%Y%m%d").strftime("%Y-%m-%d")
        except Exception:
            date = raw_date
        result.append({
            "date":         date,
            "close":        float(r.get("close", 0)),
            "change_pct":   float(r.get("changePct", 0)),   # 指数涨跌幅（%）
            "turnover":     round(float(tv), 2),             # 成交额（亿）
            "cons_number":  int(r.get("consNumber", 0)),
        })
    return result


def calc_kdj(df: pd.DataFrame, n: int = 9) -> Optional[dict]:
    """
    将日线 DataFrame 重采样为周线后计算 KDJ(n,3,3)，返回最新一周结果。

    Args:
        df: fetch_ohlcv() 返回的 DataFrame。
        n:  KDJ 参数，默认 9（对应 KDJ(9,3,3)）。

    Returns:
        {"date": str, "K": float, "D": float, "J": float, "source": "csindex"}
        数据不足时返回 None。
    """
    if df.empty or len(df) < n:
        return None

    # ── 重采样为周线 ──────────────────────────────────────────────────────────
    df2 = df.copy()
    df2["date"] = pd.to_datetime(df2["date"])
    df2 = df2.set_index("date")
    agg    = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    weekly = df2.resample("W-FRI").agg(agg).dropna().reset_index()
    weekly["date"] = weekly["date"].dt.strftime("%Y-%m-%d")

    if len(weekly) < n:
        return None

    # ── 计算 RSV ──────────────────────────────────────────────────────────────
    low_min  = weekly["low"].rolling(window=n, min_periods=n).min()
    high_max = weekly["high"].rolling(window=n, min_periods=n).max()
    denom    = high_max - low_min
    rsv      = (weekly["close"] - low_min) / denom.where(denom != 0, 1) * 100

    # ── EMA 平滑：K / D（初值 50，权重 2/3）────────────────────────────────────
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

    valid = weekly.dropna(subset=["k"])
    if valid.empty:
        return None

    last = valid.iloc[-1]
    return {
        "date":   last["date"],
        "K":      round(float(last["k"]), 2),
        "D":      round(float(last["d"]), 2),
        "J":      round(float(last["j"]), 2),
        "source": "csindex",
    }
