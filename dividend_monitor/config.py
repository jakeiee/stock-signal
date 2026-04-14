"""
红利指数监控配置
"""

import os

# ============ 飞书配置 ============
FEISHU_WEBHOOK = os.getenv(
    "FEISHU_WEBHOOK",
    "https://open.feishu.cn/open-apis/bot/v2/hook/46b97530-d458-401a-8678-82da01b3d3ca"
)

# ============ 指数配置 ============
# 跟踪：红利低波(H30269)、红利质量(931468)、东证红利低波(931446)
INDEXES = [
    {"name": "红利低波",     "code": "H30269", "csindex_code": "H30269", "query_name": "红利低波H30269"},
    {"name": "红利质量",     "code": "931468", "csindex_code": "931468", "query_name": "红利质量931468"},
    {"name": "东证红利低波", "code": "931446", "csindex_code": "931446", "query_name": "东证红利低波931446"},
]

# ============ 缓存配置 ============
VAL_CACHE_FILE = "dividend_monitor/valuation_cache.json"

# ============ 其他配置 ============
BOND_FALLBACK = 1.70  # 无法获取实时数据时的保底无风险利率(%)