"""
统计局解读数据自动抓取模块。

功能：
  - 从国家统计局网站自动抓取 CPI/PPI/PMI 最新解读数据
  - 当缓存文件没有最新月份数据时，自动更新

数据来源：
  - CPI/PPI: https://www.stats.gov.cn/sj/sjjd/
  - PMI: https://www.stats.gov.cn/sj/zxfb/
"""

import csv
import os
import re
import ssl
import urllib.request
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

# SSL 上下文
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

# 请求头
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0",
    "Accept": "text/html,application/xhtml+xml",
}

# 项目根目录
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DATA_DIR = os.path.join(_PROJECT_ROOT, "data")

# CSV 文件路径
_CPI_PPI_CSV = os.path.join(_DATA_DIR, "cpi_ppi_interpretation.csv")
_PMI_CSV = os.path.join(_DATA_DIR, "pmi_interpretation.csv")


def _fetch_page(url: str) -> Optional[str]:
    """抓取网页内容"""
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            return resp.read().decode("utf-8")
    except Exception as e:
        print(f"  抓取失败: {e}")
        return None


def _extract_text(html: str) -> str:
    """从 HTML 中提取纯文本"""
    # 去除 script 和 style
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL)
    # 去除 HTML 标签
    text = re.sub(r"<[^>]+>", " ", html)
    # 清理空白
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _get_current_period() -> str:
    """获取当前统计期（YYYY-MM 格式）"""
    now = datetime.now()
    # 统计局通常在次月中旬发布上月数据
    # 如果是月初，可能只有上上个月的数据
    if now.day <= 15:
        # 上个月
        if now.month == 1:
            return f"{now.year - 1}-12"
        return f"{now.year}-{now.month - 1:02d}"
    else:
        # 上个月
        if now.month == 1:
            return f"{now.year - 1}-12"
        return f"{now.year}-{now.month - 1:02d}"


def _get_latest_cpi_ppi_page() -> Optional[Tuple[str, str]]:
    """
    获取最新的 CPI/PPI 解读页面 URL 和标题。
    
    Returns:
        (url, title) 或 None
    """
    # 已知最新的 CPI/PPI 解读页面模式
    # 尝试不同的日期
    now = datetime.now()
    
    # 构建可能的 URL 列表（从当前月往前尝试）
    urls_to_try = []
    for i in range(6):  # 尝试最近6个月
        month = now.month - i
        year = now.year
        while month <= 0:
            month += 12
            year -= 1
        month_str = f"{year}{month:02d}"
        
        # CPI/PPI 通常在次月10日前后发布
        for day in ["15", "14", "13", "12", "11", "10", "09"]:
            # 尝试不同 ID
            for id_suffix in ["1963265", "1963200", "1963150", "1963109", "1962900"]:
                url = f"https://www.stats.gov.cn/sj/sjjd/{month_str}/t{month_str}{day}_{id_suffix}.html"
                urls_to_try.append(url)
    
    # 去重
    urls_to_try = list(dict.fromkeys(urls_to_try))
    
    # 先获取列表页
    list_url = "https://www.stats.gov.cn/sj/sjjd/"
    html = _fetch_page(list_url)
    if html:
        # 从列表页提取链接
        links = re.findall(r'href="(/sj/sjjd/\d+/t\d+_\d+\.html)"[^>]*>([^<]*CPI[^<]*|[^<]*PPI[^<]*|[^<]*居民消费[^<]*|[^<]*工业生产者[^<]*)</a>', html, re.I)
        for href, title in links[:3]:
            if "CPI" in title or "PPI" in title or "居民消费" in title or "工业生产者" in title:
                full_url = href if href.startswith("http") else f"https://www.stats.gov.cn{href}"
                return (full_url, title.strip())
    
    # 尝试直接访问已知页面
    for url in urls_to_try[:10]:
        html = _fetch_page(url)
        if html and "CPI" in html and "PPI" in html:
            # 提取标题
            title_match = re.search(r'<meta[^>]*name="ArticleTitle"[^>]*content="([^"]+)"', html)
            if title_match:
                return (url, title_match.group(1))
    
    return None


