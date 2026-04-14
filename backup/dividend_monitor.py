#!/usr/bin/env python3
"""
红利指数监控脚本
跟踪：红利低波(H30269)、红利质量(931468)、东证红利低波(931446)
指标：股息率/PE 估值（含全历史 max 百分位、风险溢价率）+ 周线 KDJ（最新一周）
无风险利率：实时从东方财富获取中国10年期国债收益率(CN10Y)

数据源策略：
  周线KDJ：优先妙想API → 失败自动降级中证官网OHLCV自算
  估值数据：优先妙想API → 成功时保存本地CSV缓存 → 失败时读取CSV缓存（报告中标注）

估值CSV缓存：
  valuation_cache.csv（脚本同目录）
  字段：code, date, div, div_pct, div_max, div_min, div_hist_n, div_hist_start,
        pe, pe_pct, pe_max, pe_min, risk_premium, hist_start, source, saved_at

用法：
    python3 dividend_monitor.py            # 仅终端输出
    python3 dividend_monitor.py --feishu   # 终端输出 + 推送飞书
环境变量：
    MX_APIKEY      妙想 API Key（未设置时使用内置默认值）
    FEISHU_WEBHOOK 飞书机器人 Webhook（可覆盖脚本内置地址）
"""

import csv
import os
import sys
import json
import time
import subprocess
import requests
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, date
from typing import Optional, List

# ─────────────────────────── 配置 ───────────────────────────

API_BASE = "https://mkapi2.dfcfs.com/finskillshub/api/claw"
APIKEY   = os.environ.get("MX_APIKEY", "mkt_HeEVfE9lWxYWMJpYsdLfU4-rWvXyKj5xU0mvS0giDOA")
MX_HEADERS = {"Content-Type": "application/json", "apikey": APIKEY}

FEISHU_WEBHOOK = os.environ.get(
    "FEISHU_WEBHOOK",
    "https://open.feishu.cn/open-apis/bot/v2/hook/46b97530-d458-401a-8678-82da01b3d3ca",
)

# 指数配置：新增 csindex_code（中证官网代码）和 em_secid（东方财富备用）
INDEXES = [
    {"name": "红利低波",     "code": "H30269", "csindex_code": "H30269", "query_name": "红利低波H30269"},
    {"name": "红利质量",     "code": "931468", "csindex_code": "931468", "query_name": "红利质量931468"},
    {"name": "东证红利低波", "code": "931446", "csindex_code": "931446", "query_name": "东证红利低波931446"},
]

WEEK_KDJ_COUNT = 1    # 只取最新一周KDJ
BOND_FALLBACK  = 1.70  # 无法获取实时数据时的保底无风险利率(%)

# 估值数据缓存文件路径（保存在脚本同目录）
_SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
VAL_CACHE_FILE = os.path.join(_SCRIPT_DIR, "valuation_cache.csv")   # CSV 格式
_VAL_CSV_FIELDS = [
    "code", "date", "div", "div_pct", "div_max", "div_min", "div_hist_n", "div_hist_start",
    "pe", "pe_pct", "pe_max", "pe_min", "risk_premium", "hist_start", "source", "saved_at",
]


# ─────────────────────────── 估值缓存（CSV） ───────────────────────────

