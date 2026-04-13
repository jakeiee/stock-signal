"""
飞书配置 - 请复制 config_example.py 为 config.py 并填入真实值
注意：这个文件包含敏感信息，请勿提交到 GitHub！
"""

import os

# ============ 飞书配置 ============

# Webhook 方式（简单，推荐用于机器人消息）
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK", "")

# 应用方式（更强大，可发送富文本卡片）
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")

# 飞书群 ID（用于应用消息推送）
FEISHU_CHAT_ID = os.getenv("FEISHU_CHAT_ID", "")
