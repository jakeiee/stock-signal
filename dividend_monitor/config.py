"""
全局配置：API 地址、密钥、指数列表、运行参数及文件路径。
所有其他模块均从此处导入常量，避免硬编码分散。
"""

import os

# ── 妙想 API ──────────────────────────────────────────────────────────────────
API_BASE   = "https://mkapi2.dfcfs.com/finskillshub/api/claw"
APIKEY     = os.environ.get("MX_APIKEY", "mkt_HeEVfE9lWxYWMJpYsdLfU4-rWvXyKj5xU0mvS0giDOA")
MX_HEADERS = {"Content-Type": "application/json", "apikey": APIKEY}

# ── 飞书 Webhook ──────────────────────────────────────────────────────────────
FEISHU_WEBHOOK = os.environ.get(
    "FEISHU_WEBHOOK",
    "https://open.feishu.cn/open-apis/bot/v2/hook/46b97530-d458-401a-8678-82da01b3d3ca",
)

# ── 跟踪指数列表 ──────────────────────────────────────────────────────────────
# code         : 指数代码（用于 kdj_data 字典 key 及终端展示）
# csindex_code : 中证官网 indexCode（备用 OHLCV 接口参数）
# query_name   : 妙想 API 自然语言查询前缀
INDEXES = [
    {
        "name":         "红利低波",
        "code":         "H30269",
        "csindex_code": "H30269",
        "query_name":   "红利低波H30269",
        # 指数真实发布日期（来源：中证指数官网）
        # H30269 基日 2004-12-31，发布日 2012-10-26，历史超10年
        "launch_date":  "2012-10-26",
    },
    {
        "name":         "红利质量",
        "code":         "931468",
        "csindex_code": "931468",
        "query_name":   "红利质量931468",
        # 931468 发布日 2020-05-21，历史不足10年，需特别标注
        "launch_date":  "2020-05-21",
    },
    {
        "name":         "东证红利低波",
        "code":         "931446",
        "csindex_code": "931446",
        "query_name":   "东证红利低波931446",
        # 931446 发布日 2020-04-21，历史不足10年，需特别标注
        "launch_date":  "2020-04-21",
    },
]

# ── 运行参数 ──────────────────────────────────────────────────────────────────
WEEK_KDJ_COUNT = 1     # 每只指数展示最新 N 周的 KDJ
BOND_FALLBACK  = 1.70  # 国债收益率获取失败时的保底值（%）

# ── 本地缓存路径 ──────────────────────────────────────────────────────────────
_SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
VAL_CACHE_FILE = os.path.join(_SCRIPT_DIR, "valuation_cache.json")
