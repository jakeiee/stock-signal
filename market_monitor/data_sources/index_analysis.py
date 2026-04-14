"""
指数分析模块（重构后的板块分析核心）。

功能划分：
  1. 持仓分析：根据持仓ETF查找跟踪指数，分析指数的成交量、知行趋势线、形态
  2. ETF选股：根据东方财富选股API获取ETF，再分析其跟踪指数的形态

ETF_Index映射表：market_monitor/data/etf_index_mapping.csv
字段：etf_code, etf_name, index_code, index_name

使用示例：
    # 持仓分析
    from market_monitor.data_sources.index_analysis import (
        load_etf_index_mapping,
        get_index_history,
        analyze_index_trend,
        analyze_portfolio_indices,
    )

    mapping = load_etf_index_mapping()
    result = analyze_portfolio_indices(["159202", "159852"])

    # ETF选股
    from market_monitor.data_sources.index_analysis import screen_good_pattern_indices

    result = screen_good_pattern_indices()
"""

import os
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple

import pandas as pd
import numpy as np

from . import etf_selector
from ..analysis import zhixing

# ── 路径配置 ─────────────────────────────────────────────────────────────────
_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
ETF_INDEX_MAPPING_FILE = os.path.join(_DATA_DIR, "etf_index_mapping.csv")

# ── 形态分析参数 ─────────────────────────────────────────────────────────────
# 均线周期配置
MA_PERIODS = {
    "ma5": 5,
    "ma10": 10,
    "ma20": 20,
    "ma60": 60,
    "ma120": 120,
    "ma250": 250,
}

# 放量阈值（成交量超过均量的倍数）
VOLUME_SURGE_RATIO = 1.5

# 底部形态识别参数
BOTTOM_PATTERN_LOOKBACK = 20  # 识别底部形态的回看天数
BOTTOM_PATTERN_THRESHOLD = 0.15  # 价格波动不超过15%视为底部区域


# ── ETF_Index映射管理 ────────────────────────────────────────────────────────

def load_etf_index_mapping(filepath: Optional[str] = None) -> pd.DataFrame:
    """
    加载ETF_Index映射表。

    Args:
        filepath: 映射文件路径，默认使用 data/etf_index_mapping.csv

    Returns:
        包含 etf_code, etf_name, index_code, index_name, index_type 的DataFrame
    """
    if filepath is None:
        filepath = ETF_INDEX_MAPPING_FILE

    if not os.path.exists(filepath):
        print(f"[指数分析] 映射文件不存在: {filepath}")
        return pd.DataFrame()

    try:
        df = pd.read_csv(filepath, dtype={"etf_code": str, "index_code": str})
        # 填充缺失的 index_type 列
        if "index_type" not in df.columns:
            df["index_type"] = "未知"
        return df
    except Exception as e:
        print(f"[指数分析] 读取映射文件失败: {e}")
        return pd.DataFrame()


def get_index_by_etf(etf_code: str, mapping: Optional[pd.DataFrame] = None) -> Optional[Dict]:
    """
    根据ETF代码查找跟踪指数。

    Args:
        etf_code: ETF代码，如 "159202"
        mapping: 映射表DataFrame

    Returns:
        {"index_code": str, "index_name": str, "index_type": str} 或 None
    """
    if mapping is None:
        mapping = load_etf_index_mapping()

    if mapping.empty:
        return None

    row = mapping[mapping["etf_code"] == str(etf_code)]
    if row.empty:
        return None

    row = row.iloc[0]
    return {
        "index_code": row["index_code"],
        "index_name": row["index_name"],
        "index_type": row.get("index_type", "未知"),
    }


def add_etf_index_mapping(
    etf_code: str,
    etf_name: str,
    index_code: str,
    index_name: str,
    index_type: str = "未知",
    filepath: Optional[str] = None,
) -> bool:
    """
    添加ETF_Index映射关系。

    Args:
        etf_code: ETF代码
        etf_name: ETF名称
        index_code: 指数代码
        index_name: 指数名称
        index_type: 指数类型（宽基指数/行业主题/策略指数等）
        filepath: 映射文件路径

    Returns:
        是否添加成功
    """
    if filepath is None:
        filepath = ETF_INDEX_MAPPING_FILE

    # 加载现有映射
    mapping = load_etf_index_mapping(filepath)

    # 检查是否已存在
    if not mapping.empty and etf_code in mapping["etf_code"].values:
        print(f"[指数分析] ETF {etf_code} 已存在映射关系")
        return False

    # 添加新记录
    new_row = pd.DataFrame([{
        "etf_code": str(etf_code),
        "etf_name": etf_name,
        "index_code": str(index_code),
        "index_name": index_name,
        "index_type": index_type,
    }])

    mapping = pd.concat([mapping, new_row], ignore_index=True)

    # 保存
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        mapping.to_csv(filepath, index=False, encoding="utf-8")
        print(f"[指数分析] 已添加映射: {etf_code} -> {index_code}({index_name}) [{index_type}]")
        return True
    except Exception as e:
        print(f"[指数分析] 保存映射失败: {e}")
        return False


