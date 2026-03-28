"""
资金面消息搜索模块（市场监控专用）。

使用妙想资讯搜索 API 获取：
1. 印花税、券商佣金率等政策消息
2. 港股互联网巨头回购、减持、融资事件
3. 百亿/千亿级 IPO 监控

判断对市场的利好/利空影响。

限额控制策略：
- 每次运行最多 4 个查询（减少 API 调用）
- 本地缓存 6 小时（避免重复调用）
- 每次查询取 top 2 条（减少数据量）
"""

import os
import time
import hashlib
import json
from typing import Optional

# 搜索关键词配置
# 印花税/佣金率政策
POLICY_QUERIES = [
    "印花税 降低 减免 减半",
    "券商佣金率 下调 优惠",
]

# 港股互联网巨头回购减持
HK_REPO_QUERIES = [
    "港股 腾讯 阿里 美团 回购 注销",
    "港股 腾讯 阿里 美团 减持 大股东",
]

# IPO/再融资监控
IPO_QUERIES = [
    "A股 IPO 上市 融资 百亿 千亿",
    "长鑫科技 长江存储 荣耀 上市 IPO",
]

# 缓存配置
CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "cache")
CACHE_TTL = 6 * 3600  # 6 小时缓存


def _get_cache_path(query: str) -> str:
    """获取查询的缓存文件路径"""
    query_hash = hashlib.md5(query.encode()).hexdigest()[:8]
    return os.path.join(CACHE_DIR, f"mx_search_{query_hash}.json")


def _load_cache(query: str) -> Optional[list]:
    """加载缓存结果，过期返回 None"""
    cache_path = _get_cache_path(query)
    if not os.path.exists(cache_path):
        return None
    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            cached = json.load(f)
        if time.time() - cached.get('timestamp', 0) < CACHE_TTL:
            return cached.get('data', [])
    except Exception:
        pass
    return None


