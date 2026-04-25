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


def _xalpha_volume_turnover(xalpha_code: str, days: int = 5) -> float:
    """使用xalpha获取指数成交量，并估算成交额（亿元）。
    
    指数volume单位是股数，成交额 = 成交量 × 均价 / 100000000
    均价通过指数收盘价与基准比例估算
    """
    try:
        import xalpha as xa
        info = xa.indexinfo(code=xalpha_code)
        if info.price is None or len(info.price) < 1:
            return None
        latest = info.price.iloc[-1]
        volume_shares = float(latest.get("volume", 0))  # 股数
        
        # 指数点位约等于均价的1000倍(粗略估算)
        # 成交额(亿元) = 成交量(股) × 均价(元) / 1亿
        # 均价 ≈ 指数点位 / 1000 (简化估算)
        close_price = float(latest.get("close", 0))
        if close_price <= 0:
            return None
        
        # 简化估算：成交额 ≈ 成交量 × (收盘价/1000) / 1亿
        # 但更准确的是用比例因子
        avg_price_factor = close_price / 1000  # 均价估算
        turnover = volume_shares * avg_price_factor / 100000000
        return turnover
    except Exception:
        return None


def fetch_turnover() -> Dict[str, Any]:
    """获取全市场成交额（最近交易日 + 前一交易日）。支持CSV缓存降级。
    
    改进：分别获取沪市、深市、京市成交额
    """
    # 1. 优先调用API
    try:
        # 获取中证全指（上证+深证+北证）
        df = _csindex_ohlcv("000985", days=15)
        if df.empty or len(df) < 2:
            raise ValueError("中证全指接口无数据")

        latest = df.iloc[-1]
        prev = df.iloc[-2]
        date_str = latest["date"]

        chg = None
        if prev["turnover"] > 0:
            chg = round((latest["turnover"] - prev["turnover"]) / prev["turnover"] * 100, 2)

        # 获取各市场成交额
        sh_turnover = None  # 上证
        sz_turnover = None  # 深证
        bj_turnover = None  # 北证

        try:
            # 上证指数
            df_sh = _csindex_ohlcv("000001", days=5)
            if not df_sh.empty:
                latest_sh = df_sh[df_sh["date"] == date_str]
                if not latest_sh.empty:
                    sh_turnover = latest_sh.iloc[0]["turnover"]

            # 北证50
            df_bj = _csindex_ohlcv("899050", days=5)
            if not df_bj.empty:
                latest_bj = df_bj[df_bj["date"] == date_str]
                if not latest_bj.empty:
                    bj_turnover = latest_bj.iloc[0]["turnover"]

            # 深证：从中证全指减去上证和北证
            if sh_turnover is not None and bj_turnover is not None:
                sz_turnover = round(latest["turnover"] - sh_turnover - bj_turnover, 2)
        except Exception:
            pass

        result = {
            "turnover":      latest["turnover"],
            "turnover_prev": prev["turnover"],
            "chg_pct":       chg,
            "date":          date_str,
            "source":        "api",
            # 各市场成交额
            "sh_turnover":   sh_turnover,
            "sz_turnover":   sz_turnover,
            "bj_turnover":   bj_turnover,
        }

        # 保存到CSV缓存
        _append_csv("turnover.csv", {
            "date":          date_str,
            "turnover":      latest["turnover"],
            "sh_turnover":   sh_turnover,
            "sz_turnover":   sz_turnover,
            "bj_turnover":   bj_turnover,
            "source":        "csindex+xalpha",
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
                "sh_turnover":   latest.get("sh_turnover"),
                "sz_turnover":   latest.get("sz_turnover"),
                "bj_turnover":   latest.get("bj_turnover"),
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

    # 1. 优先调用东方财富融资交易额接口（RPTA_WEB_MARGIN_DAILYTRADE）
    # 该接口返回：融资/融券余额、交易额、占成交额比例等完整数据
    try:
        import time
        ts = int(time.time() * 1000)
        url = f"https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPTA_WEB_MARGIN_DAILYTRADE&columns=ALL&source=WEB&sortColumns=STATISTICS_DATE&sortTypes=-1&pageNumber=1&pageSize=1&_={ts}"

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Referer": "https://data.eastmoney.com/rzrq/zhtjday.html",
        }

        resp = requests.get(url, headers=headers, timeout=15)
        data = resp.json()

        if data.get("success") and data.get("result"):
            records = data["result"].get("data", [])
            if records:
                r = records[0]
                # 转换日期格式
                raw_date = r.get("STATISTICS_DATE", "")
                date_str = ""
                if raw_date:
                    date_str = pd.to_datetime(str(raw_date)).strftime("%Y-%m-%d")

                # 融资余额（亿元，直接来自接口）
                rzye = float(r.get("FIN_BALANCE")) if r.get("FIN_BALANCE") else None
                # 融券余额（亿元）
                rqye = float(r.get("LOAN_BALANCE")) if r.get("LOAN_BALANCE") else None
                # 两融余额（亿元）
                total_bal = float(r.get("MARGIN_BALANCE")) if r.get("MARGIN_BALANCE") else None
                # 两融余额占A股流通市值比例（%，直接来自接口）
                rz_yezb = float(r.get("BALANCE_RATIO")) if r.get("BALANCE_RATIO") else None
                # 融资买入额（亿元）
                rz_buy = float(r.get("FIN_BUY_AMT")) if r.get("FIN_BUY_AMT") else None
                # 融资卖出额（亿元）
                loan_sell_amt = float(r.get("LOAN_SELL_AMT")) if r.get("LOAN_SELL_AMT") else None
                # 两融交易额（亿元）
                rz_trade_amt = float(r.get("MARGIN_TRADE_AMT")) if r.get("MARGIN_TRADE_AMT") else None
                # 两融交易额占A股成交额比例（%，直接来自接口）
                rz_turnover_ratio = float(r.get("TRADE_AMT_RATIO")) if r.get("TRADE_AMT_RATIO") else None

                result = {
                    "date":              date_str,
                    "rz_net":            None,          # 融资净买入（该接口不提供）
                    "bal_chg":           None,
                    "rz_bal":            rzye,
                    "rq_bal":            rqye,
                    "total_bal":         total_bal,
                    "rz_buy":            rz_buy,
                    "loan_sell_amt":     loan_sell_amt,
                    "rz_trade_amt":      rz_trade_amt,
                    "rz_yezb":           rz_yezb,        # 两融余额占A股流通市值比例
                    "mkt_turnover":      None,
                    "rz_turnover_ratio": rz_turnover_ratio,  # 两融交易额占A股成交额比例
                    "source":            "api",
                }

                # 保存到CSV缓存
                _append_csv("margin.csv", {
                    "date":              date_str,
                    "rz_bal":            rzye,
                    "rq_bal":            rqye,
                    "total_bal":         total_bal,
                    "rz_net":            None,
                    "rz_buy":            rz_buy,
                    "loan_sell_amt":     loan_sell_amt,
                    "rz_trade_amt":      rz_trade_amt,
                    "rz_yezb":           rz_yezb,
                    "rz_turnover_ratio": rz_turnover_ratio,
                    "source":            "eastmoney",
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
                "date":              latest.get("date", ""),
                "rz_net":            float(latest.get("rz_net")) if latest.get("rz_net") else None,
                "bal_chg":           None,
                "rz_bal":            float(latest.get("rz_bal")) if latest.get("rz_bal") else None,
                "rq_bal":            float(latest.get("rq_bal")) if latest.get("rq_bal") else None,
                "total_bal":         float(latest.get("total_bal")) if latest.get("total_bal") else None,
                "rz_buy":            float(latest.get("rz_buy")) if latest.get("rz_buy") else None,
                "loan_sell_amt":     float(latest.get("loan_sell_amt")) if latest.get("loan_sell_amt") else None,
                "rz_trade_amt":      float(latest.get("rz_trade_amt")) if latest.get("rz_trade_amt") else None,
                "rz_yezb":           float(latest.get("rz_yezb")) if latest.get("rz_yezb") else None,
                "mkt_turnover":      None,
                "rz_turnover_ratio": float(latest.get("rz_turnover_ratio")) if latest.get("rz_turnover_ratio") else None,
                "source":            "csv_cache",
            },
                "error": f"降级读取缓存（API: {e}）",
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }


def fetch_margin_history(n: int = 30) -> pd.DataFrame:
    """获取最近n天的两融历史数据，用于趋势分析。"""
    df = _load_csv("margin.csv")
    if df.empty or len(df) < 5:
        # 尝试调用API获取更多历史数据
        try:
            import time
            ts = int(time.time() * 1000)
            url = f"https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPTA_WEB_MARGIN_DAILYTRADE&columns=ALL&source=WEB&sortColumns=STATISTICS_DATE&sortTypes=-1&pageNumber=1&pageSize={n}&_={ts}"

            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Referer": "https://data.eastmoney.com/rzrq/zhtjday.html",
            }

            resp = requests.get(url, headers=headers, timeout=15)
            data = resp.json()

            if data.get("success") and data.get("result"):
                records = data["result"].get("data", [])
                rows = []
                for r in records:
                    raw_date = r.get("STATISTICS_DATE", "")
                    if raw_date:
                        date_str = pd.to_datetime(str(raw_date)).strftime("%Y-%m-%d")
                        rows.append({
                            "date": date_str,
                            "rz_bal": float(r.get("FIN_BALANCE")) if r.get("FIN_BALANCE") else None,
                            "rq_bal": float(r.get("LOAN_BALANCE")) if r.get("LOAN_BALANCE") else None,
                            "total_bal": float(r.get("MARGIN_BALANCE")) if r.get("MARGIN_BALANCE") else None,
                            "rz_yezb": float(r.get("BALANCE_RATIO")) if r.get("BALANCE_RATIO") else None,
                            "rz_trade_amt": float(r.get("MARGIN_TRADE_AMT")) if r.get("MARGIN_TRADE_AMT") else None,
                            "rz_turnover_ratio": float(r.get("TRADE_AMT_RATIO")) if r.get("TRADE_AMT_RATIO") else None,
                        })
                df = pd.DataFrame(rows)
        except Exception:
            pass

    if df.empty or len(df) < 5:
        return pd.DataFrame()

    # 确保按日期排序
    df = df.sort_values("date", ascending=False).reset_index(drop=True)
    return df.head(n)


