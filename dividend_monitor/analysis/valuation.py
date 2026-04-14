"""
估值数据查询与百分位计算。

数据源：仅使用Wind APP手动记录数据（专业金融数据，完整发布历史）。
"""

from datetime import datetime, date
from typing import Optional, Any, Dict, List, Union

# 处理导入：支持直接执行和模块执行
if __package__:
    from ..data_sources import wind_app
else:
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from dividend_monitor.data_sources import wind_app


# ── 常量 ──────────────────────────────────────────────────────────────────────

# 百分位可信阈值：至少需要约 1 年的有效交易日数据（约 240 个交易日）
MIN_HIST_DAYS = 240

# 发布年数阈值：不足此年数则在报告中特别标注
LAUNCH_YEAR_THRESHOLD = 10


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def parse_float(s: Union[str, int, float, None]) -> Optional[float]:
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

def fetch(idx: Dict[str, Any], risk_free_rate: float) -> Dict[str, Any]:
    """
    获取指定指数的全历史股息率与市盈率，计算百分位及风险溢价。
    
    数据源：
      - 只使用Wind APP手动记录数据（专业金融数据，完整发布历史）
      - 当Wind APP数据不可用时，返回错误
    
    百分位说明：
      - Wind APP数据：完整发布历史，100%可信
      - 数据区间：发布日至数据日期
    
    Args:
        idx:            INDEXES 中的单条配置字典
        risk_free_rate: 当前无风险利率（%）

    Returns:
        估值数据字典，包含以下键：
            date, div, div_pct, pe, pe_pct, risk_premium,
            hist_start, hist_years, hist_days,
            launch_date, launch_years, launch_short_history,
            source, data_quality, error
    """
    # ── 发布年数计算 ──────────────────────────────────────────────────────────
    launch_date  = idx.get("launch_date", "")
    launch_years = _years_since(launch_date) if launch_date else None
    launch_short = (
        (launch_years is not None and launch_years < LAUNCH_YEAR_THRESHOLD)
    )
    
    # ── 从Wind APP数据获取估值 ──────────────────────────────────────────────
    try:
        wind_valuation = wind_app.get_valuation_from_wind_app(idx['index_code'], risk_free_rate)
        if wind_valuation:
            # 数据质量评分
            quality_grade = wind_valuation.get("wind_app_data_quality", "A级")
            is_wind_app_reliable = quality_grade in ["A级", "B级"]
            
            return {
                "date": wind_valuation["date"],
                "div": wind_valuation["div"],
                "div_pct": wind_valuation["div_pct"],
                "pe": wind_valuation["pe"],
                "pe_pct": wind_valuation["pe_pct"],
                "risk_premium": wind_valuation["risk_premium"],
                "hist_start": wind_valuation.get("hist_start", ""),
                "hist_years": wind_valuation.get("hist_years", 0),
                "hist_days": wind_valuation.get("hist_days", 0),
                "launch_date": launch_date,
                "launch_years": launch_years,
                "launch_short_history": launch_short,
                "source": "wind_app",
                "data_quality": f"Wind APP - {quality_grade}",
                "wind_app_quality": quality_grade,
                "data_reliable": is_wind_app_reliable  # Wind APP数据天然可靠
            }
        else:
            return {"error": f"Wind APP数据中未找到指数 {idx['index_code']} 的估值数据"}
    except Exception as e:
        return {"error": f"Wind APP数据获取失败: {e}"}
