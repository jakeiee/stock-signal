"""
ETF筛选接口模块。

封装东方财富ETF筛选API，支持多条件筛选ETF。

API来源：用户提供
URL: https://np-tjxg-g.eastmoney.com/api/smart-tag/etf/v3/pw/search-code

使用示例：
    from market_monitor.data_sources.etf_selector import fetch_etf_screening, ETFFilter
    
    # 基础筛选
    result = fetch_etf_screening(
        etf_types=["行业主题", "宽基指数"],
        scale_min=5000,
        kdj_condition={"op": "<", "value": 0},
    )
    
    # 使用过滤器类
    f = ETFFilter()
    f.add_type("行业主题")
    f.add_scale_min(5000)  # 万元
    f.add_kdj_condition("<", 0)
    result = f.execute()
"""

import hashlib
import json
import random
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
_API_URL = "https://np-tjxg-g.eastmoney.com/api/smart-tag/etf/v3/pw/search-code"

# 固定的选股方案ID（来自东方财富选股页面URL）
_DEFAULT_XC_ID = "xc1200bf7bb5c2011083"

_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    "Content-Type": "application/json",
    "Referer": "https://xuangu.eastmoney.com/",
    "Origin": "https://xuangu.eastmoney.com",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0",
    "actionmode": "edit_way",
    "curpage": "stockResult",
    "jumpsource": "edit_way",
    "sec-ch-ua": '"Chromium";v="148", "Microsoft Edge";v="148", "Not/A)Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "priority": "u=1, i",
}


def _generate_request_id() -> str:
    """生成请求ID，模拟东方财富前端格式"""
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    random_part = "".join(random.choice(chars) for _ in range(37))
    timestamp = str(int(time.time() * 1000))
    return f"{random_part}{timestamp}"


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
    track_target: Optional[str] = None,
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
        track_target: 跟踪标的筛选，如 "黄金"
    
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
    
    # 始终包含"跟踪标的"以确保 API 返回 INDEX_NAME_ABBR 字段（用于后续指数映射）
    conditions.append("跟踪标的")
    
    if keyword:
        conditions.append(keyword)
    
    if track_target:
        conditions.append(f"跟踪标的{track_target}")
    
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
    
    # 构建请求体（字段名与东方财富前端一致）
    body = {
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
        "needShowStockNum": False,
        "biz": "web_ai_select_stocks",
        "xcId": _DEFAULT_XC_ID,
        "gids": [],
        # 关键字段：用 keyWordNew / customDataNew / dxInfoNew（非旧版 keyWord/customData/dxInfo）
        "keyWordNew": key_word,
        "customDataNew": json.dumps([{
            "type": "text",
            "value": key_word,
            "extra": ""
        }], ensure_ascii=False),
        "dxInfoNew": [],
    }
    
    # 发送请求
    data = _http_post(_API_URL, body)
    if not data:
        return {"success": False, "error": "API请求失败", "etfs": []}
    
    # 解析响应
    return _parse_response(data)


