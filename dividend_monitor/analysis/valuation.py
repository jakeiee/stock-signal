"""
估值数据查询与百分位计算。

数据源：妙想 API（东方财富妙想）。
指标：
  - 股息率 TTM（历史百分位）
  - 市盈率 PETTM（历史百分位）
  - 风险溢价率 = 1/PE×100% − 无风险利率

百分位可靠性说明：
  - 妙想 API 返回的历史数据起始时间可能早于或晚于指数真实发布日期。
  - 当有效历史数据不足 MIN_HIST_DAYS 个交易日时，百分位标注为 None（不可靠），
    终端/飞书展示为 "N/A（数据不足）"。
  - 指数发布日期不足 10 年时，在报告中额外标注。
"""

from datetime import datetime, date
from typing import Optional, List

from ..data_sources import miaoxiang


# ── 常量 ──────────────────────────────────────────────────────────────────────

# 百分位可信阈值：至少需要约 1 年的有效交易日数据（约 240 个交易日）
MIN_HIST_DAYS = 240

# 发布年数阈值：不足此年数则在报告中特别标注
LAUNCH_YEAR_THRESHOLD = 10


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def parse_float(s) -> Optional[float]:
    """将字符串/数字安全转换为 float，无效值返回 None。"""
    if s is None or s in ("", "null", "-"):
        return None
    try:
        return float(str(s).replace("%", ""))
    except Exception:
        return None


def percentile_rank(values: List[Optional[float]], val: float) -> float:
    """计算 val 在 values 序列中的历史百分位（%，越大表示越靠近历史最高）。"""
    valid = [v for v in values if v is not None]
    if not valid:
        return float("nan")
    return sum(1 for v in valid if v <= val) / len(valid) * 100


def _years_since(date_str: str) -> Optional[float]:
    """
    计算从 date_str（YYYY-MM-DD）到今日经过的年数。
    解析失败返回 None。
    """
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        delta = date.today() - d
        return delta.days / 365.25
    except Exception:
        return None


# ── 核心查询 ──────────────────────────────────────────────────────────────────

def fetch(idx: dict, risk_free_rate: float) -> dict:
    """
    通过妙想 API 获取指定指数的全历史股息率与市盈率，计算百分位及风险溢价。

    百分位可靠性：
      - 当有效历史数据 < MIN_HIST_DAYS 时，div_pct / pe_pct 置为 None。
      - 调用方应检查 div_pct / pe_pct 是否为 None，None 表示数据不足，不可信。

    发布年数：
      - 从 idx['launch_date'] 计算到今日的年数，存入 launch_years。
      - 发布年数 < LAUNCH_YEAR_THRESHOLD 时，launch_short_history=True。

    Args:
        idx:            INDEXES 中的单条配置字典（需含 launch_date 字段）。
        risk_free_rate: 当前无风险利率（%），用于计算风险溢价。

    Returns:
        成功时返回包含以下键的字典：
            date, div, div_pct, div_max, div_min, div_hist_n,
            pe, pe_pct, pe_max, pe_min, risk_premium,
            hist_start, hist_years,
            launch_date, launch_years, launch_short_history,
            source
        配额耗尽时额外包含 error_type="quota"；
        其他失败时包含 error 字段。
    """
    # ── 发布年数计算 ──────────────────────────────────────────────────────────
    launch_date  = idx.get("launch_date", "")
    launch_years = _years_since(launch_date) if launch_date else None
    launch_short = (
        (launch_years is not None and launch_years < LAUNCH_YEAR_THRESHOLD)
    )

    # ── 妙想查询：尝试获取尽量长的全历史数据 ────────────────────────────────
    # 优先用"全部历史"或"上市以来"的表述，让妙想返回最长数据集
    queries = [
        f"{idx['query_name']}上市以来每日股息率TTM和市盈率PETTM全部历史数据",
        f"{idx['query_name']}历史全部每日股息率TTM和PE市盈率",
        f"{idx['query_name']} 2000年至今每日股息率TTM和市盈率PETTM",
        f"{idx['query_name']}股息率TTM和PE市盈率每日历史数据",
    ]
    item = None
    for q in queries:
        try:
            items = miaoxiang.query(q)
        except RuntimeError as e:
            return {"error": str(e), "error_type": "quota"}
        if not items:
            continue
        for it in items:
            nm      = it["nameMap"]
            has_div = any("股息" in nm.get(k, "") for k in it["indicatorOrder"])
            has_pe  = any(
                "市盈" in nm.get(k, "") or "PE" in nm.get(k, "")
                for k in it["indicatorOrder"]
            )
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
    pe_key  = next(
        (k for k in io if "市盈" in nm.get(k, "") or "PE" in nm.get(k, "")), None
    )
    if not div_key or not pe_key:
        return {"error": f"字段未找到: {nm}"}

    div_vals  = [parse_float(v) for v in table[div_key]]
    pe_vals   = [parse_float(v) for v in table[pe_key]]
    valid_div = [v for v in div_vals if v is not None]
    valid_pe  = [v for v in pe_vals  if v is not None]

    latest_div = parse_float(table[div_key][0])
    latest_pe  = parse_float(table[pe_key][0])
    if latest_div is None or latest_pe is None:
        return {"error": "最新值为空"}

    # ── 百分位可靠性判断 ──────────────────────────────────────────────────────
    hist_n        = len(valid_div)
    data_reliable = hist_n >= MIN_HIST_DAYS   # 数据量是否足够

    div_pct = percentile_rank(valid_div, latest_div) if data_reliable else None
    pe_pct  = percentile_rank(valid_pe,  latest_pe)  if data_reliable else None

    # ── 历史起始年数（从 hist_start 到今日）────────────────────────────────
    hist_start = heads[-1] if heads else ""
    hist_years = _years_since(hist_start) if hist_start else None

    risk_premium = (1 / latest_pe * 100) - risk_free_rate if latest_pe else None

    return {
        "date":       heads[0] if heads else "",
        "div":        latest_div,
        "div_pct":    div_pct,       # None = 数据不足，不可信
        "div_max":    max(valid_div) if valid_div else None,
        "div_min":    min(valid_div) if valid_div else None,
        "div_hist_n": hist_n,
        "pe":         latest_pe,
        "pe_pct":     pe_pct,        # None = 数据不足，不可信
        "pe_max":     max(valid_pe)  if valid_pe  else None,
        "pe_min":     min(valid_pe)  if valid_pe  else None,
        "risk_premium":         risk_premium,
        "hist_start":           hist_start,
        "hist_years":           hist_years,
        "launch_date":          launch_date,
        "launch_years":         launch_years,
        "launch_short_history": launch_short,
        "source":               "mx",
    }
