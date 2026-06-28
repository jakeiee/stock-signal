"""
ETF → 跟踪指数 → xalpha 代码 统一映射模块。

唯一的数据源，替代之前在 portfolio_professional.py 和 portfolio_selection_workflow.py
中各自维护的映射表。

使用示例：
    from market_monitor.data.etf_index_mapping import lookup_by_index_name, lookup_by_etf_code
    
    xa_code = lookup_by_index_name("创业板50")           # → "SZ399673"
    info = lookup_by_etf_code("513180")                  # → {"xa_code": "HKHSTECH", ...}
"""

from typing import Optional, Dict, List

# ── 表1: ETF代码 → 指数/名称/xalpha代码 ────────────────────────────────────────
# 来源：etf_index_mapping.csv + 持仓ETF硬编码
# 键: etf_code, 值: {name, index_name, xa_code}

ETF_CODE_MAP: Dict[str, dict] = {
    "159202": {"name": "恒生互联网ETF",       "index_name": "恒生互联网科技业指数", "xa_code": "HKHSIII"},
    "159217": {"name": "港股通创新药ETF",      "index_name": "恒生医疗保健指数",     "xa_code": "GZ987018"},
    "159852": {"name": "软件ETF嘉实",          "index_name": "中证软件服务指数",     "xa_code": "ZZ930601"},
    "159869": {"name": "游戏ETF华夏",          "index_name": "中证游戏产业指数",     "xa_code": "ZZ930901"},
    "513090": {"name": "香港证券ETF易方达",    "index_name": "中证香港证券指数",     "xa_code": "ZZ930709"},
    "562500": {"name": "机器人ETF华夏",        "index_name": "中证机器人指数",       "xa_code": "ZZH30590"},
    "513180": {"name": "恒生科技ETF华夏",      "index_name": "恒生科技指数",         "xa_code": "HKHSTECH"},
    "512890": {"name": "红利低波ETF华泰柏瑞",   "index_name": "中证红利低波指数",     "xa_code": "ZZ930740"},
    "560860": {"name": "工业有色ETF",          "index_name": "中证工业有色指数",     "xa_code": "ZZH11059"},
    "506008": {"name": "科创板长城",            "index_name": "科创50指数",           "xa_code": "SH000688"},
    "513130": {"name": "恒生互联网ETF",        "index_name": "恒生互联网科技业指数", "xa_code": "HKHSIII"},
    "159890": {"name": "软件ETF嘉实",          "index_name": "中证软件服务指数",     "xa_code": "ZZ930601"},
    "588260": {"name": "科创板50ETF",          "index_name": "科创50指数",           "xa_code": "SH000688"},
    "562800": {"name": "机器人ETF华夏",        "index_name": "中证机器人指数",       "xa_code": "ZZH30590"},
    "159567": {"name": "港股通创新药ETF",      "index_name": "恒生医疗保健指数",     "xa_code": "GZ987018"},
    "516010": {"name": "游戏ETF华夏",          "index_name": "深圳游戏产业指数",     "xa_code": "ZZ930901"},
    "513020": {"name": "港股通科技ETF",        "index_name": "恒生科技指数",         "xa_code": "HKHSTECH"},
}

# ── 表2: 东方财富选股API INDEX_NAME_ABBR → xalpha 代码 ────────────────────────
# 用于：选股筛选后的知行分析指数映射
# 键: 东方财富API返回的跟踪指数简称
# 值: xalpha 指数代码

INDEX_NAME_TO_XACODE: Dict[str, str] = {
    # ── 宽基指数 ──
    "创业板50": "SZ399673",
    "创业板人工智能": "ZZH20034",
    
    # ── 行业主题 ──
    "CS物联网": "ZZ930712",
    "SHS物联网": "ZZ931460",
    "电力指数": "ZZ399989",
    "绿色电力": "ZZH20033",
    "消费电子": "ZZ931494",
    "家电龙头": "ZZ931102",
    "全指公用": "ZZ000990",
    "中证VR": "ZZ930821",
    "中国互联网50人民币": "HKHSIII",
    "国新港股通央企红利": "ZZ931854",
    
    # ── 港股/外盘ETF ──
    "港股通互联网": "HKHSIII",
    "恒生港股通中国科技指数": "HKHSTECH",
    "恒生港股通科技主题指数": "HKHSTECH",
    "港股通科技主题": "HKHSTECH",
    "港股通信息C人民币": "HKHSIII",
    "港股通信息C港元": "HKHSIII",
    
    # ── 价值/红利/银行（2026-06-21 新增） ──
    "中证红利": "ZZ000922",
    "中证煤炭": "ZZ399998",
    "中证银行": "ZZ399986",
    "国企红利": "ZZ000824",
    "上国红利": "ZZH50040",
    "180价值": "SH000029",
    "300价值": "SH000919",
    "300价值稳健": "ZZ931586",
    "300红利": "SH000821",
    "300红利低波": "ZZ930740",
    "800红利低波": "ZZ931848",
    "800能源": "ZZ000928",
    "A500红利低波": "ZZ931689",
    "大盘价值": "SZ399373",
    "价值100": "ZZ931468",
    "全指能源": "SH000986",
    "红利指数": "SH000015",
    "港股通消费": "HKHSCCI",
    "港股通消费港元": "HKHSIII",
    "恒生国企指数": "HKHSCEI",
    "恒生中国(香港上市)30指数": "HKHSI",
    "S&P Oil & Gas Exploration & Production Select Industry": "SPOG",
}

# ── 已知不支持 xalpha 的指数（用于报告提示） ──
UNSUPPORTED_INDEX_NAMES: set = {
    "港股通红利低波", "港股通高股息港元", "恒生中国央企指数",
    "恒生港股通中国内地企业高股息率指数", "恒生港股通高股息低波动指数",
    "恒生港股通高股息率指数",
    "MSCI USA 50 Index",
}


def lookup_by_index_name(index_name: str) -> Optional[str]:
    """根据东方财富 API 返回的跟踪指数简称，查询 xalpha 代码。
    
    Args:
        index_name: INDEX_NAME_ABBR，如 "创业板50"
    
    Returns:
        xalpha 指数代码（如 "SZ399673"），未找到返回 None
    """
    return INDEX_NAME_TO_XACODE.get(index_name)


def lookup_by_etf_code(etf_code: str) -> Optional[dict]:
    """根据 ETF 代码查询完整的指数映射信息。
    
    Args:
        etf_code: ETF代码，如 "513180"
    
    Returns:
        {"name": ..., "index_name": ..., "xa_code": ...}，未找到返回 None
    """
    return ETF_CODE_MAP.get(etf_code)


def get_xa_code(etf_code: str) -> Optional[str]:
    """根据 ETF 代码直接获取 xalpha 指数代码（快捷方法）。"""
    info = ETF_CODE_MAP.get(etf_code)
    return info["xa_code"] if info else None


def is_unsupported_index(index_name: str) -> bool:
    """判断该指数是否已知不支持 xalpha。"""
    return index_name in UNSUPPORTED_INDEX_NAMES


def list_mapped_index_names() -> List[str]:
    """列出所有已映射的指数名称。"""
    return list(INDEX_NAME_TO_XACODE.keys())


def list_mapped_etf_codes() -> List[str]:
    """列出所有已映射的 ETF 代码。"""
    return list(ETF_CODE_MAP.keys())