def load_val_cache() -> dict:
    """
    读取本地估值 CSV 缓存，返回 {code: result_dict}。
    文件不存在或解析失败时返回空字典。
    兼容旧版 JSON 缓存：若 CSV 不存在而 JSON 存在则自动迁移。
    """
    _json_path = os.path.join(_SCRIPT_DIR, "valuation_cache.json")

    # ── 优先读 CSV ──
    if os.path.isfile(VAL_CACHE_FILE):
        try:
            result = {}
            with open(VAL_CACHE_FILE, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    code = row.get("code", "").strip()
                    if not code:
                        continue
                    result[code] = {
                        "date":          row.get("date", ""),
                        "div":           float(row["div"])           if row.get("div")           else None,
                        "div_pct":       float(row["div_pct"])       if row.get("div_pct")       else None,
                        "div_max":       float(row["div_max"])       if row.get("div_max")       else None,
                        "div_min":       float(row["div_min"])       if row.get("div_min")       else None,
                        "div_hist_n":    int(float(row["div_hist_n"])) if row.get("div_hist_n") else 0,
                        "div_hist_start":row.get("div_hist_start", ""),
                        "pe":            float(row["pe"])            if row.get("pe")            else None,
                        "pe_pct":        float(row["pe_pct"])        if row.get("pe_pct")        else None,
                        "pe_max":        float(row["pe_max"])        if row.get("pe_max")        else None,
                        "pe_min":        float(row["pe_min"])        if row.get("pe_min")        else None,
                        "risk_premium":  float(row["risk_premium"])  if row.get("risk_premium")  else None,
                        "hist_start":    row.get("hist_start", ""),
                        "source":        row.get("source", "cache"),
                        "saved_at":      row.get("saved_at", ""),
                    }
            return result
        except Exception as e:
            print(f"  ⚠ CSV缓存读取失败: {e}")
            return {}

    # ── 旧版 JSON 迁移 ──
    if os.path.isfile(_json_path):
        try:
            with open(_json_path, "r", encoding="utf-8") as f:
                old = json.load(f)
            # 补全 CSV 需要的字段
            for code, v in old.items():
                v.setdefault("div_hist_start", v.get("hist_start", ""))
                v.setdefault("saved_at", "migrated")
            save_val_cache(old)   # 写入 CSV
            print(f"  ℹ 已将旧版 JSON 缓存迁移为 CSV")
            return old
        except Exception:
            pass

    return {}


def save_val_cache(cache: dict) -> None:
    """将估值结果写入本地 CSV 缓存文件（每个 code 一行，按 code 排序）。"""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    try:
        with open(VAL_CACHE_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=_VAL_CSV_FIELDS)
            writer.writeheader()
            for code in sorted(cache.keys()):
                v = cache[code]
                writer.writerow({
                    "code":           code,
                    "date":           v.get("date", ""),
                    "div":            v.get("div", ""),
                    "div_pct":        v.get("div_pct", ""),
                    "div_max":        v.get("div_max", ""),
                    "div_min":        v.get("div_min", ""),
                    "div_hist_n":     v.get("div_hist_n", ""),
                    "div_hist_start": v.get("div_hist_start", v.get("hist_start", "")),
                    "pe":             v.get("pe", ""),
                    "pe_pct":         v.get("pe_pct", ""),
                    "pe_max":         v.get("pe_max", ""),
                    "pe_min":         v.get("pe_min", ""),
                    "risk_premium":   v.get("risk_premium", ""),
                    "hist_start":     v.get("hist_start", ""),
                    "source":         v.get("source", "mx"),
                    "saved_at":       now_str,
                })
    except Exception as e:
        print(f"  ⚠ 缓存写入失败: {e}")


# ─────────────────────────── 实时国债收益率 ───────────────────────────

def fetch_risk_free_rate() -> tuple:
    """
    实时获取中国10年期国债(CN10Y)收益率。
    主链路：push2.eastmoney.com 实时行情接口（f43字段，存储值需除以10000）
    备用：push2his.eastmoney.com 历史K线（若主链路失败）
    返回 (收益率%, 日期字符串)，失败时返回 (BOND_FALLBACK, "fallback")。
    """
    # ── 主链路：push2 实时接口 ──
    try:
        r = requests.get(
            "https://push2.eastmoney.com/api/qt/stock/get",
            params={"secid": "171.CN10Y", "fields": "f43,f86"},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=8,
        )
        d = r.json().get("data") or {}
        if d.get("f43") and d["f43"] > 0:
            rate = d["f43"] / 10000       # 18316 → 1.8316
            ts   = datetime.fromtimestamp(d["f86"]).strftime("%Y-%m-%d") if d.get("f86") else "实时"
            return rate, ts
    except Exception:
        pass

    # ── 备用：push2his 历史K线 ──
    try:
        today = date.today()
        beg = (today - timedelta(days=7)).strftime("%Y%m%d")
        end = today.strftime("%Y%m%d")
        result = subprocess.run(
            ["curl", "-s", "--max-time", "10",
             "-H", "User-Agent: Mozilla/5.0",
             f"https://push2his.eastmoney.com/api/qt/stock/kline/get"
             f"?secid=171.CN10Y&klt=101&fqt=1"
             f"&fields1=f1,f2,f3,f4&fields2=f51,f52,f53,f54,f55"
             f"&beg={beg}&end={end}"],
            capture_output=True, text=True, timeout=15,
        )
        data   = json.loads(result.stdout)
        klines = data.get("data", {}).get("klines", [])
        if klines:
            latest = klines[-1].split(",")
            return float(latest[2]), latest[0]
    except Exception:
        pass

    return BOND_FALLBACK, "fallback"


# ─────────────────────────── 妙想 API ───────────────────────────

def mx_query(tool_query: str, retries: int = 3, delay: float = 4.0) -> list:
    """
    调用妙想 API，返回 dataTableDTOList，失败或空结果时重试。
    若 status=113（今日调用次数已达上限），立即抛出 RuntimeError 不再重试。
    """
    for attempt in range(retries + 1):
        try:
            resp = requests.post(
                f"{API_BASE}/query",
                headers=MX_HEADERS,
                json={"toolQuery": tool_query},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            # 识别限额错误（status=113），不重试直接上报
            api_status = data.get("status")
            if api_status == 113:
                raise RuntimeError(f"妙想API今日配额已用尽（status=113）")
            dto    = (data.get("data") or {}).get("data") or {}
            result = dto.get("searchDataResultDTO") or {}
            items  = result.get("dataTableDTOList") or []
            if items:
                return items
            # 空结果可能是频率限制，等待后重试
            if attempt < retries:
                time.sleep(delay * (attempt + 1))
        except RuntimeError:
            raise   # 配额错误直接向上抛
        except Exception as e:
            if attempt < retries:
                time.sleep(delay)
            else:
                raise
    return []


# ─────────────────────────── 工具函数 ───────────────────────────

def parse_float(s) -> Optional[float]:
    if s is None or s in ("", "null", "-"):
        return None
    try:
        return float(str(s).replace("%", ""))
    except Exception:
        return None


def percentile_rank(values: List[Optional[float]], val: float) -> float:
    valid = [v for v in values if v is not None]
    if not valid:
        return float("nan")
    return sum(1 for v in valid if v <= val) / len(valid) * 100


def iso_week(date_str: str) -> tuple:
    return datetime.strptime(date_str, "%Y-%m-%d").isocalendar()[:2]


def extract_weekly(heads: list, *value_lists) -> list:
    """
    接口返回日线序列（KDJ值以周线参数计算），按ISO周分组取每周最后一个交易日。
    数据从新到旧排列，每周首次出现的日期即为该周末最后交易日。
    """
    seen = {}
    rows = []
    for i, h in enumerate(heads):
        wk = iso_week(h)
        if wk not in seen:
            seen[wk] = True
            row = {"date": h}
            for j, vlist in enumerate(value_lists):
                row[f"v{j}"] = vlist[i] if i < len(vlist) else None
            rows.append(row)
    return rows


# ─────────────────────────── 核心查询 ───────────────────────────

def fetch_valuation(idx: dict, risk_free_rate: float) -> dict:
    """获取全历史股息率+PE，计算 max 百分位与风险溢价率。"""
    queries = [
        f"{idx['query_name']} 2020年至今每日股息率TTM和市盈率PETTM",
        f"{idx['query_name']}股息率TTM和PE市盈率每日历史数据",
    ]
    item = None
    for q in queries:
        try:
            items = mx_query(q)
        except RuntimeError as e:
            return {"error": str(e), "error_type": "quota"}
        if not items:
            continue
        # 找包含两个指标（股息率+PE）的item
        for it in items:
            nm = it["nameMap"]
            has_div = any("股息" in nm.get(k, "") for k in it["indicatorOrder"])
            has_pe  = any("市盈" in nm.get(k, "") or "PE" in nm.get(k, "") for k in it["indicatorOrder"])
            if has_div and has_pe:
                item = it
                break
        if item:
            break

    if item is None:
        return {"error": "无数据或字段不完整"}

    table = item["table"]
    io    = item["indicatorOrder"]
    nm    = item["nameMap"]
    heads = table["headName"]

    div_key = next((k for k in io if "股息" in nm.get(k, "")), None)
    pe_key  = next((k for k in io if "市盈" in nm.get(k, "") or "PE" in nm.get(k, "")), None)
    if not div_key or not pe_key:
        return {"error": f"字段未找到: {nm}"}

    div_vals = [parse_float(v) for v in table[div_key]]
    pe_vals  = [parse_float(v) for v in table[pe_key]]
    valid_div = [v for v in div_vals if v is not None]
    valid_pe  = [v for v in pe_vals  if v is not None]

    latest_div = parse_float(table[div_key][0])
    latest_pe  = parse_float(table[pe_key][0])
    if latest_div is None or latest_pe is None:
        return {"error": "最新值为空"}

    risk_premium = (1 / latest_pe * 100) - risk_free_rate if latest_pe else None

    return {
        "date":          heads[0],
        "div":           latest_div,
        "div_pct":       percentile_rank(valid_div, latest_div),
        "div_max":       max(valid_div),
        "div_min":       min(valid_div),
        "div_hist_n":    len(valid_div),
        "div_hist_start":heads[-1],        # 股息率历史起始日期
        "pe":            latest_pe,
        "pe_pct":        percentile_rank(valid_pe, latest_pe),
        "pe_max":        max(valid_pe),
        "pe_min":        min(valid_pe),
        "risk_premium":  risk_premium,
        "hist_start":    heads[-1],
        "source":        "mx",    # 数据来源标记
    }


def _csindex_ohlcv(csindex_code: str, days: int = 300) -> pd.DataFrame:
    """
    从中证指数官网获取 OHLCV 日线数据。
    用于在妙想 API 不可用时自算 KDJ。
    """
    start = (datetime.now() - timedelta(days=days + 30)).strftime("%Y%m%d")
    end   = datetime.now().strftime("%Y%m%d")
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://www.csindex.com.cn/",
    }
    resp = requests.get(
        "https://www.csindex.com.cn/csindex-home/perf/index-perf",
        params={"indexCode": csindex_code, "startDate": start, "endDate": end},
        headers=headers,
        timeout=20,
    )
    records = resp.json().get("data", [])
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df = df[df["open"] > 0]
    df["date"] = pd.to_datetime(df["tradeDate"], format="%Y%m%d").dt.strftime("%Y-%m-%d")
    df = df.rename(columns={"tradingVol": "volume", "tradingValue": "amount"})
    df = df[["date", "open", "high", "low", "close", "volume"]].copy()
    df = df.sort_values("date").reset_index(drop=True)
    return df


def _calc_kdj_from_df(df: pd.DataFrame, n: int = 9) -> Optional[dict]:
    """
    参考 kdj_calculator.py 的算法，从日线 DataFrame 重采样为周线后计算 KDJ。
    返回最新周 {date, K, D, J}，数据不足时返回 None。
    """
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
        "source": "csindex",   # 标记数据来源
    }