def analyze_margin_trend(history: pd.DataFrame, window: int = 10) -> Dict[str, Any]:
    """分析两融趋势，检测警示信号。
    
    警示条件：两融余额占流通市值比例超过3% 且 两融交易额占成交额比例见顶后快速下降
    """
    if history.empty or len(history) < window:
        return {"warning": False, "reason": ""}

    result = {"warning": False, "reason": "", "trend": {}}

    # 提取最近的数据
    latest = history.iloc[0]
    prev_window = history.head(window)

    # 1. 检查两融余额占流通市值比例
    rz_yezb = latest.get("rz_yezb")
    if rz_yezb is None:
        return result

    # 2. 检查两融交易额占成交额比例趋势
    rz_turnover_ratios = prev_window["rz_turnover_ratio"].dropna().tolist()
    if len(rz_turnover_ratios) < 3:
        return result

    # 计算比例变化趋势
    recent_avg = sum(rz_turnover_ratios[:3]) / 3
    older_avg = sum(rz_turnover_ratios[3:6]) / 3 if len(rz_turnover_ratios) >= 6 else recent_avg

    # 检测警示信号
    warning_flag = False
    warning_reason = ""

    # 条件1: 两融余额占比 > 3%
    if rz_yezb > 3.0:
        # 条件2: 两融交易额占比见顶后下降（近期均值 < 早期均值 - 0.5%）
        if older_avg > recent_avg + 0.5:
            warning_flag = True
            warning_reason = (
                f"两融余额占流通市值{rz_yezb:.2f}%，超过3%警戒线；"
                f"两融交易额占比从{older_avg:.2f}%降至{recent_avg:.2f}%，呈下降趋势"
            )
        elif rz_turnover_ratios[0] < rz_turnover_ratios[1] < rz_turnover_ratios[2]:
            # 连续下降
            warning_flag = True
            warning_reason = (
                f"两融余额占流通市值{rz_yezb:.2f}%，超过3%警戒线；"
                f"两融交易额占比连续下降({rz_turnover_ratios[2]:.2f}%→{rz_turnover_ratios[1]:.2f}%→{rz_turnover_ratios[0]:.2f}%)"
            )

    # 趋势描述
    if older_avg > recent_avg + 0.3:
        trend_desc = "下降趋势"
    elif older_avg < recent_avg - 0.3:
        trend_desc = "上升趋势"
    else:
        trend_desc = "相对平稳"

    result["warning"] = warning_flag
    result["reason"] = warning_reason
    result["trend"] = {
        "rz_yezb": rz_yezb,
        "rz_turnover_ratio_latest": rz_turnover_ratios[0],
        "rz_turnover_ratio_recent_avg": recent_avg,
        "rz_turnover_ratio_older_avg": older_avg,
        "trend_desc": trend_desc,
    }

    return result


