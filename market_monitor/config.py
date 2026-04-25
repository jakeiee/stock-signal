"""
飞书配置 - 请复制 config_example.py 为 config.py 并填入真实值
注意：这个文件包含敏感信息，请勿提交到 GitHub！
"""

import os

# ============ 飞书配置 ============

# Webhook 方式（简单，推荐用于机器人消息）
FEISHU_WEBHOOK = os.getenv(
    "FEISHU_WEBHOOK",
    "https://open.feishu.cn/open-apis/bot/v2/hook/46b97530-d458-401a-8678-82da01b3d3ca"
)

# 应用方式（更强大，可发送富文本卡片）
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")

# 飞书群 ID（用于应用消息推送）
FEISHU_CHAT_ID = os.getenv("FEISHU_CHAT_ID", "")

# 飞书图片上传接口
FEISHU_UPLOAD_URL = "https://open.feishu.cn/open-apis/im/v1/images"

# ============ 通义千问 LLM 配置 ============

# 千问 API Key（从环境变量或直接填写）
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")

# LLM 模型选择
# qwen-turbo: 快速，，适合简单任务
# qwen-plus: 效果更好，适合复杂解析
# qwen-max: 最佳效果，成本较高
LLM_MODEL = os.getenv("LLM_MODEL", "qwen-plus")

# LLM 解析超时时间（秒）
LLM_TIMEOUT = 30

# 是否启用 LLM 解析（设为 False 则使用规则解析）
LLM_ENABLED = True

# ─────────────────────────────────────────────────────────────
# ⚠️ 使用前请配置 DASHSCOPE_API_KEY：
#    1. 访问 https://dashscope.console.aliyun.com/ 获取 API Key
#    2. 在 ~/.zshrc 中添加: export DASHSCOPE_API_KEY="your-key-here"
#    3. 重启终端或执行: source ~/.zshrc
# ─────────────────────────────────────────────────────────────