def fetch_week_kdj(idx: dict) -> list:
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
            table = item["table"]
            io    = item["indicatorOrder"]
            heads = table["headName"]
            k_key = io[0]
            d_key = f"KDJSJZBD_{k_key}"
            j_key = f"KDJSJZBJ_{k_key}"

            k_list = [parse_float(v) for v in table.get(k_key, [])]
            d_list = [parse_float(v) for v in table.get(d_key, [])]
            j_list = [parse_float(v) for v in table.get(j_key, [])]

            rows = extract_weekly(heads, k_list, d_list, j_list)
            result = [{"date": r["date"], "K": r["v0"], "D": r["v1"], "J": r["v2"], "source": "mx"}
                      for r in rows[:WEEK_KDJ_COUNT]]
            if result and result[0]["K"] is not None:
                return result
    except RuntimeError:
        pass   # 配额用尽，直接降级，不打印堆栈
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


# ─────────────────────────── KDJ 信号判断 ───────────────────────────

def kdj_signal(row: dict, prev_row: Optional[dict]) -> str:
    k, d, j = row["K"], row["D"], row["J"]
    if k is None or d is None or j is None:
        return ""
    if j < 0:
        return "⚠ J<0 极度超卖"
    if j > 100:
        return "⚠ J>100 超买"
    if prev_row and prev_row["K"] is not None and prev_row["D"] is not None:
        pk, pd = prev_row["K"], prev_row["D"]
        if pk < pd and k > d:
            return "✦ 金叉"
        if pk > pd and k < d:
            return "↓ 死叉"
    if k > 80 and d > 80:
        return "高位"
    if k < 20 and d < 20:
        return "低位"
    return ""


