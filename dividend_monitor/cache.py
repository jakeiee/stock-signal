"""
估值数据本地缓存的读写封装。
缓存文件为 JSON，结构：{ "<index_code>": { ...valuation_result... } }
成功从妙想 API 获取估值后写入；API 不可用时读取缓存并标注 source='cache'。
"""

import json
from .config import VAL_CACHE_FILE


def load() -> dict:
    """
    读取本地估值缓存。
    返回 {code: result_dict}；文件不存在或解析失败时返回空字典。
    """
    try:
        with open(VAL_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save(cache: dict) -> None:
    """将估值结果写入本地缓存文件，写入失败时打印警告但不中断主流程。"""
    try:
        with open(VAL_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"  ⚠ 缓存写入失败: {e}")