def _save_cache(query: str, data: list) -> None:
    """保存结果到缓存"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_path = _get_cache_path(query)
    try:
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump({'timestamp': time.time(), 'data': data}, f, ensure_ascii=False)
    except Exception:
        pass


def _get_apikey() -> Optional[str]:
    """获取 API Key（优先级：环境变量 > 配置文件 > config.py 默认值）"""
    # 1. 环境变量
    key = os.environ.get("MX_APIKEY", "").strip()
    if key:
        return key
    
    # 2. 本地配置文件
    config_paths = [
        os.path.expanduser("~/.dfcfs/apikey"),
        os.path.expanduser("~/.config/dfcfs/apikey"),
    ]
    for p in config_paths:
        if os.path.exists(p):
            with open(p) as f:
                key = f.read().strip()
                if key:
                    return key
    
    # 3. 项目 config.py 中的默认值
    try:
        from ..config import MX_APIKEY as CONFIG_APIKEY
        if CONFIG_APIKEY:
            return CONFIG_APIKEY
    except Exception:
        pass
    
    return None


def _run_search(query: str, use_cache: bool = True) -> list:
    """
    执行单个搜索查询，优先使用缓存
    
    Args:
        query: 搜索关键词
        use_cache: 是否使用缓存（默认True）
    
    Returns:
        搜索结果列表，每项包含 title, trunk, secuList 等字段
    """
    # 先检查缓存
    if use_cache:
        cached = _load_cache(query)
        if cached is not None:
            return cached
    
    apikey = _get_apikey()
    if not apikey:
        return []

    # 直接调用妙想 API
    import urllib.request
    import ssl
    
    url = "https://mkapi2.dfcfs.com/finskillshub/api/claw/news-search"
    headers = {
        "Content-Type": "application/json",
        "apikey": apikey,
    }
    data = json.dumps({"query": query}).encode("utf-8")
    
    # 创建 SSL 上下文
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    try:
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        
        # 解析结果，限制 top 2
        # 数据结构: result['data']['data']['llmSearchResponse']['data']
        items = []
        if isinstance(result, dict):
            try:
                inner_data = result.get("data", {})
                if isinstance(inner_data, dict):
                    inner_data2 = inner_data.get("data", {})
                    if isinstance(inner_data2, dict):
                        llm_response = inner_data2.get("llmSearchResponse", {})
                        if isinstance(llm_response, dict):
                            items = llm_response.get("data", [])[:2]
            except Exception:
                items = []
        
        # 保存到缓存
        _save_cache(query, items)
        return items
    except Exception as e:
        print(f"[妙想API错误] {e}")
        return []


def _analyze_policy_sentiment(title: str, trunk: str) -> tuple:
    """
    分析印花税/佣金率政策消息的情绪
    Returns: (sentiment_label, score)
    """
    text = (title + " " + str(trunk)).lower()
    
    is_bullish = any(kw in text for kw in [
        "降低", "下调", "减免", "优惠", "减半", "取消", "利好"
    ])
    is_bearish = any(kw in text for kw in [
        "提高", "上调", "增加", "恢复", "利空"
    ])
    
    if is_bullish:
        return "利好", 1
    elif is_bearish:
        return "利空", -1
    return "中性", 0


def _extract_company_name(title: str, trunk: str) -> str:
    """从标题和内容中提取公司名称"""
    text = title + " " + str(trunk)
    
    # 港股科技巨头关键词
    companies = {
        "腾讯": ["腾讯", "Tencent", "00700"],
        "阿里巴巴": ["阿里巴巴", "阿里", "Alibaba", "BABA", "09988"],
        "美团": ["美团", "Meituan", "03690"],
        "京东": ["京东", "JD.com", "JD", "09618"],
        "小米": ["小米", "Xiaomi", "01810"],
        "百度": ["百度", "Baidu", "BIDU", "09888"],
        "网易": ["网易", "NetEase", "NTES", "09999"],
        "快手": ["快手", "Kuaishou", "01024"],
        "比亚迪": ["比亚迪", "BYD", "01211", "002594"],
    }
    
    for company, keywords in companies.items():
        for kw in keywords:
            if kw in text:
                return company
    return "其他"


def _extract_date(title: str, trunk: str) -> str:
    """从标题和内容中提取日期"""
    import re
    text = title + " " + str(trunk)
    
    # 匹配常见日期格式
    patterns = [
        r'(\d{4})[年/-](\d{1,2})[月/-](\d{1,2})[日]?',  # 2024年3月15日 / 2024-03-15
        r'(\d{4})[年/-](\d{1,2})[月/-]?',  # 2024年3月 / 2024-03
        r'(\d{1,2})[月](\d{1,2})[日]',  # 3月15日
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            groups = match.groups()
            if len(groups) == 3:
                return f"{groups[0]}-{groups[1].zfill(2)}-{groups[2].zfill(2)}"
            elif len(groups) == 2 and len(groups[0]) == 4:
                return f"{groups[0]}-{groups[1].zfill(2)}"
            elif len(groups) == 2:
                return f"{groups[0].zfill(2)}-{groups[1].zfill(2)}"
    return ""


def _analyze_repo_sentiment(title: str, trunk: str) -> tuple:
    """
    分析回购/减持消息的情绪
    Returns: (sentiment_label, score, category, company, date)
    """
    text = (title + " " + str(trunk)).lower()
    
    company = _extract_company_name(title, trunk)
    date = _extract_date(title, trunk)
    
    # 回购注销 - 利好
    if any(kw in text for kw in ["回购", "注销"]):
        if "注销" in text:
            return "利好", 1, "回购注销", company, date
        return "利好", 0.5, "回购", company, date
    
    # 减持 - 利空
    if any(kw in text for kw in ["减持", "抛售", "套现"]):
        return "利空", -1, "减持", company, date
    
    # 融资 - 偏利空（抽血）
    if any(kw in text for kw in ["融资", "配股", "定增"]):
        return "偏空", -0.5, "融资", company, date
    
    return "中性", 0, "其他", company, date


def _extract_ipo_company(title: str, trunk: str) -> str:
    """从IPO标题中提取公司名称"""
    import re
    text = title + " " + str(trunk)
    
    # 重点关注的大型IPO公司
    big_companies = ["长鑫科技", "长江存储", "荣耀", "先正达", "华虹", "中芯国际", 
                     "蚂蚁集团", "字节跳动", "滴滴", "Shein", "菜鸟网络"]
    for name in big_companies:
        if name in text:
            return name
    
    # 通用提取：尝试提取公司名（通常在标题开头）
    # 匹配 "XX公司"、"XX科技"、"XX集团" 等
    patterns = [
        r'^([^：:|丨\s]{2,8})(?:科技|集团|股份|公司|生物|医药|电子|智能)',
        r'([^：:|丨\s]{2,8})(?:科技|集团|股份|公司|生物|医药|电子|智能)(?:\s|的|拟|将|申请|IPO|上市)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    
    return "其他"


def _analyze_ipo_sentiment(title: str, trunk: str) -> tuple:
    """
    分析IPO消息的情绪和规模
    Returns: (sentiment_label, score, scale, company, date)
    """
    text = (title + " " + str(trunk)).lower()
    
    # 识别规模
    scale = None
    if any(kw in text for kw in ["千亿", "1000亿", "数千亿"]):
        scale = "千亿级"
    elif any(kw in text for kw in ["百亿", "100亿", "数百亿"]):
        scale = "百亿级"
    elif any(kw in text for kw in ["ipo", "上市", "发行"]):
        scale = "常规"
    
    # 识别公司
    company = _extract_ipo_company(title, trunk)
    
    # 提取日期
    date = _extract_date(title, trunk)
    
    # 判断情绪
    if any(kw in text for kw in ["终止", "撤回", "暂停", "暂缓"]):
        return "利好", 0.5, scale, company, date  # IPO放缓是利好
    elif any(kw in text for kw in ["启动", "招股", "发行", "上市", "过会", "获批"]):
        if scale in ["千亿级", "百亿级"]:
            return "警示", -1.5, scale, company, date  # 巨量IPO是警示信号
        return "偏空", -0.5, scale, company, date
    
    return "中性", 0, scale, company, date


def fetch_policy() -> dict:
    """
    搜索近期印花税、券商佣金率相关消息
    
    Returns:
        {
            "score": float,      # -2(利空) ~ +2(利好)
            "label": str,       # "利好" / "利空" / "中性" / "N/A"
            "detail": str,      # 详细说明
            "news": [            # 相关资讯列表
                {"title": str, "sentiment": str}
            ],
            "available": bool,   # 是否可用
            "source": str,      # "api" / "cache" / "N/A"
        }
    """
    apikey = _get_apikey()
    if not apikey:
        return {
            "score": 0.0,
            "label": "N/A",
            "detail": "未配置 MX_APIKEY",
            "news": [],
            "available": False,
            "source": "N/A",
        }

    all_news = []
    sentiment_scores = []
    api_calls = 0
    cache_hits = 0

    for query in POLICY_QUERIES:
        cached = _load_cache(query)
        if cached is not None:
            items = cached
            cache_hits += 1
        else:
            items = _run_search(query, use_cache=False)
            api_calls += 1
        
        for item in items:
            title = item.get("title", "")
            trunk = item.get("trunk", "")
            sentiment, score = _analyze_policy_sentiment(title, trunk)
            
            if score != 0:
                sentiment_scores.append(score)
            all_news.append({"title": title, "sentiment": sentiment})

    # 构建来源说明
    if api_calls > 0 and cache_hits > 0:
        source_detail = f"API{api_calls}次+缓存{cache_hits}个"
    elif api_calls > 0:
        source_detail = f"API{api_calls}次"
    elif cache_hits > 0:
        source_detail = f"缓存{cache_hits}个"
    else:
        source_detail = "N/A"

    if not all_news:
        return {
            "score": 0.0,
            "label": "中性",
            "detail": "近期无政策调整",
            "news": [],
            "available": True,
            "source": source_detail,
        }

    avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0

    if avg_sentiment > 0.3:
        score = min(2.0, avg_sentiment * 2)
        label = "利好"
    elif avg_sentiment < -0.3:
        score = max(-2.0, avg_sentiment * 2)
        label = "利空"
    else:
        score = 0.0
        label = "中性"

    news_summary = {}
    for n in all_news:
        s = n["sentiment"]
        news_summary[s] = news_summary.get(s, 0) + 1
    detail = " / ".join(f"{k}{v}条" for k, v in news_summary.items())

    return {
        "score": round(score, 1),
        "label": label,
        "detail": detail,
        "news": all_news[:4],
        "available": True,
        "source": source_detail,
    }


def fetch_hk_repo() -> dict:
    """
    搜索港股互联网巨头回购、减持、融资事件
    
    Returns:
        {
            "score": float,      # -2(利空) ~ +2(利好)
            "label": str,       # "利好" / "利空" / "中性" / "警示"
            "detail": str,      # 详细说明
            "news": [            # 相关资讯列表
                {"title": str, "sentiment": str, "category": str}
            ],
            "available": bool,
            "source": str,
            "summary": {         # 分类统计
                "回购": int,
                "回购注销": int,
                "减持": int,
                "融资": int,
            }
        }
    """
    apikey = _get_apikey()
    if not apikey:
        return {
            "score": 0.0,
            "label": "N/A",
            "detail": "未配置 MX_APIKEY",
            "news": [],
            "available": False,
            "source": "N/A",
            "summary": {},
        }

    all_news = []
    sentiment_scores = []
    api_calls = 0
    cache_hits = 0
    summary = {"回购": 0, "回购注销": 0, "减持": 0, "融资": 0, "其他": 0}

    for query in HK_REPO_QUERIES:
        cached = _load_cache(query)
        if cached is not None:
            items = cached
            cache_hits += 1
        else:
            items = _run_search(query, use_cache=False)
            api_calls += 1
        
        for item in items:
            title = item.get("title", "")
            trunk = item.get("trunk", "")
            sentiment, score, category, company, date = _analyze_repo_sentiment(title, trunk)
            
            summary[category] = summary.get(category, 0) + 1
            if score != 0:
                sentiment_scores.append(score)
            all_news.append({
                "title": title,
                "sentiment": sentiment,
                "category": category,
                "company": company,
                "date": date,
            })

    # 构建来源说明
    if api_calls > 0 and cache_hits > 0:
        source_detail = f"API{api_calls}次+缓存{cache_hits}个"
    elif api_calls > 0:
        source_detail = f"API{api_calls}次"
    elif cache_hits > 0:
        source_detail = f"缓存{cache_hits}个"
    else:
        source_detail = "N/A"

    if not all_news:
        return {
            "score": 0.0,
            "label": "中性",
            "detail": "近期无相关事件",
            "news": [],
            "available": True,
            "source": source_detail,
            "summary": summary,
        }

    avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0

    # 构建详细说明
    parts = []
    if summary.get("回购注销", 0) > 0:
        parts.append(f"🟢回购注销{summary['回购注销']}条")
    if summary.get("回购", 0) > 0:
        parts.append(f"🟡回购{summary['回购']}条")
    if summary.get("减持", 0) > 0:
        parts.append(f"🔴减持{summary['减持']}条")
    if summary.get("融资", 0) > 0:
        parts.append(f"🟠融资{summary['融资']}条")
    detail = " | ".join(parts) if parts else "近期无显著事件"

    if avg_sentiment > 0.5:
        label = "利好"
    elif avg_sentiment < -0.5:
        label = "利空"
    elif summary.get("减持", 0) > 0 or summary.get("融资", 0) > 0:
        label = "偏空"
    else:
        label = "中性"

    return {
        "score": round(avg_sentiment, 1),
        "label": label,
        "detail": detail,
        "news": all_news[:4],
        "available": True,
        "source": source_detail,
        "summary": summary,
    }


def fetch_ipo() -> dict:
    """
    搜索百亿/千亿级 IPO 及再融资事件
    
    Returns:
        {
            "score": float,      # -2(利空) ~ +2(利好)
            "label": str,       # "利好" / "警示" / "偏空" / "中性"
            "detail": str,      # 详细说明
            "news": [            # 相关资讯列表
                {"title": str, "sentiment": str, "scale": str, "company": str}
            ],
            "available": bool,
            "source": str,
            "warning": bool,     # 是否有巨量IPO警示
            "warning_companies": [str],  # 警示公司列表
        }
    """
    apikey = _get_apikey()
    if not apikey:
        return {
            "score": 0.0,
            "label": "N/A",
            "detail": "未配置 MX_APIKEY",
            "news": [],
            "available": False,
            "source": "N/A",
            "warning": False,
            "warning_companies": [],
        }

    all_news = []
    sentiment_scores = []
    api_calls = 0
    cache_hits = 0
    warning_companies = []

    for query in IPO_QUERIES:
        cached = _load_cache(query)
        if cached is not None:
            items = cached
            cache_hits += 1
        else:
            items = _run_search(query, use_cache=False)
            api_calls += 1
        
        for item in items:
            title = item.get("title", "")
            trunk = item.get("trunk", "")
            sentiment, score, scale, company, date = _analyze_ipo_sentiment(title, trunk)
            
            # 巨量IPO启动是警示信号
            if scale in ["千亿级", "百亿级"] and score < 0:
                if company and company not in warning_companies:
                    warning_companies.append(company)
            
            if score != 0:
                sentiment_scores.append(score)
            all_news.append({
                "title": title,
                "sentiment": sentiment,
                "scale": scale,
                "company": company,
                "date": date,
            })

    # 构建来源说明
    if api_calls > 0 and cache_hits > 0:
        source_detail = f"API{api_calls}次+缓存{cache_hits}个"
    elif api_calls > 0:
        source_detail = f"API{api_calls}次"
    elif cache_hits > 0:
        source_detail = f"缓存{cache_hits}个"
    else:
        source_detail = "N/A"

    if not all_news:
        return {
            "score": 0.0,
            "label": "中性",
            "detail": "近期无IPO/再融资动态",
            "news": [],
            "available": True,
            "source": source_detail,
            "warning": False,
            "warning_companies": [],
        }

    avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0

    # 构建详细说明
    has_warning = len(warning_companies) > 0
    if has_warning:
        detail = f"⚠️巨量IPO警示：{', '.join(warning_companies)}"
        label = "警示"
    elif avg_sentiment < -0.3:
        detail = "IPO/再融资活跃，注意资金分流"
        label = "偏空"
    elif avg_sentiment > 0.3:
        detail = "IPO节奏放缓，融资压力减轻"
        label = "利好"
    else:
        detail = "IPO节奏平稳"
        label = "中性"

    return {
        "score": round(avg_sentiment, 1),
        "label": label,
        "detail": detail,
        "news": all_news[:4],
        "available": True,
        "source": source_detail,
        "warning": has_warning,
        "warning_companies": warning_companies,
    }


def fetch() -> dict:
    """
    兼容旧接口：搜索近期印花税、券商佣金率相关消息
    建议使用 fetch_policy() 替代
    """
    return fetch_policy()


if __name__ == "__main__":
    import json
    print(json.dumps(fetch(), ensure_ascii=False, indent=2))
