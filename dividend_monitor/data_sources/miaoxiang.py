"""
妙想（MiaoXiang）API 封装。

提供统一的 query() 入口，处理重试、频率限制和配额耗尽（status=113）场景。
当 API 返回 status=113 时立即抛出 RuntimeError，调用方应捕获并快速降级。
"""

import time
import requests

from ..config import API_BASE, MX_HEADERS


def query(tool_query: str, retries: int = 3, delay: float = 4.0) -> list:
    """
    向妙想 API 发送自然语言查询，返回 dataTableDTOList。

    Args:
        tool_query: 自然语言查询字符串，如 "红利低波H30269最近30天周线KDJ指标"。
        retries:    空结果时的最大重试次数。
        delay:      基础重试间隔（秒），每次乘以 (attempt+1) 递增。

    Returns:
        dataTableDTOList（列表），空结果时返回 []。

    Raises:
        RuntimeError: 当 status=113（今日配额已用尽）时立即抛出，不重试。
        Exception:    网络或解析异常在超过最大重试次数后向上传播。
    """
    for attempt in range(retries + 1):
        try:
            resp = requests.post(
                f"{API_BASE}/query",
                headers=MX_HEADERS,
                json={"toolQuery": tool_query},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            api_status = data.get("status")
            if api_status == 113:
                raise RuntimeError("妙想API今日配额已用尽（status=113）")

            dto    = (data.get("data") or {}).get("data") or {}
            result = dto.get("searchDataResultDTO") or {}
            items  = result.get("dataTableDTOList") or []
            if items:
                return items

            # 空结果可能是频率限制，稍等后重试
            if attempt < retries:
                time.sleep(delay * (attempt + 1))

        except RuntimeError:
            raise   # 配额错误直接向上传播，不重试
        except Exception:
            if attempt < retries:
                time.sleep(delay)
            else:
                raise

    return []
