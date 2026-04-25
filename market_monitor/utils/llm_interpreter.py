"""
LLM 解析模块 - 使用通义千问自动解析官方解读。

功能：
  - 将国家统计局官方解读的原始文本解析为结构化输出
  - 支持 CPI/PPI/PMI/GDP 等指标的统一格式
  - 规则兜底：LLM 不可用时回退到规则解析
  - 缓存机制：同月份数据只解析一次，避免重复调用 LLM

输出格式：
{
    "summary_short": "CPI+1.0%/PPI+0.5% 价格回暖",
    "key_trend": "需求回升+工业反弹",
    "sentiment": "positive/neutral/negative"
}
"""

import json
import re
import os
from datetime import datetime
from typing import Dict, Any, Optional

try:
    import dashscope
    from dashscope import Generation
    HAS_DASHSCOPE = True
except ImportError:
    HAS_DASHSCOPE = False

from ..config import DASHSCOPE_API_KEY, LLM_MODEL, LLM_TIMEOUT, LLM_ENABLED

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
_CACHE_FILE = os.path.join(_DATA_DIR, "llm_interpretation_cache.json")


# ─────────────────────────────────────────────────────────────
# 缓存机制
# ─────────────────────────────────────────────────────────────

def _load_cache() -> Dict[str, Any]:
    """加载缓存"""
    if os.path.exists(_CACHE_FILE):
        try:
            with open(_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {}


def _save_cache(cache: Dict[str, Any]) -> None:
    """保存缓存"""
    try:
        with open(_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"    ⚠️ 缓存保存失败: {e}")


def _get_cache_key(indicator: str, period: str = None) -> str:
    """
    生成缓存 key。
    
    Args:
        indicator: 指标类型 "cpi_ppi" / "pmi" / "gdp" / "income"
        period: 数据期，如 "2026-03"，自动取当前年月
    
    Returns:
        缓存 key，如 "cpi_ppi_2026_03"
    """
    if period:
        # 标准化 period 格式
        period = period.replace("/", "_").replace("-", "_")
        # 确保是 YYYY_MM 格式
        parts = period.split("_")
        if len(parts) >= 2:
            period = f"{parts[0][-4:]}_{parts[1].zfill(2)}"
    else:
        now = datetime.now()
        period = f"{now.year}_{now.month:02d}"
    
    return f"{indicator}_{period}"


def _is_cache_valid(cache_entry: Dict[str, Any]) -> bool:
    """
    检查缓存是否有效。
    
    缓存有效期：
    - 当前月数据：保留到下个月末
    - 历史月份数据：永久有效（因为官方解读不会变）
    """
    if not cache_entry:
        return False
    
    cached_month = cache_entry.get("month", "")
    if not cached_month:
        return False
    
    # 解析缓存月份
    try:
        cached_year, cached_mon = cached_month.split("_")
        cached_year = int(cached_year)
        cached_mon = int(cached_mon)
    except:
        return False
    
    now = datetime.now()
    current_year = now.year
    current_mon = now.month
    
    # 如果是当前月或上月：有效
    if cached_year == current_year and cached_mon >= current_mon - 1:
        return True
    if cached_year == current_year - 1 and current_mon == 1 and cached_mon == 12:
        return True
    
    # 如果是更早的历史月份（官方解读不会变）：永久有效
    return True


def _check_cache(indicator: str, period: str = None) -> Optional[Dict[str, Any]]:
    """
    检查缓存是否存在且有效。
    
    Args:
        indicator: 指标类型
        period: 数据期
    
    Returns:
        缓存数据或 None
    """
    cache = _load_cache()
    cache_key = _get_cache_key(indicator, period)
    cache_entry = cache.get(cache_key)
    
    if _is_cache_valid(cache_entry):
        print(f"    📦 使用缓存: {cache_key}")
        return cache_entry.get("result")
    
    return None


def _save_to_cache(indicator: str, period: str, result: Dict[str, Any]) -> None:
    """
    保存结果到缓存。
    
    Args:
        indicator: 指标类型
        period: 数据期
        result: 解析结果
    """
    cache = _load_cache()
    cache_key = _get_cache_key(indicator, period)
    
    # 标准化 period 为 YYYY_MM 格式
    now = datetime.now()
    cache_month = f"{now.year}_{now.month:02d}"
    
    cache[cache_key] = {
        "month": cache_month,
        "result": result,
        "cached_at": datetime.now().isoformat()
    }
    
    _save_cache(cache)
    print(f"    💾 已缓存: {cache_key}")


# ─────────────────────────────────────────────────────────────
# Prompt 模板
# ─────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """你是一个宏观经济数据分析师，负责将国家统计局的官方解读文本解析为结构化信息。

输出格式要求（JSON）：
{
    "summary_short": "一句话概括，包含指标数值和核心趋势，20字以内",
    "key_trend": "1-2个关键词描述主要趋势，如'需求回暖'、'工业反弹'、'价格承压'等",
    "sentiment": "positive（利好）/ neutral（中性）/ negative（利空）"
}

注意：
- 只输出JSON，不要其他内容
- summary_short 要包含具体数值
- 如果是 CPI/PPI，重点关注价格趋势
- 如果是 PMI，重点关注经济景气度
- 如果是 GDP，重点关注增长质量和结构"""

_USER_TEMPLATE_GDP = """请解析以下GDP官方解读：

{summary}

请输出JSON格式的解析结果。"""

_USER_TEMPLATE_CPI_PPI = """请解析以下CPI/PPI官方解读：

{summary}

请输出JSON格式的解析结果。"""

_USER_TEMPLATE_PMI = """请解析以下PMI官方解读：

{summary}

请输出JSON格式的解析结果。"""

_USER_TEMPLATE_INCOME = """请解析以下居民收入官方解读：

{summary}

请输出JSON格式的解析结果。"""


# ─────────────────────────────────────────────────────────────
# LLM 调用
# ─────────────────────────────────────────────────────────────

def _call_qwen(prompt: str, model: str = None) -> Optional[Dict[str, Any]]:
    """调用通义千问 API"""
    if not HAS_DASHSCOPE:
        return None
    
    api_key = DASHSCOPE_API_KEY or os.getenv("DASHSCOPE_API_KEY", "")
    if not api_key:
        return None
    
    model = model or LLM_MODEL
    
    try:
        dashscope.api_key = api_key
        
        response = Generation.call(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            result_format="message",
            timeout=LLM_TIMEOUT
        )
        
        if response.status_code == 200:
            content = response.output.choices[0].message.content
            # 提取 JSON
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                return json.loads(json_match.group(0))
        else:
            print(f"    ⚠️ LLM调用失败: {response.message}")
    except Exception as e:
        print(f"    ⚠️ LLM调用异常: {e}")
    
    return None


# ─────────────────────────────────────────────────────────────
# 规则解析兜底
# ─────────────────────────────────────────────────────────────

def _rule_parse_cpi_ppi(summary: str, cpi: float = None, ppi: float = None) -> Dict[str, Any]:
    """规则解析 CPI/PPI"""
    parts = []
    if cpi is not None:
        parts.append(f"CPI{cpi:+.1f}%")
    if ppi is not None:
        parts.append(f"PPI{ppi:+.1f}%")
    data_str = "/".join(parts)
    
    # 简单规则判断
    if cpi is not None and ppi is not None:
        if cpi > 0 and ppi >= 0:
            sentiment = "positive"
            trend = "价格回暖"
        elif cpi < 0 and ppi < 0:
            sentiment = "negative"
            trend = "价格承压"
        elif cpi > 0 and ppi < 0:
            sentiment = "neutral"
            trend = "消费回暖/工业低迷"
        else:
            sentiment = "neutral"
            trend = "整体平稳"
    else:
        sentiment = "neutral"
        trend = ""
    
    summary_short = f"{data_str} {trend}" if trend else data_str
    
    return {
        "summary_short": summary_short,
        "key_trend": trend,
        "sentiment": sentiment
    }


def _rule_parse_pmi(pmi_mfg: float = None, pmi_svc: float = None, summary: str = "") -> Dict[str, Any]:
    """规则解析 PMI"""
    parts = []
    if pmi_mfg is not None:
        parts.append(f"制造PMI{pmi_mfg:.1f}")
    if pmi_svc is not None:
        parts.append(f"非制造PMI{pmi_svc:.1f}")
    data_str = " / ".join(parts)
    
    # 判断趋势
    if pmi_mfg is not None and pmi_mfg >= 50:
        sentiment = "positive"
        trend = "经济扩张"
    elif pmi_mfg is not None and pmi_mfg >= 45:
        sentiment = "neutral"
        trend = "临界"
    else:
        sentiment = "negative"
        trend = "经济收缩"
    
    summary_short = f"PMI {data_str} {trend}"
    
    return {
        "summary_short": summary_short,
        "key_trend": trend,
        "sentiment": sentiment
    }


def _rule_parse_gdp(gdp_yoy: float = None, summary: str = "") -> Dict[str, Any]:
    """规则解析 GDP"""
    data_str = f"GDP{gdp_yoy:+.1f}%" if gdp_yoy is not None else "GDP"
    
    if gdp_yoy is not None:
        if gdp_yoy >= 5:
            sentiment = "positive"
            trend = "稳健增长"
        elif gdp_yoy >= 4:
            sentiment = "neutral"
            trend = "平稳增长"
        else:
            sentiment = "negative"
            trend = "增速放缓"
    else:
        sentiment = "neutral"
        trend = ""
    
    summary_short = f"{data_str} {trend}" if trend else data_str
    
    return {
        "summary_short": summary_short,
        "key_trend": trend,
        "sentiment": sentiment
    }


# ─────────────────────────────────────────────────────────────
# 主解析函数
# ─────────────────────────────────────────────────────────────

def parse_cpi_ppi_interpretation(
    summary: str,
    cpi: float = None,
    ppi: float = None,
    cpi_mom: float = None,
    ppi_mom: float = None,
    period: str = None
) -> Dict[str, Any]:
    """
    解析 CPI/PPI 官方解读。
    
    Args:
        summary: 官方解读原始文本
        cpi: CPI 同比
        ppi: PPI 同比
        cpi_mom: CPI 环比
        ppi_mom: PPI 环比
        period: 数据期，如 "2026-03"
    
    Returns:
        解析结果 dict
    """
    # ── 1. 检查缓存 ──
    cached = _check_cache("cpi_ppi", period)
    if cached:
        return cached
    
    # 构建环比箭头
    arrow = ""
    if cpi_mom is not None:
        arrow += "↑" if cpi_mom > 0 else "↓"
    if ppi_mom is not None:
        arrow += "↑" if ppi_mom > 0 else "↓"
    
    result = None
    
    # ── 2. 优先尝试 LLM ──
    if LLM_ENABLED and summary and HAS_DASHSCOPE:
        result = _call_qwen(_USER_TEMPLATE_CPI_PPI.format(summary=summary))
        if result:
            # 添加数据部分
            parts = []
            if cpi is not None:
                parts.append(f"CPI{cpi:+.1f}%{arrow[0] if arrow else ''}")
            if ppi is not None:
                parts.append(f"PPI{ppi:+.1f}%{arrow[1] if len(arrow) > 1 else ''}")
            data_str = "/".join(parts)
            result["summary_short"] = f"{data_str} {result.get('summary_short', '')}"
    
    # ── 3. 规则兜底 ──
    if result is None:
        result = _rule_parse_cpi_ppi(summary, cpi, ppi)
    
    # ── 4. 保存缓存 ──
    _save_to_cache("cpi_ppi", period, result)
    
    return result


def parse_pmi_interpretation(
    summary: str,
    pmi_mfg: float = None,
    pmi_svc: float = None,
    pmi_mfg_mom: float = None,
    pmi_svc_mom: float = None,
    period: str = None
) -> Dict[str, Any]:
    """
    解析 PMI 官方解读。
    
    Args:
        summary: 官方解读原始文本
        pmi_mfg: 制造业 PMI
        pmi_svc: 非制造业 PMI
        pmi_mfg_mom: 制造业 PMI 环比变化
        pmi_svc_mom: 非制造业 PMI 环比变化
        period: 数据期，如 "2026-03"
    
    Returns:
        解析结果 dict
    """
    # ── 1. 检查缓存 ──
    cached = _check_cache("pmi", period)
    if cached:
        return cached
    
    # 构建箭头
    arrows = []
    if pmi_mfg_mom is not None:
        arrows.append("↑" if pmi_mfg_mom > 0 else "↓")
    if pmi_svc_mom is not None:
        arrows.append("↑" if pmi_svc_mom > 0 else "↓")
    arrow_str = "".join(arrows)
    
    result = None
    
    # ── 2. 优先尝试 LLM ──
    if LLM_ENABLED and summary and HAS_DASHSCOPE:
        result = _call_qwen(_USER_TEMPLATE_PMI.format(summary=summary))
        if result:
            # 添加数据部分
            parts = []
            if pmi_mfg is not None:
                parts.append(f"制造PMI{pmi_mfg:.1f}{arrow_str[0] if arrow_str else ''}")
            if pmi_svc is not None:
                parts.append(f"非制造PMI{pmi_svc:.1f}{arrow_str[1] if len(arrow_str) > 1 else ''}")
            data_str = " / ".join(parts)
            result["summary_short"] = f"PMI {data_str} {result.get('summary_short', '')}"
    
    # ── 3. 规则兜底 ──
    if result is None:
        result = _rule_parse_pmi(pmi_mfg, pmi_svc, summary)
    
    # ── 4. 保存缓存 ──
    _save_to_cache("pmi", period, result)
    
    return result


def parse_gdp_interpretation(
    summary: str,
    gdp_yoy: float = None,
    gdp_qoq: float = None,
    period: str = None
) -> Dict[str, Any]:
    """
    解析 GDP 官方解读。
    
    Args:
        summary: 官方解读原始文本
        gdp_yoy: GDP 同比
        gdp_qoq: GDP 环比
        period: 数据期，如 "2026Q1"
    
    Returns:
        解析结果 dict
    """
    # ── 1. 检查缓存 ──
    cached = _check_cache("gdp", period)
    if cached:
        return cached
    
    # 构建箭头
    arrow = ""
    if gdp_qoq is not None:
        arrow = "↑" if gdp_qoq > 0 else "↓"
    
    result = None
    
    # ── 2. 优先尝试 LLM ──
    if LLM_ENABLED and summary and HAS_DASHSCOPE:
        result = _call_qwen(_USER_TEMPLATE_GDP.format(summary=summary))
        if result:
            # 添加数据部分
            data_str = f"GDP同比{gdp_yoy:+.1f}%{arrow}" if gdp_yoy is not None else "GDP"
            result["summary_short"] = f"{data_str} {result.get('summary_short', '')}"
    
    # ── 3. 规则兜底 ──
    if result is None:
        result = _rule_parse_gdp(gdp_yoy, summary)
    
    # ── 4. 保存缓存 ──
    _save_to_cache("gdp", period, result)
    
    return result


def parse_income_interpretation(
    summary: str,
    income_yoy: float = None,
    period: str = None
) -> Dict[str, Any]:
    """
    解析居民收入官方解读。
    
    Args:
        summary: 官方解读原始文本
        income_yoy: 人均收入同比
        period: 数据期，如 "2026Q1"
    
    Returns:
        解析结果 dict
    """
    # ── 1. 检查缓存 ──
    cached = _check_cache("income", period)
    if cached:
        return cached
    
    result = None
    
    # ── 2. 优先尝试 LLM ──
    if LLM_ENABLED and summary and HAS_DASHSCOPE:
        result = _call_qwen(_USER_TEMPLATE_INCOME.format(summary=summary))
        if result:
            # 添加数据部分
            data_str = f"收入同比{income_yoy:+.1f}%" if income_yoy is not None else "收入"
            result["summary_short"] = f"{data_str} {result.get('summary_short', '')}"
    
    # ── 3. 规则兜底 ──
    if result is None:
        data_str = f"收入同比{income_yoy:+.1f}%" if income_yoy is not None else "收入"
        sentiment = "positive" if income_yoy and income_yoy >= 5 else "neutral"
        trend = "收入增长" if income_yoy and income_yoy > 0 else "收入下降"
        result = {
            "summary_short": f"{data_str} {trend}",
            "key_trend": trend,
            "sentiment": sentiment
        }
    
    # ── 4. 保存缓存 ──
    _save_to_cache("income", period, result)
    
    return result


# ─────────────────────────────────────────────────────────────
# 便捷函数：直接从 CSV 行解析
# ─────────────────────────────────────────────────────────────

def parse_from_csv_row(row: dict, indicator: str) -> Dict[str, Any]:
    """
    从 CSV 行数据直接解析。
    
    Args:
        row: CSV 行字典
        indicator: 指标类型 "cpi_ppi" / "pmi" / "gdp" / "income"
    
    Returns:
        解析结果 dict
    """
    summary = row.get("summary", "")
    
    if indicator == "cpi_ppi":
        return parse_cpi_ppi_interpretation(
            summary=summary,
            cpi=_safe_float(row.get("cpi_yoy")),
            ppi=_safe_float(row.get("ppi_yoy")),
            cpi_mom=_safe_float(row.get("cpi_mom")),
            ppi_mom=_safe_float(row.get("ppi_mom"))
        )
    elif indicator == "pmi":
        return parse_pmi_interpretation(
            summary=summary,
            pmi_mfg=_safe_float(row.get("pmi_mfg")),
            pmi_svc=_safe_float(row.get("pmi_svc"))
        )
    elif indicator == "gdp":
        return parse_gdp_interpretation(
            summary=summary,
            gdp_yoy=_safe_float(row.get("gdp_yoy"))
        )
    elif indicator == "income":
        return parse_income_interpretation(
            summary=summary,
            income_yoy=_safe_float(row.get("income_yoy"))
        )
    
    return {"summary_short": "", "key_trend": "", "sentiment": "neutral"}


def _safe_float(val) -> Optional[float]:
    """安全转换为 float"""
    if val is None or val == "" or (isinstance(val, str) and not val.replace(".", "").replace("-", "").isdigit()):
        return None
    try:
        return float(val)
    except:
        return None
