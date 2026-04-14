"""
ETF筛选接口模块。

封装东方财富ETF筛选API，支持多条件筛选ETF。

API来源：用户提供
URL: https://np-tjxg-b.eastmoney.com/api/smart-tag/etf/v3/pw/search-code

使用示例：
    from market_monitor.data_sources.etf_selector import fetch_etf_screening, ETFFilter
    
    # 基础筛选
    result = fetch_etf_screening({
        "keyWord": "跟踪标的;资产规模大于5000万元;ETF类型是行业主题;KDJ<0;",
        "pageSize": 50,
    })
    
    # 使用过滤器类
    f = ETFFilter()
    f.add_type("行业主题")
    f.add_scale_min(5000)  # 万元
    f.add_kdj_condition("<", 0)
    result = f.execute()
"""

import hashlib
import json
import ssl
import time
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Optional, List, Dict, Any

# ── SSL 配置 ─────────────────────────────────────────────────────────────────
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

# ── API 配置 ─────────────────────────────────────────────────────────────────
_API_URL = "https://np-tjxg-b.eastmoney.com/api/smart-tag/etf/v3/pw/search-code"

_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    "Content-Type": "application/json",
    "Referer": "https://xuangu.eastmoney.com/",
    "Origin": "https://xuangu.eastmoney.com",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
}


def _generate_request_id() -> str:
    """生成请求ID"""
    timestamp = str(int(time.time() * 1000))
    return f"req_{timestamp}"


def _generate_fingerprint() -> str:
    """生成浏览器指纹（简化版）"""
    return hashlib.md5(str(time.time()).encode()).hexdigest()[:32]


def _http_post(url: str, body: dict, headers: Optional[dict] = None) -> Optional[dict]:
    """通用 HTTP POST 请求"""
    all_headers = {**_HEADERS}
    if headers:
        all_headers.update(headers)
    
    try:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=all_headers, method="POST")
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result
    except Exception as e:
        print(f"[ETF筛选] API请求失败: {e}")
        return None


def fetch_etf_screening(
    keyword: str = "",
    page_size: int = 50,
    page_no: int = 1,
    etf_types: Optional[List[str]] = None,
    scale_min: Optional[float] = None,
    kdj_condition: Optional[Dict[str, Any]] = None,
    sort_by: str = "kdj",
    sort_order: str = "asc",
) -> Dict:
    """
    调用东方财富ETF筛选API。
    
    Args:
        keyword: 搜索关键词
        page_size: 每页数量
        page_no: 页码
        etf_types: ETF类型列表，如 ["行业主题", "宽基指数", "风格策略", "外盘ETF", "黄金ETF"]
        scale_min: 最小资产规模（万元）
        kdj_condition: KDJ条件，如 {"op": "<", "value": 0}
        sort_by: 排序字段，如 "kdj", "scale", "premium"
        sort_order: 排序方向，"asc" 或 "desc"
    
    Returns:
        {
            "success": bool,
            "total": int,
            "page_no": int,
            "page_size": int,
            "etfs": [
                {
                    "code": str,        # ETF代码
                    "name": str,        # ETF名称
                    "type": str,        # ETF类型
                    "scale": float,     # 资产规模（万元）
                    "kdj_value": float, # KDJ值
                    "premium": float,   # 溢价率(%)
                    "change_pct": float,# 涨跌幅(%)
                    "track_target": str,# 跟踪标的
                },
                ...
            ]
        }
    """
    # 构建关键词字符串
    conditions = []
    
    if keyword:
        conditions.append(keyword)
    
    if etf_types:
        type_str = "或".join(etf_types)
        conditions.append(f"ETF类型是{type_str}")
    
    if scale_min:
        conditions.append(f"资产规模大于{scale_min}万元")
    
    if kdj_condition:
        op = kdj_condition.get("op", "<")
        val = kdj_condition.get("value", 0)
        conditions.append(f"KDJ{op}{val}")
    
    key_word = ";".join(conditions) + ";" if conditions else ""
    
    # 排序
    sort_field_map = {
        "kdj": "按日线KDJ值",
        "scale": "按资产规模",
        "premium": "按溢价率",
        "change": "按涨跌幅",
    }
    sort_str = sort_field_map.get(sort_by, "按日线KDJ值")
    sort_order_str = "升序" if sort_order == "asc" else "降序"
    key_word += f"按日线KDJ值升序排列;" if sort_by == "kdj" and sort_order == "asc" else ""
    
    # 构建请求体
    body = {
        "keyWord": key_word,
        "needAmbiguousSuggest": True,
        "pageSize": page_size,
        "pageNo": page_no,
        "fingerprint": _generate_fingerprint(),
        "matchWord": "",
        "shareToGuba": False,
        "timestamp": str(int(time.time() * 1000)),
        "requestId": _generate_request_id(),
        "removedConditionIdList": [],
        "ownSelectAll": False,
        "needCorrect": True,
        "client": "WEB",
        "product": "",
        "dxInfo": [],
        "customData": json.dumps([{
            "type": "text",
            "value": key_word,
            "extra": ""
        }], ensure_ascii=False),
        "needShowStockNum": False,
        "biz": "web_ai_select_stocks",
        "xcId": f"xc{int(time.time())}",
        "gids": []
    }
    
    # 发送请求
    data = _http_post(_API_URL, body)
    if not data:
        return {"success": False, "error": "API请求失败", "etfs": []}
    
    # 解析响应
    return _parse_response(data)


