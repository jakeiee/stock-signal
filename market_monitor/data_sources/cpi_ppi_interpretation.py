"""
CPI/PPI 官方解读抓取模块。

功能：
  - 通过 Web Search 抓取国家统计局 CPI/PPI 官方解读文章
  - 解析文章结构，提取关键结论、分项数据
  - 与 CPI/PPI 数值数据融合，形成完整的分析报告

数据源：
  - 国家统计局官网「数据解读」栏目
  - URL 模式：https://www.stats.gov.cn/sj/sjjd/YYYYMM/tYYYYMMDD_xxxxxx.html

缓存机制：
  - 本地 CSV 缓存：market_monitor/data/cpi_ppi_interpretation.csv
  - 缓存有效期：30 天（月度数据，无需频繁更新）
"""

import csv
import json
import os
import re
import subprocess
from datetime import datetime, timedelta
from typing import Optional, Dict, List

# 缓存文件路径
_CACHE_FILE = os.path.join(
    os.path.dirname(__file__), "..", "data", "cpi_ppi_interpretation.csv"
)

# CSV 字段定义
_CSV_FIELDS = [
    "period",           # 数据期，如 "2026-02"
    "publish_date",     # 发布日期，如 "2026-03-10"
    "cpi_yoy",          # CPI 同比（%）
    "cpi_mom",          # CPI 环比（%）
    "ppi_yoy",          # PPI 同比（%）
    "ppi_mom",          # PPI 环比（%）
    "title",            # 文章标题
    "author",           # 解读人
    "summary",          # 核心结论摘要
    "key_points",       # 关键要点（JSON 列表）
    "source_url",       # 原文链接
    "cached_at",        # 缓存时间
]


def _get_cache_path() -> str:
    """获取缓存文件绝对路径。"""
    return os.path.abspath(_CACHE_FILE)


def _read_cache(period: str) -> Optional[Dict]:
    """
    读取指定月份的缓存数据。
    
    Returns:
        缓存数据字典，或 None（未找到或已过期）
    """
    cache_path = _get_cache_path()
    if not os.path.exists(cache_path):
        return None
    
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("period") == period:
                    # 检查缓存有效期（30天）
                    cached_at = row.get("cached_at", "")
                    if cached_at:
                        try:
                            cache_time = datetime.fromisoformat(cached_at)
                            if datetime.now() - cache_time < timedelta(days=30):
                                # 解析 JSON 字段
                                result = dict(row)
                                result["key_points"] = json.loads(row.get("key_points", "[]"))
                                result["cpi_yoy"] = float(row["cpi_yoy"]) if row.get("cpi_yoy") else None
                                result["cpi_mom"] = float(row["cpi_mom"]) if row.get("cpi_mom") else None
                                result["ppi_yoy"] = float(row["ppi_yoy"]) if row.get("ppi_yoy") else None
                                result["ppi_mom"] = float(row["ppi_mom"]) if row.get("ppi_mom") else None
                                result["_source"] = "csv_cache"
                                return result
                        except (ValueError, TypeError):
                            pass
                    return None
    except Exception as e:
        print(f"[CPI/PPI解读] 读取缓存失败: {e}")
    
    return None


def _write_cache(data: Dict) -> None:
    """写入缓存文件。"""
    cache_path = _get_cache_path()
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    
    # 读取现有数据
    existing_rows = []
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                existing_rows = [row for row in reader if row.get("period") != data.get("period")]
        except Exception:
            pass
    
    # 准备新数据行
    new_row = {
        "period": data.get("period", ""),
        "publish_date": data.get("publish_date", ""),
        "cpi_yoy": str(data.get("cpi_yoy", "")) if data.get("cpi_yoy") is not None else "",
        "cpi_mom": str(data.get("cpi_mom", "")) if data.get("cpi_mom") is not None else "",
        "ppi_yoy": str(data.get("ppi_yoy", "")) if data.get("ppi_yoy") is not None else "",
        "ppi_mom": str(data.get("ppi_mom", "")) if data.get("ppi_mom") is not None else "",
        "title": data.get("title", ""),
        "author": data.get("author", ""),
        "summary": data.get("summary", ""),
        "key_points": json.dumps(data.get("key_points", []), ensure_ascii=False),
        "source_url": data.get("source_url", ""),
        "cached_at": datetime.now().isoformat(),
    }
    existing_rows.append(new_row)
    
    # 写入文件
    try:
        with open(cache_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=_CSV_FIELDS)
            writer.writeheader()
            writer.writerows(existing_rows)
        print(f"[CPI/PPI解读] 缓存已更新: {cache_path}")
    except Exception as e:
        print(f"[CPI/PPI解读] 写入缓存失败: {e}")


