"""
飞书图片上传工具。

用于将本地图片上传到飞书并获取图片 URL。
"""

import os
import json
import base64
import time
from typing import Optional

from ..config import FEISHU_WEBHOOK, FEISHU_UPLOAD_URL, FEISHU_APP_ID, FEISHU_APP_SECRET

# Token 缓存
_cached_token: Optional[str] = None
_token_expires_at: float = 0


def _get_tenant_access_token() -> Optional[str]:
    """
    获取飞书 tenant_access_token。
    
    使用缓存机制，token 有效期约 2 小时。
    """
    global _cached_token, _token_expires_at
    
    # 检查缓存
    if _cached_token and time.time() < _token_expires_at:
        return _cached_token
    
    # 获取新 token
    token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    payload = {
        "app_id": FEISHU_APP_ID,
        "app_secret": FEISHU_APP_SECRET,
    }
    
    try:
        import requests
        resp = requests.post(token_url, json=payload, timeout=10)
        result = resp.json()
        
        if result.get("code") == 0:
            _cached_token = result.get("tenant_access_token")
            # 提前 5 分钟过期，留出缓冲时间
            _token_expires_at = time.time() + result.get("expire", 7200) - 300
            print(f"[飞书] 获取 token 成功")
            return _cached_token
        else:
            print(f"[飞书] 获取 token 失败: {result.get('msg')}")
            return None
            
    except Exception as e:
        print(f"[飞书] 获取 token 请求失败: {e}")
        return None


def upload_image_to_feishu(image_path: str) -> Optional[str]:
    """
    上传图片到飞书并返回图片 URL。
    
    Args:
        image_path: 本地图片路径
    
    Returns:
        飞书图片 URL，失败返回 None
    """
    if not os.path.exists(image_path):
        print(f"[飞书图片] 文件不存在: {image_path}")
        return None
    
    # 获取 token
    token = _get_tenant_access_token()
    if not token:
        print(f"[飞书图片] 无法获取授权 token")
        return None
    
    # 使用 multipart/form-data 格式上传
    try:
        with open(image_path, "rb") as f:
            files = {"image": (os.path.basename(image_path), f, "image/png")}
            data = {"image_type": "message"}
            headers = {"Authorization": f"Bearer {token}"}
            
            import requests
            resp = requests.post(FEISHU_UPLOAD_URL, files=files, data=data, headers=headers, timeout=30)
            result = resp.json()
        
        if result.get("code") == 0:
            # 飞书 Markdown 中图片格式应该是 fileutil/{image_key}
            image_key = result.get("data", {}).get("image_key")
            img_url = f"fileutil/{image_key}"
            print(f"[飞书图片] 上传成功: {img_url}")
            return img_url
        else:
            print(f"[飞书图片] 上传失败: {result.get('msg')}")
            return None
            
    except Exception as e:
        print(f"[飞书图片] 请求失败: {e}")
        return None


if __name__ == "__main__":
    # 测试
    test_img = os.path.join(os.path.dirname(__file__), "..", "data", "global_valuation_2026-03-27.png")
    if os.path.exists(test_img):
        url = upload_image_to_feishu(test_img)
        print(f"图片URL: {url}")