def batch_add_etf_index_mapping(
    mappings: List[Dict],
    filepath: Optional[str] = None,
) -> int:
    """
    批量添加ETF_Index映射。

    Args:
        mappings: [{"etf_code": "", "etf_name": "", "index_code": "", "index_name": "", "index_type": ""}, ...]
        filepath: 映射文件路径

    Returns:
        成功添加的数量
    """
    success_count = 0
    for m in mappings:
        if add_etf_index_mapping(
            etf_code=m["etf_code"],
            etf_name=m["etf_name"],
            index_code=m["index_code"],
            index_name=m["index_name"],
            index_type=m.get("index_type", "未知"),
            filepath=filepath,
        ):
            success_count += 1
    return success_count


# ── 指数数据获取 ──────────────────────────────────────────────────────────────

def _parse_index_code(code: str) -> Tuple[str, str]:
    """
    解析指数代码，返回 (指数代码, 交易所后缀)。

    A股指数示例：
        "000001.SH" -> ("000001", "SH")
        "399001.SZ" -> ("399001", "SZ")
        "000688"    -> ("000688", "SH")  # 默认沪市
        "HSIII.HI"  -> ("HSIII", "HI")  # 恒生指数
    """
    # 恒生/港股指数
    if "." in code and code.upper().endswith(".HI"):
        return code.split(".")[0], "HI"

    if "." in code:
        parts = code.split(".")
        return parts[0], parts[1]

    # 6开头是沪市，0开头是深市
    # 但科创50(000688)实际上是沪市
    if code.startswith("6") or code.startswith("9"):
        return code, "SH"
    elif code.startswith("0") or code.startswith("3") or code.startswith("4"):
        # 特殊处理：000688 是科创50（沪市）
        if code == "000688":
            return code, "SH"
        return code, "SZ"
    elif code.startswith("93"):
        return code, "CSI"  # 中证系列
    else:
        return code, "SH"  # 默认沪市


def _to_baostock_code(code: str, suffix: str = "") -> str:
    """
    转换为 baostock 格式的代码。

    Args:
        code: 指数代码，如 "000688"
        suffix: 交易所后缀

    Returns:
        baostock 格式，如 "sh.000688"
    """
    # 如果已经是完整格式
    if "." in code:
        return code.replace(".", ".").lower()

    # 推断交易所
    if suffix == "CSI" or code.startswith("93"):
        return f"sh.{code}"
    elif suffix == "SH" or code.startswith(("0", "6")):
        return f"sh.{code}"
    elif suffix == "SZ" or code.startswith(("1", "3", "4")):
        return f"sz.{code}"
    else:
        # 默认沪市
        return f"sh.{code}"


def fetch_index_history(
    index_code: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    period: str = "daily",
) -> Optional[pd.DataFrame]:
    """
    获取指数历史数据。

    Args:
        index_code: 指数代码，支持格式：
            - "000001.SH" / "000001.SZ" -> 上证/深证指数
            - "000688" (自动推断交易所) -> 科创50等
            - "399001.SZ" -> 深圳指数
            - "HSI" / "HSCEI" -> 恒生指数/国企指数
            - "HSTECH" -> 恒生科技
        start_date: 开始日期 "YYYY-MM-DD"
        end_date: 结束日期 "YYYY-MM-DD"

    Returns:
        DataFrame，包含 date/open/high/low/close/vol/change_pct 字段
    """
    # 解析代码
    code, suffix = _parse_index_code(index_code)

    # 标准化列名映射
    def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
        """标准化DataFrame列名"""
        column_mapping = {
            "日期": "date",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
            "成交额": "turnover",
            "涨跌幅": "change_pct",
            "涨跌额": "change",
            "换手率": "turnover_rate",
            "date": "date",
            "open": "open",
            "close": "close",
            "high": "high",
            "low": "low",
            "volume": "volume",
            "amount": "turnover",
        }
        df = df.rename(columns=column_mapping)

        # 过滤日期范围
        if start_date:
            start_dt = pd.to_datetime(start_date)
            df = df[df["date"] >= start_dt]
        if end_date:
            end_dt = pd.to_datetime(end_date)
            df = df[df["date"] <= end_dt]

        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        return df

    # 方法1: AkShare stock_zh_index_daily_em
    try:
        import akshare as ak

        # A股指数
        if suffix in ("SH", "SZ") or (len(code) == 6 and code.isdigit()):
            symbol = f"sh{code}" if suffix == "SH" or code.startswith(("0", "6")) else f"sz{code}"
            try:
                df = ak.stock_zh_index_daily_em(symbol=symbol)
                if df is not None and not df.empty:
                    return standardize_columns(df)
            except Exception:
                pass

        # 恒生系列
        if index_code.upper() in ("HSI", "HSCEI", "HSTECH", "HHCIO", "HSIII", "HSIII.HI", "HSHCI.HI"):
            try:
                df = ak.stock_hk_index_daily_em(symbol=index_code.upper().replace(".HI", ""))
                if df is not None and not df.empty:
                    return standardize_columns(df)
            except Exception:
                pass

    except ImportError:
        pass

    # 方法2: AkShare index_zh_a_hist（备用）
    try:
        import akshare as ak
        df = ak.index_zh_a_hist(symbol=code, period="daily")
        if df is not None and not df.empty:
            return standardize_columns(df)
    except Exception:
        pass

        # 方法3: Baostock 备用
        try:
            import baostock as bs

            # 登录
            bs.login()

            # 转换代码格式
            bs_code = _to_baostock_code(code, suffix)

            # 获取数据（baostock 需要 YYYY-MM-DD 格式）
            start_str = start_date if start_date else "2020-01-01"
            end_str = end_date if end_date else "2026-12-31"

            rs = bs.query_history_k_data_plus(
                bs_code,
                "date,open,high,low,close,volume,amount",
                start_date=start_str,
                end_date=end_str,
                frequency="d",
            )

            if rs and rs.error_code == "0":
                data_list = []
                while rs.next():
                    row = rs.get_row()
                    if row:
                        data_list.append(row)

                if data_list:
                    df = pd.DataFrame(data_list, columns=rs.fields)
                    df = df.rename(columns={"amount": "turnover"})
                    bs.logout()
                    return standardize_columns(df)

            bs.logout()
        except ImportError:
            pass
        except Exception as e:
            print(f"[指数分析] baostock 备用失败: {e}")
            try:
                import baostock as bs
                bs.logout()
            except Exception:
                pass

    print(f"[指数分析] 获取指数 {index_code} 数据失败（所有数据源均不可用）")
    return None