def _fetch_article_via_browser(url: str) -> Optional[str]:
    """
    使用 Browser Automation 抓取文章内容。
    
    Returns:
        文章正文文本
    """
    try:
        # 调用 agent-browser 命令
        result = subprocess.run(
            ["agent-browser", "open", url],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            print(f"[CPI/PPI解读] 打开页面失败: {result.stderr}")
            return None
        
        # 获取页面内容
        js_code = "document.querySelector('.TRS_Editor, .content, #content, article')?.innerText || document.body.innerText"
        result = subprocess.run(
            ["agent-browser", "eval", js_code],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            # 去除前后引号
            content = result.stdout.strip()
            if content.startswith('"') and content.endswith('"'):
                content = content[1:-1]
            return content
        else:
            print(f"[CPI/PPI解读] 获取内容失败: {result.stderr}")
            return None
            
    except subprocess.TimeoutExpired:
        print("[CPI/PPI解读] 浏览器操作超时")
        return None
    except Exception as e:
        print(f"[CPI/PPI解读] 浏览器抓取失败: {e}")
        return None


def _parse_interpretation(text: str, year: int, month: int) -> Dict:
    """
    解析 CPI/PPI 解读文章内容，提取结构化数据。
    
    Args:
        text: 文章正文
        year: 年份
        month: 月份
    """
    result = {
        "period": f"{year}-{month:02d}",
        "publish_date": "",
        "cpi_yoy": None,
        "cpi_mom": None,
        "ppi_yoy": None,
        "ppi_mom": None,
        "title": "",
        "author": "",
        "summary": "",
        "key_points": [],
        "source_url": "",
        "_parse_method": "rule_based",
    }
    
    if not text:
        return result
    
    # 提取作者（格式：XXX 解读）
    author_match = re.search(r"(\S+?)\s*解读", text)
    if author_match:
        result["author"] = author_match.group(1)
    
    # 提取 CPI 数值
    cpi_yoy_match = re.search(r"居民消费价格.*?上涨.*?([\d\.]+)%", text)
    if cpi_yoy_match:
        try:
            result["cpi_yoy"] = float(cpi_yoy_match.group(1))
        except ValueError:
            pass
    
    cpi_mom_match = re.search(r"环比.*?下降.*?([\d\.]+)%|环比.*?上涨.*?([\d\.]+)%", text)
    if cpi_mom_match:
        try:
            val = cpi_mom_match.group(1) or cpi_mom_match.group(2)
            result["cpi_mom"] = float(val)
        except ValueError:
            pass
    
    # 提取 PPI 数值
    ppi_yoy_match = re.search(r"工业生产者.*?下降.*?([\d\.]+)%|工业生产者.*?上涨.*?([\d\.]+)%", text)
    if ppi_yoy_match:
        try:
            val = ppi_yoy_match.group(1) or ppi_yoy_match.group(2)
            result["ppi_yoy"] = float(val)
        except ValueError:
            pass
    
    # 提取发布日期
    date_match = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", text)
    if date_match:
        result["publish_date"] = f"{date_match.group(1)}-{int(date_match.group(2)):02d}-{int(date_match.group(3)):02d}"
    
    # 提取摘要
    result["summary"] = _extract_summary(text, year, month)
    
    # 提取关键要点
    result["key_points"] = _extract_key_points(text)
    
    return result


def _extract_summary(text: str, year: int, month: int) -> str:
    """
    提取摘要 - 基于段落结构
    """
    clean_text = re.sub(r'\s+', '', text)
    
    # 找包含月份和 CPI/PPI 的第一段长文本
    month_cn = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "十一", "十二"]
    month_str = month_cn[month - 1] if month <= 12 else str(month)
    
    # 匹配 "X月份，..." 开头的段落
    pattern = rf"({month_str}|[\d]+)月[份]*，[^。]{{20,150}}。"
    match = re.search(pattern, clean_text)
    if match:
        summary = match.group(0)
        if "价格" in summary or "指数" in summary:
            return summary
    
    # 备选：找包含 CPI/PPI 的最长句子
    sentences = clean_text.split("。")
    for sent in sorted(sentences, key=len, reverse=True):
        if "消费价格" in sent or "工业生产者" in sent:
            if 30 < len(sent) < 200:
                return sent + "。"
    
    return ""


def _extract_key_points(text: str) -> List[str]:
    """
    提取关键要点
    """
    key_points = []
    clean_text = re.sub(r'\s+', '', text)
    
    # 策略1：找包含具体数字和"上涨/下降"的句子
    change_patterns = [
        r"([^。]{10,60}上涨[^。]{5,30})",
        r"([^。]{10,60}下降[^。]{5,30})",
        r"([^。]{10,60}涨幅[^。]{5,30})",
        r"([^。]{10,60}降幅[^。]{5,30})",
    ]
    for pattern in change_patterns:
        matches = re.findall(pattern, clean_text)
        for match in matches[:3]:
            point = match.strip()
            if point and point not in key_points and len(point) > 15:
                key_points.append(point)
    
    # 策略2：找分项描述
    dimension_patterns = [
        r"从品类看，([^。]{10,60})",
        r"从行业看，([^。]{10,60})",
        r"从环比看，([^。]{10,60})",
    ]
    for pattern in dimension_patterns:
        match = re.search(pattern, clean_text)
        if match:
            point = match.group(1).strip()
            if point and point not in key_points:
                key_points.append(point)
                break
    
    return key_points[:5]


# 预置已知 URL（作为后备）
_PRESET_URLS = {
    (2026, 2): "https://www.stats.gov.cn/sj/sjjd/202603/t20260309_1962728.html",
    (2026, 1): "https://www.stats.gov.cn/sj/sjjd/202602/t20260211_1962586.html",
}


def _search_url_via_web_search(year: int, month: int) -> Optional[str]:
    """
    使用 Web Search 查找 CPI/PPI 解读文章 URL。
    """
    try:
        from market_monitor.utils.web_search import search_web
        
        search_queries = [
            f"{year}年{month}月 居民消费价格 解读 site:stats.gov.cn",
            f"{year}年{month}月 CPI PPI 解读 site:stats.gov.cn",
            f"{year}年{month}月 国民经济运行 解读 site:stats.gov.cn",
        ]
        
        for query in search_queries:
            print(f"[CPI/PPI解读] 搜索: {query}")
            
            try:
                search_results = search_web(query, limit=5, engine="duckduckgo")
                
                if isinstance(search_results, list) and len(search_results) > 0:
                    for item in search_results:
                        url = item.get("url", "") if isinstance(item, dict) else str(item)
                        if _is_valid_url(url, year, month):
                            print(f"[CPI/PPI解读] ✓ 找到有效 URL: {url}")
                            return url
                        
            except Exception as e:
                print(f"[CPI/PPI解读] 搜索失败: {e}")
                continue
        
        return None
        
    except ImportError as e:
        print(f"[CPI/PPI解读] Web Search 模块导入失败: {e}")
        return None


def _is_valid_url(url: str, year: int, month: int) -> bool:
    """
    验证 URL 是否为有效的 CPI/PPI 解读文章链接。
    """
    if not url or "stats.gov.cn" not in url:
        return False
    
    # 排除数据查询平台
    if "data.stats.gov.cn" in url:
        return False
    
    # 必须是数据解读栏目
    if "/sjjd/" not in url and "/zxfbhjd/" not in url and "/sj/" not in url:
        return False
    
    # 发布年月应该在数据月之后（通常是次月发布）
    pub_year = year
    pub_month = month + 1
    if pub_month > 12:
        pub_year += 1
        pub_month = 1
    
    pub_year_month = f"{pub_year}{pub_month:02d}"
    
    # 检查 URL 是否包含发布年月或数据年月
    url_indicators = [
        pub_year_month,
        f"{year}{month:02d}",
        f"t{pub_year}{pub_month:02d}",
    ]
    
    has_date = any(ind in url for ind in url_indicators)
    if not has_date:
        if str(pub_year) not in url and str(year) not in url:
            return False
    
    return True


def _auto_get_url(year: int, month: int) -> Optional[str]:
    """
    自动获取 CPI/PPI 解读 URL。
    
    优先级:
    1. 检查预置列表
    2. Web Search 搜索
    3. 返回 None
    """
    period = (year, month)
    
    # 1. 检查预置列表
    if period in _PRESET_URLS:
        print(f"[CPI/PPI解读] 使用预置 URL: {_PRESET_URLS[period]}")
        return _PRESET_URLS[period]
    
    print(f"[CPI/PPI解读] 未预置 {year}年{month}月 的 URL，尝试自动获取...")
    
    # 2. 尝试 Web Search
    url = _search_url_via_web_search(year, month)
    if url:
        _PRESET_URLS[period] = url
        return url
    
    print(f"[CPI/PPI解读] 自动获取失败")
    return None


def fetch_cpi_ppi_interpretation(
    year: int, 
    month: int, 
    use_cache: bool = True,
    auto_search: bool = True
) -> Dict:
    """
    获取 CPI/PPI 官方解读（带缓存，支持自动 URL 获取）。
    
    Args:
        year: 年份
        month: 月份
        use_cache: 是否使用缓存
        auto_search: 是否自动搜索 URL
    
    Returns:
        包含解读数据的字典
    """
    period = f"{year}-{month:02d}"
    
    # 1. 检查缓存
    if use_cache:
        cached = _read_cache(period)
        if cached:
            print(f"[CPI/PPI解读] 命中缓存: {period}")
            return cached
    
    # 2. 获取文章 URL
    article_url = None
    
    if auto_search:
        article_url = _auto_get_url(year, month)
    else:
        article_url = _PRESET_URLS.get((year, month))
    
    if not article_url:
        return {
            "error": f"未找到 {period} 的解读文章 URL",
            "hint": f"使用 fetch_cpi_ppi_interpretation_by_url(url, {year}, {month}) 手动传入 URL"
        }
    
    # 3. 使用浏览器抓取
    print(f"[CPI/PPI解读] 正在抓取: {article_url}")
    text = _fetch_article_via_browser(article_url)
    
    if not text:
        return {"error": "抓取文章失败", "url": article_url}
    
    # 4. 解析内容
    result = _parse_interpretation(text, year, month)
    result["source_url"] = article_url
    result["_source"] = "browser_fetch"
    
    # 5. 写入缓存
    _write_cache(result)
    
    return result


def fetch_cpi_ppi_with_interpretation(
    year: Optional[int] = None, 
    month: Optional[int] = None
) -> Dict:
    """
    获取完整的 CPI/PPI 数据（数值 + 官方解读）。
    
    Args:
        year: 年份，默认为上个月
        month: 月份，默认为上个月
    
    Returns:
        融合后的 CPI/PPI 数据字典
    """
    # 默认获取上个月数据
    if year is None or month is None:
        today = datetime.now()
        if today.month == 1:
            year = today.year - 1
            month = 12
        else:
            year = today.year
            month = today.month - 1
    
    period = f"{year}-{month:02d}"
    
    # 1. 获取 CPI/PPI 数值（从 fundamental 模块）
    from .fundamental import fetch_macro_supply_demand
    
    supply_demand = fetch_macro_supply_demand()
    
    if "error" in supply_demand:
        return {"error": f"获取 CPI/PPI 数值失败: {supply_demand['error']}"}
    
    # 2. 获取官方解读
    interpretation = fetch_cpi_ppi_interpretation(year, month)
    
    # 3. 融合数据
    result = {
        "period": period,
        "cpi_yoy": supply_demand.get("cpi_yoy"),
        "cpi_mom": supply_demand.get("cpi_mom"),
        "ppi_yoy": supply_demand.get("ppi_yoy"),
        "ppi_mom": supply_demand.get("ppi_mom"),
        "ppi_cpi_spread": supply_demand.get("ppi_cpi_spread"),
        "interpretation": interpretation if "error" not in interpretation else None,
        "data_source": supply_demand.get("source", "eastmoney"),
        "interp_source": "stats_gov_cn" if "error" not in interpretation else None,
        "_source": "merged",
    }
    
    return result


if __name__ == "__main__":
    # 测试
    print("=" * 60)
    print("测试 CPI/PPI 解读抓取")
    print("=" * 60)
    
    # 测试获取 2026年2月数据
    result = fetch_cpi_ppi_with_interpretation(2026, 2)
    
    print("\n完整 CPI/PPI 数据（数值+解读）：")
    print(json.dumps(result, ensure_ascii=False, indent=2))