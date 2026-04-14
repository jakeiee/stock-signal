"""
资金面数据源：全市场成交额、北向资金净流入、融资融券余额。

数据来源：
  - 全市场成交额：中证全指历史接口
  - 北向资金：东方财富沪深港通接口
  - 融资融券：东方财富融资融券接口

返回格式统一为 {"data": ..., "error": str|None, "updated_at": str}。
"""

import os
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict, Any


def _csindex_ohlcv(csindex_code: str = "000985", days: int = 30) -> pd.DataFrame:
    """从 中证官网 获取日线 OHLCV 数据（pandas DataFrame）。"""
    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=days + 30)).strftime("%Y%m%d")

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://www.csindex.com.cn/",
        "Accept": "application/json",
    }

    try:
        resp = requests.get(
            "https://www.csindex.com.cn/csindex-home/perf/index-perf",
            params={"indexCode": csindex_code, "startDate": start, "endDate": end},
            headers=headers,
            timeout=20,
        )
        records = resp.json().get("data", [])
        if not records:
            return pd.DataFrame()

        rows = []
        for r in records:
            close = r.get("close") or r.get("closePri")
            if not close or float(close) <= 0:
                continue
            rows.append({
                "date":      r.get("tradeDate", ""),
                "open":      float(r.get("open", 0)),
                "high":      float(r.get("high", 0)),
                "low":       float(r.get("low", 0)),
                "close":     float(close),
                "volume":    float(r.get("tradingVol", 0)),
                "turnover":  float(r.get("tradingValue", 0)),  # 亿元
                "cons_number": int(r.get("consNumber", 0)),
            })

        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"], format="%Y%m%d").dt.strftime("%Y-%m-%d")
        return df.sort_values("date").reset_index(drop=True)

    except Exception:
        return pd.DataFrame()


def fetch_turnover() -> Dict[str, Any]:
    """获取全市场成交额（最近交易日 + 前一交易日）。"""
    try:
        df = _csindex_ohlcv("000985", days=15)
        if df.empty or len(df) < 2:
            return {"data": None, "error": "中证全指接口无数据", "updated_at": ""}

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        chg = None
        if prev["turnover"] > 0:
            chg = round((latest["turnover"] - prev["turnover"]) / prev["turnover"] * 100, 2)

        return {
            "data": {
                "turnover":      latest["turnover"],
                "turnover_prev": prev["turnover"],
                "chg_pct":       chg,
                "date":          latest["date"],
            },
            "error": None,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    except Exception as e:
        return {"data": None, "error": str(e), "updated_at": ""}


def fetch_northbound() -> Dict[str, Any]:
    """获取北向资金净流入。"""
    try:
        url = "https://push2.eastmoney.com/api/qt/kamt.rtmin/get"
        headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.eastmoney.com/"}

        resp = requests.get(url, headers=headers, timeout=10)
        data = resp.json()

        mkt = data.get("data", {})
        if not mkt:
            return {"data": None, "error": "北向资金接口无数据", "updated_at": ""}

        return {
            "data": {
                "net_inflow":      mkt.get("northMktCapFlowNet", 0) or 0,
                "net_inflow_sh":   mkt.get("shanghaiMktCapFlowNet", 0) or 0,
                "net_inflow_sz":   mkt.get("shenzhenMktCapFlowNet", 0) or 0,
                "date":            datetime.now().strftime("%Y-%m-%d"),
            },
            "error": None,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    except Exception as e:
        return {"data": None, "error": str(e), "updated_at": ""}


def fetch_margin(override: Optional[Dict] = None) -> Dict[str, Any]:
    """获取融资融券余额数据。"""
    if override:
        return {
            "data": {
                "date":          override.get("date", ""),
                "rz_net":        override.get("rz_net"),
                "bal_chg":       override.get("bal_chg"),
                "mkt_turnover":  override.get("mkt_turnover"),
                "source":        "manual",
            },
            "error": None,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }

    try:
        csv_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "data", "margin.csv"
        )

        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path)
            if not df.empty:
                latest = df.iloc[-1]
                return {
                    "data": {
                        "date":           latest.get("date", ""),
                        "rz_net":         latest.get("rz_net"),
                        "bal_chg":        latest.get("bal_chg"),
                        "bal_chg_pct":    latest.get("bal_chg_pct"),
                        "rz_bal":         latest.get("rz_bal"),
                        "rq_bal":         latest.get("rq_bal"),
                        "rz_buy":         latest.get("rz_buy"),
                        "rq_sell":        latest.get("rq_sell"),
                        "mkt_turnover":   latest.get("mkt_turnover"),
                        "sh_turnover":    latest.get("sh_turnover"),
                        "sz_turnover":    latest.get("sz_turnover"),
                        "bj_turnover":    latest.get("bj_turnover"),
                        "turnover_ratio": latest.get("turnover_ratio"),
                        "source":         latest.get("source", "csv"),
                    },
                    "error": None,
                    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                }

        return {"data": None, "error": "未找到 margin.csv", "updated_at": ""}

    except Exception as e:
        return {"data": None, "error": str(e), "updated_at": ""}


def fetch_znz_active_cap() -> Dict[str, Any]:
    """获取指南针活跃市值。"""
    return {
        "data": {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "active_cap": None,
            "chg_pct": None,
            "signal_desc": "待接入",
            "position_suggest": "",
        },
        "error": None,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def fetch_new_accounts(override: Optional[float] = None) -> Dict[str, Any]:
    """获取新开户数。"""
    if override is not None:
        return {
            "data": {
                "period": datetime.now().strftime("%Y-%m"),
                "new_accounts": override,
                "source": "manual",
                "mom_pct": None,
            },
            "error": None,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }

    return {
        "data": {
            "period": datetime.now().strftime("%Y-%m"),
            "new_accounts": None,
            "source": "csv_cache",
            "mom_pct": None,
        },
        "error": None,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
