"""
资金面数据源。

已实现指标：
  - A股月度新开户数（散户资金情绪）：上交所接口自动获取，CSV 本地缓存，手动录入作为回退
  - 融资融券（杠杆资金）：东方财富 datacenter-web API 实时获取，CSV 缓存离线兜底

    接口 RPTA_WEB_MARGIN_DAILYTRADE（两融每日交易汇总，主接口）：
        STATISTICS_DATE  - 日期
        FIN_BALANCE      - 融资余额（亿元）
        LOAN_BALANCE     - 融券余额（亿元）
        MARGIN_BALANCE   - 两融余额（亿元）= FIN_BALANCE + LOAN_BALANCE
        BALANCE_RATIO    - 两融余额/全市场市值（%，接口直给，口径略异于流通市值）
        FIN_BUY_AMT      - 融资买入额（亿元）
        LOAN_SELL_AMT    - 融券卖出额（亿元）
        MARGIN_TRADE_AMT - 两融交易额（亿元）= FIN_BUY_AMT + LOAN_SELL_AMT
        TRADE_AMT_RATIO  - 两融交易/全市场成交额（%，接口直给）

    接口 RPTA_RZRQ_LSHJ（两融历史汇总，补充接口）：
        DIM_DATE   - 日期
        LTSZ       - A股流通市值（元，用于自算 bal_mktcap_ratio）
        RZYEZB     - 融资余额/流通市值（%，接口直给精确值 rz_mktcap_ratio）
        RZYE       - 融资余额（元，验证用）
        RZRQYE     - 两融余额（元，验证用）
        RZMRE      - 融资买入额（元）
        RZCHE      - 融资偿还额（元）
        RZJME      - 融资净买入额（元）= RZMRE - RZCHE
        RZRQYECZ   - 字段含义不明（实测非前一交易日余额，不可用于日变动计算）

    全市场成交额（实时）：push2.eastmoney.com 行情快照
        secid=1.000001（上证综指）f48 → 沪市当日成交额（元）
        secid=0.399001（深证成指）f48 → 深市当日成交额（元）
        secid=0.899050（北证50）  f48 → 京市（北交所）当日成交额（元）
        全市场 = 沪 + 深 + 京

  数据获取策略：
    主接口 RPTA_WEB_MARGIN_DAILYTRADE → 补充接口 RPTA_RZRQ_LSHJ（补 LTSZ/RZYEZB）
    → push2 实时成交额 → CSV 缓存 → 手动录入

待实现指标：
  - 北向资金净流入（当日 + 近5日累计）：来源 东方财富沪深港通接口

接口设计原则：
  - 每个指标单独函数，便于按需调用
  - 失败时返回 {"error": str}，不抛异常
  - 所有数值单位在字段名或注释中标注

数据文件：
  market_monitor/data/new_accounts.csv  — 月度新开户数
    字段：period(YYYY-MM), new_accounts(万户), mom_pct(%), yoy_pct(%), source

  market_monitor/data/margin.csv        — 融资融券日度数据
    字段：
      date(YYYY-MM-DD)       - 数据日期
      total_bal(亿元)        - 两融余额 = 融资余额 + 融券余额
      bal_chg(亿元)          - 两融余额较前日变动
      bal_chg_pct(%)         - 两融余额较前日变动幅度
      rz_mktcap_ratio(%)     - 融资余额/A股流通市值（来自 RZYEZB，接口直给）
      bal_mktcap_ratio(%)    - 两融余额/A股流通市值（自算 = total_bal / LTSZ）
      rz_bal(亿元)           - 融资余额
      rq_bal(亿元)           - 融券余额
      rz_buy(亿元)           - 融资买入额（来自 FIN_BUY_AMT）
      rq_sell(亿元)          - 融券卖出额（来自 LOAN_SELL_AMT）
      rz_repay(亿元)         - 融资偿还额（来自 RZCHE，LSHJ 接口）
      rz_net(亿元)           - 融资净买入额 = rz_buy - rz_repay
      mkt_turnover(亿元)     - 全市场A股成交额（沪+深+京）
      sh_turnover(亿元)      - 沪市成交额
      sz_turnover(亿元)      - 深市成交额
      bj_turnover(亿元)      - 京市（北交所）成交额
      turnover_ratio(%)      - 两融交易/全市场成交额（来自 TRADE_AMT_RATIO 或自算）
      source                 - 数据来源标识

  market_monitor/data/znz_active_cap.csv — 指南针活跃市值（判断增量资金最有效指标）
    字段：
      date(YYYY-MM-DD)       - 数据日期
      active_cap(亿元)       - 活跃市值
      chg_pct(%)             - 日变动幅度
      signal                 - 信号："incremental"(增量入场)/"exit"(资金离场)/"neutral"(中性)
      source                 - 数据来源标识（manual/auto）
    
    信号判断规则：
      - 单日涨幅 ≥ +4%：增量资金入场信号（🟢 加仓信号）
      - 单日跌幅 ≤ -2.3%：资金离场警示信号（🔴 减仓信号）
      - 其他：中性（🟡 观望）
    
    仓位建议（动态仓位 0-40%）：
      - 增量入场信号：40% 仓位
      - 资金离场信号：0-10% 仓位
      - 中性：20% 仓位
"""

import csv
import os
import ssl
import time
import urllib.request
import json
import re
from datetime import datetime
from typing import Optional, List

# macOS 自带 Python 常存在 SSL 根证书缺失问题，对上交所公开接口允许跳过验证
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


# ── CSV 缓存路径 ────────────────────────────────────────────────────────────
_DATA_DIR  = os.path.join(os.path.dirname(__file__), "..", "data")
_CSV_PATH  = os.path.join(_DATA_DIR, "new_accounts.csv")
_CSV_FIELDS = ["period", "new_accounts", "mom_pct", "yoy_pct", "source"]

# 融资融券缓存
_MARGIN_CSV_PATH   = os.path.join(_DATA_DIR, "margin.csv")
_MARGIN_CSV_FIELDS = [
    "date",
    "total_bal",       # 两融余额（亿元）
    "bal_chg",         # 两融余额日变动（亿元）
    "bal_chg_pct",     # 两融余额日变动幅度（%）
    "rz_mktcap_ratio", # 融资余额/流通市值（%，接口 RZYEZB 直给）
    "bal_mktcap_ratio",# 两融余额/流通市值（%，自算）
    "rz_bal",          # 融资余额（亿元）
    "rq_bal",          # 融券余额（亿元）
    "rz_buy",          # 融资买入额（亿元）
    "rq_sell",         # 融券卖出额（亿元，来自 RQMRE）
    "rz_repay",        # 融资偿还额（亿元）
    "rz_net",          # 融资净买入额（亿元）= rz_buy - rz_repay
    "mkt_turnover",    # 全市场成交额（亿元，沪+深+京）
    "sh_turnover",     # 沪市成交额（亿元）
    "sz_turnover",     # 深市成交额（亿元）
    "bj_turnover",     # 京市（北交所）成交额（亿元）
    "turnover_ratio",  # 两融交易/全市场成交额（%，两融交易 = 融资买入 + 融券卖出）
    "source",
]

