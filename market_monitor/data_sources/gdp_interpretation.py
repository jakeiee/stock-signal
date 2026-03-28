"""
GDP 官方解读抓取模块。

功能：
  - 通过 Web Search 抓取国家统计局 GDP 官方解读文章
  - 解析文章结构，提取关键结论
  - 与 GDP 数值数据融合，形成完整的分析报告

数据源：
  - 国家统计局官网「数据解读」栏目
  - URL 模式：https://www.stats.gov.cn/sj/sjjd/YYYYMM/tYYYYMMDD_xxxxxx.html

缓存机制：
  - 本地 CSV 缓存：market_monitor/data/gdp_interpretation.csv
  - 缓存有效期：90 天（季度数据，更新频率低）
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
    os.path.dirname(__file__), "..", "data", "gdp_interpretation.csv"
)

# CSV 字段定义
_CSV_FIELDS = [
    "period",           # 数据期，如 "2025Q4"
    "publish_date",     # 发布日期
    "gdp_yoy",          # GDP 同比（%）
    "title",            # 文章标题
    "author",           # 解读人
    "summary",          # 核心结论摘要
    "key_points",       # 关键要点（JSON 列表）
    "source_url",       # 原文链接
    "cached_at",        # 缓存时间
]


def _get_cache_path() -> str:
    return os.path.abspath(_CACHE_FILE)


def _read_cache(period: str) -> Optional[Dict]:
    """读取指定季度的缓存数据。"""
    cache_path = _get_cache_path()
    if not os.path.exists(cache_path):
        return None
    
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("period") == period:
                    cached_at = row.get("cached_at", "")
                    if cached_at:
                        try:
                            cache_time = datetime.fromisoformat(cached_at)
                            if datetime.now() - cache_time < timedelta(days=90):
                                result = dict(row)
                                result["key_points"] = json.loads(row.get("key_points", "[]"))
                                result["gdp_yoy"] = float(row["gdp_yoy"]) if row.get("gdp_yoy") else None
                                result["_source"] = "csv_cache"
                                return result
                        except (ValueError, TypeError):
                            pass
                    return None
    except Exception as e:
        print(f"[GDP解读] 读取缓存失败: {e}")
    
    return None


def _write_cache(data: Dict) -> None:
    """写入缓存文件。"""
    cache_path = _get_cache_path()
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    
    existing_rows = []
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                existing_rows = [row for row in reader if row.get("period") != data.get("period")]
        except Exception:
            pass
    
    new_row = {
        "period": data.get("period", ""),
        "publish_date": data.get("publish_date", ""),
        "gdp_yoy": str(data.get("gdp_yoy", "")) if data.get("gdp_yoy") is not None else "",
        "title": data.get("title", ""),
        "author": data.get("author", ""),
        "summary": data.get("summary", ""),
        "key_points": json.dumps(data.get("key_points", []), ensure_ascii=False),
        "source_url": data.get("source_url", ""),
        "cached_at": datetime.now().isoformat(),
    }
    existing_rows.append(new_row)
    
    try:
        with open(cache_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=_CSV_FIELDS)
            writer.writeheader()
            writer.writerows(existing_rows)
        print(f"[GDP解读] 缓存已更新: {cache_path}")
    except Exception as e:
        print(f"[GDP解读] 写入缓存失败: {e}")


def _fetch_article_via_browser(url: str) -> Optional[str]:
    """使用 Browser Automation 抓取文章内容。"""
    try:
        result = subprocess.run(
            ["agent-browser", "open", url],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            print(f"[GDP解读] 打开页面失败: {result.stderr}")
            return None
        
        js_code = "document.querySelector('.TRS_Editor, .content, #content, article')?.innerText || document.body.innerText"
        result = subprocess.run(
            ["agent-browser", "eval", js_code],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            content = result.stdout.strip()
            if content.startswith('"') and content.endswith('"'):
                content = content[1:-1]
            return content
        else:
            print(f"[GDP解读] 获取内容失败: {result.stderr}")
            return None
            
    except subprocess.TimeoutExpired:
        print("[GDP解读] 浏览器操作超时")
        return None
    except Exception as e:
        print(f"[GDP解读] 浏览器抓取失败: {e}")
        return None


def _parse_interpretation(text: str, year: int, quarter: int) -> Dict:
    """解析 GDP 解读文章内容。"""
    result = {
        "period": f"{year}Q{quarter}",
        "publish_date": "",
        "gdp_yoy": None,
        "title": "",
        "author": "",
        "summary": "",
        "key_points": [],
        "source_url": "",
        "_parse_method": "rule_based",
    }
    
    if not text:
        return result
    
    # 提取作者
    author_match = re.search(r"(\S+?)\s*解读", text)
    if author_match:
        result["author"] = author_match.group(1)
    
    # 提取 GDP 数值
    gdp_yoy_match = re.search(r"国内生产总值.*?增长.*?([\d\.]+)%|GDP.*?增长.*?([\d\.]+)%", text)
    if gdp_yoy_match:
        try:
            val = gdp_yoy_match.group(1) or gdp_yoy_match.group(2)
            result["gdp_yoy"] = float(val)
        except ValueError:
            pass
    
    # 提取发布日期
    date_match = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", text)
    if date_match:
        result["publish_date"] = f"{date_match.group(1)}-{int(date_match.group(2)):02d}-{int(date_match.group(3)):02d}"
    
    # 提取摘要
    result["summary"] = _extract_summary(text, year, quarter)
    
    # 提取关键要点
    result["key_points"] = _extract_key_points(text)
    
    return result


def _extract_summary(text: str, year: int, quarter: int) -> str:
    """提取摘要。"""
    clean_text = re.sub(r'\s+', '', text)
    
    # 方法1：找包含 GDP 的第一段
    sentences = clean_text.split("。")
    for sent in sentences[:10]:
        if "国内生产总值" in sent or "GDP" in sent:
            if 20 < len(sent) < 150:
                return sent + "。"
    
    # 方法2：记者问答格式，提取核心评价（"稳、进、新、韧"等关键词）
    for sent in sentences[:15]:
        # 找包含年度总结关键词的句子
        if any(kw in sent for kw in ["稳", "进", "新", "韧", "向好", "向优", "回升", "增长5.0%"]):
            if 15 < len(sent) < 120:
                return sent + "。"
    
    # 方法3：取第一段含数字的句子
    for sent in sentences[:10]:
        if any(c.isdigit() for c in sent) and len(sent) > 30:
            return sent + "。"
    
    return ""


def _extract_key_points(text: str) -> List[str]:
    """提取关键要点。"""
    key_points = []
    clean_text = re.sub(r'\s+', '', text)
    
    # 找包含具体数字的句子
    patterns = [
        r"([^。]{10,60}增长[^。]{5,30})",
        r"([^。]{10,60}下降[^。]{5,30})",
        r"([^。]{10,60}回升[^。]{5,30})",
        r"([^。]{10,60}回落[^。]{5,30})",
    ]
    for pattern in patterns:
        matches = re.findall(pattern, clean_text)
        for match in matches[:3]:
            point = match.strip()
            if point and point not in key_points and len(point) > 15:
                key_points.append(point)
    
    return key_points[:4]


# 预置 URL（作为后备）
_PRESET_URLS = {
    (2025, 4): "https://www.stats.gov.cn/sj/sjjd/202601/t20260119_1962345.html",
    (2025, 3): "https://www.stats.gov.cn/sj/zxfb/202510/t20251020_1961612.html",
    (2025, 2): "https://www.stats.gov.cn/xxgk/sjfb/zxfb2020/202507/t20250715_1960414.html",
    (2025, 1): "https://www.stats.gov.cn/sj/sjjd/202504/t20250416_1959325.html",
}

# 季度标签映射
_QUARTER_LABELS = {
    1: "一季度",
    2: "上半年", 
    3: "前三季度",
    4: "全年",
}


def _search_url_via_web_search(year: int, quarter: int) -> Optional[str]:
    """使用 Web Search 动态查找 GDP 解读文章 URL。"""
    try:
        from market_monitor.utils.web_search import search_web
        
        # 根据季度构建搜索关键词
        quarter_label = _QUARTER_LABELS.get(quarter, "一季度")
        search_queries = [
            f"{year}年 {quarter_label} GDP 国民经济运行 答记者问 site:stats.gov.cn",
            f"{year}年 国民经济运行 {quarter_label} 解读 site:stats.gov.cn",
            f"{year}年 GDP 同比增长 统计局 解读",
        ]
        
        for query in search_queries:
            print(f"[GDP解读] 搜索: {query}")
            
            try:
                search_results = search_web(query, limit=8, engine="duckduckgo")
                
                if isinstance(search_results, list) and len(search_results) > 0:
                    for item in search_results:
                        url = item.get("url", "") if isinstance(item, dict) else str(item)
                        if _is_valid_url(url, year):
                            print(f"[GDP解读] ✓ 找到有效 URL: {url}")
                            # 更新预置URL，供下次使用
                            _PRESET_URLS[(year, quarter)] = url
                            return url
                                
            except Exception as e:
                print(f"[GDP解读] 搜索失败: {e}")
                continue
        
        return None
        
    except ImportError as e:
        print(f"[GDP解读] Web Search 模块导入失败: {e}")
        return None


def _is_valid_url(url: str, year: int) -> bool:
    """验证 URL 是否为有效的 GDP 解读文章链接。"""
    if not url or "stats.gov.cn" not in url:
        return False
    
    if "data.stats.gov.cn" in url:
        return False
    
    if "/sjjd/" not in url and "/zxfbhjd/" not in url and "/sj/" not in url and "/sjfb/" not in url and "/xxgk/" not in url:
        return False
    
    # GDP 数据通常在季度结束后约15-20天发布
    if str(year) not in url:
        # 也可能是发布年（次年1月发布全年数据）
        return False
    
    return True


def _auto_get_url(year: int, quarter: int) -> Optional[str]:
    """自动获取 GDP 解读 URL。"""
    period = (year, quarter)
    
    # 1. 优先检查预置列表（成功率最高）
    if period in _PRESET_URLS:
        print(f"[GDP解读] 使用预置 URL: {_PRESET_URLS[period]}")
        return _PRESET_URLS[period]
    
    print(f"[GDP解读] 未预置 {year}Q{quarter} 的 URL，尝试Web Search...")
    
    # 2. 尝试 Web Search
    url = _search_url_via_web_search(year, quarter)
    if url:
        _PRESET_URLS[period] = url
        return url
    
    print(f"[GDP解读] 自动获取失败")
    return None


def _parse_with_llm(text: str, year: int, quarter: int) -> Dict:
    """使用千问LLM解析GDP解读文章（额度控制：90天只调用一次）"""
    try:
        from market_monitor.utils.llm_client import LLMClient
        
        # 使用 qwen-turbo 节省额度
        client = LLMClient(
            provider="qwen",
            model="qwen-turbo",
            max_tokens=1500,
            temperature=0.3,
        )
        
        quarter_label = _QUARTER_LABELS.get(quarter, f"Q{quarter}")
        
        prompt = f"""从以下国家统计局{year}年{quarter_label}GDP解读文章中提取信息，返回严格JSON格式：

