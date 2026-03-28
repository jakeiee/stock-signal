"""
Web 搜索工具封装。

支持多种搜索方式:
1. DuckDuckGo (默认，无需 API Key)
2. Bing Web Search API (需 API Key)
3. Google Custom Search API (需 API Key)

使用方法:
    from market_monitor.utils.web_search import search_web
    
    results = search_web("国家统计局 PMI 解读", limit=5)
    for item in results:
        print(item["title"], item["url"])
"""

import json
import re
import subprocess
from typing import List, Dict, Optional
from urllib.parse import quote


def search_duckduckgo(query: str, limit: int = 5) -> List[Dict]:
    """
    使用 DuckDuckGo 搜索（无需 API Key）。
    
    通过 ddgs Python 包实现。
    """
    results = []
    
    # 方法1: 尝试使用 ddgs 包（新版）
    try:
        from ddgs import DDGS
        
        with DDGS() as ddgs:
            search_results = list(ddgs.text(query, max_results=limit))
            for r in search_results:
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                })
            
            if results:
                return results
                
    except ImportError:
        pass  # ddgs 未安装
    except Exception as e:
        print(f"[WebSearch] DDGS 失败: {e}")
    
    # 方法2: 尝试使用 duckduckgo-search 旧包
    try:
        from duckduckgo_search import DDGS as DDGS_OLD
        
        with DDGS_OLD() as ddgs:
            search_results = ddgs.text(query, max_results=limit)
            for r in search_results:
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                })
            
            if results:
                return results
                
    except ImportError:
        pass
    except Exception as e:
        print(f"[WebSearch] DDGS_OLD 失败: {e}")
    
    return results


def search_bing(query: str, limit: int = 5, api_key: Optional[str] = None) -> List[Dict]:
    """
    使用 Bing Web Search API。
    
    需要 API Key: https://portal.azure.com/
    """
    import urllib.request
    
    api_key = api_key or ""
    if not api_key:
        return []
    
    try:
        encoded_query = quote(query)
        url = f"https://api.bing.microsoft.com/v7.0/search?q={encoded_query}&count={limit}"
        
        req = urllib.request.Request(url)
        req.add_header("Ocp-Apim-Subscription-Key", api_key)
        
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
            
            results = []
            for item in data.get("webPages", {}).get("value", []):
                results.append({
                    "title": item.get("name", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("snippet", ""),
                })
            
            return results
            
    except Exception as e:
        print(f"[WebSearch] Bing API 失败: {e}")
        return []


def search_google(query: str, limit: int = 5, api_key: Optional[str] = None, cx: Optional[str] = None) -> List[Dict]:
    """
    使用 Google Custom Search API。
    
    需要:
    - API Key: https://developers.google.com/custom-search/v1/overview
    - Search Engine ID (cx): https://cse.google.com/cse/all
    """
    import urllib.request
    
    api_key = api_key or ""
    cx = cx or ""
    
    if not api_key or not cx:
        return []
    
    try:
        encoded_query = quote(query)
        url = f"https://www.googleapis.com/customsearch/v1?key={api_key}&cx={cx}&q={encoded_query}&num={limit}"
        
        with urllib.request.urlopen(url, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
            
            results = []
            for item in data.get("items", []):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                })
            
            return results
            
    except Exception as e:
        print(f"[WebSearch] Google API 失败: {e}")
        return []


def search_web(query: str, limit: int = 5, engine: str = "auto") -> List[Dict]:
    """
    统一的 Web 搜索接口。
    
    Args:
        query: 搜索关键词
        limit: 返回结果数量
        engine: 搜索引擎 (auto/duckduckgo/bing/google)
    
    Returns:
        搜索结果列表，每项包含 title, url, snippet
    """
    results = []
    
    if engine == "auto":
        # 自动选择：优先 DuckDuckGo（无需 API Key）
        engines = ["duckduckgo", "bing", "google"]
    else:
        engines = [engine]
    
    for eng in engines:
        try:
            if eng == "duckduckgo":
                results = search_duckduckgo(query, limit)
            elif eng == "bing":
                import os
                api_key = os.getenv("BING_API_KEY")
                results = search_bing(query, limit, api_key)
            elif eng == "google":
                import os
                api_key = os.getenv("GOOGLE_API_KEY")
                cx = os.getenv("GOOGLE_CX")
                results = search_google(query, limit, api_key, cx)
            
            if results:
                print(f"[WebSearch] 使用 {eng} 找到 {len(results)} 条结果")
                return results
                
        except Exception as e:
            print(f"[WebSearch] {eng} 失败: {e}")
            continue
    
    return results


if __name__ == "__main__":
    # 测试
    print("测试 Web 搜索...")
    
    test_queries = [
        "国家统计局 2026年2月 PMI 官方解读",
        "Python tutorial",
    ]
    
    for query in test_queries:
        print(f"\n搜索: {query}")
        results = search_web(query, limit=3)
        
        for i, item in enumerate(results, 1):
            print(f"  {i}. {item['title'][:50]}...")
            print(f"     {item['url'][:60]}...")
