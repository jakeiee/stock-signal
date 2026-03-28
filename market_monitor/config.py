"""
stock_monitor 全局配置。
"""

import os

# ── 飞书 Webhook ──────────────────────────────────────────────────────────────
FEISHU_WEBHOOK = os.environ.get(
    "FEISHU_WEBHOOK",
    "https://open.feishu.cn/open-apis/bot/v2/hook/46b97530-d458-401a-8678-82da01b3d3ca",
)

# 飞书图片上传接口
FEISHU_UPLOAD_URL = "https://open.feishu.cn/open-apis/im/v1/images"

# 飞书开放平台应用凭据（用于图片上传）
FEISHU_APP_ID = "cli_a93ff91685f89bb4"
FEISHU_APP_SECRET = "a4BqKG39Cpo8E9YOnQkLRdVT3JD7pW8a"

# ── 东方财富接口公共 Headers ──────────────────────────────────────────────────
EM_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://finance.eastmoney.com/",
}

# ── 中证官网接口公共 Headers ──────────────────────────────────────────────────
CS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer":    "https://www.csindex.com.cn/",
}

# ── 请求超时（秒）────────────────────────────────────────────────────────────
DEFAULT_TIMEOUT = 20

# ── 妙想资讯 API Key ─────────────────────────────────────────────────────────
MX_APIKEY = os.environ.get("MX_APIKEY", "mkt_HeEVfE9lWxYWMJpYsdLfU4-rWvXyKj5xU0mvS0giDOA")
