"""
PMI 官方解读抓取模块。

功能：
  - 通过 Browser Automation 抓取国家统计局 PMI 官方解读文章
  - 解析文章结构，提取关键结论、分项数据、行业分析
  - 与 PMI 数值数据融合，形成完整的 PMI 分析报告

数据源：
  - 国家统计局官网「数据解读」栏目
  - URL 模式：https://www.stats.gov.cn/sj/sjjd/YYYYMM/tYYYYMMDD_xxxxxx.html

缓存机制：
  - 本地 CSV 缓存：market_monitor/data/pmi_interpretation.csv
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
_PMI_CACHE_FILE = os.path.join(
    os.path.dirname(__file__), "..", "data", "pmi_interpretation.csv"
)

# CSV 字段定义
_PMI_CSV_FIELDS = [
    "period",           # 数据期，如 "2026-02"
    "publish_date",     # 发布日期，如 "2026-03-04"
    "pmi_mfg",          # 制造业 PMI
    "pmi_svc",          # 非制造业 PMI
    "pmi_composite",    # 综合 PMI
    "title",            # 文章标题
    "author",           # 解读人
    "summary",          # 核心结论摘要
    "key_points",       # 关键要点（JSON 列表）
    "sector_analysis",  # 行业分析（JSON 字典）
    "source_url",       # 原文链接
    "cached_at",        # 缓存时间
]


def _get_cache_path() -> str:
    """获取缓存文件绝对路径。"""
    return os.path.abspath(_PMI_CACHE_FILE)


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
                                result["sector_analysis"] = json.loads(row.get("sector_analysis", "{}"))
                                result["pmi_mfg"] = float(row["pmi_mfg"]) if row.get("pmi_mfg") else None
                                result["pmi_svc"] = float(row["pmi_svc"]) if row.get("pmi_svc") else None
                                result["pmi_composite"] = float(row["pmi_composite"]) if row.get("pmi_composite") else None
                                result["_source"] = "csv_cache"
                                return result
                        except (ValueError, TypeError):
                            pass
                    return None
    except Exception as e:
        print(f"[PMI解读] 读取缓存失败: {e}")
    
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
        "pmi_mfg": str(data.get("pmi_mfg", "")) if data.get("pmi_mfg") is not None else "",
        "pmi_svc": str(data.get("pmi_svc", "")) if data.get("pmi_svc") is not None else "",
        "pmi_composite": str(data.get("pmi_composite", "")) if data.get("pmi_composite") is not None else "",
        "title": data.get("title", ""),
        "author": data.get("author", ""),
        "summary": data.get("summary", ""),
        "key_points": json.dumps(data.get("key_points", []), ensure_ascii=False),
        "sector_analysis": json.dumps(data.get("sector_analysis", {}), ensure_ascii=False),
        "source_url": data.get("source_url", ""),
        "cached_at": datetime.now().isoformat(),
    }
    existing_rows.append(new_row)
    
    # 写入文件
    try:
        with open(cache_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=_PMI_CSV_FIELDS)
            writer.writeheader()
            writer.writerows(existing_rows)
        print(f"[PMI解读] 缓存已更新: {cache_path}")
    except Exception as e:
        print(f"[PMI解读] 写入缓存失败: {e}")


def _fetch_article_via_browser(url: str) -> Optional[str]:
    """
    使用 Browser Automation 抓取文章内容。
    
    Returns:
        文章正文文本
    """
    try:
        # 调用 agent-browser 命令
        # 先打开页面
        result = subprocess.run(
            ["agent-browser", "open", url],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            print(f"[PMI解读] 打开页面失败: {result.stderr}")
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
            print(f"[PMI解读] 获取内容失败: {result.stderr}")
            return None
            
    except subprocess.TimeoutExpired:
        print("[PMI解读] 浏览器操作超时")
        return None
    except Exception as e:
        print(f"[PMI解读] 浏览器抓取失败: {e}")
        return None


def _parse_interpretation(text: str, year: int, month: int, use_llm: bool = False) -> Dict:
    """
    解析 PMI 解读文章内容，提取结构化数据（混合方案）。
    
    策略：
    1. 先用规则提取基础数据（稳定、快速）
    2. 如果规则提取要点不足，且启用 LLM，则补充提取
    
    Args:
        text: 文章正文
        year: 年份
        month: 月份
        use_llm: 是否使用 LLM 增强提取（默认 False，避免延迟和成本）
    """
    result = {
        "period": f"{year}-{month:02d}",
        "publish_date": "",
        "pmi_mfg": None,
        "pmi_svc": None,
        "pmi_composite": None,
        "title": "",
        "author": "",
        "summary": "",
        "key_points": [],
        "sector_analysis": {},
        "source_url": "",
        "_parse_method": "rule_based",  # 标记解析方式
    }
    
    if not text:
        return result
    
    # ========== 第一步：规则提取基础数据（稳定、快速）==========
    
    # 提取作者（格式固定：首席统计师 XXX 解读）
    author_match = re.search(r"首席统计师\s*(\S+?)\s*解读", text)
    if author_match:
        result["author"] = author_match.group(1)
        result["title"] = f"国家统计局服务业调查中心首席统计师{author_match.group(1)}解读"
    
    # 提取 PMI 数值（格式相对固定）
    pmi_patterns = [
        (r"制造业采购经理指数.*?([\d\.]+)%", "pmi_mfg"),
        (r"非制造业商务活动指数.*?([\d\.]+)%", "pmi_svc"),
        (r"综合PMI产出指数.*?([\d\.]+)%", "pmi_composite"),
    ]
    for pattern, key in pmi_patterns:
        match = re.search(pattern, text)
        if match:
            try:
                result[key] = float(match.group(1))
            except ValueError:
                pass
    
    # 提取发布日期
    date_match = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", text)
    if date_match:
        result["publish_date"] = f"{date_match.group(1)}-{int(date_match.group(2)):02d}-{int(date_match.group(3)):02d}"
    
    # 提取摘要（第一段包含 PMI 的描述）
    result["summary"] = _extract_summary_generic(text, year, month)
    
    # 提取关键要点（通用规则版）
    result["key_points"] = _extract_key_points_generic(text)
    
    # 提取行业分析（通用规则版）
    result["sector_analysis"] = _extract_sector_analysis_generic(text)
    
    # ========== 第二步：LLM 增强（可选，默认不启用）==========
    if use_llm and len(result["key_points"]) < 2:
        try:
            llm_result = _extract_with_llm(text, result)
            if llm_result.get("key_points"):
                result["key_points"] = llm_result["key_points"]
                result["_llm_enhanced"] = True
                result["_parse_method"] = "hybrid"
        except Exception as e:
            print(f"[PMI解读] LLM 增强失败: {e}")
    
    return result


def _extract_summary_generic(text: str, year: int, month: int) -> str:
    """
    通用摘要提取 - 基于段落结构而非硬编码关键词
    """
    # 清理文本
    clean_text = re.sub(r'\s+', '', text)
    
    # 找包含月份和 PMI 的第一段长文本
    month_cn = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "十一", "十二"]
    month_str = month_cn[month - 1] if month <= 12 else str(month)
    
    # 匹配 "X月份，..." 开头的段落
    pattern = rf"({month_str}|[\d]+)月[份]*，[^。]{{20,150}}。"
    match = re.search(pattern, clean_text)
    if match:
        summary = match.group(0)
        # 如果包含 PMI 数值，就采用
        if "指数" in summary:
            return summary
    
    # 备选：找包含 PMI 的最长句子
    sentences = clean_text.split("。")
    for sent in sorted(sentences, key=len, reverse=True):
        if "采购经理指数" in sent or "商务活动指数" in sent:
            if 50 < len(sent) < 200:
                return sent + "。"
    
    return ""


def _extract_key_points_generic(text: str) -> List[str]:
    """
    通用关键要点提取 - 基于段落特征识别
    """
    key_points = []
    clean_text = re.sub(r'\s+', '', text)
    
    # 策略1：找包含数字和"指数"的短句（通常是具体指标）
    indicator_pattern = r"([^。]{10,60}指数[^。]{5,40})"
    matches = re.findall(indicator_pattern, clean_text)
    for match in matches[:4]:  # 最多取4条
        point = match.strip()
        # 过滤掉太泛的
        if any(kw in point for kw in ["生产", "订单", "价格", "预期", "景气", "扩张", "收缩"]):
            if point not in key_points:
                key_points.append(point)
    
    # 策略2：找"从行业看"、"分规模看"等分维度描述
    dimension_patterns = [
        r"从行业看，([^。]{10,80})",
        r"分规模看，([^。]{10,80})",
        r"从分类指数看，([^。]{10,80})",
    ]
    for pattern in dimension_patterns:
        match = re.search(pattern, clean_text)
        if match:
            point = match.group(1).strip()
            if point and point not in key_points:
                key_points.append(point)
                break  # 只取一个维度的
    
    # 策略3：找包含"比上月"的环比变化描述
    mom_matches = re.findall(r"([^。]{8,50}比上月[上升下降][^。]{3,30})", clean_text)
    for match in mom_matches[:2]:
        point = match.strip()
        if point and point not in key_points:
            key_points.append(point)
            break  # 只取一条环比
    
    return key_points[:5]  # 最多5条


def _extract_sector_analysis_generic(text: str) -> Dict[str, str]:
    """
    通用行业分析提取 - 基于行业关键词定位
    """
    sectors = {}
    clean_text = re.sub(r'\s+', '', text)
    
    # 定义行业关键词映射
    sector_keywords = {
        "制造业": ["制造业", "装备制造", "高技术制造", "消费品", "原材料"],
        "服务业": ["服务业", "交通运输", "住宿", "餐饮", "信息技术", "金融", "房地产"],
        "建筑业": ["建筑业", "房屋建筑", "土木工程", "建筑安装"],
    }
    
    for sector_name, keywords in sector_keywords.items():
        # 找包含该行业关键词的句子
        for keyword in keywords:
            # 匹配包含该关键词的句子
            pattern = rf"([^。]{{0,30}}{keyword}[^。]{{10,80}})"
            match = re.search(pattern, clean_text)
            if match:
                desc = match.group(1).strip()
                # 验证是否包含实质性描述（有指数、景气、增长等词）
                if any(indicator in desc for indicator in ["指数", "景气", "增长", "回落", "扩张", "收缩", "位于"]):
                    sectors[sector_name] = desc[:100] + "..." if len(desc) > 100 else desc
                    break  # 该行业已找到，跳出关键词循环
    
    return sectors


def _extract_with_llm(text: str, existing_result: Dict, provider: str = "qwen") -> Dict:
    """
    使用 LLM 提取关键信息（当规则提取不足时作为补充）。
    
    默认使用阿里云百炼通义千问模型，支持 qwen-turbo（快速便宜）或 qwen-plus（更强）。
    
    Args:
        text: PMI 解读文章全文
        existing_result: 规则提取的已有结果
        provider: LLM 提供商，默认 qwen
    
    Returns:
        包含 key_points 和 sector_analysis 的字典
    """
    try:
        # 延迟导入，避免循环依赖
        from market_monitor.utils.llm_client import LLMClient
        
        client = LLMClient(
            provider=provider,
            temperature=0.3,  # 低温度，更确定性的输出
            max_tokens=1500,
        )
        
        # 构建提取提示词
        prompt = _build_extraction_prompt(text, existing_result)
        
        print(f"[PMI解读] 调用 {provider} LLM 提取关键信息...")
        
        # 调用 LLM 提取 JSON
        result = client.extract_json(prompt)
        
        # 验证结果格式
        if "key_points" not in result:
            result["key_points"] = []
        if "sector_analysis" not in result:
            result["sector_analysis"] = {}
        
        # 限制数量
        result["key_points"] = result["key_points"][:5]
        
        print(f"[PMI解读] LLM 提取完成，获得 {len(result['key_points'])} 条要点")
        
        return result
        
    except Exception as e:
        print(f"[PMI解读] LLM 提取失败: {e}")
        # 返回空结果，让上层使用规则提取的结果
        return {"key_points": [], "sector_analysis": {}}


def _build_extraction_prompt(text: str, existing_result: Dict) -> str:
    """
    构建 LLM 提取提示词。
    """
    period = existing_result.get("period", "")
    pmi_mfg = existing_result.get("pmi_mfg")
    pmi_svc = existing_result.get("pmi_svc")
    
    # 截断文本避免过长
    truncated_text = text[:2500] if len(text) > 2500 else text
    
    prompt = f"""请从以下国家统计局 PMI 官方解读文章中提取结构化信息。