def _get_latest_pmi_page() -> Optional[Tuple[str, str]]:
    """
    获取最新的 PMI 解读页面 URL 和标题。
    
    Returns:
        (url, title) 或 None
    """
    # 尝试获取列表页
    list_url = "https://www.stats.gov.cn/sj/zxfb/"
    html = _fetch_page(list_url)
    if html:
        # 从列表页提取链接
        links = re.findall(r'href="(/sj/zxfb/\d+/t\d+_\d+\.html)"[^>]*>([^<]*PMI[^<]*|[^<]*采购经理[^<]*)</a>', html, re.I)
        for href, title in links[:3]:
            if "PMI" in title or "采购经理" in title:
                full_url = href if href.startswith("http") else f"https://www.stats.gov.cn{href}"
                return (full_url, title.strip())
    
    # 尝试已知的 URL 模式
    now = datetime.now()
    for i in range(6):
        month = now.month - i
        year = now.year
        while month <= 0:
            month += 12
            year -= 1
        month_str = f"{year}{month:02d}"
        
        for day in ["01", "02", "03", "04", "05"]:
            for id_suffix in ["1962890", "1962889", "1962800", "1962700", "1962600"]:
                url = f"https://www.stats.gov.cn/sj/zxfb/{month_str}/t{month_str}{day}_{id_suffix}.html"
                html = _fetch_page(url)
                if html and "PMI" in html and "采购经理" in html:
                    title_match = re.search(r'<meta[^>]*name="ArticleTitle"[^>]*content="([^"]+)"', html)
                    if title_match:
                        return (url, title_match.group(1))
    
    return None


def _parse_cpi_ppi_page(html: str, url: str) -> Dict[str, Any]:
    """
    解析 CPI/PPI 解读页面。
    
    Returns:
        {
            "period": "2026-03",
            "publish_date": "2026-04-10",
            "cpi_yoy": 1.0,
            "cpi_mom": -0.7,
            "ppi_yoy": 0.5,
            "title": "...",
            "author": "董莉娟",
            "summary": "...",
            "source_url": url,
        }
    """
    text = _extract_text(html)
    
    # 提取标题
    title_match = re.search(r'([0-9]{4}年[0-9]{1,2}月份CPI[^P]+|国家统计局[^C]+董莉娟[^0-9]+)', text)
    title = title_match.group(0)[:100] if title_match else ""
    
    # 提取发布日期
    date_match = re.search(r'([0-9]{4})年([0-9]{1,2})月([0-9]{1,2})日', text)
    publish_date = ""
    if date_match:
        publish_date = f"{date_match.group(1)}-{date_match.group(2).zfill(2)}-{date_match.group(3).zfill(2)}"
    
    # 提取作者
    author_match = re.search(r'董莉娟', text)
    author = author_match.group(0) if author_match else ""
    
    # 提取正文摘要（第一个完整句子）
    # 找到正文开始位置
    summary_start = text.find("3月份，")
    if summary_start == -1:
        summary_start = text.find("董莉娟解读")
    if summary_start == -1:
        summary_start = 0
    
    summary_text = text[summary_start:summary_start + 2000]
    
    # 提取第一个完整句子
    sentence_match = re.search(r'[^。？！.!?]{20,}', summary_text)
    first_sentence = sentence_match.group(0)[:300] if sentence_match else summary_text[:300]
    
    # 提取关键数据
    cpi_yoy = None
    cpi_mom = None
    ppi_yoy = None
    
    # CPI 同比
    cpi_yoy_match = re.search(r'CPI[^0-9]*同比[^上涨下降]*?([+-]?[0-9]+\.?[0-9]*)%', text)
    if cpi_yoy_match:
        cpi_yoy = float(cpi_yoy_match.group(1))
    
    # CPI 环比
    cpi_mom_match = re.search(r'CPI[^0-9]*环比[^上涨下降]*?([+-]?[0-9]+\.?[0-9]*)%', text)
    if cpi_mom_match:
        cpi_mom = float(cpi_mom_match.group(1))
    
    # PPI 同比
    ppi_yoy_match = re.search(r'PPI[^0-9]*同比[^上涨下降]*?([+-]?[0-9]+\.?[0-9]*)%', text)
    if ppi_yoy_match:
        ppi_yoy = float(ppi_yoy_match.group(1))
    
    # 推断统计期
    period_match = re.search(r'([0-9]{4})年([0-9]{1,2})月份', text)
    if period_match:
        period = f"{period_match.group(1)}-{period_match.group(2).zfill(2)}"
    else:
        # 根据发布日期推断
        if publish_date:
            year = int(publish_date[:4])
            month = int(publish_date[5:7])
            # 统计局数据通常是上月数据
            if month > 1:
                period = f"{year}-{month - 1:02d}"
            else:
                period = f"{year - 1}-12"
        else:
            period = _get_current_period()
    
    return {
        "period": period,
        "publish_date": publish_date,
        "cpi_yoy": cpi_yoy,
        "cpi_mom": cpi_mom,
        "ppi_yoy": ppi_yoy,
        "ppi_mom": None,
        "title": title,
        "author": author,
        "summary": first_sentence,
        "key_points": "",
        "source_url": url,
        "cached_at": datetime.now().isoformat(),
    }


