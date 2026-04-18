"""
资金面数据源：全市场成交额、北向资金净流入、融资融券余额。

数据来源：
  - 全市场成交额：中证全指历史接口
  - 北向资金：东方财富沪深港通接口
  - 融资融券：东方财富融资融券接口

返回格式统一为 {"data": ..., "error": str|None, "updated_at": str}。
"""

import os
import json
import re
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict, Any


# CSV缓存路径
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


def _csv_path(name: str) -> str:
    """返回CSV文件路径"""
    return os.path.join(DATA_DIR, name)


def _load_csv(name: str, date_col: str = "date") -> pd.DataFrame:
    """从CSV加载数据，无数据或异常返回空DataFrame"""
    path = _csv_path(name)
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        df = pd.read_csv(path)
        if df.empty:
            return df
        if date_col in df.columns:
            # 保持原始格式排序，日期格式YYYY-MM-DD，月格式YYYY-MM
            return df.sort_values(date_col).reset_index(drop=True)
        return df
    except Exception:
        return pd.DataFrame()


def _append_csv(name: str, row: Dict, key_col: str = "date") -> None:
    """追加一行数据到CSV，避免重复"""
    path = _csv_path(name)
    df_new = pd.DataFrame([row])
    if os.path.exists(path):
        df_existing = pd.read_csv(path)
        if key_col in df_existing.columns:
            # 避免重复key覆盖
            existing_keys = set(df_existing[key_col].astype(str).tolist())
            if str(row.get(key_col, "")) in existing_keys:
                return
        df = pd.concat([df_existing, df_new], ignore_index=True)
    else:
        df = df_new
    df.to_csv(path, index=False)


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
    """获取全市场成交额（最近交易日 + 前一交易日）。支持CSV缓存降级。"""
    # 1. 优先调用API
    try:
        df = _csindex_ohlcv("000985", days=15)
        if df.empty or len(df) < 2:
            raise ValueError("中证全指接口无数据")

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        chg = None
        if prev["turnover"] > 0:
            chg = round((latest["turnover"] - prev["turnover"]) / prev["turnover"] * 100, 2)

        result = {
            "turnover":      latest["turnover"],
            "turnover_prev": prev["turnover"],
            "chg_pct":       chg,
            "date":          latest["date"],
            "source":        "api",
        }

        # 保存到CSV缓存
        _append_csv("turnover.csv", {
            "date":    latest["date"],
            "turnover": latest["turnover"],
            "source":  "csindex",
        })

        return {
            "data": result,
            "error": None,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    except Exception as e:
        # 2. API失败，降级读取CSV缓存
        df_cache = _load_csv("turnover.csv")
        if df_cache.empty:
            return {"data": None, "error": f"API失败: {e}，无缓存数据", "updated_at": ""}

        latest = df_cache.iloc[-1]
        prev = df_cache.iloc[-2] if len(df_cache) >= 2 else latest

        chg = None
        if prev["turnover"] > 0:
            chg = round((latest["turnover"] - prev["turnover"]) / prev["turnover"] * 100, 2)

        return {
            "data": {
                "turnover":      latest["turnover"],
                "turnover_prev": prev["turnover"],
                "chg_pct":       chg,
                "date":          latest["date"],
                "source":        "csv_cache",
            },
            "error": f"降级读取缓存（API: {e}）",
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }


def fetch_northbound() -> Dict[str, Any]:
    """获取北向资金净流入。支持CSV缓存降级。"""
    # 1. 优先调用API
    try:
        url = "https://push2.eastmoney.com/api/qt/kamt.rtmin/get"
        headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.eastmoney.com/"}

        resp = requests.get(url, headers=headers, timeout=10)
        data = resp.json()

        mkt = data.get("data", {})
        if not mkt:
            raise ValueError("北向资金接口无数据")

        result = {
            "net_inflow":      mkt.get("northMktCapFlowNet", 0) or 0,
            "net_inflow_sh":   mkt.get("shanghaiMktCapFlowNet", 0) or 0,
            "net_inflow_sz":   mkt.get("shenzhenMktCapFlowNet", 0) or 0,
            "date":            datetime.now().strftime("%Y-%m-%d"),
            "source":          "api",
        }

        # 保存到CSV缓存
        _append_csv("northbound.csv", {
            "date":          result["date"],
            "net_inflow":    result["net_inflow"],
            "net_inflow_sh": result["net_inflow_sh"],
            "net_inflow_sz": result["net_inflow_sz"],
            "source":        "eastmoney",
        })

        return {
            "data": result,
            "error": None,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    except Exception as e:
        # 2. API失败，降级读取CSV缓存
        df_cache = _load_csv("northbound.csv")
        if df_cache.empty:
            return {"data": None, "error": f"API失败: {e}，无缓存数据", "updated_at": ""}

        latest = df_cache.iloc[-1]
        return {
            "data": {
                "net_inflow":      float(latest["net_inflow"]),
                "net_inflow_sh":   float(latest.get("net_inflow_sh", 0)),
                "net_inflow_sz":   float(latest.get("net_inflow_sz", 0)),
                "date":            latest["date"],
                "source":          "csv_cache",
            },
            "error": f"降级读取缓存（API: {e}）",
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }


def fetch_margin(override: Optional[Dict] = None) -> Dict[str, Any]:
    """获取融资融券余额数据。支持API+CSV缓存降级。"""
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

    # 1. 优先调用东方财富API
    try:
        import time
        ts = int(time.time() * 1000)
        url = f"https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPTA_RZRQ_LSHJ&columns=ALL&source=WEB&sortColumns=dim_date&sortTypes=-1&pageNumber=1&pageSize=1&filter=&_={ts}"

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Referer": "https://data.eastmoney.com/rzrq/total.html",
        }

        resp = requests.get(url, headers=headers, timeout=15)
        data = resp.json()

        if data.get("success") and data.get("result"):
            records = data["result"].get("data", [])
            if records:
                r = records[0]
                # 转换日期格式
                raw_date = r.get("DIM_DATE", "")
                date_str = ""
                if raw_date:
                    date_str = pd.to_datetime(str(raw_date)).strftime("%Y-%m-%d")

                # 两融余额（元 → 亿元）
                rzrqye = float(r.get("RZRQYE", 0)) / 100000000
                # 融资余额
                rzye = float(r.get("RZYE", 0)) / 100000000 if r.get("RZYE") else None
                # 融券余额
                rqye = float(r.get("RQYE", 0)) / 100000000 if r.get("RQYE") else None
                # 融资净买入
                rz_net = float(r.get("RZJMG", 0)) / 100000000 if r.get("RZJMG") else None
                # 融资买入额
                rz_buy = float(r.get("RZJME", 0)) / 100000000 if r.get("RZJME") else None
                # 融券卖出额（RQMCE：元 → 亿元）
                rqmc = float(r.get("RQMCE", 0)) / 100000000 if r.get("RQMCE") else None

                result = {
                    "date":           date_str,
                    "rz_net":         rz_net,
                    "bal_chg":        None,
                    "rz_bal":         rzye,
                    "rq_bal":         rqye,
                    "total_bal":      rzrqye,
                    "rz_buy":         rz_buy,
                    "rq_sell":        rqmc,
                    "mkt_turnover":   None,
                    "source":         "api",
                }

                # 保存到CSV缓存
                _append_csv("margin.csv", {
                    "date":         date_str,
                    "rz_bal":       rzye,
                    "rq_bal":       rqye,
                    "total_bal":    rzrqye,
                    "rz_net":       rz_net,
                    "rz_buy":       rz_buy,
                    "rq_sell":      rqmc,
                    "source":        "eastmoney",
                })

                return {
                    "data": result,
                    "error": None,
                    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                }

        raise ValueError(f"API返回异常: {data.get('message', '未知错误')}")

    except Exception as e:
        # 2. API失败，降级读取CSV缓存
        df_cache = _load_csv("margin.csv")
        if df_cache.empty:
            return {"data": None, "error": f"API失败: {e}，无缓存数据", "updated_at": ""}

        latest = df_cache.iloc[-1]
        return {
            "data": {
                "date":           latest.get("date", ""),
                "rz_net":         float(latest.get("rz_net")) if latest.get("rz_net") else None,
                "bal_chg":        None,
                "rz_bal":         float(latest.get("rz_bal")) if latest.get("rz_bal") else None,
                "rq_bal":         float(latest.get("rq_bal")) if latest.get("rq_bal") else None,
                "total_bal":      float(latest.get("total_bal")) if latest.get("total_bal") else None,
                "rz_buy":         float(latest.get("rz_buy")) if latest.get("rz_buy") else None,
                "rq_sell":        float(latest.get("rq_sell")) if latest.get("rq_sell") else None,
                "mkt_turnover":   None,
                "source":          "csv_cache",
            },
            "error": f"降级读取缓存（API: {e}）",
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }


def fetch_znz_active_cap() -> Dict[str, Any]:
    """获取指南针活跃市值。从CSV缓存读取。"""
    try:
        df_cache = _load_csv("znz_active_cap.csv")
        if df_cache.empty:
            return {
                "data": None,
                "error": "无缓存数据",
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }

        latest = df_cache.iloc[-1]
        prev = df_cache.iloc[-2] if len(df_cache) >= 2 else latest

        # 计算环比变化
        mom_pct = None
        if prev["active_cap"] > 0:
            mom_pct = round((latest["active_cap"] - prev["active_cap"]) / prev["active_cap"] * 100, 2)

        # 信号描述
        signal_map = {
            "exit": "离场信号",
            "neutral": "中性",
            "caution": "谨慎",
            "opportunity": "机会",
        }
        signal_desc = signal_map.get(str(latest.get("signal", "")), latest.get("signal", ""))

        return {
            "data": {
                "date":          latest["date"],
                "active_cap":    latest["active_cap"],
                "chg_pct":       float(latest["chg_pct"]) if latest.get("chg_pct") else None,
                "mom_pct":       mom_pct,
                "signal":        latest.get("signal", ""),
                "signal_desc":   signal_desc,
                "source":        "csv_cache",
            },
            "error": None,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    except Exception as e:
        return {
            "data": None,
            "error": str(e),
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }


def _fetch_new_accounts_api() -> list:
    """从上证所接口获取新开户数据，返回[{period, new_accounts}]"""
    try:
        import time
        # 上个月日期
        last_month = (datetime.now().replace(day=1) - timedelta(days=1)).strftime("%Y%m")
        ts = int(time.time() * 1000)

        url = f"https://query.sse.com.cn/commonQuery.do?jsonCallBack=jsonpCallback&sqlId=COMMON_SSE_TZZ_M_ALL_ACCT_C&isPagination=false&MDATE={last_month}&_={ts}"

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Referer": "https://www.sse.com.cn/",
        }

        resp = requests.get(url, headers=headers, timeout=15)
        text = resp.text

        # 解析JSONP响应
        json_str = re.search(r'jsonpCallback\((.+)\)', text)
        if not json_str:
            raise ValueError("JSONP解析失败")

        data = json.loads(json_str.group(1))
        records = data.get("result", [])

        results = []
        for r in records:
            term = r.get("TERM", "")
            a_acct = r.get("A_ACCT", "0")
            # 只取有效数据（TERM格式如2026.01，跳过特殊行）
            if term and re.match(r"^\d{4}\.\d{2}$", term) and float(a_acct) > 0:
                period = term.replace(".", "-")  # 2026.01 -> 2026-01
                results.append({
                    "period": period,
                    "new_accounts": float(a_acct),
                    "source": "sse",
                })

        return results

    except Exception as e:
        raise e


def fetch_new_accounts(override: Optional[float] = None) -> Dict[str, Any]:
    """获取散户新开户数量。优先CSV，CSV无数据则调用API。"""
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

    # 检查上个月
    last_month = (datetime.now().replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    last_month_short = (datetime.now().replace(day=1) - timedelta(days=1)).strftime("%Y%m")

    # 1. 检查CSV是否有上个月数据
    df_cache = _load_csv("new_accounts.csv", date_col="period")
    has_latest = False
    if not df_cache.empty and "period" in df_cache.columns:
        existing_periods = set(df_cache["period"].astype(str).tolist())
        has_latest = last_month in existing_periods

    # 2. CSV没有上个月数据，调用API获取
    if not has_latest:
        try:
            api_records = _fetch_new_accounts_api()
            for record in api_records:
                _append_csv("new_accounts.csv", {
                    "period": record["period"],
                    "new_accounts": record["new_accounts"],
                    "mom_pct": None,
                    "yoy_pct": None,
                    "source": record["source"],
                }, key_col="period")
            # 重新加载
            df_cache = _load_csv("new_accounts.csv", date_col="period")
        except Exception as e:
            # API失败，降级读取CSV
            if df_cache.empty:
                return {
                    "data": None,
                    "error": f"API失败: {e}，无缓存数据",
                    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                }

    # 3. 从CSV返回最新数据
    if df_cache.empty:
        return {
            "data": None,
            "error": "无缓存数据",
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }

    # 按period降序，取最新一条
    df_sorted = df_cache.sort_values("period", ascending=False)
    latest = df_sorted.iloc[0]
    prev = df_sorted.iloc[1] if len(df_sorted) >= 2 else None

    # 计算环比
    mom_pct = None
    if prev is not None and prev["new_accounts"] > 0:
        mom_pct = round((latest["new_accounts"] - prev["new_accounts"]) / prev["new_accounts"] * 100, 2)

    source = "csv_cache" if has_latest else "api+csv"

    return {
        "data": {
            "period":       latest["period"],
            "new_accounts": float(latest["new_accounts"]),
            "mom_pct":      mom_pct,
            "source":       source,
        },
        "error": None if has_latest else "降级读取（API获取后缓存）",
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
