"""
资金面消息搜索模块。

使用妙想资讯搜索 API 获取印花税、券商佣金率等政策消息，
判断对市场的利好/利空影响，作为资金面评分维度。

调用方式：
    python3 -m dividend_monitor  # 自动搜索并集成

或单独测试：
    python3 -c "from dividend_monitor.data_sources.mx_search import fetch; print(fetch())"
"""

import os
import sys
from typing import Optional

# 妙想 API 搜索脚本路径
MX_SEARCH_SCRIPT = os.path.expanduser("~/.codebuddy/skills/mx_search/scripts/mx_search.py")

# 搜索关键词（近期关于印花税、券商佣金率）
SEARCH_QUERIES = [
    "印花税 降低 利好",
    "券商佣金率 下调",
    "证券交易印花税 调整",
]


def _get_apikey() -> Optional[str]:
    """获取 API Key，优先从环境变量，其次尝试本地配置。"""
    key = os.environ.get("MX_APIKEY", "").strip()
    if key:
        return key

    # 尝试从本地配置文件读取
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
    return None


def _run_search(query: str) -> list:
    """执行单个搜索查询。"""
    apikey = _get_apikey()
    if not apikey:
        return []

    import json
    import subprocess

    cmd = [
        sys.executable, MX_SEARCH_SCRIPT,
        query,
        "--top", "3",
        "--json",
    ]
    try:
        # 设置环境变量传递 apikey
        env = os.environ.copy()
        env["MX_APIKEY"] = apikey
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        if result.returncode != 0:
            return []
        return json.loads(result.stdout) if result.stdout.strip() else []
    except Exception:
        return []


def fetch() -> dict:
    """
    搜索近期印花税、券商佣金率相关消息，判断市场影响。

    Returns:
        {
            "score": float,          # -2(利空) ~ +2(利好)
            "label": str,           # "利好" / "利空" / "中性" / "N/A"
            "detail": str,           # 详细说明
            "news": [                # 相关资讯列表（供展示）
                {"title": str, "sentiment": str}
            ],
            "available": bool,       # 是否可用（API key 是否配置）
        }
    """
    apikey = _get_apikey()
    if not apikey:
        return {
            "score": 0.0,
            "label": "N/A",
            "detail": "未配置 MX_APIKEY，跳过资金面维度",
            "news": [],
            "available": False,
        }

    all_news = []
    sentiment_scores = []

    for query in SEARCH_QUERIES:
        items = _run_search(query)
        for item in items:
            title = item.get("title", "")
            trunk = item.get("trunk", "")

            # 分析情感：查找关键词
            text = (title + " " + str(trunk)).lower()
            is_bullish = any(kw in text for kw in [
                "降低", "下调", "减免", "优惠", "下调", "减半", "取消",
                "降低", "减免", "优惠", "利好", "好消息"
            ])
            is_bearish = any(kw in text for kw in [
                "提高", "上调", "增加", "恢复", "利空", "坏消息"
            ])

            sentiment = "利好" if is_bullish else ("利空" if is_bearish else "中性")
            if is_bullish:
                sentiment_scores.append(1)
            elif is_bearish:
                sentiment_scores.append(-1)

            all_news.append({
                "title": title,
                "sentiment": sentiment,
                "query": query,
            })

    if not all_news:
        return {
            "score": 0.0,
            "label": "中性",
            "detail": "未搜索到相关消息，资金面无明显变化",
            "news": [],
            "available": True,
        }

    # 综合评分
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

    detail = f"综合 {len(all_news)} 条消息："
    news_summary = {}
    for n in all_news:
        s = n["sentiment"]
        news_summary[s] = news_summary.get(s, 0) + 1
    detail += " / ".join(f"{k}{v}条" for k, v in news_summary.items())

    return {
        "score": round(score, 1),
        "label": label,
        "detail": detail,
        "news": all_news[:5],  # 最多展示5条
        "available": True,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(fetch(), ensure_ascii=False, indent=2))