def _parse_pmi_page(html: str, url: str) -> Dict[str, Any]:
    """
    解析 PMI 解读页面。
    
    Returns:
        {
            "period": "2026-03",
            "publish_date": "2026-03-31",
            "pmi_mfg": 50.4,
            "pmi_svc": 50.1,
            "pmi_composite": 50.5,
            "title": "...",
            "author": "霍丽慧",
            "summary": "...",
            "source_url": url,
        }
    """
    text = _extract_text(html)
    
    # 提取标题
    title_match = re.search(r'([0-9]{4}年[0-9]{1,2}月[^C]+|国家统计局[^H]+霍丽慧[^0-9]+)', text)
    title = title_match.group(0)[:100] if title_match else ""
    
    # 提取发布日期
    date_match = re.search(r'([0-9]{4})年([0-9]{1,2})月([0-9]{1,2})日', text)
    publish_date = ""
    if date_match:
        publish_date = f"{date_match.group(1)}-{date_match.group(2).zfill(2)}-{date_match.group(3).zfill(2)}"
    
    # 提取作者
    author_match = re.search(r'霍丽慧', text)
    author = author_match.group(0) if author_match else ""
    
    # 提取正文摘要
    summary_start = text.find("3月份，")
    if summary_start == -1:
        summary_start = text.find("霍丽慧解读")
    if summary_start == -1:
        summary_start = 0
    
    summary_text = text[summary_start:summary_start + 2000]
    
    # 提取第一个完整句子
    sentence_match = re.search(r'[^。？！.!?]{20,}', summary_text)
    first_sentence = sentence_match.group(0)[:300] if sentence_match else summary_text[:300]
    
    # 提取 PMI 数据
    pmi_mfg = None
    pmi_svc = None
    pmi_composite = None
    
    # 制造业 PMI
    mfg_match = re.search(r'制造业[^0-9]*PMI[^为是]*为?([0-9]+\.?[0-9]*)%', text)
    if mfg_match:
        pmi_mfg = float(mfg_match.group(1))
    
    # 非制造业 PMI
    svc_match = re.search(r'非制造业[^0-9]*商务活动[^0-9]*指数[^为是]*为?([0-9]+\.?[0-9]*)%', text)
    if svc_match:
        pmi_svc = float(svc_match.group(1))
    
    # 综合 PMI
    comp_match = re.search(r'综合[^0-9]*PMI[^0-9]*产出[^0-9]*指数[^为是]*为?([0-9]+\.?[0-9]*)%', text)
    if comp_match:
        pmi_composite = float(comp_match.group(1))
    
    # 推断统计期
    period_match = re.search(r'([0-9]{4})年([0-9]{1,2})月', text)
    if period_match:
        period = f"{period_match.group(1)}-{period_match.group(2).zfill(2)}"
    else:
        period = _get_current_period()
    
    return {
        "period": period,
        "publish_date": publish_date,
        "pmi_mfg": pmi_mfg,
        "pmi_svc": pmi_svc,
        "pmi_composite": pmi_composite,
        "title": title,
        "author": author,
        "summary": first_sentence,
        "key_points": "",
        "source_url": url,
        "cached_at": datetime.now().isoformat(),
    }


def _read_csv_cache(csv_path: str) -> Dict[str, Dict]:
    """读取 CSV 缓存，返回 {period: row_dict}"""
    if not os.path.isfile(csv_path):
        return {}
    
    result = {}
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                p = row.get("period", "").strip()
                if p:
                    result[p] = row
    except Exception:
        pass
    return result


def _write_csv_cache(csv_path: str, data: Dict[str, Dict], fieldnames: List[str]) -> bool:
    """写入 CSV 缓存"""
    try:
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for period in sorted(data.keys()):
                writer.writerow(data[period])
        return True
    except Exception as e:
        print(f"  写入 CSV 失败: {e}")
        return False


