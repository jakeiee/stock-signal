#!/usr/bin/env python3
"""
数据源自动故障转移装饰器
当主数据源连续失败≥N次时，自动切换到备用数据源
"""

import functools
from typing import Callable, Any, Dict, Optional
import time


# 全局失败计数器
_fail_counters: Dict[str, int] = {}
_switch_states: Dict[str, bool] = {}  # False=主源, True=备用源


def auto_failover(
    primary_func: Callable = None,
    fallback_func: Callable = None,
    max_failures: int = 3,
    reset_timeout: int = 300,
    key: str = "default"
):
    """
    数据源自动故障转移装饰器

    Args:
        primary_func: 主数据源函数（可选，作为装饰器参数）
        fallback_func: 备用数据源函数（可选，作为装饰器参数）
        max_failures: 最大失败次数，超过则切换
        reset_timeout: 恢复检查的超时时间（秒）
        key: 数据源标识key

    Returns:
        装饰器函数
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # 检查是否需要恢复主源
            _check_recovery(key, reset_timeout)

            # 如果已切换到备用源，直接调用备用函数
            if _switch_states.get(key, False):
                if fallback_func:
                    try:
                        return fallback_func(*args, **kwargs)
                    except Exception as e:
                        print(f"  ✗ 备用数据源也失败: {e}")
                        raise
                else:
                    print(f"  ⚠️ 已切换到备用数据源，但未提供fallback_func")
                    # 继续执行主函数（可能已恢复）

            # 调用主函数
            try:
                result = func(*args, **kwargs)
                # 成功，重置失败计数器
                _fail_counters[key] = 0
                return result
            except Exception as e:
                # 失败，增加计数器
                _fail_counters[key] = _fail_counters.get(key, 0) + 1
                current_failures = _fail_counters[key]

                print(f"  ⚠️ 主数据源失败 ({current_failures}/{max_failures}): {e}")

                # 检查是否需要切换
                if current_failures >= max_failures:
                    print(f"  🔴 主数据源连续失败 {current_failures} 次，自动切换到备用数据源")
                    _switch_states[key] = True

                    # 调用备用数据源
                    if fallback_func:
                        try:
                            return fallback_func(*args, **kwargs)
                        except Exception as fallback_e:
                            print(f"  ✗ 备用数据源也失败: {fallback_e}")
                            raise
                    else:
                        print(f"  ⚠️ 未提供备用数据源函数")
                        raise e

                # 未达到切换阈值，继续抛出异常
                raise e

        return wrapper

    # 支持两种用法：
    # 1. @auto_failover  (直接装饰函数)
    # 2. @auto_failover(fallback_func=xxx)  (带参数)
    if primary_func and callable(primary_func):
        # 用法1：直接装饰
        return decorator(primary_func)
    else:
        # 用法2：带参数
        return decorator


def _check_recovery(key: str, reset_timeout: int) -> None:
    """
    检查是否可以恢复主数据源

    策略：每隔reset_timeout秒，尝试使用主数据源
    """
    # 如果当前使用的是主数据源，不需要恢复
    if not _switch_states.get(key, False):
        return

    # 检查是否到了重试时间
    last_check_key = f"_{key}_last_check"
    current_time = time.time()
    last_check = _fail_counters.get(last_check_key, 0)

    if current_time - last_check < reset_timeout:
        return

    # 更新最后检查时间
    _fail_counters[last_check_key] = current_time

    print(f"  🔍 尝试恢复主数据源: {key}")
    # 注意：这里不实际调用主函数，只是标记可以尝试
    # 实际恢复由下一次调用失败触发（失败后重置计数器）


def get_failover_status(key: str = "default") -> Dict[str, Any]:
    """
    获取故障转移状态

    Args:
        key: 数据源标识key

    Returns:
        状态字典
    """
    return {
        "key": key,
        "fail_count": _fail_counters.get(key, 0),
        "switched": _switch_states.get(key, False),
        "status": "fallback" if _switch_states.get(key, False) else "primary"
    }


def reset_failover(key: str = "default") -> None:
    """
    手动重置故障转移状态

    Args:
        key: 数据源标识key
    """
    _fail_counters[key] = 0
    _switch_states[key] = False
    print(f"  ✓ 已重置故障转移状态: {key}")


# ═══════════════════════════════════════════════════════════════════
# 使用示例
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # 示例1：直接装饰函数
    @auto_failover(max_failures=3, key="valuation_api")
    def fetch_valuation_data(*args, **kwargs):
        """模拟主数据源"""
        print("  调用主数据源...")
        raise Exception("主数据源失败")

    def fetch_valuation_fallback(*args, **kwargs):
        """模拟备用数据源"""
        print("  调用备用数据源...")
        return {"status": "success", "source": "fallback"}

    # 测试：连续调用3次，应该触发切换
    print("测试1：连续失败触发切换")
    for i in range(5):
        try:
            result = fetch_valuation_data(fallback_func=fetch_valuation_fallback)
            print(f"  结果: {result}")
        except Exception as e:
            print(f"  异常: {e}")

    # 查看状态
    status = get_failover_status("valuation_api")
    print(f"\n状态: {status}")

    # 重置
    reset_failover("valuation_api")
    status = get_failover_status("valuation_api")
    print(f"重置后状态: {status}")
