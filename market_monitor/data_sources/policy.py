"""
政策面数据源：货币政策事件。

数据来源：
- M2/M1 同比、社融（来源：东方财富/国家统计局）
- 10年国债收益率（来源：ChinaMoney）
- LPR、存款准备金率（来源：AkShare，如可用）
"""

from datetime import datetime
from typing import Dict, Any

from . import fundamental as fundamental_mod


def fetch() -> Dict[str, Any]:
    """获取政策事件。"""
    return fetch_policy_events()


def fetch_policy_events() -> Dict[str, Any]:
    """
    获取政策事件列表。
    
    货币政策数据从 fundamental.py 的 fetch_macro_liquidity() 获取：
    - period: 数据周期（如 "2026-03"）
    - m2_yoy: M2 同比增速（%）
    - m1_yoy: M1 同比增速（%）
    - bond_10y: 10年国债收益率（%）
    - social_fin_yoy: 社融存量同比（%）
    - source: 数据来源标识
    """
    error_msg = None
    
    # 从 fundamental.py 获取流动性数据（M2/社融/国债）
    try:
        liq_result = fundamental_mod.fetch_macro_liquidity()
        if "error" in liq_result:
            error_msg = liq_result.get("error", "流动性数据获取失败")
            monetary = None
        else:
            # 转换字段名以匹配飞书报告的预期格式
            liq_data = liq_result
            monetary = {
                "date": liq_data.get("period", ""),
                "period": liq_data.get("period", ""),
                "m2_yoy": liq_data.get("m2_yoy"),
                "m1_yoy": liq_data.get("m1_yoy"),
                "bond_10y": liq_data.get("bond_10y"),
                "bond_10y_code": liq_data.get("bond_10y_code", ""),
                "social_fin_yoy": liq_data.get("social_fin_yoy"),
                # LPR/准备金率暂无数据源
                "lpr_1y": None,
                "lpr_5y": None,
                "rrr_large": None,
                "rrr_small": None,
                "source": liq_data.get("source", "东方财富"),
                "error": None,
            }
    except Exception as e:
        error_msg = f"获取货币政策数据异常: {e}"
        monetary = None
    
    # 尝试从 AkShare 获取 LPR 和准备金率（如可用）
    if monetary:
        try:
            import akshare as ak
            
            # 获取最新 LPR
            try:
                lpr_df = ak.lpr_history()
                if lpr_df is not None and not lpr_df.empty:
                    latest = lpr_df.iloc[0]
                    lpr_cols = [c for c in lpr_df.columns if '1' in str(c) and '年' in str(c)]
                    if lpr_cols:
                        monetary["lpr_1y"] = float(latest.get(lpr_cols[0], 0)) or None
                    lpr_5y_cols = [c for c in lpr_df.columns if '5' in str(c) and '年' in str(c)]
                    if lpr_5y_cols:
                        monetary["lpr_5y"] = float(latest.get(lpr_5y_cols[0], 0)) or None
            except Exception:
                pass  # LPR 获取失败不影响主逻辑
            
            # 获取存款准备金率
            try:
                rrr_df = ak.rate_rrr()
                if rrr_df is not None and not rrr_df.empty:
                    latest = rrr_df.iloc[0]
                    # 尝试找到大小行准备金率列
                    for col in rrr_df.columns:
                        if '大型' in str(col):
                            monetary["rrr_large"] = float(latest.get(col, 0)) or None
                        elif '中小' in str(col) or '小型' in str(col):
                            monetary["rrr_small"] = float(latest.get(col, 0)) or None
            except Exception:
                pass  # RRR 获取失败不影响主逻辑
                
        except ImportError:
            # AkShare 未安装，跳过额外数据
            pass
        except Exception:
            # 其他错误不影响主逻辑
            pass
    
    return {
        "data": {
            "monetary": monetary,
            "events": [],  # 政策事件列表暂未实现
        },
        "error": error_msg,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