def _parse_response(data: dict) -> Dict:
    """解析API响应"""
    try:
        result_data = data.get("data", {}) or data
        
        # 处理不同的响应格式
        if isinstance(result_data, list):
            etfs = [_parse_etf_item(item) for item in result_data]
            return {
                "success": True,
                "total": len(etfs),
                "etfs": etfs,
            }
        
        # 东方财富标准响应格式
        records = result_data.get("records", [])
        total = result_data.get("total", len(records))
        
        etfs = [_parse_etf_item(item) for item in records]
        
        return {
            "success": True,
            "total": total,
            "page_no": result_data.get("pageNo", 1),
            "page_size": result_data.get("pageSize", 50),
            "etfs": etfs,
        }
    except Exception as e:
        print(f"[ETF筛选] 解析响应失败: {e}")
        return {"success": False, "error": str(e), "etfs": []}


def _parse_etf_item(item: dict) -> Dict:
    """解析单个ETF项目"""
    # 东方财富ETF筛选接口的字段映射
    return {
        "code": item.get("secucode", item.get("code", "")),
        "name": item.get("secuname", item.get("name", "")),
        "type": item.get("type", item.get("fund_type", "")),
        "scale": item.get("scale", item.get("net_scale", 0)),  # 万元
        "kdj_value": item.get("kdj", item.get("kdj_value", 0)),
        "premium": item.get("premium", item.get("premium_rate", 0)),  # %
        "change_pct": item.get("change_pct", item.get("chg_pct", 0)),
        "track_target": item.get("track_target", item.get("index_name", "")),
        "volume": item.get("volume", 0),
        "turnover": item.get("turnover", 0),
    }


# ── ETF筛选器类 ─────────────────────────────────────────────────────────────