【文章信息】
- 数据期：{period}
- 制造业 PMI：{pmi_mfg if pmi_mfg is not None else "未提供"}
- 非制造业 PMI：{pmi_svc if pmi_svc is not None else "未提供"}

【文章内容】
{truncated_text}

【提取要求】
请提取以下信息，以 JSON 格式返回：

{{
    "key_points": [
        "要点1：描述核心结论，20-40字",
        "要点2：描述具体指标变化，20-40字",
        "要点3：描述行业分化情况，20-40字"
    ],
    "sector_analysis": {{
        "制造业": "制造业整体情况简述，30-50字",
        "服务业": "服务业情况简述，30-50字",
        "建筑业": "建筑业情况简述，30-50字（如有）"
    }}
}}

【注意事项】
1. key_points 提取 3-5 条核心要点，每条简洁明了
2. 优先提取包含具体数字和变化的要点
3. 如果某个行业没有相关内容，sector_analysis 中可省略该字段
4. 只返回 JSON，不要包含其他解释文字"""

    return prompt


def fetch_pmi_interpretation_by_url(article_url: str, year: int, month: int) -> Dict:
    """
    通过指定 URL 获取 PMI 官方解读（用于 Agent 搜索后传入 URL）。
    
    Args:
        article_url: 文章 URL（由 Agent 通过 web_search 获取）
        year: 年份
        month: 月份
    
    Returns:
        包含解读数据的字典
    """
    period = f"{year}-{month:02d}"
    
    # 1. 检查缓存
    cached = _read_cache(period)
    if cached:
        print(f"[PMI解读] 命中缓存: {period}")
        return cached
    
    # 2. 使用浏览器抓取
    print(f"[PMI解读] 正在抓取: {article_url}")
    text = _fetch_article_via_browser(article_url)
    
    if not text:
        return {"error": "抓取文章失败"}
    
    # 3. 解析内容
    result = _parse_interpretation(text, year, month)
    result["source_url"] = article_url
    result["_source"] = "browser_fetch"
    
    # 4. 写入缓存
    _write_cache(result)
    
    return result


# 预置已知 URL（作为后备）
_PRESET_URLS = {
    (2026, 2): "https://www.stats.gov.cn/sj/sjjd/202603/t20260304_1962700.html",
    (2026, 1): "https://www.stats.gov.cn/sj/zxfbhjd/202601/t20260131_1962415.html",
}


def _search_pmi_url_via_web_search(year: int, month: int) -> Optional[str]:
    """
    使用 Web Search 查找 PMI 解读文章 URL。
    
    搜索策略:
    1. 优先搜索 site:stats.gov.cn 的精确匹配
    2. 筛选包含 "sjjd" (数据解读) 路径的链接
    3. 验证标题包含 PMI 相关关键词
    
    Args:
        year: 数据年份
        month: 数据月份
    
    Returns:
        文章 URL 或 None
    """
    try:
        # 延迟导入，避免循环依赖
        from market_monitor.utils.web_search import search_web
        
        # 构建搜索查询（简化查询词，提高成功率）
        search_queries = [
            f"{year}年{month}月 采购经理指数 解读 site:stats.gov.cn",
            f"{year}年{month}月 PMI 解读 site:stats.gov.cn",
        ]
        
        for query in search_queries:
            print(f"[PMI解读] 搜索: {query}")
            
            try:
                search_results = search_web(query, limit=5, engine="duckduckgo")
                
                if isinstance(search_results, list) and len(search_results) > 0:
                    print(f"[PMI解读] 搜索返回 {len(search_results)} 条结果")
                    for item in search_results:
                        url = item.get("url", "") if isinstance(item, dict) else str(item)
                        title = item.get("title", "") if isinstance(item, dict) else ""
                        print(f"[PMI解读] 检查: {title[:40]}... -> {url[:50]}...")
                        # 验证 URL 格式
                        if _is_valid_pmi_url(url, year, month):
                            print(f"[PMI解读] ✓ 找到有效 URL: {url}")
                            return url
                        else:
                            print(f"[PMI解读]   URL 验证失败")
                        
            except Exception as e:
                print(f"[PMI解读] 搜索失败: {e}")
                continue
        
        print(f"[PMI解读] Web Search 未找到有效 URL")
        return None
        
    except ImportError as e:
        print(f"[PMI解读] Web Search 模块导入失败: {e}")
        return None
    except Exception as e:
        print(f"[PMI解读] Web Search 异常: {e}")
        return None


def _is_valid_pmi_url(url: str, year: int, month: int) -> bool:
    """
    验证 URL 是否为有效的 PMI 解读文章链接。
    """
    if not url or "stats.gov.cn" not in url:
        return False
    
    # 排除数据查询平台
    if "data.stats.gov.cn" in url:
        return False
    
    # 必须是数据解读栏目或新闻发布
    if "/sjjd/" not in url and "/zxfbhjd/" not in url and "/sj/" not in url:
        return False
    
    # 发布年月应该在数据月之后（PMI 是次月发布）
    # 例如：2月数据在3月发布，URL 包含 202603
    pub_year = year
    pub_month = month + 1
    if pub_month > 12:
        pub_year += 1
        pub_month = 1
    
    pub_year_month = f"{pub_year}{pub_month:02d}"
    
    # 检查 URL 是否包含发布年月或数据年月
    url_indicators = [
        pub_year_month,  # 202601
        f"{year}{month:02d}",  # 202512 (数据月)
        f"t{pub_year}{pub_month:02d}",  # t202601
    ]
    
    has_date = any(ind in url for ind in url_indicators)
    if not has_date:
        # 放宽：只要年份对即可
        if str(pub_year) not in url and str(year) not in url:
            return False
    
    return True


def _guess_pmi_urls(year: int, month: int) -> List[str]:
    """
    基于发布规律生成可能的 URL 列表（日期探测）。
    
    PMI 发布时间规律:
    - 通常在次月 1-3 日发布上月数据
    - URL 格式: .../YYYYMM/tYYYYMMDD_xxxxxx.html
    """
    urls = []
    
    # 发布年月（数据月的下个月）
    pub_year = year
    pub_month = month + 1
    if pub_month > 12:
        pub_year += 1
        pub_month = 1
    
    pub_year_month = f"{pub_year}{pub_month:02d}"
    
    # 生成可能的日期（1-5日）
    for day in range(1, 6):
        date_str = f"{pub_year}{pub_month:02d}{day:02d}"
        base_path = f"https://www.stats.gov.cn/sj/sjjd/{pub_year_month}/t{date_str}_"
        
        # 根据历史 ID 范围生成可能的 URL
        # 注意：这是估算，实际 ID 可能变化
        base_id = 1962700  # 2026年2月的ID
        for offset in range(-100, 200, 10):
            article_id = base_id + offset
            url = f"{base_path}{article_id}.html"
            urls.append(url)
    
    return urls[:20]  # 限制数量


def _probe_pmi_url(year: int, month: int) -> Optional[str]:
    """
    探测有效的 PMI 解读 URL（HEAD 请求验证）。
    """
    import urllib.request
    
    urls = _guess_pmi_urls(year, month)
    
    for url in urls[:10]:  # 只尝试前10个
        try:
            # 发送 HEAD 请求检查是否存在
            req = urllib.request.Request(url, method='HEAD')
            req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.0')
            
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    # 进一步验证内容（可选）
                    print(f"[PMI解读] 探测到有效 URL: {url}")
                    return url
        except Exception:
            continue
    
    return None


def _auto_get_pmi_url(year: int, month: int) -> Optional[str]:
    """
    自动获取 PMI 解读 URL（混合方案 D）。
    
    优先级:
    1. 检查预置列表（已知的直接返回）
    2. Web Search 搜索（自动化获取）
    3. 日期探测（暴力尝试）
    4. 返回 None，提示手动传入
    
    Args:
        year: 数据年份
        month: 数据月份
    
    Returns:
        文章 URL 或 None
    """
    period = (year, month)
    
    # 1. 检查预置列表
    if period in _PRESET_URLS:
        print(f"[PMI解读] 使用预置 URL: {_PRESET_URLS[period]}")
        return _PRESET_URLS[period]
    
    print(f"[PMI解读] 未预置 {year}年{month}月 的 URL，尝试自动获取...")
    
    # 2. 尝试 Web Search
    url = _search_pmi_url_via_web_search(year, month)
    if url:
        # 添加到预置列表（缓存）
        _PRESET_URLS[period] = url
        print(f"[PMI解读] Web Search 成功，已缓存 URL")
        return url
    
    print(f"[PMI解读] Web Search 未找到，尝试日期探测...")
    
    # 3. 尝试日期探测
    url = _probe_pmi_url(year, month)
    if url:
        _PRESET_URLS[period] = url
        print(f"[PMI解读] 日期探测成功，已缓存 URL")
        return url
    
    # 4. 全部失败
    print(f"[PMI解读] 自动获取失败，需要手动传入 URL")
    return None


def fetch_pmi_interpretation(
    year: int, 
    month: int, 
    use_cache: bool = True,
    auto_search: bool = True
) -> Dict:
    """
    获取 PMI 官方解读（带缓存，支持自动 URL 获取）。
    
    Args:
        year: 年份
        month: 月份
        use_cache: 是否使用缓存
        auto_search: 是否自动搜索 URL（混合方案 D）
    
    Returns:
        包含解读数据的字典
    """
    period = f"{year}-{month:02d}"
    
    # 1. 检查缓存
    if use_cache:
        cached = _read_cache(period)
        if cached:
            print(f"[PMI解读] 命中缓存: {period}")
            return cached
    
    # 2. 获取文章 URL
    article_url = None
    
    if auto_search:
        # 使用混合方案自动获取
        article_url = _auto_get_pmi_url(year, month)
    else:
        # 仅使用预置列表
        article_url = _PRESET_URLS.get((year, month))
    
    if not article_url:
        return {
            "error": f"未找到 {period} 的解读文章 URL",
            "hint": f"使用 fetch_pmi_interpretation_by_url(url, {year}, {month}) 手动传入 URL",
            "suggestion": "或设置 auto_search=True 启用自动搜索"
        }
    
    # 3. 使用浏览器抓取
    print(f"[PMI解读] 正在抓取: {article_url}")
    text = _fetch_article_via_browser(article_url)
    
    if not text:
        return {"error": "抓取文章失败", "url": article_url}
    
    # 4. 解析内容
    result = _parse_interpretation(text, year, month)
    result["source_url"] = article_url
    result["_source"] = "browser_fetch"
    result["_url_method"] = "auto_search" if auto_search else "preset"
    
    # 5. 写入缓存
    _write_cache(result)
    
    return result


def fetch_pmi_with_interpretation(year: Optional[int] = None, month: Optional[int] = None) -> Dict:
    """
    获取完整的 PMI 数据（数值 + 官方解读）。
    
    这是主要对外接口，融合代码接口的 PMI 数值和 Agent 抓取的官方解读。
    
    Args:
        year: 年份，默认为上个月
        month: 月份，默认为上个月
    
    Returns:
        融合后的 PMI 数据字典
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
    
    # 1. 获取 PMI 数值（从 fundamental 模块）
    from .fundamental import fetch_macro_supply_demand
    
    supply_demand = fetch_macro_supply_demand()
    
    if "error" in supply_demand:
        return {"error": f"获取 PMI 数值失败: {supply_demand['error']}"}
    
    # 2. 获取官方解读
    interpretation = fetch_pmi_interpretation(year, month)
    
    # 3. 融合数据
    result = {
        "period": period,
        "pmi_mfg": supply_demand.get("pmi_mfg"),
        "pmi_svc": supply_demand.get("pmi_svc"),
        "pmi_composite": interpretation.get("pmi_composite"),
        "cpi_yoy": supply_demand.get("cpi_yoy"),
        "ppi_yoy": supply_demand.get("ppi_yoy"),
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
    print("测试 PMI 解读抓取")
    print("=" * 60)
    
    # 测试获取 2026年2月数据
    result = fetch_pmi_with_interpretation(2026, 2)
    
    print("\n完整 PMI 数据（数值+解读）：")
    print(json.dumps(result, ensure_ascii=False, indent=2))