def update_cpi_ppi_cache() -> Dict[str, Any]:
    """
    更新 CPI/PPI 解读缓存。
    
    Returns:
        {"updated": bool, "period": str, "data": dict, "error": str|None}
    """
    # 读取现有缓存
    cached = _read_csv_cache(_CPI_PPI_CSV)
    current_period = _get_current_period()
    
    # 检查是否已有当前月份数据
    if current_period in cached:
        return {
            "updated": False,
            "period": current_period,
            "data": cached[current_period],
            "error": "缓存已是最新"
        }
    
    # 尝试获取最新页面
    page_info = _get_latest_cpi_ppi_page()
    if not page_info:
        return {
            "updated": False,
            "period": current_period,
            "data": None,
            "error": "无法获取最新页面"
        }
    
    url, title = page_info
    html = _fetch_page(url)
    if not html:
        return {
            "updated": False,
            "period": current_period,
            "data": None,
            "error": "页面抓取失败"
        }
    
    # 解析页面
    parsed = _parse_cpi_ppi_page(html, url)
    period = parsed["period"]
    
    # 更新缓存
    cached[period] = parsed
    
    # 写入 CSV
    fieldnames = ["period", "publish_date", "cpi_yoy", "cpi_mom", "ppi_yoy", "ppi_mom", 
                  "title", "author", "summary", "key_points", "source_url", "cached_at"]
    if _write_csv_cache(_CPI_PPI_CSV, cached, fieldnames):
        return {
            "updated": True,
            "period": period,
            "data": parsed,
            "error": None
        }
    else:
        return {
            "updated": False,
            "period": period,
            "data": parsed,
            "error": "CSV写入失败"
        }


def update_pmi_cache() -> Dict[str, Any]:
    """
    更新 PMI 解读缓存。
    
    Returns:
        {"updated": bool, "period": str, "data": dict, "error": str|None}
    """
    # 读取现有缓存
    cached = _read_csv_cache(_PMI_CSV)
    current_period = _get_current_period()
    
    # 检查是否已有当前月份数据
    if current_period in cached:
        return {
            "updated": False,
            "period": current_period,
            "data": cached[current_period],
            "error": "缓存已是最新"
        }
    
    # 尝试获取最新页面
    page_info = _get_latest_pmi_page()
    if not page_info:
        return {
            "updated": False,
            "period": current_period,
            "data": None,
            "error": "无法获取最新页面"
        }
    
    url, title = page_info
    html = _fetch_page(url)
    if not html:
        return {
            "updated": False,
            "period": current_period,
            "data": None,
            "error": "页面抓取失败"
        }
    
    # 解析页面
    parsed = _parse_pmi_page(html, url)
    period = parsed["period"]
    
    # 更新缓存
    cached[period] = parsed
    
    # 写入 CSV
    fieldnames = ["period", "publish_date", "pmi_mfg", "pmi_svc", "pmi_composite",
                  "title", "author", "summary", "key_points", "source_url", "cached_at"]
    if _write_csv_cache(_PMI_CSV, cached, fieldnames):
        return {
            "updated": True,
            "period": period,
            "data": parsed,
            "error": None
        }
    else:
        return {
            "updated": False,
            "period": period,
            "data": parsed,
            "error": "CSV写入失败"
        }


def update_all_caches() -> Dict[str, Any]:
    """更新所有解读缓存"""
    print("  正在检查统计局解读数据缓存...")
    
    cpi_result = update_cpi_ppi_cache()
    pmi_result = update_pmi_cache()
    
    results = {
        "cpi_ppi": cpi_result,
        "pmi": pmi_result,
    }
    
    if cpi_result["updated"]:
        print(f"  ✓ CPI/PPI {cpi_result['period']} 数据已更新")
    if pmi_result["updated"]:
        print(f"  ✓ PMI {pmi_result['period']} 数据已更新")
    
    if not cpi_result["updated"] and not pmi_result["updated"]:
        print("  缓存已是最新，无需更新")
    
    return results


if __name__ == "__main__":
    # 测试
    print("=" * 60)
    print("统计局解读数据自动抓取测试")
    print("=" * 60)
    
    results = update_all_caches()
    
    print("\n结果:")
    print(f"CPI/PPI: 更新={results['cpi_ppi']['updated']}, 期间={results['cpi_ppi']['period']}")
    print(f"PMI: 更新={results['pmi']['updated']}, 期间={results['pmi']['period']}")