def _parse_response(data: dict) -> Dict:
    """解析API响应。
    
    实际响应结构: data.result.dataList (列表) + data.result.total (总数)
    dataList 中每个元素为 dict，key 为列名（如 SECURITY_CODE, KDJ_J{date}）
    """
    try:
        result_wrapper = data.get("data", {})
        
        # 提取 result 对象
        result_obj = result_wrapper.get("result", {})
        if not result_obj and isinstance(result_wrapper, list):
            # 兼容旧格式
            etfs = [_parse_etf_item(item) for item in result_wrapper]
            return {"success": True, "total": len(etfs), "etfs": etfs}
        
        # 标准格式: result.dataList
        data_list = result_obj.get("dataList", [])
        total = result_obj.get("total", len(data_list))
        
        # 构建列名映射（key -> title），方便字段查找
        columns = result_obj.get("columns", [])
        col_map = {c["key"]: c["title"] for c in columns}
        
        etfs = [_parse_etf_item(item, col_map) for item in data_list]
        
        return {
            "success": True,
            "total": total,
            "page_no": result_obj.get("pageNo", 1),
            "page_size": result_obj.get("pageSize", 50),
            "etfs": etfs,
        }
    except Exception as e:
        print(f"[ETF筛选] 解析响应失败: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e), "etfs": []}


def _parse_scale_value(raw: str) -> float:
    """解析资产规模字符串为万元数值。
    
    例: "1376.16亿|2026-06-12" → 13761600 万元
        "4.54亿|2026-06-11" → 45400 万元
        "5000万" → 5000 万元
    """
    if not raw:
        return 0.0
    # 取管道分隔的第一部分（去掉日期后缀）
    val_str = str(raw).split("|")[0].strip().replace(",", "")
    if not val_str or val_str == "-":
        return 0.0
    try:
        if "亿" in val_str:
            return float(val_str.replace("亿", "")) * 10000  # 亿→万元
        elif "万" in val_str:
            return float(val_str.replace("万", ""))
        else:
            return float(val_str)
    except (ValueError, TypeError):
        return 0.0


def _find_value_by_key(item: dict, col_map: dict, *key_candidates: str) -> Any:
    """在 dataList 项中按可能的 key 查找字段值。
    
    col_map: 列名映射 {key: title}，用于辅助查找
    """
    for key in key_candidates:
        # 精确匹配
        if key in item:
            return item[key]
        # 模糊匹配（带日期后缀的 key，如 KDJ_J{2026-06-12}）
        for k in item:
            if k.startswith(key):
                return item[k]
    return None


def _parse_etf_item(item: dict, col_map: dict = None) -> Dict:
    """解析单个ETF项目，适配东方财富 v3 API 的 dataList 格式。
    
    dataList 元素示例:
    {
        "SECURITY_CODE": "510300",
        "SECURITY_SHORT_NAME": "沪深300ETF华泰柏瑞",
        "ETF_TYPE": "宽基指数",
        "INDEX_NAME_ABBR": "沪深300",
        "NEWEST_PRICE": "4.818",
        "CHG": "1.41",
        "KDJ_J{2026-06-12}": "-4.97",
        "PREMIUM_RATE{2026-06-14}": "0.08",
        "NEW_SCALE{2026-06-14}": "1376.16亿|2026-06-12",
        "TRADING_VOLUMES": "37.62亿",
        "PER_NAV": "4.8077",
        "T0": "T+1",
    }
    """
    if col_map is None:
        col_map = {}
    
    # 安全取值辅助
    def _float(key, default=0.0):
        v = _find_value_by_key(item, col_map, key)
        if v is None or v == "-":
            return default
        try:
            return float(str(v).replace(",", ""))
        except (ValueError, TypeError):
            return default
    
    def _str(key, default=""):
        v = _find_value_by_key(item, col_map, key)
        return str(v) if v and v != "-" else default
    
    price = _float("NEWEST_PRICE")
    
    return {
        "code": _str("SECURITY_CODE"),
        "name": _str("SECURITY_SHORT_NAME"),
        "type": _str("ETF_TYPE"),
        "scale": _parse_scale_value(_str("NEW_SCALE")),  # 转换为万元
        "scale_raw": _str("NEW_SCALE"),
        "kdj_value": _float("KDJ_J"),
        "premium": _float("PREMIUM_RATE"),  # 溢价率(%)
        "change_pct": _float("CHG"),  # 涨跌幅(%)
        "track_target": _str("INDEX_NAME_ABBR"),  # 跟踪标的
        "price": price,
        "nav": _float("PER_NAV"),  # 单位净值
        "volume_raw": _str("TRADING_VOLUMES"),  # 成交额（字符串带单位）
        "t0": _str("T0"),
        "market_num": _str("MARKET_NUM"),
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
        self._track_target: Optional[str] = None   # 跟踪标的
    
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
    
    def add_track_target(self, target: str) -> "ETFFilter":
        """设置跟踪标的筛选"""
        self._track_target = target
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
        """构建关键词字符串。
        
        始终包含"跟踪标的"以确保API返回 INDEX_NAME_ABBR 字段。
        """
        parts = []
        
        # 跟踪标的是必需字段（为了获取INDEX_NAME_ABBR用于指数映射）
        parts.append("跟踪标的")
        
        if self._keyword and "跟踪标的" not in self._keyword:
            parts.append(self._keyword)
        
        if self._track_target:
            parts.append(f"跟踪标的{self._track_target}")
        
        if self._etf_types:
            type_str = "或".join(self._etf_types)
            parts.append(f"ETF类型是{type_str}")
        
        if self._scale_min:
            parts.append(f"资产规模大于{self._scale_min}万元")
        
        if self._kdj_op and self._kdj_value is not None:
            parts.append(f"KDJ{self._kdj_op}{self._kdj_value}")
        
        # 去重：保持首次出现的顺序
        seen = set()
        unique_parts = []
        for p in parts:
            if p not in seen:
                seen.add(p)
                unique_parts.append(p)
        
        return ";".join(unique_parts) + ";"
    
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
            track_target=self._track_target,
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


def get_selection_etfs(
    etf_types: Optional[List[str]] = None,
    scale_min: float = 5000,
    track_target: Optional[str] = None,
) -> Dict:
    """
    获取选股专用ETF初筛结果。
    
    覆盖全部主要ETF类型，按KDJ升序排列。
    
    Args:
        etf_types: ETF类型列表，默认 ["行业主题", "宽基指数", "风格策略", "外盘ETF", "黄金ETF"]
        scale_min: 最小资产规模（万元），默认5000
        track_target: 跟踪标的筛选（可选），如 "黄金"
    
    Returns:
        ETF筛选结果
    """
    if etf_types is None:
        etf_types = ["行业主题", "宽基指数", "风格策略", "外盘ETF", "黄金ETF"]
    
    f = ETFFilter()
    f.add_types(etf_types)
    f.add_scale_min(scale_min)
    f.add_kdj_condition("<", 0)
    f.sort_by("kdj", "asc")
    if track_target:
        f.add_track_target(track_target)
    
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
