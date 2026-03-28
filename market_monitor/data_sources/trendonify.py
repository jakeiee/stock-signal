"""
Trendonify 全球指数估值数据爬虫。

数据来源: https://trendonify.com/pe-ratio
覆盖: 美国、香港、日本、韩国等主要市场指数的 PE 估值和 10 年百分位

使用方法:
    from market_monitor.data_sources.trendonify import fetch_trendonify_valuation
    data = fetch_trendonify_valuation()
"""

import json
import os
import subprocess
import time
from datetime import date, datetime
from typing import Optional

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_CACHE_FILE = os.path.join(_DATA_DIR, "trendonify_cache.json")
_SCRAPER_SCRIPT = os.path.join(os.path.dirname(__file__), "trendonify_scraper.js")

# 备用静态数据（当爬取失败时使用）
_FALLBACK_DATA = {
    "US":   {"pe": 24.43, "pct_10y": 75.8, "label": "高估"},
    "HK":   {"pe": 12.70, "pct_10y": 68.1, "label": "高估"},
    "JP":   {"pe": 18.81, "pct_10y": 100.0, "label": "昂贵"},
    "KR":   {"pe": 18.95, "pct_10y": 99.2, "label": "昂贵"},
}


def _save_cache(data: dict) -> None:
    """保存数据到缓存文件。"""
    os.makedirs(_DATA_DIR, exist_ok=True)
    cache = {
        "data": data,
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    with open(_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def _load_cache() -> Optional[dict]:
    """从缓存文件加载数据。"""
    if not os.path.exists(_CACHE_FILE):
        return None
    try:
        with open(_CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
        # 检查缓存是否过期（4小时内有效，减少爬虫调用频率）
        updated = datetime.strptime(cache.get("updated", ""), "%Y-%m-%d %H:%M:%S")
        hours_old = (datetime.now() - updated).total_seconds() / 3600
        if hours_old > 4:
            print(f"[Trendonify] 缓存已过期 ({hours_old:.1f} 小时)，需要刷新")
            return None
        return cache.get("data")
    except Exception:
        return None


def _run_scraper() -> Optional[dict]:
    """运行Node.js爬虫脚本。"""
    if not os.path.exists(_SCRAPER_SCRIPT):
        print(f"[Trendonify] 爬虫脚本不存在: {_SCRAPER_SCRIPT}")
        return None
    
    try:
        # 使用绝对路径运行node
        result = subprocess.run(
            ["node", _SCRAPER_SCRIPT],
            capture_output=True,
            text=True,
            timeout=180,  # 3分钟超时
            cwd=os.path.dirname(_SCRAPER_SCRIPT)
        )
        
        if result.returncode != 0:
            print(f"[Trendonify] 爬虫执行失败: {result.stderr}")
            return None
        
        # 读取生成的缓存文件
        if os.path.exists(_CACHE_FILE):
            with open(_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        
        return None
        
    except subprocess.TimeoutExpired:
        print("[Trendonify] 爬虫执行超时")
        return None
    except Exception as e:
        print(f"[Trendonify] 爬虫执行异常: {e}")
        return None


def fetch_trendonify_valuation(force_refresh: bool = False) -> dict:
    """
    获取 Trendonify 全球指数估值数据。

    Args:
        force_refresh: 是否强制刷新缓存

    Returns:
        {
            "US":   {"pe": float, "pct_10y": float, "label": str},
            "HK":   {"pe": float, "pct_10y": float, "label": str},
            "JP":   {"pe": float, "pct_10y": float, "label": str},
            "KR":   {"pe": float, "pct_10y": float, "label": str},
            "source": "trendonify",
            "date": "YYYY-MM-DD",
        }
        失败时返回 {"error": str}
    """
    # 1. 尝试从缓存加载（除非强制刷新）
    if not force_refresh:
        cached = _load_cache()
        if cached:
            print("[Trendonify] 使用缓存数据")
            return cached

    print("[Trendonify] 开始获取实时数据...")
    
    # 2. 运行爬虫获取数据
    result = _run_scraper()
    
    if result:
        print("[Trendonify] 爬虫获取数据成功")
        return result
    
    # 3. 爬虫失败，尝试加载旧的缓存（即使过期）
    if os.path.exists(_CACHE_FILE):
        try:
            with open(_CACHE_FILE, "r", encoding="utf-8") as f:
                old_cache = json.load(f)
            print("[Trendonify] 使用过期缓存数据")
            return old_cache.get("data", {})
        except Exception:
            pass
    
    # 4. 所有方法都失败，使用fallback数据
    print("[Trendonify] 使用静态fallback数据")
    result = {
        "source": "trendonify_fallback",
        "date": date.today().strftime("%Y-%m-%d"),
        "note": "静态数据，所有获取方式失败",
    }
    result.update(_FALLBACK_DATA.copy())
    return result


if __name__ == "__main__":
    # 测试
    print("=" * 50)
    print("Trendonify 估值数据获取测试")
    print("=" * 50)
    result = fetch_trendonify_valuation()
    print(json.dumps(result, ensure_ascii=False, indent=2))
