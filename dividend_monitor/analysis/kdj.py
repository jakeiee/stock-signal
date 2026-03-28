"""
周线 KDJ 数据获取与信号判断。

数据源优先级：
  1. 中证官网 OHLCV 自算（source='csindex'）—— 免费、稳定、不占妙想配额
  2. 妙想 API（source='mx'）               —— 自算失败时降级

信号判断规则：
  J < 0        → 极度超卖
  J > 100      → 超买
  K 上穿 D     → 金叉（需前一周数据）
  K 下穿 D     → 死叉（需前一周数据）
  K>80 且 D>80 → 高位
  K<20 且 D<20 → 低位
"""

from datetime import datetime
from typing import Optional

from ..config import WEEK_KDJ_COUNT
from ..data_sources import miaoxiang, csindex
from .valuation import parse_float


# ── 工具 ──────────────────────────────────────────────────────────────────────

def _iso_week(date_str: str) -> tuple:
    return datetime.strptime(date_str, "%Y-%m-%d").isocalendar()[:2]


def _extract_weekly(heads: list, *value_lists) -> list:
    """
    将接口返回的日线序列（KDJ 值以周线参数计算）按 ISO 周分组，
    取每周最后一个交易日（数据从新到旧，首次出现即为周末最后交易日）。
    """
    seen: dict = {}
    rows = []
    for i, h in enumerate(heads):
        wk = _iso_week(h)
        if wk not in seen:
            seen[wk] = True
            row = {"date": h}
            for j, vlist in enumerate(value_lists):
                row[f"v{j}"] = vlist[i] if i < len(vlist) else None
            rows.append(row)
    return rows


# ── 核心获取 ──────────────────────────────────────────────────────────────────

def fetch(idx: dict) -> list:
    """
    获取指定指数的最新 WEEK_KDJ_COUNT 周周线 KDJ。

    Args:
        idx: INDEXES 中的单条配置字典。

    Returns:
        [{"date": str, "K": float, "D": float, "J": float, "source": str}, ...]
        无数据时返回空列表。
    """
    # ── 优先：中证官网 OHLCV 自算（不占妙想配额）──────────────────────────────
    code = idx.get("csindex_code")
    if code:
        try:
            df  = csindex.fetch_ohlcv(code, days=300)
            kdj_row = csindex.calc_kdj(df)
            if kdj_row and kdj_row.get("K") is not None:
                return [kdj_row]
        except Exception:
            pass

    # ── 降级：妙想 API ─────────────────────────────────────────────────────────
    try:
        items = miaoxiang.query(f"{idx['query_name']}最近30天周线KDJ指标")
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

            rows   = _extract_weekly(heads, k_list, d_list, j_list)
            result = [
                {"date": r["date"], "K": r["v0"], "D": r["v1"], "J": r["v2"], "source": "mx"}
                for r in rows[:WEEK_KDJ_COUNT]
            ]
            if result and result[0]["K"] is not None:
                return result
    except RuntimeError:
        pass   # 配额用尽，静默失败
    except Exception:
        pass

    return []


# ── 信号判断 ──────────────────────────────────────────────────────────────────

def signal(row: dict, prev_row: Optional[dict]) -> str:
    """
    根据最新一周与上一周 KDJ 值判断交易信号。

    Args:
        row:      当前周 KDJ 字典 {"K": float, "D": float, "J": float, ...}。
        prev_row: 上一周 KDJ 字典，无则传 None（此时不判断金叉死叉）。

    Returns:
        信号描述字符串，无信号时返回空字符串。
    """
    k, d, j = row["K"], row["D"], row["J"]
    if k is None or d is None or j is None:
        return ""
    if j < 0:
        return "⚠ J<0 极度超卖"
    if j > 100:
        return "⚠ J>100 超买"
    if prev_row and prev_row["K"] is not None and prev_row["D"] is not None:
        pk, pd_ = prev_row["K"], prev_row["D"]
        if pk < pd_ and k > d:
            return "✦ 金叉"
        if pk > pd_ and k < d:
            return "↓ 死叉"
    if k > 80 and d > 80:
        return "高位"
    if k < 20 and d < 20:
        return "低位"
    return ""