{{
    "gdp_yoy": 数值(百分比，如5.0)或null,
    "gdp_total": "总量(万亿元，如140)",
    "summary": "核心结论(不超过50字)",
    "highlights": ["亮点1", "亮点2", "亮点3"],
    "author": "发言人姓名",
    "publish_date": "发布日期如2026-01-19"
}}

要求：
1. 只返回JSON，不要其他文字
2. JSON格式正确可解析
3. summary用一句话概括经济总体表现

文章内容（前4000字）：
{text[:4000]}
"""
        
        result = client.extract_json(prompt)
        
        # 添加解析方式标记
        result["_parse_method"] = "llm"
        result["period"] = f"{year}Q{quarter}"
        
        print(f"[GDP解读] LLM解析完成，使用模型: {client.model}")
        
        return result
        
    except ImportError as e:
        print(f"[GDP解读] LLM模块导入失败: {e}，回退到正则解析")
        return _parse_interpretation(text, year, quarter)
    except Exception as e:
        print(f"[GDP解读] LLM解析失败: {e}，回退到正则解析")
        return _parse_interpretation(text, year, quarter)


def fetch_gdp_interpretation(
    year: int, 
    quarter: int, 
    use_cache: bool = True,
    auto_search: bool = True,
    use_llm: bool = True,
    force_llm: bool = False,
) -> Dict:
    """获取 GDP 官方解读（带缓存，支持LLM解析）。
    
    Args:
        year: 年份
        quarter: 季度 (1=Q1, 2=H1, 3=Q3, 4=FY)
        use_cache: 是否使用缓存
        auto_search: 是否自动搜索URL
        use_llm: 是否使用LLM解析（默认开启，额度控制）
        force_llm: 是否强制重新调用LLM（忽略缓存）
    """
    period = f"{year}Q{quarter}"
    
    # 1. 检查缓存
    if use_cache:
        cached = _read_cache(period)
        if cached:
            print(f"[GDP解读] 命中缓存: {period}")
            return cached
    
    # 2. 获取文章URL
    article_url = None
    
    if auto_search:
        article_url = _auto_get_url(year, quarter)
    else:
        article_url = _PRESET_URLS.get((year, quarter))
    
    if not article_url:
        return {
            "error": f"未找到 {period} 的解读文章 URL",
            "hint": f"使用 fetch_gdp_interpretation_by_url(url, {year}, {quarter}) 手动传入 URL"
        }
    
    print(f"[GDP解读] 正在抓取: {article_url}")
    text = _fetch_article_via_browser(article_url)
    
    if not text:
        return {"error": "抓取文章失败", "url": article_url}
    
    # 3. 解析：优先使用LLM（额度控制）
    if use_llm:
        result = _parse_with_llm(text, year, quarter)
    else:
        result = _parse_interpretation(text, year, quarter)
    
    result["source_url"] = article_url
    result["_source"] = "browser_fetch"
    
    # 4. 写入缓存
    _write_cache(result)
    
    return result


def fetch_gdp_with_interpretation(
    year: Optional[int] = None, 
    quarter: Optional[int] = None
) -> Dict:
    """获取完整的 GDP 数据（数值 + 官方解读）。"""
    # 默认获取上一季度数据
    if year is None or quarter is None:
        today = datetime.now()
        quarter = (today.month - 1) // 3 + 1
        if quarter == 1:
            year = today.year - 1
            quarter = 4
        else:
            year = today.year
            quarter = quarter - 1
    
    period = f"{year}Q{quarter}"
    
    # 1. 获取 GDP 数值
    from .fundamental import fetch_gdp
    
    gdp_data = fetch_gdp()
    
    if "error" in gdp_data:
        return {"error": f"获取 GDP 数值失败: {gdp_data['error']}"}
    
    # 2. 获取官方解读
    interpretation = fetch_gdp_interpretation(year, quarter)
    
    # 3. 融合数据
    result = {
        "period": period,
        "gdp_yoy": gdp_data.get("gdp_yoy"),
        "p1_yoy": gdp_data.get("p1_yoy"),
        "p2_yoy": gdp_data.get("p2_yoy"),
        "p3_yoy": gdp_data.get("p3_yoy"),
        "p1_pct": gdp_data.get("p1_pct"),
        "p2_pct": gdp_data.get("p2_pct"),
        "p3_pct": gdp_data.get("p3_pct"),
        "interpretation": interpretation if "error" not in interpretation else None,
        "data_source": gdp_data.get("source", "eastmoney"),
        "interp_source": "stats_gov_cn" if "error" not in interpretation else None,
        "_source": "merged",
    }
    
    return result


if __name__ == "__main__":
    print("=" * 60)
    print("测试 GDP 解读抓取")
    print("=" * 60)
    
    result = fetch_gdp_with_interpretation(2025, 4)
    
    print("\n完整 GDP 数据（数值+解读）：")
    print(json.dumps(result, ensure_ascii=False, indent=2))