# ─────────────────────────── 终端输出 ───────────────────────────

def fmt_pct_bar(pct: float, width: int = 10) -> str:
    """用简单字符条显示百分位。"""
    filled = round(pct / 100 * width)
    return "[" + "█" * filled + "░" * (width - filled) + f"] {pct:.1f}%"


def print_report(val_results: list, kdj_data: dict, risk_free_rate: float,
                 rf_date: str, now: str):
    W = 68
    rf_src = f"实时 CN10Y ({rf_date})" if rf_date != "fallback" else "保底默认值"
    print(f"\n{'═' * W}")
    print(f"  📊 红利指数监控  |  {now}")
    print(f"  无风险利率: {risk_free_rate:.4f}%（{rf_src}）")
    print(f"{'═' * W}")

    for idx, res in zip(INDEXES, val_results):
        print(f"\n  ▌ {idx['name']}（{idx['code']}）", end="")
        if "error" in res:
            print(f"  ✗ {res['error']}")
        else:
            # 数据来源标注
            src = res.get("source", "mx")
            src_tag = "  ⚠ 缓存数据" if src == "cache" else ""
            print(f"  数据日期: {res['date']}{src_tag}")

            # 历史区间信息（用于说明百分位的统计范围）
            hist_start = res.get("hist_start") or res.get("div_hist_start", "")
            hist_n     = res.get("div_hist_n", 0)
            hist_tag   = f"（{hist_start} 起，共 {hist_n} 个交易日）" if hist_start and hist_n else ""

            # 估值指标
            rp = f"{res['risk_premium']:+.2f}%" if res["risk_premium"] is not None else "N/A"
            print(f"    股息率  {res['div']:.3f}%  {fmt_pct_bar(res['div_pct'])}  {hist_tag}")
            print(f"    市盈率  {res['pe']:.2f}    {fmt_pct_bar(res['pe_pct'])}")
            print(f"    风险溢价  {rp}")

        # KDJ（最新一周）—— 无论估值是否有误都始终展示
        rows = kdj_data.get(idx["code"], [])
        if rows:
            r = rows[0]
            k_s = f"{r['K']:.1f}" if r["K"] is not None else "N/A"
            d_s = f"{r['D']:.1f}" if r["D"] is not None else "N/A"
            j_s = f"{r['J']:.1f}" if r["J"] is not None else "N/A"
            sig = kdj_signal(r, rows[1] if len(rows) > 1 else None)
            sig_str = f"  {sig}" if sig else ""
            kdj_src = r.get("source", "mx")
            kdj_tag = "  ⚠ 自算" if kdj_src == "csindex" else ""
            print(f"    周KDJ  K={k_s}  D={d_s}  J={j_s}{sig_str}  （{r['date']}）{kdj_tag}")
        else:
            print(f"    周KDJ  暂无数据")

    print(f"\n  ─ 百分位说明：全历史max分位；PE%位越低越便宜；股息率%位越高越丰厚")
    print(f"  ─ 风险溢价 = 1/PE×100% − {risk_free_rate:.4f}%（无风险利率）")
    print(f"{'═' * W}\n")