class ETFFilter:
    """
    ETF筛选器，简化多条件筛选的构建。
    
    使用示例：
        f = ETFFilter()
        f.add_type("行业主题").add_type("宽基指数")
        f.add_scale_min(5000)
        f.add_kdj_condition("<", 0)
        f.sort_by("kdj", "asc")
        result = f.execute()
    """
    
    def __init__(self):
        self._etf_types: List[str] = []
        self._scale_min: Optional[float] = None
        self._kdj_op: Optional[str] = None
        self._kdj_value: Optional[float] = None
        self._sort_by: str = "kdj"
        self._sort_order: str = "asc"
        self._keyword: str = ""
        self._page_size: int = 50
        self._page_no: int = 1
    
    def add_type(self, etf_type: str) -> "ETFFilter":
        """添加ETF类型"""
        if etf_type not in self._etf_types:
            self._etf_types.append(etf_type)
        return self
    
    def add_types(self, etf_types: List[str]) -> "ETFFilter":
        """批量添加ETF类型"""
        for t in etf_types:
            self.add_type(t)
        return self
    
    def add_scale_min(self, scale: float) -> "ETFFilter":
        """设置最小资产规模（万元）"""
        self._scale_min = scale
        return self
    
    def add_kdj_condition(self, op: str, value: float) -> "ETFFilter":
        """设置KDJ条件"""
        self._kdj_op = op
        self._kdj_value = value
        return self
    
    def set_keyword(self, keyword: str) -> "ETFFilter":
        """设置搜索关键词"""
        self._keyword = keyword
        return self
    
    def sort_by(self, field: str, order: str = "asc") -> "ETFFilter":
        """设置排序"""
        self._sort_by = field
        self._sort_order = order
        return self
    
    def set_page(self, page_no: int, page_size: int = 50) -> "ETFFilter":
        """设置分页"""
        self._page_no = page_no
        self._page_size = page_size
        return self
    
    def build_keyword(self) -> str:
        """构建关键词字符串"""
        parts = []
        
        if self._keyword:
            parts.append(self._keyword)
        
        if self._etf_types:
            type_str = "或".join(self._etf_types)
            parts.append(f"ETF类型是{type_str}")
        
        if self._scale_min:
            parts.append(f"资产规模大于{self._scale_min}万元")
        
        if self._kdj_op and self._kdj_value is not None:
            parts.append(f"KDJ{self._kdj_op}{self._kdj_value}")
        
        return ";".join(parts) + ";"
    
    def execute(self) -> Dict:
        """执行筛选"""
        return fetch_etf_screening(
            keyword=self._keyword,
            page_size=self._page_size,
            page_no=self._page_no,
            etf_types=self._etf_types if self._etf_types else None,
            scale_min=self._scale_min,
            kdj_condition={"op": self._kdj_op, "value": self._kdj_value} if self._kdj_op else None,
            sort_by=self._sort_by,
            sort_order=self._sort_order,
        )


# ── 常用筛选预设 ─────────────────────────────────────────────────────────────

def get_kdj_oversold_etfs(etf_types: Optional[List[str]] = None) -> Dict:
    """
    获取KDJ超卖ETF（KDJ < 0）
    
    Args:
        etf_types: ETF类型列表，默认包含主要类型
    """
    if etf_types is None:
        etf_types = ["行业主题", "宽基指数", "风格策略", "外盘ETF", "黄金ETF"]
    
    f = ETFFilter()
    f.add_types(etf_types)
    f.add_scale_min(5000)  # 5000万规模
    f.add_kdj_condition("<", 0)
    f.sort_by("kdj", "asc")
    
    return f.execute()


def get_main_sectors_etfs() -> Dict:
    """获取主流行业ETF"""
    return get_kdj_oversold_etfs(["行业主题", "宽基指数"])


def get_gold_etfs() -> Dict:
    """获取黄金ETF"""
    f = ETFFilter()
    f.add_type("黄金ETF")
    f.add_kdj_condition("<", 0)
    f.sort_by("kdj", "asc")
    return f.execute()


if __name__ == "__main__":
    # 测试代码
    print("[ETF筛选] 测试KDJ超卖ETF...")
    result = get_kdj_oversold_etfs()
    
    if result.get("success"):
        print(f"找到 {result['total']} 只符合条件的ETF")
        for etf in result["etfs"][:5]:
            print(f"  {etf['code']} {etf['name']}: KDJ={etf['kdj_value']:.2f}, 溢价={etf['premium']:.2f}%")
    else:
        print(f"筛选失败: {result.get('error')}")