# 指南针活跃市值缓存
_ZNZ_CSV_PATH = os.path.join(_DATA_DIR, "znz_active_cap.csv")
_ZNZ_CSV_FIELDS = [
    "date",
    "active_cap",      # 活跃市值（亿元）
    "chg_pct",         # 日变动幅度（%）
    "signal",          # 信号：incremental/exit/neutral
    "source",
]


def _ensure_data_dir() -> None:
    os.makedirs(_DATA_DIR, exist_ok=True)


def _read_csv() -> dict:
    """
    读取 CSV 缓存，返回 {period: row_dict} 的字典，按月份索引。
    period 格式为 "YYYY-MM"。
    """
    if not os.path.isfile(_CSV_PATH):
        return {}
    result = {}
    with open(_CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            p = row.get("period", "").strip()
            if p:
                result[p] = {
                    "period":       p,
                    "new_accounts": float(row["new_accounts"]) if row.get("new_accounts") else None,
                    "mom_pct":      float(row["mom_pct"])      if row.get("mom_pct")      else None,
                    "yoy_pct":      float(row["yoy_pct"])      if row.get("yoy_pct")      else None,
                    "source":       row.get("source", ""),
                }
    return result


def _write_csv(records: dict) -> None:
    """
    将 {period: row_dict} 写入 CSV，按 period 升序排列。
    """
    _ensure_data_dir()
    sorted_periods = sorted(records.keys())
    with open(_CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_FIELDS)
        writer.writeheader()
        for p in sorted_periods:
            row = records[p]
            writer.writerow({
                "period":       row.get("period", p),
                "new_accounts": row.get("new_accounts", ""),
                "mom_pct":      "" if row.get("mom_pct") is None else row["mom_pct"],
                "yoy_pct":      "" if row.get("yoy_pct") is None else row["yoy_pct"],
                "source":       row.get("source", ""),
            })


def _fetch_sse_raw(timeout: int = 15) -> list:
    """
    调用上交所月度新开户数接口，返回原始 result 列表。

    接口：https://query.sse.com.cn/commonQuery.do
    sqlId：COMMON_SSE_TZZ_M_ALL_ACCT_C
    字段说明：
      TERM     - 月份标识，格式 "YYYY.MM" 或 "YYYY年合计" / "累计总户数"
      A_ACCT   - A 股新开账户数（万户）
      MDATE    - 数据截止日期（YYYYMM）
    """
    ts  = int(time.time() * 1000)
    url = (
        "https://query.sse.com.cn/commonQuery.do"
        f"?jsonCallBack=jsonpCB&sqlId=COMMON_SSE_TZZ_M_ALL_ACCT_C"
        f"&isPagination=false&MDATE=&_={ts}"
    )
    req = urllib.request.Request(
        url,
        headers={
            "Accept":          "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer":         "https://www.sse.com.cn/",
            "User-Agent":      (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        },
    )
    with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:
        raw = resp.read().decode("utf-8")

    # 响应格式为 JSONP：jsonpCB({...})，提取花括号内容
    m = re.search(r"jsonpCB\((\{.*\})\)", raw, re.DOTALL)
    if not m:
        raise ValueError(f"无法解析 JSONP 响应：{raw[:200]}")
    data = json.loads(m.group(1))
    return data.get("result", [])


def _parse_sse_rows(rows: list) -> dict:
    """
    将上交所接口原始 result 行解析为 {period: row_dict}。
    仅保留格式为 "YYYY.MM" 的月度数据（排除合计行）。
    """
    parsed = {}
    monthly = []
    for row in rows:
        term = str(row.get("TERM", "")).strip()
        # 仅处理月度行："2025.01" / "2026.02" 等
        m = re.match(r"^(\d{4})\.(\d{2})$", term)
        if not m:
            continue
        year, month = int(m.group(1)), int(m.group(2))
        a_acct = float(row.get("A_ACCT", 0) or 0)
        if a_acct <= 0:
            continue
        period = f"{year:04d}-{month:02d}"
        monthly.append((period, a_acct))

    # 计算环比（月度数据按 period 排序后逐月计算）
    monthly.sort(key=lambda x: x[0])
    prev_val = None
    for period, a_acct in monthly:
        if prev_val is not None and prev_val > 0:
            mom_pct = round((a_acct - prev_val) / prev_val * 100, 2)
        else:
            mom_pct = None
        parsed[period] = {
            "period":       period,
            "new_accounts": a_acct,
            "mom_pct":      mom_pct,
            "yoy_pct":      None,   # 上交所接口未直接提供同比，留空
            "source":       "sse(上交所)",
        }
        prev_val = a_acct

    return parsed


def _latest_valid_record(records: dict) -> Optional[dict]:
    """从 {period: row_dict} 中取 new_accounts > 0 的最新月份记录。"""
    valid = [
        (p, r) for p, r in records.items()
        if r.get("new_accounts") and r["new_accounts"] > 0
    ]
    if not valid:
        return None
    return max(valid, key=lambda x: x[0])[1]


def fetch_new_accounts(
    override: Optional[float] = None,
    timeout:  int = 20,
) -> dict:
    """
    获取 A 股月度新开户数（散户资金情绪指标）。

    数据获取策略（优先级从高到低）：
      1. override 手动覆盖值（通过 --new-accounts 命令行参数传入）
      2. 上交所接口自动拉取，增量合并到本地 CSV 缓存
      3. 本地 CSV 缓存读取最新记录（网络失败时的离线回退）
      4. 以上均失败 → 返回 {"error": str}

    数据来源：
      - 上交所 COMMON_SSE_TZZ_M_ALL_ACCT_C 月度投资者统计接口
      - 本地缓存文件：market_monitor/data/new_accounts.csv
      - 字段 A_ACCT 单位：万户

    Args:
        override: 手动覆盖的新开户数（万户）。非 None 时跳过网络请求。
        timeout:  网络请求超时（秒）。

    Returns:
        {
            "period":        str,          # 数据所属月份 "YYYY-MM"
            "new_accounts":  float,        # 新开户数（万户）
            "mom_pct":       float|None,   # 环比变化（%，正=环比增加）
            "yoy_pct":       float|None,   # 同比变化（%）
            "source":        str,          # "sse(上交所)" | "csv_cache" | "manual"
        }
        失败时：{"error": str}

    评分阈值（来自用户定义）：
        ≥ 600 万户/月 → 顶部区间，强空头信号 (-2)
        400–599 万户  → 偏热                  (-1)
        200–399 万户  → 正常                  ( 0)
        100–199 万户  → 偏冷                  (+1)
        <  100 万户   → 极冷，强多头信号       (+2)
    """
    # ── 优先：手动覆盖 ────────────────────────────────────────────────────────
    if override is not None:
        if override <= 0:
            return {"error": f"手动录入的新开户数无效：{override}（万户）"}
        today  = datetime.today()
        year   = today.year if today.month > 1 else today.year - 1
        month  = today.month - 1 if today.month > 1 else 12
        period = f"{year:04d}-{month:02d}"
        return {
            "period":       period,
            "new_accounts": float(override),
            "mom_pct":      None,
            "yoy_pct":      None,
            "source":       "manual",
        }

    # ── 读取现有 CSV 缓存 ─────────────────────────────────────────────────────
    cached = _read_csv()

    # ── 自动获取：上交所接口 ───────────────────────────────────────────────────
    fetch_error = None
    try:
        raw_rows  = _fetch_sse_raw(timeout=timeout)
        new_data  = _parse_sse_rows(raw_rows)

        if not new_data:
            raise ValueError("上交所接口返回无有效月度数据")

        # 增量合并：用接口新数据覆盖/补充缓存中的记录
        merged = dict(cached)
        merged.update(new_data)

        # 重新计算跨越新旧边界的环比（如缓存最后一条和接口第一条之间的环比）
        # new_data 内部已计算好环比，merged 中纯缓存段保持原样
        _write_csv(merged)

        latest = _latest_valid_record(new_data)
        if latest:
            return latest
        # new_data 有记录但全为 0（不应出现，保险起见）
        raise ValueError("接口数据解析后无有效数值")

    except Exception as e:
        fetch_error = str(e)

    # ── 离线回退：读 CSV 缓存最新记录 ─────────────────────────────────────────
    latest_cached = _latest_valid_record(cached)
    if latest_cached:
        rec = dict(latest_cached)
        rec["source"] = "csv_cache"
        return rec

    # ── 全部失败 ──────────────────────────────────────────────────────────────
    return {"error": f"上交所接口获取失败：{fetch_error}；本地亦无缓存数据"}


def fetch_turnover(days: int = 10, timeout: int = 20) -> dict:
    """
    获取全市场近 N 日成交额（中证全指口径）。

    Returns:
        {
            "latest_date":   str,           # 最新交易日 "YYYY-MM-DD"
            "turnover":      float,         # 当日成交额（亿元）
            "turnover_prev": float|None,    # 前一交易日成交额（亿元）
            "chg_pct":       float|None,    # 日环比（%）
            "history":       list[dict],    # 近 N 日记录，每项含 date/turnover
            "source":        str,
        }
        失败时：{"error": str}
    """
    # TODO: 对接中证全指历史接口（参考 dividend_monitor.data_sources.csindex.fetch_daily_chg）
    return {"error": "待实现（TODO: fetch_turnover）"}


def fetch_northbound(timeout: int = 20) -> dict:
    """
    获取北向资金（沪股通 + 深股通）当日净流入。

    Returns:
        {
            "date":          str,   # 数据日期
            "net_inflow":    float, # 当日净流入（亿元，正=净买入，负=净卖出）
            "sh_net":        float, # 沪股通净流入（亿元）
            "sz_net":        float, # 深股通净流入（亿元）
            "5d_cumulative": float, # 近5交易日累计净流入（亿元）
            "source":        str,
        }
        失败时：{"error": str}
    """
    # TODO: 对接东方财富沪深港通资金接口
    return {"error": "待实现（TODO: fetch_northbound）"}


# ── 融资融券 CSV 缓存工具 ──────────────────────────────────────────────────

def _read_margin_csv() -> dict:
    """读取融资融券 CSV 缓存，返回 {date: row_dict}。"""
    if not os.path.isfile(_MARGIN_CSV_PATH):
        return {}
    result = {}
    with open(_MARGIN_CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            d = row.get("date", "").strip()
            if not d:
                continue
            def _f(key, _row=row):
                v = _row.get(key, "")
                return float(v) if v not in ("", None) else None
            result[d] = {
                "date":               d,
                "total_bal":          _f("total_bal"),
                "bal_chg":            _f("bal_chg"),
                "bal_chg_pct":        _f("bal_chg_pct"),
                "rz_mktcap_ratio":    _f("rz_mktcap_ratio"),
                "bal_mktcap_ratio":   _f("bal_mktcap_ratio"),
                "rz_bal":             _f("rz_bal"),
                "rq_bal":             _f("rq_bal"),
                "rz_buy":             _f("rz_buy"),
                "rq_sell":            _f("rq_sell"),
                "rz_repay":           _f("rz_repay"),
                "rz_net":             _f("rz_net"),
                "mkt_turnover":       _f("mkt_turnover"),
                "sh_turnover":        _f("sh_turnover"),
                "sz_turnover":        _f("sz_turnover"),
                "bj_turnover":        _f("bj_turnover"),
                "turnover_ratio":     _f("turnover_ratio"),
                "source":             row.get("source", ""),
            }
    return result


def _write_margin_csv(records: dict) -> None:
    """将 {date: row_dict} 写入融资融券 CSV，按日期升序。"""
    _ensure_data_dir()
    with open(_MARGIN_CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_MARGIN_CSV_FIELDS)
        writer.writeheader()
        for d in sorted(records.keys()):
            row = records[d]
            writer.writerow({
                k: ("" if row.get(k) is None else row[k])
                for k in _MARGIN_CSV_FIELDS
            })


def _latest_margin_record(records: dict) -> Optional[dict]:
    """取 total_bal 有效的最新一条记录。"""
    valid = [(d, r) for d, r in records.items() if r.get("total_bal")]
    if not valid:
        return None
    return max(valid, key=lambda x: x[0])[1]


_EM_BASE_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
_EM_PUSH2_URL = "https://push2.eastmoney.com/api/qt/stock/get"

_EM_HEADERS = {
    "Accept":          "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer":         "https://data.eastmoney.com/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}


def _em_fetch_json(url: str, timeout: int = 15) -> dict:
    """
    调用东方财富 datacenter-web API，解析 JSONP / JSON 响应，返回整个响应体字典。
    """
    req = urllib.request.Request(url, headers=_EM_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:
        raw = resp.read().decode("utf-8")
    # 响应可能是 JSONP（jQuery123...({...})）或纯 JSON
    m = re.search(r"(?:jQuery\w+|datatable\w+)\((.+)\)\s*;?\s*$", raw, re.DOTALL)
    return json.loads(m.group(1)) if m else json.loads(raw)


def _em_extract_rows(data: dict) -> list:
    """从东方财富 API 响应中提取 result.data 列表，失败时返回空列表。"""
    result = data.get("result") or {}
    if isinstance(result, dict):
        return result.get("data") or []
    return []


def _fetch_mkt_turnover_realtime(timeout: int = 10) -> Optional[dict]:
    """
    通过 push2.eastmoney.com 行情快照获取 A 股实时成交额（沪+深+京）。

    接口：https://push2.eastmoney.com/api/qt/stock/get
      secid=1.000001（上证综指）f48 → 沪市当日成交额（元）
      secid=0.399001（深证成指）f48 → 深市当日成交额（元）
      secid=0.899050（北证50）  f48 → 京市（北交所）当日成交额（元）

    注：盘中实时更新；收盘后为当日最终成交额。

    Returns:
        {
            "sh": float,    # 沪市成交额（亿元）
            "sz": float,    # 深市成交额（亿元）
            "bj": float,    # 京市（北交所）成交额（亿元）
            "total": float, # 全市场合计（亿元）
        }
        任一市场请求失败时返回 None。
    """
    mapping = [
        ("1.000001", "sh"),
        ("0.399001", "sz"),
        ("0.899050", "bj"),
    ]
    result = {}
    for secid, key in mapping:
        ts  = int(time.time() * 1000)
        url = f"{_EM_PUSH2_URL}?secid={secid}&fields=f48&_={ts}"
        req = urllib.request.Request(url, headers=_EM_HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:
                raw = resp.read().decode("utf-8")
            d   = json.loads(raw)
            amt = d.get("data", {}).get("f48")
            if isinstance(amt, (int, float)) and amt > 0:
                result[key] = round(amt / 1e8, 2)
            else:
                return None  # 任一无效则放弃
        except Exception:
            return None
    result["total"] = round(result["sh"] + result["sz"] + result["bj"], 2)
    return result


def _fetch_margin_dailytrade(timeout: int = 15) -> dict:
    """
    通过东方财富 RPTA_WEB_MARGIN_DAILYTRADE 接口获取两融每日交易汇总。

    该接口直接提供融资买入额、融券卖出额、两融交易额及占成交额比例，
    数据单位均为亿元（接口原始值即为亿元，无需换算）。

    字段映射：
      STATISTICS_DATE  → date           日期
      FIN_BALANCE      → rz_bal         融资余额（亿元）
      LOAN_BALANCE     → rq_bal         融券余额（亿元）
      MARGIN_BALANCE   → total_bal      两融余额（亿元）
      BALANCE_RATIO    → balance_ratio  两融余额占比（%，接口口径，备用）
      FIN_BUY_AMT      → rz_buy         融资买入额（亿元）
      LOAN_SELL_AMT    → rq_sell        融券卖出额（亿元）
      MARGIN_TRADE_AMT → margin_trade   两融交易额（亿元）= rz_buy + rq_sell
      TRADE_AMT_RATIO  → turnover_ratio 两融交易/成交额（%，接口直给）

    Returns:
        {
            "date":          str,   # YYYY-MM-DD
            "rz_bal":        float, # 融资余额（亿元）
            "rq_bal":        float, # 融券余额（亿元）
            "total_bal":     float, # 两融余额（亿元）
            "balance_ratio": float, # 两融余额/市值（%，接口口径）
            "rz_buy":        float, # 融资买入额（亿元）
            "rq_sell":       float, # 融券卖出额（亿元）
            "margin_trade":  float, # 两融交易额（亿元）
            "turnover_ratio":float, # 两融交易/成交额（%）
        }
        失败时抛出异常。
    """
    ts  = int(time.time() * 1000)
    url = (
        f"{_EM_BASE_URL}?reportName=RPTA_WEB_MARGIN_DAILYTRADE"
        f"&columns=ALL&pageNumber=1&pageSize=2"
        f"&sortColumns=STATISTICS_DATE&sortTypes=-1&_={ts}"
    )
    data = _em_fetch_json(url, timeout=timeout)
    rows = _em_extract_rows(data)
    if not rows:
        raise RuntimeError("RPTA_WEB_MARGIN_DAILYTRADE 返回空数据")

    r = rows[0]  # 最新一条

    def _f(key):
        v = r.get(key)
        return round(float(v), 2) if v is not None else 0.0

    date_str = str(r.get("STATISTICS_DATE", "")).strip()[:10]

    return {
        "date":          date_str,
        "rz_bal":        _f("FIN_BALANCE"),
        "rq_bal":        _f("LOAN_BALANCE"),
        "total_bal":     _f("MARGIN_BALANCE"),
        "balance_ratio": _f("BALANCE_RATIO"),
        "rz_buy":        _f("FIN_BUY_AMT"),
        "rq_sell":       _f("LOAN_SELL_AMT"),
        "margin_trade":  _f("MARGIN_TRADE_AMT"),
        "turnover_ratio":_f("TRADE_AMT_RATIO"),
        # 保存前日两融余额（用于日变动计算，接口第二条即前交易日）
        "_prev_total_bal": round(float(rows[1].get("MARGIN_BALANCE") or 0), 2) if len(rows) > 1 else None,
    }


def _fetch_margin_eastmoney(timeout: int = 15) -> dict:
    """
    合并 RPTA_WEB_MARGIN_DAILYTRADE（主）和 RPTA_RZRQ_LSHJ（补充）两个接口，
    获取完整的两融数据。

    主接口提供：融资买入、融券卖出、两融交易额、成交额占比
    补充接口提供：A股流通市值（LTSZ）、融资余额/流通市值（RZYEZB）、
                  融资偿还额（RZCHE）、融资净买入（RZJME）

    日变动计算策略（优先级从高到低）：
      1. RPTA_WEB_MARGIN_DAILYTRADE 接口第二条（前一交易日，直接从接口获取）
      2. RPTA_RZRQ_LSHJ 接口第二条
    """
    # ── 主接口：RPTA_WEB_MARGIN_DAILYTRADE ───────────────────────────────────
    dt = _fetch_margin_dailytrade(timeout=timeout)
    date_str     = dt["date"]
    total_bal    = dt["total_bal"]
    rz_bal       = dt["rz_bal"]
    rq_bal       = dt["rq_bal"]
    rz_buy       = dt["rz_buy"]
    rq_sell      = dt["rq_sell"]
    turnover_ratio = dt["turnover_ratio"]
    _prev_from_dt  = dt.get("_prev_total_bal")   # DAILYTRADE 接口前日余额

    # ── 补充接口：RPTA_RZRQ_LSHJ（LTSZ / RZYEZB / 偿还额 / 净买入）────────
    rz_mktcap_ratio  = None
    bal_mktcap_ratio = None
    rz_repay         = None
    rz_net           = None
    _prev_from_lshj  = None   # LSHJ 接口前日余额（备用）

    try:
        ts   = int(time.time() * 1000)
        url2 = (
            f"{_EM_BASE_URL}?reportName=RPTA_RZRQ_LSHJ&columns=ALL"
            f"&source=WEB&sortColumns=DIM_DATE&sortTypes=-1"
            f"&pageNumber=1&pageSize=2&_={ts}"
        )
        d2    = _em_fetch_json(url2, timeout=timeout)
        rows2 = _em_extract_rows(d2)
        if rows2:
            lshj    = rows2[0]
            # 流通市值反推：用融资余额/融资占比，而不是两融余额
            # RZYEZB = 融资余额/流通市值(%)
            # 流通市值 = 融资余额 / (RZYEZB/100)
            rz_mktcap_ratio = round(float(lshj.get("RZYEZB") or 0), 4)  # 融资/流通市值(%)
            if rz_mktcap_ratio and rz_mktcap_ratio > 0:
                # 流通市值(亿元) = 融资余额 / 融资占比
                ltsz_yi = rz_bal / (rz_mktcap_ratio / 100)
                # 两融余额/流通市值 = 两融余额 / 流通市值 * 100
                bal_mktcap_ratio = round(total_bal / ltsz_yi * 100, 4)
            else:
                ltsz_yi = round(float(lshj.get("LTSZ") or 0) / 1e8, 2)
                bal_mktcap_ratio = round(total_bal / ltsz_yi * 100, 4) if ltsz_yi > 0 else None
            rz_repay = round(float(lshj.get("RZCHE") or 0) / 1e8, 2)
            rz_net   = round(float(lshj.get("RZJME") or 0) / 1e8, 2)
            if len(rows2) > 1:
                prev_rzrqye = float(rows2[1].get("RZRQYE") or 0)
                _prev_from_lshj = round(prev_rzrqye / 1e8, 2) if prev_rzrqye > 0 else None
    except Exception:
        pass   # 补充接口失败不影响主流程

    # ── 日变动：DAILYTRADE 接口前日 > LSHJ 接口前日 ─────────────────────────
    if _prev_from_dt and _prev_from_dt > 0:
        prev_total = _prev_from_dt
    elif _prev_from_lshj and _prev_from_lshj > 0:
        prev_total = _prev_from_lshj
    else:
        prev_total = None

    if prev_total and prev_total > 0:
        bal_chg     = round(total_bal - prev_total, 2)
        bal_chg_pct = round(bal_chg / prev_total * 100, 4)
    else:
        bal_chg = bal_chg_pct = None

    # ── 全市场成交额：优先用接口返回的 TRADE_AMT_RATIO（时间一致）────────────
    # 注：两融数据在收盘后统计，与成交额存在时间差
    # 方案1：直接用接口返回的 TRADE_AMT_RATIO（推荐，两融口径一致）
    # 方案2：用实时成交额自算（存在1天时间差）
    # 
    # 先保留接口返回的比例，如果没有再用实时成交额计算
    # ── 全市场成交额：获取实时数据并保存到 CSV ───────────────────────────────
    # 问题：两融数据日期（如3/19）与实时成交额日期（3/20）不一致
    # 解决：获取实时成交额后，保存到 CSV（用两融日期作为 key）
    #       下次计算时从 CSV 读取对应日期的历史成交额
    
    # 先获取实时成交额
    turnover_data = _fetch_mkt_turnover_realtime(timeout=10)
    if turnover_data:
        mkt_turnover = turnover_data["total"]
        sh_turnover  = turnover_data["sh"]
        sz_turnover  = turnover_data["sz"]
        bj_turnover  = turnover_data["bj"]
        
        # 保存到 CSV（用两融日期作为 key，确保时间一致）
        cached = _read_margin_csv()
        if date_str not in cached:
            cached[date_str] = {}
        cached[date_str]["mkt_turnover"] = mkt_turnover
        cached[date_str]["sh_turnover"] = sh_turnover
        cached[date_str]["sz_turnover"] = sz_turnover
        cached[date_str]["bj_turnover"] = bj_turnover
        _write_margin_csv(cached)
    else:
        mkt_turnover = sh_turnover = sz_turnover = bj_turnover = None
    
    # 计算两融/成交额（优先用接口返回值，时间一致；若无则用历史成交额）
    if turnover_ratio is None or turnover_ratio == 0:
        # 从 CSV 读取对应日期的历史成交额
        cached = _read_margin_csv()
        if date_str in cached:
            hist_turnover = cached[date_str].get("mkt_turnover")
            if hist_turnover and hist_turnover > 0 and (rz_buy or 0) + (rq_sell or 0) > 0:
                margin_trade = (rz_buy or 0) + (rq_sell or 0)
                turnover_ratio = round(margin_trade / hist_turnover * 100, 4)

    return {
        "date":             date_str,
        "total_bal":        total_bal,
        "bal_chg":          bal_chg,
        "bal_chg_pct":      bal_chg_pct,
        "rz_mktcap_ratio":  rz_mktcap_ratio,
        "bal_mktcap_ratio": bal_mktcap_ratio,
        "rz_bal":           rz_bal,
        "rq_bal":           rq_bal,
        "rz_buy":           rz_buy,
        "rq_sell":          rq_sell,
        "rz_repay":         rz_repay,
        "rz_net":           rz_net,
        "mkt_turnover":     mkt_turnover,
        "sh_turnover":      sh_turnover,
        "sz_turnover":      sz_turnover,
        "bj_turnover":      bj_turnover,
        "turnover_ratio":   turnover_ratio,
        "source":           "eastmoney",
    }


def _fetch_margin_akshare(timeout: int = 30) -> dict:
    """
    通过 AkShare 获取全市场两融最新数据（沪深合并口径）。
    作为东方财富接口的降级备用方案。

    数据来源：
      - macro_china_market_margin_sh() + macro_china_market_margin_sz()（沪深合并）
      - 流通市值：近似值 103,000 亿元（2026 年估算），或从 CSV 缓存反推

    注：AkShare 数据通常 T+0 当日盘后可用。

    Returns:
        与 _fetch_margin_eastmoney() 相同结构，source="akshare"
    """
    try:
        import akshare as ak
        import pandas as pd
    except ImportError:
        raise RuntimeError("akshare 未安装，请执行: pip install akshare")

    # ── 获取沪深两融余额 ──────────────────────────────────────────────────────
    sh_margin = ak.macro_china_market_margin_sh()
    sz_margin = ak.macro_china_market_margin_sz()

    sh_margin["日期"] = sh_margin["日期"].astype(str)
    sz_margin["日期"] = sz_margin["日期"].astype(str)

    sh_recent = sh_margin.tail(5).copy()
    sz_recent = sz_margin.tail(5).copy()

    merged = pd.merge(
        sh_recent[["日期", "融资融券余额", "融资余额", "融资买入额"]],
        sz_recent[["日期", "融资融券余额", "融资余额", "融资买入额"]],
        on="日期", how="inner", suffixes=("_sh", "_sz"),
    )

    if merged.empty:
        sh_latest = sh_margin.iloc[-1]
        sz_latest = sz_margin.iloc[-1]
        date_str  = str(sh_latest["日期"])[:10]
        total_bal = round((float(sh_latest["融资融券余额"]) + float(sz_latest["融资融券余额"])) / 1e8, 2)
        rz_bal    = round((float(sh_latest["融资余额"])    + float(sz_latest["融资余额"]))    / 1e8, 2)
        rz_buy    = round((float(sh_latest["融资买入额"]) + float(sz_latest["融资买入额"])) / 1e8, 2)
        prev_total = None
    else:
        latest    = merged.iloc[-1]
        date_str  = str(latest["日期"])[:10]
        total_bal = round((float(latest["融资融券余额_sh"]) + float(latest["融资融券余额_sz"])) / 1e8, 2)
        rz_bal    = round((float(latest["融资余额_sh"])    + float(latest["融资余额_sz"]))    / 1e8, 2)
        rz_buy    = round((float(latest["融资买入额_sh"]) + float(latest["融资买入额_sz"])) / 1e8, 2)
        if len(merged) > 1:
            prev = merged.iloc[-2]
            prev_total = round((float(prev["融资融券余额_sh"]) + float(prev["融资融券余额_sz"])) / 1e8, 2)
        else:
            prev_total = None

    if prev_total and prev_total > 0:
        bal_chg     = round(total_bal - prev_total, 2)
        bal_chg_pct = round(bal_chg / prev_total * 100, 4)
    else:
        bal_chg = bal_chg_pct = None

    # 流通市值近似值（2026年估算）或从 CSV 缓存反推
    _approx_circ_mktcap_yi = 103_000.0
    bal_mktcap_ratio = round(total_bal / _approx_circ_mktcap_yi * 100, 4)

    cached = _read_margin_csv()
    if cached:
        for d in reversed(sorted(cached.keys())[-3:]):
            rec = cached[d]
            if rec.get("total_bal") and rec.get("bal_mktcap_ratio"):
                implied_mktcap   = rec["total_bal"] / rec["bal_mktcap_ratio"] * 100
                bal_mktcap_ratio = round(total_bal / implied_mktcap * 100, 4)
                break

    # A股总成交额（push2实时 → AkShare指数）
    mkt_turnover   = _fetch_mkt_turnover_realtime(timeout=10)
    turnover_ratio = None
    if mkt_turnover is None:
        try:
            sh_idx = ak.stock_zh_index_daily_em(symbol="sh000001")
            sz_idx = ak.stock_zh_index_daily_em(symbol="sz399001")
            sh_idx["date"] = sh_idx["date"].astype(str)
            sz_idx["date"] = sz_idx["date"].astype(str)
            sh_row = sh_idx[sh_idx["date"] == date_str]
            sz_row = sz_idx[sz_idx["date"] == date_str]
            if not sh_row.empty and not sz_row.empty:
                sh_amt = float(sh_row.iloc[0]["amount"])
                sz_amt = float(sz_row.iloc[0]["amount"])
                mkt_turnover = round((sh_amt + sz_amt) / 1e8, 2)
        except Exception:
            pass

    if mkt_turnover and mkt_turnover > 0 and rz_buy > 0:
        turnover_ratio = round(rz_buy / mkt_turnover * 100, 4)

    return {
        "date":             date_str,
        "total_bal":        total_bal,
        "bal_chg":          bal_chg,
        "bal_chg_pct":      bal_chg_pct,
        "bal_mktcap_ratio": bal_mktcap_ratio,
        "rz_bal":           rz_bal,
        "rz_buy":           rz_buy,
        "mkt_turnover":     mkt_turnover,
        "turnover_ratio":   turnover_ratio,
        "source":           "akshare",
    }


def fetch_margin_history(n: int = 30) -> List[dict]:
    """
    获取近 N 个交易日的两融历史数据（用于趋势分析）。

    数据获取策略：
      1. 优先读取本地 CSV 缓存
      2. 不足时通过东方财富 RPTA_RZRQ_LSHJ 接口补充历史（支持多日）
      3. 东方财富失败时降级使用 AkShare 历史数据

    Returns:
        按日期升序排列的记录列表，每项格式同 fetch_margin() 返回值。
        失败时返回空列表。
    """
    records = _read_margin_csv()
    history = sorted(records.values(), key=lambda r: r.get("date", ""))

    if len(history) >= n:
        return history[-n:]

    # ── 优先：东方财富 RPTA_RZRQ_LSHJ 历史数据 ───────────────────────────────
    try:
        ts = int(time.time() * 1000)
        url = (
            f"{_EM_BASE_URL}?reportName=RPTA_RZRQ_LSHJ&columns=ALL"
            f"&source=WEB&sortColumns=DIM_DATE&sortTypes=-1"
            f"&pageNumber=1&pageSize={n + 1}&_={ts}"
        )
        d = _em_fetch_json(url, timeout=20)
        rows = _em_extract_rows(d)
        if rows:
            # 倒序排列 → 升序（最旧的在前）
            rows_sorted = list(reversed(rows))
            hist_list = []
            prev_bal = None
            for row in rows_sorted:
                date_s   = str(row.get("DIM_DATE", ""))[:10]
                rzrqye   = float(row.get("RZRQYE") or 0)
                bal      = round(rzrqye / 1e8, 2) if rzrqye > 0 else None
                rz_bal   = round(float(row.get("RZYE") or 0) / 1e8, 2)
                rz_buy   = round(float(row.get("RZMRE") or 0) / 1e8, 2)
                rzyezb   = float(row.get("RZYEZB") or 0) or None  # 融资余额/流通市值
                ltsz     = float(row.get("LTSZ") or 0)

                # 近似两融余额/流通市值（注：RZYEZB 是融资余额/流通市值，全量口径略高）
                # 全量占比 = total_bal / (LTSZ/1e8) × 100
                if bal and ltsz > 0:
                    total_ratio = round(bal / (ltsz / 1e8) * 100, 4)
                elif rzyezb:
                    total_ratio = rzyezb   # 近似值（略低于全量口径）
                else:
                    total_ratio = None

                chg = round(bal - prev_bal, 2) if (bal and prev_bal) else None
                chg_pct = round(chg / prev_bal * 100, 4) if (chg is not None and prev_bal and prev_bal > 0) else None
                prev_bal = bal

                # 若 CSV 中已有该日记录，优先保留 CSV 中的 mkt_turnover / turnover_ratio
                csv_rec = records.get(date_s, {})
                mkt_to  = csv_rec.get("mkt_turnover")
                tr_ratio = csv_rec.get("turnover_ratio")
                if mkt_to and rz_buy and mkt_to > 0:
                    tr_ratio = round(rz_buy / mkt_to * 100, 4)

                hist_list.append({
                    "date":             date_s,
                    "total_bal":        bal,
                    "bal_chg":          chg,
                    "bal_chg_pct":      chg_pct,
                    "bal_mktcap_ratio": total_ratio,
                    "rz_bal":           rz_bal,
                    "rz_buy":           rz_buy,
                    "mkt_turnover":     mkt_to,
                    "turnover_ratio":   tr_ratio,
                    "source":           "eastmoney_hist",
                })

            return hist_list[-n:] if hist_list else history[-n:]

    except Exception:
        pass

    # ── 降级：AkShare 历史数据 ────────────────────────────────────────────────
    try:
        import akshare as ak
        import pandas as pd

        sh_all = ak.macro_china_market_margin_sh()
        sz_all = ak.macro_china_market_margin_sz()
        sh_all["日期"] = sh_all["日期"].astype(str)
        sz_all["日期"] = sz_all["日期"].astype(str)

        merged = pd.merge(
            sh_all[["日期", "融资融券余额", "融资余额", "融资买入额"]],
            sz_all[["日期", "融资融券余额", "融资余额", "融资买入额"]],
            on="日期", how="inner", suffixes=("_sh", "_sz"),
        ).tail(n)

        hist_list = []
        prev_bal = None
        for _, row in merged.iterrows():
            bal = round((float(row["融资融券余额_sh"]) + float(row["融资融券余额_sz"])) / 1e8, 2)
            rz  = round((float(row["融资余额_sh"])    + float(row["融资余额_sz"]))    / 1e8, 2)
            buy = round((float(row["融资买入额_sh"]) + float(row["融资买入额_sz"])) / 1e8, 2)
            chg     = round(bal - prev_bal, 2) if prev_bal else None
            chg_pct = round(chg / prev_bal * 100, 4) if (prev_bal and prev_bal > 0 and chg is not None) else None
            prev_bal = bal

            date_s = str(row["日期"])[:10]
            csv_rec  = records.get(date_s, {})
            mkt_to   = csv_rec.get("mkt_turnover")
            tr_ratio = csv_rec.get("turnover_ratio")
            if mkt_to and buy and mkt_to > 0:
                tr_ratio = round(buy / mkt_to * 100, 4)

            hist_list.append({
                "date":             date_s,
                "total_bal":        bal,
                "bal_chg":          chg,
                "bal_chg_pct":      chg_pct,
                "bal_mktcap_ratio": csv_rec.get("bal_mktcap_ratio"),
                "rz_bal":           rz,
                "rz_buy":           buy,
                "mkt_turnover":     mkt_to,
                "turnover_ratio":   tr_ratio,
                "source":           "akshare_hist",
            })

        return hist_list

    except Exception:
        return history[-n:] if history else []


def analyze_margin_trend(history: List[dict], window: int = 5) -> dict:
    """
    分析两融趋势，检测用户定义的警示信号。

    警示信号条件（同时满足）：
      A. 两融余额/流通市值 >= 3.0%（杠杆积累到高位）
      B. 融资买入额/A股成交额（turnover_ratio）已从近期高点持续下降
         具体：当前值 <= 峰值 × (1 - 快速下降阈值)，且峰值出现在近 window 个交易日内

    Args:
        history:  按日期升序的两融历史记录列表（每项含 date/bal_mktcap_ratio/turnover_ratio）
        window:   检测窗口（交易日数，默认5日）

    Returns:
        {
            "warning":       bool,    # 是否触发警示
            "warning_reason": str,    # 警示原因描述
            "bal_ratio_trend":  str,  # "rising"/"falling"/"stable"
            "tr_ratio_trend":   str,  # "rising"/"falling"/"stable"
            "tr_ratio_peak":    float|None,  # 近window日内 turnover_ratio 峰值
            "tr_ratio_latest":  float|None,  # 最新 turnover_ratio
            "tr_ratio_drop_pct":float|None,  # 较峰值回落百分点
        }
    """
    result = {
        "warning":        False,
        "warning_reason": "",
        "bal_ratio_trend": "unknown",
        "tr_ratio_trend":  "unknown",
        "tr_ratio_peak":   None,
        "tr_ratio_latest": None,
        "tr_ratio_drop_pct": None,
    }

    if len(history) < 3:
        return result

    recent = history[-max(window, 3):]

    # 最新一条
    latest = recent[-1]
    bal_ratio_now = latest.get("bal_mktcap_ratio")
    tr_ratio_now  = latest.get("turnover_ratio")

    result["tr_ratio_latest"] = tr_ratio_now

    # ── 计算 bal_mktcap_ratio 趋势 ──────────────────────────────────────────
    bal_ratios = [r.get("bal_mktcap_ratio") for r in recent if r.get("bal_mktcap_ratio")]
    if len(bal_ratios) >= 3:
        if bal_ratios[-1] > bal_ratios[-3]:
            result["bal_ratio_trend"] = "rising"
        elif bal_ratios[-1] < bal_ratios[-3]:
            result["bal_ratio_trend"] = "falling"
        else:
            result["bal_ratio_trend"] = "stable"

    # ── 计算 turnover_ratio 趋势和峰值回落 ──────────────────────────────────
    tr_ratios = [r.get("turnover_ratio") for r in recent if r.get("turnover_ratio") is not None]
    if len(tr_ratios) >= 2:
        if tr_ratios[-1] > tr_ratios[-2]:
            result["tr_ratio_trend"] = "rising"
        elif tr_ratios[-1] < tr_ratios[-2]:
            result["tr_ratio_trend"] = "falling"
        else:
            result["tr_ratio_trend"] = "stable"

        peak = max(tr_ratios)
        result["tr_ratio_peak"] = peak
        if tr_ratio_now is not None and peak > 0:
            drop = round(peak - tr_ratio_now, 4)
            result["tr_ratio_drop_pct"] = drop
            drop_threshold = 0.15 * peak   # 较峰值下降超过15%即视为快速下降
            # ── 触发警示：余额占比高 + 交易额占比快速回落 ──────────────────
            # 条件 A：余额/流通市值 >= 3.0%
            # 条件 B：交易额占比从峰值回落 > 15%（且峰值 != 当前，即非刚刚到顶）
            if (bal_ratio_now is not None
                    and bal_ratio_now >= 3.0
                    and tr_ratio_now < peak
                    and drop >= drop_threshold
                    and peak != tr_ratio_now):
                result["warning"] = True
                result["warning_reason"] = (
                    f"两融余额占流通市值 {bal_ratio_now:.2f}%（≥3%），"
                    f"融资买入额占成交额已从峰值 {peak:.2f}% 回落至 {tr_ratio_now:.2f}%"
                    f"（↓{drop:.2f}pp），杠杆积累叠加交易热度退潮，注意风险"
                )

    return result


def fetch_margin(
    override: Optional[dict] = None,
    timeout:  int = 30,
) -> dict:
    """
    获取全市场融资融券数据（杠杆资金指标）。

    数据获取策略（优先级从高到低）：
      1. override 手动录入字典（如 --margin 命令行参数传入）
      2. 东方财富 datacenter-web API（RPTA_RZRQ_LSHJ）
         + push2.eastmoney.com 实时成交额（沪+深+京）
      3. CSV 缓存最新记录（离线回退）
      4. 以上均失败 → 返回 {"error": str}

    东方财富接口说明：
      RPTA_RZRQ_LSHJ    ：精确流通市值（LTSZ）、融资余额占比（RZYEZB）、两融余额（RZRQYE）、
                          融资买入/偿还/净买入（RZMRE/RZCHE/RZJME）、融券余额（RQYE）
      push2.eastmoney.com：上证(f48)+深证(f48)+北证50(f48) 实时成交额（盘中实时/盘后最终）

    Args:
        override: 手动录入字典，可包含：
            date, total_bal, bal_chg, bal_chg_pct,
            rz_mktcap_ratio, bal_mktcap_ratio,
            rz_bal, rq_bal, rz_buy, rq_sell, rz_repay, rz_net,
            mkt_turnover, sh_turnover, sz_turnover, bj_turnover, turnover_ratio
        timeout: 网络超时（秒）

    Returns:
        {
            "date":               str,        # 数据日期 "YYYY-MM-DD"
            "total_bal":          float,      # 两融余额（亿元）
            "bal_chg":            float|None, # 较前日变化（亿元）
            "bal_chg_pct":        float|None, # 较前日变化（%）
            "rz_mktcap_ratio":    float|None, # 融资余额/流通市值（%，RZYEZB 接口直给）
            "bal_mktcap_ratio":   float|None, # 两融余额/流通市值（%，自算）
            "rz_bal":             float|None, # 融资余额（亿元）
            "rq_bal":             float|None, # 融券余额（亿元）
            "rz_buy":             float|None, # 融资买入额（亿元）
            "rq_sell":            float|None, # 融券卖出额（亿元）
            "rz_repay":           float|None, # 融资偿还额（亿元）
            "rz_net":             float|None, # 融资净买入额（亿元）
            "mkt_turnover":       float|None, # 全市场成交额（亿元，沪+深+京）
            "sh_turnover":        float|None, # 沪市成交额（亿元）
            "sz_turnover":        float|None, # 深市成交额（亿元）
            "bj_turnover":        float|None, # 京市（北交所）成交额（亿元）
            "turnover_ratio":     float|None, # 两融交易/全市场成交额（%，两融交易=融资买入+融券卖出）
            "source":             str,        # "manual"|"eastmoney"|"csv_cache"
        }
        失败时：{"error": str}

    评分参考（杠杆热度，bal_mktcap_ratio = 两融余额/流通市值）：
        > 3.5% → 极热  -2
        3.0–3.5% → 偏热 -1
        2.0–3.0% → 正常  0
        1.5–2.0% → 偏冷 +1
        < 1.5%   → 极冷 +2

    警示信号（趋势型，见 analyze_margin_trend）：
        余额占比 >= 3.0% 且交易额占比从近期峰值快速下降（>15%）→ 杠杆积累叠加热度退潮
    """
    # ── 优先：手动录入 ────────────────────────────────────────────────────────
    if override is not None:
        valid_keys = [k for k in _MARGIN_CSV_FIELDS if k != "source"]
        rec = {k: override.get(k) for k in valid_keys}
        rec["source"] = "manual"
        if not rec.get("date"):
            rec["date"] = datetime.today().strftime("%Y-%m-%d")
        cached = _read_margin_csv()
        cached[rec["date"]] = rec
        _write_margin_csv(cached)
        return rec

    # ── 读取现有 CSV 缓存 ─────────────────────────────────────────────────────
    cached = _read_margin_csv()

    # ── 自动获取：东方财富（首选）────────────────────────────────────────────
    fetch_errors = []
    try:
        new_rec  = _fetch_margin_eastmoney(timeout=timeout)
        date_key = new_rec.get("date", "")
        if date_key:
            merged = dict(cached)
            merged[date_key] = new_rec
            _write_margin_csv(merged)
            return new_rec
        raise ValueError("东方财富接口返回日期为空")
    except Exception as e:
        fetch_errors.append(f"eastmoney: {e}")

    # ── 离线回退：CSV 缓存最新记录 ────────────────────────────────────────────
    latest = _latest_margin_record(cached)
    if latest:
        rec = dict(latest)
        rec["source"] = "csv_cache"
        return rec

    return {"error": f"东方财富两融接口获取失败：{'; '.join(fetch_errors)}；本地亦无缓存数据"}


# ── 指南针活跃市值相关函数 ───────────────────────────────────────────────────

def _read_znz_csv() -> dict:
    """
    读取指南针活跃市值 CSV 缓存，返回 {date: row_dict} 字典。
    """
    if not os.path.isfile(_ZNZ_CSV_PATH):
        return {}
    result = {}
    with open(_ZNZ_CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            d = row.get("date", "").strip()
            if d:
                result[d] = {
                    "date": d,
                    "active_cap": float(row["active_cap"]) if row.get("active_cap") else None,
                    "chg_pct": float(row["chg_pct"]) if row.get("chg_pct") else None,
                    "signal": row.get("signal", "neutral"),
                    "source": row.get("source", "manual"),
                }
    return result


def _write_znz_csv(records: dict) -> None:
    """
    将指南针活跃市值记录写入 CSV，按日期升序排列。
    """
    _ensure_data_dir()
    sorted_dates = sorted(records.keys())
    with open(_ZNZ_CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_ZNZ_CSV_FIELDS)
        writer.writeheader()
        for d in sorted_dates:
            row = records[d]
            writer.writerow({
                "date": row.get("date", d),
                "active_cap": row.get("active_cap", ""),
                "chg_pct": "" if row.get("chg_pct") is None else row["chg_pct"],
                "signal": row.get("signal", "neutral"),
                "source": row.get("source", "manual"),
            })


def _calc_znz_signal(chg_pct: Optional[float]) -> str:
    """
    根据日变动幅度计算指南针活跃市值信号。
    
    信号规则：
      - 单日涨幅 ≥ +4%：incremental（增量资金入场）
      - 单日跌幅 ≤ -2.3%：exit（资金离场）
      - 其他：neutral（中性）
    """
    if chg_pct is None:
        return "neutral"
    if chg_pct >= 4.0:
        return "incremental"
    if chg_pct <= -2.3:
        return "exit"
    return "neutral"


def _find_last_clear_signal(records: dict, until_date: str = None) -> str:
    """
    从历史记录中找出最近一个明显信号（入场/离场）。
    
    逻辑：倒序遍历，找到第一个 incremental 或 exit 信号即返回
    如果未找到明显信号，返回 "neutral"
    """
    sorted_dates = sorted(records.keys(), reverse=True)
    
    for d in sorted_dates:
        if until_date and d > until_date:
            continue
        sig = records[d].get("signal", "neutral")
        if sig in ("incremental", "exit"):
            return sig
    
    return "neutral"


def _suggest_position(signal: str) -> str:
    """
    根据信号给出动态仓位建议（0-60%）。
    方案一：指南针核心仓位
    """
    if signal == "incremental":
        return "60%"
    if signal == "exit":
        return "0-10%"
    return "30%"


def save_znz_active_cap(date: str, active_cap: float, chg_pct: Optional[float] = None) -> dict:
    """
    手动录入指南针活跃市值数据并保存至 CSV。
    
    Args:
        date: 日期 "YYYY-MM-DD"
        active_cap: 活跃市值（亿元）
        chg_pct: 日变动幅度（%），可选，不传则自动从 CSV 历史计算
    
    Returns:
        保存的记录字典
    """
    records = _read_znz_csv()
    
    # 如果未提供 chg_pct，尝试从历史计算
    if chg_pct is None:
        sorted_dates = sorted(records.keys())
        if sorted_dates:
            last_date = sorted_dates[-1]
            last_cap = records[last_date].get("active_cap")
            if last_cap and last_cap > 0:
                chg_pct = round((active_cap - last_cap) / last_cap * 100, 2)
    
    signal = _calc_znz_signal(chg_pct)
    
    rec = {
        "date": date,
        "active_cap": active_cap,
        "chg_pct": chg_pct,
        "signal": signal,
        "source": "manual",
    }
    
    records[date] = rec
    _write_znz_csv(records)
    return rec


def fetch_znz_active_cap() -> dict:
    """
    获取指南针活跃市值最新数据（优先从 CSV 读取最新记录）。
    
    Returns:
        {
            "date": str,           # 数据日期
            "active_cap": float,   # 活跃市值（亿元）
            "chg_pct": float|None, # 日变动幅度（%）
            "signal": str,         # incremental/exit/neutral
            "position_suggest": str, # 仓位建议 "40%"/"0-10%"/"20%"
            "signal_desc": str,    # 信号描述
            "source": str,         # manual/auto
        }
        无数据时：{"error": str}
    """
    records = _read_znz_csv()
    if not records:
        return {"error": "暂无指南针活跃市值数据，请使用 --znz 参数手动录入"}
    
    # 获取最新记录
    latest_date = max(records.keys())
    rec = records[latest_date]
    
    # 找出最近一个明显信号（避免追涨杀跌）
    last_clear_signal = _find_last_clear_signal(records)
    
    # 当天信号
    today_signal = rec.get("signal", "neutral")
    
    signal_desc_map = {
        "incremental": "🟢 增量资金入场（单日涨幅≥4%）",
        "exit": "🔴 资金离场警示（单日跌幅≤-2.3%）",
        "neutral": "🟡 观望（无明显信号）",
    }
    
    # 最近明显信号的描述
    last_clear_desc = signal_desc_map.get(last_clear_signal, "🟡 观望")
    
    return {
        **rec,
        "today_signal": today_signal,
        "last_clear_signal": last_clear_signal,
        "last_clear_signal_desc": last_clear_desc,
        "position_suggest": _suggest_position(last_clear_signal),
        "signal_desc": signal_desc_map.get(today_signal, "🟡 观望"),
    }