# ─────────────────────────── 飞书推送 ───────────────────────────

def _pct_label(pct: float) -> str:
    """百分位等级标签。"""
    if pct >= 80:
        return "极高"
    if pct >= 60:
        return "偏高"
    if pct >= 40:
        return "适中"
    if pct >= 20:
        return "偏低"
    return "极低"


def build_feishu_card(val_results: list, kdj_data: dict, risk_free_rate: float,
                      rf_date: str, now: str) -> dict:
    """构建飞书交互式卡片消息（简洁版）。"""
    rf_src = f"实时 ({rf_date})" if rf_date != "fallback" else "保底默认"

    # 拼装每只指数的摘要行
    index_lines = []
    for idx, res in zip(INDEXES, val_results):
        name = idx["name"]
        code = idx["code"]
        # KDJ最新一周（无论估值是否有误都展示）
        rows = kdj_data.get(code, [])
        if rows:
            r   = rows[0]
            k_s = f"{r['K']:.1f}" if r["K"] is not None else "-"
            d_s = f"{r['D']:.1f}" if r["D"] is not None else "-"
            j_s = f"{r['J']:.1f}" if r["J"] is not None else "-"
            sig = kdj_signal(r, rows[1] if len(rows) > 1 else None)
            kdj_src = r.get("source", "mx")
            kdj_label = "自算⚠" if kdj_src == "csindex" else "妙想"
            kdj_str = f"K={k_s} D={d_s} J={j_s}" + (f" *{sig}*" if sig else "")
            kdj_date = r["date"]
        else:
            kdj_str   = "暂无数据"
            kdj_label = "-"
            kdj_date  = "-"

        if "error" in res:
            block = (
                f"**{name}**（{code}）　❌ 估值数据：{res['error']}\n"
                f"　📈 周KDJ（{kdj_date}，{kdj_label}）{kdj_str}"
            )
            index_lines.append(block)
            continue

        rp = f"{res['risk_premium']:+.2f}%" if res["risk_premium"] is not None else "N/A"
        div_lv = _pct_label(res["div_pct"])
        pe_lv  = _pct_label(100 - res["pe_pct"])   # PE越低越好，取反

        # 图标
        div_icon = "🔴" if res["div_pct"] > 70 else ("🟢" if res["div_pct"] < 30 else "🟡")
        pe_icon  = "🟢" if res["pe_pct"] < 20 else ("🔴" if res["pe_pct"] > 80 else "🟡")
        rp_icon  = "🟢" if (res["risk_premium"] or 0) > 3 else ("🔴" if (res["risk_premium"] or 0) < 1 else "🟡")

        # 估值来源
        val_src = res.get("source", "mx")
        val_src_note = " ⚠*缓存*" if val_src == "cache" else ""

        # 历史区间
        hist_start = res.get("hist_start") or res.get("div_hist_start", "")
        hist_n     = res.get("div_hist_n", 0)
        hist_note  = f"*（{hist_start} 起，{hist_n} 日）*" if hist_start and hist_n else ""

        block = (
            f"**{name}**（{code}）　数据日期：{res['date']}{val_src_note}\n"
            f"　{div_icon} 股息率 **{res['div']:.3f}%**　百分位 {res['div_pct']:.1f}% *{div_lv}*　{hist_note}\n"
            f"　{pe_icon} 市盈率 **{res['pe']:.2f}**　百分位 {res['pe_pct']:.1f}% *{pe_lv}*\n"
            f"　{rp_icon} 风险溢价 **{rp}**\n"
            f"　📈 周KDJ（{kdj_date}，{kdj_label}）{kdj_str}"
        )
        index_lines.append(block)

    # 说明文字
    note = (
        f"无风险利率 **{risk_free_rate:.4f}%**（10年期国债 CN10Y，{rf_src}）\n"
        "百分位为全历史max分位 · PE%位越低越便宜 · 股息率%位越高越丰厚\n"
        f"风险溢价 = 1/PE×100% − {risk_free_rate:.4f}%"
    )

    elements = []
    # 说明行
    elements.append({
        "tag": "div",
        "text": {"tag": "lark_md", "content": note},
    })
    elements.append({"tag": "hr"})
    # 各指数块
    for i, block_text in enumerate(index_lines):
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": block_text},
        })
        if i < len(index_lines) - 1:
            elements.append({"tag": "hr"})

    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": f"📊 红利指数监控  {now}"},
                "template": "blue",
            },
            "elements": elements,
        },
    }


