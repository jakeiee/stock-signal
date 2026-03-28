"""
人均可支配收入官方解读抓取模块。

功能：
  - 通过 Web Search 抓取国家统计局人均收入官方解读文章
  - 解析文章结构，提取关键结论
  - 与收入数据融合，形成完整的分析报告

数据源：
  - 国家统计局官网「数据解读」栏目

缓存机制：
  - 本地 CSV 缓存：market_monitor/data/income_interpretation.csv
  - 缓存有效期：90 天（季度数据）
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
    os.path.dirname(__file__), "..", "data", "income_interpretation.csv"
)

# CSV 字段定义
_CSV_FIELDS = [
    "period",           # 数据期，如 "2025Q4"
    "publish_date",     # 发布日期
    "income_yoy",       # 人均可支配收入同比（%）
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
                                result["income_yoy"] = float(row["income_yoy"]) if row.get("income_yoy") else None
                                result["_source"] = "csv_cache"
                                return result
                        except (ValueError, TypeError):
                            pass
                    return None
    except Exception as e:
        print(f"[收入解读] 读取缓存失败: {e}")
    
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
        "income_yoy": str(data.get("income_yoy", "")) if data.get("income_yoy") is not None else "",
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
        print(f"[收入解读] 缓存已更新: {cache_path}")
    except Exception as e:
        print(f"[收入解读] 写入缓存失败: {e}")


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
            print(f"[收入解读] 打开页面失败: {result.stderr}")
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
            print(f"[收入解读] 获取内容失败: {result.stderr}")
            return None
            
    except subprocess.TimeoutExpired:
        print("[收入解读] 浏览器操作超时")
        return None
    except Exception as e:
        print(f"[收入解读] 浏览器抓取失败: {e}")
        return None


def _parse_interpretation(text: str, year: int, quarter: int) -> Dict:
    """解析收入解读文章内容。"""
    result = {
        "period": f"{year}Q{quarter}",
        "publish_date": "",
        "income_yoy": None,
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
    
    # 提取收入增速
    income_yoy_match = re.search(r"人均可支配收入.*?名义增长.*?([\d\.]+)%|收入.*?增长.*?([\d\.]+)%", text)
    if income_yoy_match:
        try:
            val = income_yoy_match.group(1) or income_yoy_match.group(2)
            result["income_yoy"] = float(val)
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
    
    sentences = clean_text.split("。")
    for sent in sentences[:5]:
        if "可支配收入" in sent or "居民收入" in sent:
            if 20 < len(sent) < 150:
                return sent + "。"
    
    return ""


def _extract_key_points(text: str) -> List[str]:
    """提取关键要点。"""
    key_points = []
    clean_text = re.sub(r'\s+', '', text)
    
    patterns = [
        r"([^。]{10,60}增长[^。]{5,30})",
        r"([^。]{10,60}提高[^。]{5,30})",
        r"([^。]{10,60}加快[^。]{5,30})",
        r"([^。]{10,60}回落[^。]{5,30})",
    ]
    for pattern in patterns:
        matches = re.findall(pattern, clean_text)
        for match in matches[:2]:
            point = match.strip()
            if point and point not in key_points and len(point) > 15:
                key_points.append(point)
    
    return key_points[:4]


# 预置 URL
_PRESET_URLS = {
    (2025, 4): "https://www.stats.gov.cn/sj/sjjd/202601/t20260121_1959085.html",
    (2025, 3): "https://www.stats.gov.cn/sj/sjjd/202410/t20241018_1957733.html",
}


def _search_url_via_web_search(year: int, quarter: int) -> Optional[str]:
    """使用 Web Search 查找收入解读文章 URL。"""
    try:
        from market_monitor.utils.web_search import search_web
        
        search_queries = [
            f"{year}年 居民人均可支配收入 解读 site:stats.gov.cn",
            f"{year}年 收入 解读 site:stats.gov.cn",
        ]
        
        for query in search_queries:
            print(f"[收入解读] 搜索: {query}")
            
            try:
                search_results = search_web(query, limit=5, engine="duckduckgo")
                
                if isinstance(search_results, list) and len(search_results) > 0:
                    for item in search_results:
                        url = item.get("url", "") if isinstance(item, dict) else str(item)
                        if _is_valid_url(url, year):
                            print(f"[收入解读] ✓ 找到有效 URL: {url}")
                            return url
                        
            except Exception as e:
                print(f"[收入解读] 搜索失败: {e}")
                continue
        
        return None
        
    except ImportError as e:
        print(f"[收入解读] Web Search 模块导入失败: {e}")
        return None


def _is_valid_url(url: str, year: int) -> bool:
    """验证 URL。"""
    if not url or "stats.gov.cn" not in url:
        return False
    
    if "data.stats.gov.cn" in url:
        return False
    
    if "/sjjd/" not in url and "/zxfbhjd/" not in url and "/sj/" not in url:
        return False
    
    if str(year) not in url:
        return False
    
    return True


def _auto_get_url(year: int, quarter: int) -> Optional[str]:
    """自动获取收入解读 URL。"""
    period = (year, quarter)
    
    if period in _PRESET_URLS:
        print(f"[收入解读] 使用预置 URL: {_PRESET_URLS[period]}")
        return _PRESET_URLS[period]
    
    print(f"[收入解读] 未预置 {year}Q{quarter} 的 URL，尝试自动获取...")
    
    url = _search_url_via_web_search(year, quarter)
    if url:
        _PRESET_URLS[period] = url
        return url
    
    print(f"[收入解读] 自动获取失败")
    return None


def fetch_income_interpretation(
    year: int, 
    quarter: int, 
    use_cache: bool = True,
    auto_search: bool = True
) -> Dict:
    """获取人均收入官方解读（带缓存）。"""
    period = f"{year}Q{quarter}"
    
    if use_cache:
        cached = _read_cache(period)
        if cached:
            print(f"[收入解读] 命中缓存: {period}")
            return cached
    
    article_url = None
    
    if auto_search:
        article_url = _auto_get_url(year, quarter)
    else:
        article_url = _PRESET_URLS.get((year, quarter))
    
    if not article_url:
        return {
            "error": f"未找到 {period} 的解读文章 URL",
            "hint": f"使用 fetch_income_interpretation_by_url(url, {year}, {quarter}) 手动传入 URL"
        }
    
    print(f"[收入解读] 正在抓取: {article_url}")
    text = _fetch_article_via_browser(article_url)
    
    if not text:
        return {"error": "抓取文章失败", "url": article_url}
    
    result = _parse_interpretation(text, year, quarter)
    result["source_url"] = article_url
    result["_source"] = "browser_fetch"
    
    _write_cache(result)
    
    return result


def fetch_income_with_interpretation(
    year: Optional[int] = None, 
    quarter: Optional[int] = None
) -> Dict:
    """获取完整的人均收入数据（数值 + 官方解读）。"""
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
    
    # 1. 获取收入数值
    from .fundamental import fetch_disposable_income
    
    income_data = fetch_disposable_income()
    
    if "error" in income_data:
        return {"error": f"获取收入数值失败: {income_data['error']}"}
    
    # 2. 获取官方解读
    interpretation = fetch_income_interpretation(year, quarter)
    
    # 3. 融合数据
    result = {
        "period": period,
        "income_yoy": income_data.get("income_yoy"),
        "real_yoy": income_data.get("real_yoy"),
        "interpretation": interpretation if "error" not in interpretation else None,
        "data_source": income_data.get("source", "stats.gov.cn"),
        "interp_source": "stats_gov_cn" if "error" not in interpretation else None,
        "_source": "merged",
    }
    
    return result


if __name__ == "__main__":
    print("=" * 60)
    print("测试 人均收入 解读抓取")
    print("=" * 60)
    
    result = fetch_income_with_interpretation(2025, 4)
    
    print("\n完整收入数据（数值+解读）：")
    print(json.dumps(result, ensure_ascii=False, indent=2))