def fetch_znz_active_cap() -> Dict[str, Any]:
    """获取指南针活跃市值。从CSV缓存读取。
    
    入场/持有/离场周期判断逻辑：
    - 大于4%：入场信号
    - 小于-2.3%：离场信号
    - 上一个明显信号为入场 → 多头区间
    - 上一个明显信号为离场 → 空头区间
    """
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

        # 当前涨跌幅
        chg_pct = float(latest["chg_pct"]) if latest.get("chg_pct") else None

        # 入场/持有/离场周期判断
        # 查找最近一个明显信号（从最新数据往前找）
        last_clear_signal = None
        last_clear_signal_date = None
        for idx in range(len(df_cache) - 1, -1, -1):
            row = df_cache.iloc[idx]
            cap_chg = float(row["chg_pct"]) if row.get("chg_pct") else None
            if cap_chg is None:
                continue
            if cap_chg >= 4.0:
                last_clear_signal = "entry"  # 入场
                last_clear_signal_date = row["date"]
                break
            elif cap_chg <= -2.3:
                last_clear_signal = "exit"  # 离场
                last_clear_signal_date = row["date"]
                break

        # 判断当前区间类型
        if last_clear_signal == "entry":
            zone_type = "bullish"  # 多头区间
            zone_desc = "多头区间"
        elif last_clear_signal == "exit":
            zone_type = "bearish"  # 空头区间
            zone_desc = "空头区间"

        # 当前信号判断
        if chg_pct is not None:
            if chg_pct >= 4.0:
                current_signal = "entry"
                current_signal_desc = "入场信号"
            elif chg_pct <= -2.3:
                current_signal = "exit"
                current_signal_desc = "离场信号"
            else:
                current_signal = "holding"
                current_signal_desc = f"持有中({zone_desc})"
        else:
            current_signal = "neutral"
            current_signal_desc = "观望"

        # 原始信号描述（兼容旧逻辑）
        signal_map = {
            "exit": "离场信号",
            "neutral": "中性",
            "caution": "谨慎",
            "opportunity": "机会",
        }
        signal_desc = signal_map.get(str(latest.get("signal", "")), latest.get("signal", ""))

        # 打印活跃市值数据（供调试/检查空头区间）
        print(f"[DEBUG] 活跃市值数据: 日期={latest['date']}, 市值={latest['active_cap']/10000:.2f}万亿, "
              f"涨跌幅={chg_pct:+.2f}%, 区间类型={zone_type}({zone_desc}), "
              f"上次信号={'入场' if last_clear_signal == 'entry' else '离场' if last_clear_signal == 'exit' else '无'}={last_clear_signal_date}")

        return {
            "data": {
                "date": latest["date"],
                "active_cap": latest["active_cap"],
                "chg_pct": chg_pct,
                "mom_pct": mom_pct,
                "signal": latest.get("signal", ""),
                "signal_desc": signal_desc,
                "source": "csv_cache",
                # 新增：入场/持有/离场周期
                "current_signal": current_signal,
                "current_signal_desc": current_signal_desc,
                "zone_type": zone_type,
                "zone_desc": zone_desc,
                "last_clear_signal": last_clear_signal,
                "last_clear_signal_date": last_clear_signal_date,
                "entry_threshold": 4.0,
                "exit_threshold": -2.3,
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