def get_index_history(
    index_code: str,
    index_name: str,
    lookback_days: int = 250,
) -> Optional[pd.DataFrame]:
    """
    获取指数历史数据（便捷封装）。

    Args:
        index_code: 指数代码
        index_name: 指数名称（用于日志）
        lookback_days: 回看天数

    Returns:
        DataFrame
    """
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

    print(f"[指数分析] 获取 {index_name}({index_code}) 历史数据...", end=" ", flush=True)
    df = fetch_index_history(index_code, start_date, end_date)

    if df is not None and not df.empty:
        print(f"✓ ({len(df)} 条)")
    else:
        print("✗ 失败")

    return df


# ── 形态分析 ─────────────────────────────────────────────────────────────────

def calculate_volume_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算成交量相关指标。

    添加字段：
        - ma_volume_5/20/60: 成交量均线
        - volume_ratio: 今日成交量/5日均量
        - volume_surge: 是否放量（超过均量1.5倍）
    """
    if df is None or len(df) < 60:
        return df

    result = df.copy()

    # 成交量均线
    result["ma_volume_5"] = result["volume"].rolling(window=5, min_periods=1).mean()
    result["ma_volume_20"] = result["volume"].rolling(window=20, min_periods=1).mean()
    result["ma_volume_60"] = result["volume"].rolling(window=60, min_periods=1).mean()

    # 放量倍数
    result["volume_ratio"] = result["volume"] / result["ma_volume_5"].shift(1)
    result["volume_surge"] = result["volume_ratio"] > VOLUME_SURGE_RATIO

    return result


def detect_ma_breakout(df: pd.DataFrame) -> Dict:
    """
    检测均线突破。

    Returns:
        {
            "breakout_ma20": bool,   # 突破20日均线
            "breakout_ma60": bool,   # 突破60日均线
            "ma20_slope": float,     # 20日均线斜率
            "ma60_slope": float,     # 60日均线斜率
            "price_vs_ma20": float,  # 价格/MA20比率
            "price_vs_ma60": float,  # 价格/MA60比率
        }
    """
    if df is None or len(df) < 65:
        return {}

    result = df.copy()

    # 计算均线
    result["ma20"] = result["close"].rolling(window=20, min_periods=20).mean()
    result["ma60"] = result["close"].rolling(window=60, min_periods=60).mean()
    result["ma120"] = result["close"].rolling(window=120, min_periods=120).mean()

    latest = result.iloc[-1]
    prev5 = result.iloc[-6] if len(result) >= 6 else latest

    # 突破判断：今日收盘价 > 均线，且前一日收盘价 <= 均线
    breakout_ma20 = (latest["close"] > latest["ma20"]) and (result.iloc[-2]["close"] <= result.iloc[-2]["ma20"] if len(result) >= 2 else False)
    breakout_ma60 = (latest["close"] > latest["ma60"]) and (result.iloc[-2]["close"] <= result.iloc[-2]["ma60"] if len(result) >= 2 else False)

    # 均线斜率（5日变化百分比）
    ma20_slope = (latest["ma20"] - prev5["ma20"]) / prev5["ma20"] * 100 if prev5["ma20"] > 0 else 0
    ma60_slope = (latest["ma60"] - prev5["ma60"]) / prev5["ma60"] * 100 if prev5["ma60"] > 0 else 0

    # 价格与均线比率
    price_vs_ma20 = (latest["close"] - latest["ma20"]) / latest["ma20"] * 100 if latest["ma20"] > 0 else 0
    price_vs_ma60 = (latest["close"] - latest["ma60"]) / latest["ma60"] * 100 if latest["ma60"] > 0 else 0

    return {
        "breakout_ma20": breakout_ma20,
        "breakout_ma60": breakout_ma60,
        "ma20_slope": round(ma20_slope, 2),
        "ma60_slope": round(ma60_slope, 2),
        "price_vs_ma20": round(price_vs_ma20, 2),
        "price_vs_ma60": round(price_vs_ma60, 2),
    }


def detect_volume_surge(df: pd.DataFrame) -> Dict:
    """
    检测放量上涨。

    Returns:
        {
            "volume_surge": bool,      # 是否放量
            "volume_ratio": float,     # 放量倍数
            "price_up": bool,          # 价格是否上涨
            "volume_price_match": bool,# 量价配合（放量上涨）
        }
    """
    if df is None or len(df) < 10:
        return {}

    result = calculate_volume_indicators(df)

    latest = result.iloc[-1]
    prev = result.iloc[-2] if len(result) >= 2 else latest

    volume_ratio = latest.get("volume_ratio", 1)
    volume_surge = latest.get("volume_surge", False)
    price_up = latest["close"] > prev["close"]
    volume_price_match = volume_surge and price_up

    return {
        "volume_surge": volume_surge,
        "volume_ratio": round(volume_ratio, 2),
        "price_up": price_up,
        "volume_price_match": volume_price_match,
    }


def detect_bottom_pattern(df: pd.DataFrame) -> Dict:
    """
    检测底部形态。

    识别方法：
        1. 近期价格波动收窄（振幅 < 15%）
        2. 成交量温和放大
        3. 价格创新低后反弹

    Returns:
        {
            "has_bottom_pattern": bool,  # 是否有底部形态
            "bottom_type": str,          # 底部类型：double_bottom/w底/平台底
            "bottom_strength": float,    # 底部强度 0-1
            "days_from_bottom": int,     # 距底部天数
        }
    """
    if df is None or len(df) < BOTTOM_PATTERN_LOOKBACK:
        return {}

    result = calculate_volume_indicators(df)

    # 取最近N天
    recent = result.tail(BOTTOM_PATTERN_LOOKBACK).copy()

    # 计算波动率
    recent["price_range"] = (recent["high"] - recent["low"]) / recent["close"].mean()
    avg_range = recent["price_range"].mean()

    # 检查是否在底部区域（波动收窄）
    in_bottom_zone = avg_range < BOTTOM_PATTERN_THRESHOLD

    # 找最低价位置
    lowest_idx = recent["low"].idxmin()
    lowest_date = recent.loc[lowest_idx, "date"]
    days_from_bottom = (result["date"].max() - lowest_date).days

    # 判断是否有反弹
    after_low_data = result[result["date"] > lowest_date]
    has_rebound = len(after_low_data) > 0 and after_low_data["close"].iloc[-1] > recent["low"].min() * 1.02

    # 成交量是否温和放大
    first_half_vol = recent.iloc[:len(recent)//2]["volume"].mean()
    second_half_vol = recent.iloc[len(recent)//2:]["volume"].mean()
    vol_increasing = second_half_vol > first_half_vol * 0.9

    # 底部形态判定
    has_bottom_pattern = in_bottom_zone and days_from_bottom <= 10 and has_rebound

    # 底部强度
    bottom_strength = 0.0
    if in_bottom_zone:
        bottom_strength += 0.3
    if has_rebound:
        bottom_strength += 0.3
    if vol_increasing:
        bottom_strength += 0.2
    if days_from_bottom <= 5:
        bottom_strength += 0.2

    # 简化判断底部类型
    if not has_bottom_pattern:
        bottom_type = "无明显底部"
    elif days_from_bottom <= 3:
        bottom_type = "新底形成"
    elif days_from_bottom <= 7:
        bottom_type = "反弹确认"
    else:
        bottom_type = "底部盘整"

    return {
        "has_bottom_pattern": has_bottom_pattern,
        "bottom_type": bottom_type,
        "bottom_strength": round(bottom_strength, 2),
        "days_from_bottom": days_from_bottom,
    }


# ── 综合指数分析 ─────────────────────────────────────────────────────────────

def analyze_index_trend(
    index_code: str,
    index_name: str,
    lookback_days: int = 250,
) -> Dict:
    """
    综合分析指数：成交量、知行趋势线、形态。

    Args:
        index_code: 指数代码
        index_name: 指数名称
        lookback_days: 回看天数

    Returns:
        综合分析结果
    """
    result = {
        "index_code": index_code,
        "index_name": index_name,
    }

    # 1. 获取历史数据
    df = get_index_history(index_code, index_name, lookback_days)
    if df is None or df.empty:
        result["error"] = "获取数据失败"
        return result

    result["data_date"] = df["date"].max().strftime("%Y-%m-%d") if len(df) > 0 else None
    result["last_close"] = round(df["close"].iloc[-1], 2)
    result["change_pct"] = round(df["change_pct"].iloc[-1], 2) if "change_pct" in df.columns else 0

    # 2. 知行趋势线分析
    try:
        trend_status = zhixing.get_trend_status(df)
        result.update({
            "signal": trend_status.get("signal", "HOLD"),
            "position": trend_status.get("position", ""),
            "trend_direction": trend_status.get("trend_direction", ""),
            "short_trend": trend_status.get("short_trend"),
            "long_trend": trend_status.get("long_trend"),
            "trend_diff_pct": trend_status.get("trend_diff_pct"),
            "kdj_k": trend_status.get("kdj_k"),
            "kdj_d": trend_status.get("kdj_d"),
            "kdj_j": trend_status.get("kdj_j"),
        })
    except Exception as e:
        print(f"[指数分析] 知行趋势线计算失败: {e}")

    # 3. 均线突破检测
    try:
        ma_breakout = detect_ma_breakout(df)
        result.update(ma_breakout)
    except Exception as e:
        print(f"[指数分析] 均线突破检测失败: {e}")

    # 4. 放量检测
    try:
        vol_analysis = detect_volume_surge(df)
        result.update(vol_analysis)
    except Exception as e:
        print(f"[指数分析] 放量检测失败: {e}")

    # 5. 底部形态检测
    try:
        bottom_pattern = detect_bottom_pattern(df)
        result.update(bottom_pattern)
    except Exception as e:
        print(f"[指数分析] 底部形态检测失败: {e}")

    # 6. 形态评分
    result["pattern_score"] = _calculate_pattern_score(result)

    return result


def _calculate_pattern_score(analysis: Dict) -> float:
    """
    计算形态综合评分 (0-100)。

    评分维度：
        - 知行趋势线信号 (40分)
        - 均线突破 (20分)
        - 放量配合 (20分)
        - 底部形态 (20分)
    """
    score = 0.0

    # 知行趋势线信号 (40分)
    signal = analysis.get("signal", "")
    position = analysis.get("position", "")
    if signal == "BUY":
        score += 40
    elif "多头排列" in position:
        score += 30
    elif signal == "HOLD_BULL":
        score += 25
    elif signal == "HOLD_NEUTRAL":
        score += 10

    # 均线突破 (20分)
    if analysis.get("breakout_ma20"):
        score += 10
    if analysis.get("breakout_ma60"):
        score += 10
    elif analysis.get("price_vs_ma20", 0) > 0:
        score += 5
    elif analysis.get("price_vs_ma60", 0) > 0:
        score += 3

    # 放量配合 (20分)
    if analysis.get("volume_price_match"):
        score += 20
    elif analysis.get("volume_surge"):
        score += 10

    # 底部形态 (20分)
    if analysis.get("has_bottom_pattern"):
        score += 20 * analysis.get("bottom_strength", 0.5)

    return round(score, 1)


def is_good_pattern(analysis: Dict) -> bool:
    """
    判断是否为好的形态。

    标准：
        - 形态评分 >= 60
        - 知行趋势线为多头排列或买入信号
        - 有放量或突破迹象
    """
    if analysis.get("error"):
        return False

    # 形态评分
    if analysis.get("pattern_score", 0) < 60:
        return False

    # 知行趋势线
    signal = analysis.get("signal", "")
    position = analysis.get("position", "")
    if signal not in ("BUY", "HOLD_BULL") and "多头排列" not in position:
        return False

    return True


# ── 持仓分析流程 ─────────────────────────────────────────────────────────────

def analyze_portfolio_indices(
    etf_codes: List[str],
    etf_names: Optional[List[str]] = None,
    mapping: Optional[pd.DataFrame] = None,
) -> Dict:
    """
    持仓分析：根据ETF列表查找跟踪指数，分析指数形态。

    Args:
        etf_codes: ETF代码列表
        etf_names: ETF名称列表（可选）
        mapping: ETF_Index映射表

    Returns:
        {
            "etf_count": int,
            "index_count": int,
            "indices": [分析结果列表],
            "summary": {...},
            "missing_mapping": [无法映射的ETF列表],
        }
    """
    if mapping is None:
        mapping = load_etf_index_mapping()

    if etf_names is None:
        etf_names = [None] * len(etf_codes)

    print(f"\n[持仓分析] 开始分析 {len(etf_codes)} 只ETF...")

    indices = []
    missing_mapping = []

    for i, (etf_code, etf_name) in enumerate(zip(etf_codes, etf_names)):
        # 查找跟踪指数
        mapping_info = get_index_by_etf(etf_code, mapping)

        if mapping_info is None:
            print(f"  [{i+1}/{len(etf_codes)}] {etf_code} {etf_name or ''} - 无法找到跟踪指数")
            missing_mapping.append({"etf_code": etf_code, "etf_name": etf_name})
            continue

        index_code = mapping_info["index_code"]
        index_name = mapping_info["index_name"]

        print(f"  [{i+1}/{len(etf_codes)}] {etf_code}({etf_name or ''}) -> {index_name}({index_code})")

        # 分析指数
        analysis = analyze_index_trend(index_code, index_name)
        analysis["etf_code"] = etf_code
        analysis["etf_name"] = etf_name

        indices.append(analysis)

    # 去重（按index_code）
    unique_indices = {}
    for idx in indices:
        code = idx.get("index_code", "")
        if code not in unique_indices:
            unique_indices[code] = idx

    unique_indices = list(unique_indices.values())

    # 汇总统计
    summary = {
        "total_etfs": len(etf_codes),
        "total_indices": len(unique_indices),
        "good_pattern_count": sum(1 for i in unique_indices if is_good_pattern(i)),
        "avg_pattern_score": round(sum(i.get("pattern_score", 0) for i in unique_indices) / len(unique_indices), 1) if unique_indices else 0,
        "bullish_count": sum(1 for i in unique_indices if "多头排列" in i.get("position", "")),
        "buy_signals": [i["index_name"] for i in unique_indices if i.get("signal") == "BUY"],
        "missing_count": len(missing_mapping),
    }

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "etf_count": len(etf_codes),
        "index_count": len(unique_indices),
        "indices": unique_indices,
        "summary": summary,
        "missing_mapping": missing_mapping,
    }


# ── ETF选股流程 ───────────────────────────────────────────────────────────────

def screen_good_pattern_indices(
    etf_types: Optional[List[str]] = None,
    scale_min: float = 5000,
    kdj_op: str = "<",
    kdj_value: float = 0,
    mapping: Optional[pd.DataFrame] = None,
) -> Dict:
    """
    ETF选股：根据东方财富选股API获取ETF，分析跟踪指数形态。

    Args:
        etf_types: ETF类型列表，如 ["行业主题", "宽基指数"]
        scale_min: 最小资产规模（万元）
        kdj_op: KDJ比较操作符
        kdj_value: KDJ目标值
        mapping: ETF_Index映射表

    Returns:
        {
            "etf_count": int,
            "unique_index_count": int,
            "good_pattern_indices": [好形态指数列表],
            "all_indices": [所有分析结果],
            "summary": {...},
        }
    """
    if mapping is None:
        mapping = load_etf_index_mapping()

    print("\n[ETF选股] 开始选股流程...")

    # 1. 获取KDJ超卖ETF
    print("[ETF选股] Step 1: 获取KDJ超卖ETF...")
    if etf_types is None:
        etf_types = ["行业主题", "宽基指数"]

    etf_filter = etf_selector.ETFFilter()
    etf_filter.add_types(etf_types)
    etf_filter.add_scale_min(scale_min)
    etf_filter.add_kdj_condition(kdj_op, kdj_value)
    etf_filter.sort_by("kdj", "asc")
    etf_filter.set_page(1, 100)

    screening_result = etf_filter.execute()

    if not screening_result.get("success"):
        return {
            "error": "ETF筛选失败",
            "error_detail": screening_result.get("error"),
        }

    etfs = screening_result.get("etfs", [])
    print(f"[ETF选股] 找到 {len(etfs)} 只符合条件的ETF")

    if not etfs:
        return {
            "etf_count": 0,
            "unique_index_count": 0,
            "good_pattern_indices": [],
            "all_indices": [],
            "summary": {},
        }

    # 2. 映射到指数并去重
    print("[ETF选股] Step 2: 映射到跟踪指数...")
    etf_to_analyze = []
    already_analyzed = set()

    for etf in etfs:
        etf_code = etf.get("code", "")
        mapping_info = get_index_by_etf(etf_code, mapping)

        if mapping_info is None:
            # 无法自动映射，跳过
            continue

        index_code = mapping_info["index_code"]

        # 去重
        if index_code in already_analyzed:
            continue

        already_analyzed.add(index_code)
        etf_to_analyze.append({
            "etf": etf,
            "index_code": index_code,
            "index_name": mapping_info["index_name"],
        })

    print(f"[ETF选股] 去重后 {len(etf_to_analyze)} 只唯一指数需要分析")

    # 3. 分析指数形态
    print("[ETF选股] Step 3: 分析指数形态...")
    all_indices = []
    for item in etf_to_analyze:
        index_code = item["index_code"]
        index_name = item["index_name"]
        etf = item["etf"]

        print(f"       分析 {index_name}({index_code})...", end=" ", flush=True)

        analysis = analyze_index_trend(index_code, index_name)
        analysis["etf_code"] = etf.get("code")
        analysis["etf_name"] = etf.get("name")
        analysis["etf_kdj"] = etf.get("kdj_value")

        all_indices.append(analysis)

        if is_good_pattern(analysis):
            print(f"✓ 好形态({analysis.get('pattern_score')}分)")
        else:
            print(f"○ 评分{analysis.get('pattern_score')}分")

    # 4. 筛选好形态
    good_pattern_indices = [i for i in all_indices if is_good_pattern(i)]
    good_pattern_indices.sort(key=lambda x: x.get("pattern_score", 0), reverse=True)

    # 5. 汇总
    summary = {
        "total_etfs": len(etfs),
        "unique_indices": len(all_indices),
        "good_pattern_count": len(good_pattern_indices),
        "avg_pattern_score": round(sum(i.get("pattern_score", 0) for i in all_indices) / len(all_indices), 1) if all_indices else 0,
    }

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "etf_count": len(etfs),
        "unique_index_count": len(all_indices),
        "good_pattern_indices": good_pattern_indices,
        "all_indices": all_indices,
        "summary": summary,
    }


# ── 报告输出 ─────────────────────────────────────────────────────────────────

def print_index_analysis(analysis: Dict) -> None:
    """打印指数分析结果"""
    if analysis.get("error"):
        print(f"错误: {analysis['error']}")
        return

    print(f"\n指数: {analysis.get('index_name', '')}({analysis.get('index_code', '')})")
    print(f"日期: {analysis.get('data_date', 'N/A')}")
    print(f"收盘价: {analysis.get('last_close', 'N/A')}  涨跌幅: {analysis.get('change_pct', 0):+.2f}%")

    print("\n知行趋势线:")
    print(f"  信号: {analysis.get('signal', 'N/A')}")
    print(f"  排列: {analysis.get('position', 'N/A')}")
    print(f"  趋势: {analysis.get('trend_direction', 'N/A')}")
    print(f"  KDJ: K={analysis.get('kdj_k', 'N/A')}, D={analysis.get('kdj_d', 'N/A')}, J={analysis.get('kdj_j', 'N/A')}")

    print("\n均线分析:")
    print(f"  突破MA20: {'是' if analysis.get('breakout_ma20') else '否'}")
    print(f"  突破MA60: {'是' if analysis.get('breakout_ma60') else '否'}")
    print(f"  价格/MA20: {analysis.get('price_vs_ma20', 0):+.2f}%")
    print(f"  价格/MA60: {analysis.get('price_vs_ma60', 0):+.2f}%")

    print("\n成交量:")
    print(f"  放量: {'是' if analysis.get('volume_surge') else '否'} (放量{analysis.get('volume_ratio', 1):.1f}倍)")
    print(f"  量价配合: {'是' if analysis.get('volume_price_match') else '否'}")

    print("\n底部形态:")
    print(f"  底部形态: {analysis.get('bottom_type', '无')}")
    print(f"  底部强度: {analysis.get('bottom_strength', 0)*100:.0f}%")

    print(f"\n形态评分: {analysis.get('pattern_score', 0)}/100")


def print_portfolio_analysis(result: Dict) -> None:
    """打印持仓分析报告（详细版：原数据 + 加工逻辑 + 输出结果）"""
    print("\n" + "=" * 80)
    print(f"📊 持仓指数分析报告 - {result.get('generated_at', '')}")
    print("=" * 80)

    summary = result.get("summary", {})

    # ── 一、汇总统计（输出结果）───────────────────────────────────────────────
    print(f"\n{'='*40}")
    print(f"【输出结果】汇总统计")
    print(f"{'='*40}")
    print(f"  ETF数量: {summary.get('total_etfs', 0)}")
    print(f"  指数数量: {summary.get('total_indices', 0)}")
    print(f"  好形态数量: {summary.get('good_pattern_count', 0)}")
    print(f"  平均评分: {summary.get('avg_pattern_score', 0)}")
    print(f"  多头排列: {summary.get('bullish_count', 0)}")

    # 买入信号
    buy_signals = summary.get("buy_signals", [])
    if buy_signals:
        print(f"\n🟢 买入信号 ({len(buy_signals)}只)")
        for name in buy_signals:
            print(f"    {name}")

    # 缺失映射
    missing = result.get("missing_mapping", [])
    if missing:
        print(f"\n⚠️ 无法映射 ({len(missing)}只)")
        for m in missing:
            print(f"    {m['etf_code']} {m['etf_name'] or ''}")

    # ── 二、每个指数的详细分析（包含原数据 + 加工逻辑）────────────────────────
    indices = result.get("indices", [])
    if indices:
        print(f"\n{'='*40}")
        print(f"【原数据 → 加工步骤 → 输出结果】指数明细")
        print(f"{'='*40}")

        for idx in sorted(indices, key=lambda x: x.get("pattern_score", 0), reverse=True):
            _print_single_index_analysis(idx)

    print("\n" + "=" * 80)


def _print_single_index_analysis(idx: Dict) -> None:
    """打印单个指数的详细分析（包含原数据、加工逻辑、输出）"""
    index_code = idx.get("index_code", "")
    index_name = idx.get("index_name", "")
    index_type = idx.get("index_type", "未知")
    etf_code = idx.get("etf_code", "")
    etf_name = idx.get("etf_name", "")

    print(f"\n{'-'*60}")
    print(f"▶ {index_name}({index_code})")
    print(f"  来源: {etf_name or 'ETF'}({etf_code})")
    print(f"  类型: {index_type}")
    print(f"{'-'*60}")

    # ── Step 1: 原数据 ─────────────────────────────────────────────────────
    print(f"\n  【1/4】原数据")
    print(f"  ├─ 数据日期: {idx.get('data_date', 'N/A')}")
    print(f"  ├─ 收盘价: {idx.get('last_close', 'N/A')}")
    print(f"  └─ 涨跌幅: {idx.get('change_pct', 0):+.2f}%")

    # ── Step 2: 知行趋势线（数据加工逻辑）──────────────────────────────────
    signal = idx.get("signal", "")
    position = idx.get("position", "")
    trend_direction = idx.get("trend_direction", "")

    print(f"\n  【2/4】知行趋势线分析")
    print(f"  ├─ 原始数据: 收盘价序列(close)")
    print(f"  ├─ 加工步骤:")
    print(f"  │    ① 短期趋势线 = EMA(EMA(C,10),10)  # 双重EMA平滑")
    print(f"  │    ② 多空趋势线 = (MA(C,14)+MA(C,28)+MA(C,57)+MA(C,114))/4  # 4周期均线平均")
    print(f"  │    ③ 计算KDJ: K/D/J = f(RSV)")
    print(f"  │    ④ 金叉/死叉判定")
    print(f"  └─ 输出结果:")
    print(f"       信号: {signal}")
    print(f"       排列: {position}")
    print(f"       趋势: {trend_direction}")
    kdj_k = idx.get("kdj_k", 0)
    kdj_d = idx.get("kdj_d", 0)
    kdj_j = idx.get("kdj_j", 0)
    print(f"       KDJ: K={kdj_k:.2f}, D={kdj_d:.2f}, J={kdj_j:.2f}")

    # ── Step 3: 均线突破（数据加工逻辑）────────────────────────────────────
    breakout_ma20 = idx.get("breakout_ma20", False)
    breakout_ma60 = idx.get("breakout_ma60", False)
    price_vs_ma20 = idx.get("price_vs_ma20", 0)
    price_vs_ma60 = idx.get("price_vs_ma60", 0)

    print(f"\n  【3/4】均线突破分析")
    print(f"  ├─ 原始数据: 收盘价序列(close)")
    print(f"  ├─ 加工步骤:")
    print(f"  │    ① MA20 = rolling_mean(close, 20)")
    print(f"  │    ② MA60 = rolling_mean(close, 60)")
    print(f"  │    ③ 突破判定: 今日收盘 > 均线 AND 前日收盘 <= 均线")
    print(f"  └─ 输出结果:")
    print(f"       突破MA20: {'是 ✓' if breakout_ma20 else '否'}")
    print(f"       突破MA60: {'是 ✓' if breakout_ma60 else '否'}")
    print(f"       价格偏离MA20: {price_vs_ma20:+.2f}%")
    print(f"       价格偏离MA60: {price_vs_ma60:+.2f}%")

    # ── Step 4: 放量与底部形态（数据加工逻辑）──────────────────────────────
    volume_surge = idx.get("volume_surge", False)
    volume_ratio = idx.get("volume_ratio", 1)
    volume_price_match = idx.get("volume_price_match", False)
    has_bottom = idx.get("has_bottom_pattern", False)
    bottom_type = idx.get("bottom_type", "无")
    bottom_strength = idx.get("bottom_strength", 0)

    print(f"\n  【4/4】放量与形态分析")
    print(f"  ├─ 原始数据: 成交量序列(volume)")
    print(f"  ├─ 加工步骤:")
    print(f"  │    ① MA5量 = rolling_mean(volume, 5)")
    print(f"  │    ② 放量倍数 = 今日成交量 / 昨日MA5量")
    print(f"  │    ③ 放量判定: 倍数 > 1.5")
    print(f"  │    ④ 底部形态: 波动收窄 + 反弹确认 + 成交量温和放大")
    print(f"  └─ 输出结果:")
    print(f"       放量: {'是 ✓' if volume_surge else '否'} (放量{volume_ratio:.1f}倍)")
    print(f"       量价配合: {'是 ✓' if volume_price_match else '否'}")
    print(f"       底部形态: {bottom_type if has_bottom else '无'}")
    print(f"       底部强度: {bottom_strength*100:.0f}%")

    # ── 综合评分 ─────────────────────────────────────────────────────────
    pattern_score = idx.get("pattern_score", 0)
    is_good = is_good_pattern(idx)

    print(f"\n  【综合评分】")
    print(f"  ├─ 评分维度:")
    print(f"  │    知行趋势线信号 (40分)")
    print(f"  │    均线突破 (20分)")
    print(f"  │    放量配合 (20分)")
    print(f"  │    底部形态 (20分)")
    print(f"  └─ 形态评分: {pattern_score}/100 {'✓ 好形态' if is_good else ''}")


def print_selector_result(result: Dict) -> None:
    """打印选股结果"""
    if result.get("error"):
        print(f"选股失败: {result['error']}")
        return

    print("\n" + "=" * 60)
    print(f"🎯 ETF选股结果 - {result.get('generated_at', '')}")
    print("=" * 60)

    summary = result.get("summary", {})

    print(f"\n📊 筛选统计")
    print(f"  符合条件ETF: {summary.get('total_etfs', 0)}")
    print(f"  唯一指数: {summary.get('unique_indices', 0)}")
    print(f"  好形态指数: {summary.get('good_pattern_count', 0)}")
    print(f"  平均评分: {summary.get('avg_pattern_score', 0)}")

    # 好形态指数
    good_indices = result.get("good_pattern_indices", [])
    if good_indices:
        print(f"\n🟢 好形态指数 TOP{len(good_indices)}")
        print("-" * 60)
        print(f"{'指数名称':<20} {'评分':<6} {'信号':<10} {'排列':<10} {'ETF_KDJ':<8}")
        print("-" * 60)

        for idx in good_indices[:10]:
            name = idx.get("index_name", "")[:18]
            score = idx.get("pattern_score", 0)
            signal = idx.get("signal", "")
            position = idx.get("position", "")[:8]
            kdj = idx.get("etf_kdj", "N/A")
            if isinstance(kdj, float):
                kdj = f"{kdj:.1f}"
            print(f"{name:<20} {score:<6} {signal:<10} {position:<10} {kdj:<8}")

    print("=" * 60)


# ── 主入口 ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # 测试代码

    # 测试1：加载映射表
    print("[测试] 加载ETF_Index映射表...")
    mapping = load_etf_index_mapping()
    print(f"已加载 {len(mapping)} 条映射")

    # 测试2：持仓分析
    print("\n[测试] 持仓分析...")
    test_etfs = ["159202", "159852", "159869", "506008", "562500"]
    result = analyze_portfolio_indices(test_etfs, mapping=mapping)
    print_portfolio_analysis(result)

    # 测试3：选股
    print("\n[测试] ETF选股...")
    selector_result = screen_good_pattern_indices(mapping=mapping)
    print_selector_result(selector_result)
