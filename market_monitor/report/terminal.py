"""
终端报告输出。
"""

from typing import Dict, Any


def print_report(report_data: Dict[str, Any]) -> None:
    """打印报告到终端。"""
    print("=" * 60)
    print("市场监控日报")
    print("=" * 60)
    print(report_data)