def send_feishu(payload: dict) -> bool:
    """发送飞书消息，返回是否成功。"""
    try:
        r = requests.post(FEISHU_WEBHOOK, json=payload, timeout=15)
        resp = r.json()
        if resp.get("code") == 0 or resp.get("StatusCode") == 0:
            return True
        print(f"  飞书返回异常: {resp}")
        return False
    except Exception as e:
        print(f"  飞书推送失败: {e}")
        return False


# ─────────────────────────── 主流程 ───────────────────────────

def main():
    send_to_feishu = "--feishu" in sys.argv
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Step 0: 实时无风险利率
    print("→ 获取10年期国债收益率(CN10Y)...", end=" ", flush=True)
    risk_free_rate, rf_date = fetch_risk_free_rate()
    if rf_date == "fallback":
        print(f"✗ 获取失败，使用保底值 {risk_free_rate}%")
    else:
        print(f"✓ {risk_free_rate:.4f}%（{rf_date}）")

    # Step 1: 估值数据（妙想API优先，失败降级本地缓存）
    print("\n[1/2] 获取估值数据...")
    val_cache = load_val_cache()
    val_results = []
    cache_updated = False
    quota_exhausted = False   # 妙想配额是否已用尽

    for i, idx in enumerate(INDEXES):
        if i > 0:
            time.sleep(3)
        print(f"  → {idx['name']}...", end=" ", flush=True)
        try:
            if quota_exhausted:
                # 配额用尽，直接走缓存，不再请求妙想
                raise RuntimeError("妙想API今日配额已用尽（status=113）")

            res = fetch_valuation(idx, risk_free_rate)

            if res.get("error_type") == "quota":
                quota_exhausted = True
                raise RuntimeError(res["error"])

            if "error" not in res:
                # 成功：更新缓存
                val_cache[idx["code"]] = res
                cache_updated = True
                print(f"✓  [妙想]")
            else:
                # 妙想返回其他错误，尝试降级到缓存
                cached = val_cache.get(idx["code"])
                if cached:
                    pe = cached.get("pe")
                    cached["risk_premium"] = (1 / pe * 100) - risk_free_rate if pe else None
                    cached["source"] = "cache"
                    res = cached
                    print(f"✗ {res.get('error','?')}  [降级→缓存 {cached.get('date','?')}]")
                else:
                    print(f"✗ {res.get('error','?')}  [无缓存]")
            val_results.append(res)

        except Exception as e:
            err_msg = str(e)
            cached = val_cache.get(idx["code"])
            if cached:
                pe = cached.get("pe")
                cached["risk_premium"] = (1 / pe * 100) - risk_free_rate if pe else None
                cached["source"] = "cache"
                val_results.append(cached)
                label = "配额用尽" if "113" in err_msg or "配额" in err_msg else str(e)[:30]
                print(f"✗ {label}  [降级→缓存 {cached.get('date','?')}]")
            else:
                val_results.append({"error": err_msg})
                label = "配额用尽" if "113" in err_msg or "配额" in err_msg else err_msg[:40]
                print(f"✗ {label}  [无缓存]")

    if cache_updated:
        save_val_cache(val_cache)
        print(f"  ✓ 估值缓存已更新 → {VAL_CACHE_FILE}")

    # Step 2: 周线KDJ（妙想优先，失败降级中证官网自算）
    print("\n[2/2] 获取周线 KDJ...")
    kdj_data = {}
    for i, idx in enumerate(INDEXES):
        if i > 0:
            time.sleep(3)
        print(f"  → {idx['name']}...", end=" ", flush=True)
        try:
            rows = fetch_week_kdj(idx)
            kdj_data[idx["code"]] = rows
            if rows:
                src = rows[0].get("source", "?")
                src_label = "妙想" if src == "mx" else "中证官网自算"
                print(f"✓  [{src_label}]")
            else:
                print("✗ 无数据")
        except Exception as e:
            kdj_data[idx["code"]] = []
            print(f"✗ {e}")

    # 终端输出
    print_report(val_results, kdj_data, risk_free_rate, rf_date, now)

    # 飞书推送
    if send_to_feishu:
        print("→ 推送飞书...", end=" ", flush=True)
        card = build_feishu_card(val_results, kdj_data, risk_free_rate, rf_date, now)
        ok = send_feishu(card)
        print("✓ 已发送" if ok else "✗ 发送失败")
    else:
        print("  提示：添加 --feishu 参数可将报告推送到飞书机器人")


if __name__ == "__main__":
    main()
