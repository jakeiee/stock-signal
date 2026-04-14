"""
知行趋势线指标计算模块。

基于通达信公式实现：
  - 短期趋势线：EMA(EMA(C,10),10) - 双重EMA平滑
  - 多空趋势线：(MA(C,14)+MA(C,28)+MA(C,57)+MA(C,114))/4 - 4周期均线平均

选股信号：
  - 买入信号（金叉）：短期趋势线上穿多空趋势线
  - 卖出信号（死叉）：短期趋势线下穿多空趋势线
  - 多头排列：短期 > 多空 且 价 > 短期

使用示例：
    from market_monitor.analysis.zhixing import (
        calculate_short_trend, calculate_long_trend, 
        generate_signal, analyze_stock
    )
    
    df = get_stock_history("000001")
    signal = generate_signal(df)
"""

import os
import sys
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple

import pandas as pd
import numpy as np

# ── 知行趋势线参数 ─────────────────────────────────────────────────────────────

# 短期趋势线参数：双重EMA
SHORT_EMA_PERIOD = 10

# 多空趋势线参数：4周期均线平均
LONG_MA_PERIODS = [14, 28, 57, 114]

# KDJ参数
KDJ_N = 9       # RSV平滑周期
KDJ_M1 = 3      # K线平滑因子
KDJ_M2 = 3      # D线平滑因子

# 信号阈值
CROSSOVER_THRESHOLD = 0.001  # 金叉/死叉判定阈值（相对变化）
BULLISH_THRESHOLD = 0.01     # 多头排列阈值（短期至少高于长期1%）


# ── 数据获取 ─────────────────────────────────────────────────────────────────

def fetch_stock_history(
    code: str,
    period: str = "daily",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    adjust: str = "qfq",
) -> Optional[pd.DataFrame]:
    """
    获取个股历史数据。
    
    Args:
        code: 股票代码，如 "000001" 或 "000001.SZ"
        period: 数据周期，"daily"/"weekly"/"monthly"
        start_date: 开始日期 "YYYY-MM-DD"
        end_date: 结束日期 "YYYY-MM-DD"
        adjust: 复权方式，"qfq"(前复权)/"hfq"(后复权)/""(不复权)
    
    Returns:
        DataFrame，包含 date/open/high/low/close/vol 字段
    """
    try:
        import akshare as ak
        
        # 自动添加后缀
        if not code.endswith((".SH", ".SZ", ".BJ")):
            if code.startswith(("6", "9")):
                code = f"{code}.SH"
            elif code.startswith(("0", "3")):
                code = f"{code}.SZ"
            elif code.startswith(("4", "8")):
                code = f"{code}.BJ"
        
        # 计算默认日期范围（最近2年）
        if end_date is None:
            end_date = datetime.now().strftime("%Y%m%d")
        if start_date is None:
            start = datetime.now() - timedelta(days=730)
            start_date = start.strftime("%Y%m%d")
        
        df = ak.stock_zh_a_hist(
            symbol=code.replace(".SH", "").replace(".SZ", "").replace(".BJ", ""),
            period=period,
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
            adjust=adjust,
        )
        
        if df is None or df.empty:
            return None
        
        # 标准化列名
        df = df.rename(columns={
            "日期": "date",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
            "成交额": "turnover",
            "振幅": "amplitude",
            "涨跌幅": "change_pct",
            "涨跌额": "change",
            "换手率": "turnover_rate",
        })
        
        # 确保日期格式
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        
        return df
    
    except ImportError:
        print("[知行趋势线] AkShare 未安装，无法获取股票数据")
        return None
    except Exception as e:
        print(f"[知行趋势线] 获取股票 {code} 历史数据失败: {e}")
        return None


def fetch_etf_history(
    code: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Optional[pd.DataFrame]:
    """
    获取ETF历史数据。
    
    Args:
        code: ETF代码，如 "510300"
        start_date: 开始日期 "YYYY-MM-DD"
        end_date: 结束日期 "YYYY-MM-DD"
    
    Returns:
        DataFrame，包含 date/open/high/low/close/vol 字段
    """
    try:
        import akshare as ak
        
        if end_date is None:
            end_date = datetime.now().strftime("%Y%m%d")
        if start_date is None:
            start = datetime.now() - timedelta(days=730)
            start_date = start.strftime("%Y%m%d")
        
        df = ak.fund_etf_hist_em(
            symbol=code,
            period="daily",
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
            adjust="qfq",
        )
        
        if df is None or df.empty:
            return None
        
        # 标准化列名
        df = df.rename(columns={
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
        })
        
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        
        return df
    
    except ImportError:
        return None
    except Exception as e:
        print(f"[知行趋势线] 获取ETF {code} 历史数据失败: {e}")
        return None


# ── 知行趋势线计算 ─────────────────────────────────────────────────────────────

def calculate_short_trend(close: pd.Series, period: int = SHORT_EMA_PERIOD) -> pd.Series:
    """
    计算短期趋势线：双重EMA
    
    Formula: EMA(EMA(C, period), period)
    
    Args:
        close: 收盘价序列
        period: EMA周期，默认10
    
    Returns:
        短期趋势线序列
    """
    # 第一层EMA
    ema1 = close.ewm(span=period, adjust=False).mean()
    # 第二层EMA
    ema2 = ema1.ewm(span=period, adjust=False).mean()
    return ema2


def calculate_long_trend(
    close: pd.Series,
    periods: List[int] = LONG_MA_PERIODS,
) -> pd.Series:
    """
    计算多空趋势线：4周期均线平均
    
    Formula: (MA(C,14) + MA(C,28) + MA(C,57) + MA(C,114)) / 4
    
    Args:
        close: 收盘价序列
        periods: 均线周期列表，默认 [14, 28, 57, 114]
    
    Returns:
        多空趋势线序列
    """
    ma_sum = pd.Series(0.0, index=close.index)
    
    for p in periods:
        ma_sum += close.rolling(window=p, min_periods=1).mean()
    
    return ma_sum / len(periods)


def calculate_kdj(high: pd.Series, low: pd.Series, close: pd.Series, 
                   n: int = KDJ_N, m1: int = KDJ_M1, m2: int = KDJ_M2) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    计算KDJ指标。
    
    Args:
        high: 最高价序列
        low: 最低价序列
        close: 收盘价序列
        n: RSV平滑周期
        m1: K线平滑因子
        m2: D线平滑因子
    
    Returns:
        (K, D, J) 三条线序列
    """
    # 计算RSV
    lowest_low = low.rolling(window=n, min_periods=1).min()
    highest_high = high.rolling(window=n, min_periods=1).max()
    
    rsv = (close - lowest_low) / (highest_high - lowest_low + 1e-10) * 100
    
    # 计算K、D、J
    k = rsv.ewm(alpha=1/m1, adjust=False).mean()
    d = k.ewm(alpha=1/m2, adjust=False).mean()
    j = 3 * k - 2 * d
    
    return k, d, j


def calculate_zhixing(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算完整的知行趋势线指标。
    
    Args:
        df: 包含 high/low/close 列的DataFrame
    
    Returns:
        添加了知行趋势线指标的DataFrame
    """
    if df is None or df.empty:
        return df
    
    result = df.copy()
    
    # 计算短期趋势线（双重EMA）
    result["short_trend"] = calculate_short_trend(result["close"])
    
    # 计算多空趋势线（4周期MA平均）
    result["long_trend"] = calculate_long_trend(result["close"])
    
    # 计算KDJ
    k, d, j = calculate_kdj(result["high"], result["low"], result["close"])
    result["kdj_k"] = k
    result["kdj_d"] = d
    result["kdj_j"] = j
    
    # 计算趋势差值（短期 - 长期）
    result["trend_diff"] = result["short_trend"] - result["long_trend"]
    result["trend_diff_pct"] = result["trend_diff"] / result["long_trend"] * 100
    
    # 计算状态标志
    result["bullish"] = result["short_trend"] > result["long_trend"] * (1 + BULLISH_THRESHOLD)
    
    return result


# ── 信号生成 ─────────────────────────────────────────────────────────────────

def detect_crossover(
    short: pd.Series, 
    long: pd.Series,
) -> Tuple[pd.Series, pd.Series]:
    """
    检测金叉和死叉。
    
    Returns:
        (golden_cross, dead_cross) - bool Series
    """
    # 金叉：短期从下往上穿过长期
    golden_cross = (short > long) & (short.shift(1) <= long.shift(1))
    
    # 死叉：短期从上往下穿过长期
    dead_cross = (short < long) & (short.shift(1) >= long.shift(1))
    
    return golden_cross, dead_cross


def generate_signal(df: pd.DataFrame, threshold: float = CROSSOVER_THRESHOLD) -> str:
    """
    生成交易信号。
    
    Args:
        df: 包含知行趋势线指标的DataFrame
        threshold: 交叉判定阈值
    
    Returns:
        信号类型："BUY" / "SELL" / "HOLD"
    """
    if df is None or len(df) < 2:
        return "HOLD"
    
    result = calculate_zhixing(df)
    if result is None:
        return "HOLD"
    
    # 获取最近几天的数据
    recent = result.tail(5)
    
    # 检测金叉/死叉
    golden_cross, dead_cross = detect_crossover(recent["short_trend"], recent["long_trend"])
    
    # 获取最新状态
    latest = result.iloc[-1]
    prev = result.iloc[-2] if len(result) >= 2 else latest
    
    # 金叉信号
    if golden_cross.iloc[-1]:
        return "BUY"
    
    # 死叉信号
    if dead_cross.iloc[-1]:
        return "SELL"
    
    # 多头排列（持有信号）
    if latest["short_trend"] > latest["long_trend"] * (1 + threshold):
        if latest["close"] > latest["short_trend"]:
            return "HOLD_BULL"  # 多头排列，持有
    
    # 空头排列（观望）
    if latest["short_trend"] < latest["long_trend"] * (1 - threshold):
        return "HOLD_BEAR"  # 空头排列
    
    return "HOLD_NEUTRAL"


def get_trend_status(df: pd.DataFrame) -> Dict:
    """
    获取趋势状态详情。
    
    Returns:
        {
            "signal": str,           # 信号 BUY/SELL/HOLD_*
            "short_trend": float,     # 短期趋势线值
            "long_trend": float,      # 多空趋势线值
            "trend_diff_pct": float,  # 差值百分比
            "kdj_k": float,           # K值
            "kdj_d": float,           # D值
            "kdj_j": float,           # J值
            "position": str,           # 排列状态
            "trend_direction": str,    # 趋势方向
        }
    """
    if df is None or len(df) < 114:  # 需要足够的历史数据
        return {"error": "数据不足"}
    
    result = calculate_zhixing(df)
    if result is None:
        return {"error": "计算失败"}
    
    latest = result.iloc[-1]
    prev = result.iloc[-2] if len(result) >= 2 else latest
    
    # 判断排列状态
    if latest["short_trend"] > latest["long_trend"] * 1.01:
        position = "多头排列"
    elif latest["short_trend"] < latest["long_trend"] * 0.99:
        position = "空头排列"
    else:
        position = "纠缠整理"
    
    # 判断趋势方向
    short_slope = (latest["short_trend"] - result.iloc[-5]["short_trend"]) if len(result) >= 5 else 0
    long_slope = (latest["long_trend"] - result.iloc[-5]["long_trend"]) if len(result) >= 5 else 0
    
    if short_slope > 0 and long_slope > 0:
        trend_direction = "上升"
    elif short_slope < 0 and long_slope < 0:
        trend_direction = "下降"
    else:
        trend_direction = "震荡"
    
    return {
        "signal": generate_signal(df),
        "short_trend": round(latest["short_trend"], 3),
        "long_trend": round(latest["long_trend"], 3),
        "trend_diff_pct": round(latest["trend_diff_pct"], 2),
        "kdj_k": round(latest["kdj_k"], 2),
        "kdj_d": round(latest["kdj_d"], 2),
        "kdj_j": round(latest["kdj_j"], 2),
        "position": position,
        "trend_direction": trend_direction,
        "price": round(latest["close"], 2),
        "change_pct": round(latest.get("change_pct", 0), 2),
    }


# ── 个股/ETF分析 ─────────────────────────────────────────────────────────────

def analyze_stock(code: str, name: Optional[str] = None) -> Dict:
    """
    分析单只股票/ETF。
    
    Args:
        code: 股票/ETF代码
        name: 名称（可选）
    
    Returns:
        分析结果字典
    """
    # 判断是ETF还是股票
    is_etf = code.startswith(("51", "15", "16", "50", "56"))
    
    # 获取数据
    if is_etf:
        df = fetch_etf_history(code)
    else:
        df = fetch_stock_history(code)
    
    if df is None or df.empty:
        return {"code": code, "name": name or code, "error": "获取数据失败"}
    
    # 计算指标
    status = get_trend_status(df)
    status["code"] = code
    status["name"] = name or code
    status["is_etf"] = is_etf
    
    return status


def analyze_stocks(codes: List[str], names: Optional[List[str]] = None) -> List[Dict]:
    """
    批量分析多只股票/ETF。
    
    Args:
        codes: 代码列表
        names: 名称列表（可选）
    
    Returns:
        分析结果列表
    """
    results = []
    names = names or [None] * len(codes)
    
    for code, name in zip(codes, names):
        result = analyze_stock(code, name)
        results.append(result)
    
    return results


def screen_by_signal(results: List[Dict], signal: str) -> List[Dict]:
    """
    按信号筛选股票。
    
    Args:
        results: analyze_stocks 输出结果
        signal: 信号类型 "BUY"/"SELL"/"HOLD_*"
    
    Returns:
        符合条件的股票列表
    """
    return [r for r in results if r.get("signal") == signal]


def screen_bullish(results: List[Dict]) -> List[Dict]:
    """筛选多头排列的股票"""
    return [r for r in results if "多头排列" in r.get("position", "")]


# ── 持仓分析 ─────────────────────────────────────────────────────────────────

def analyze_positions(positions: List[Dict]) -> Dict:
    """
    分析持仓列表。
    
    Args:
        positions: 持仓列表，每项包含 code/name/amount/cost
    
    Returns:
        {
            "positions": List[Dict],  # 每只持仓的分析结果
            "summary": {
                "total": int,
                "bullish": int,
                "bearish": int,
                "buy_signals": int,
                "sell_signals": int,
            }
        }
    """
    codes = [p.get("code", p.get("stock_code", "")) for p in positions]
    names = [p.get("name", p.get("stock_name", "")) for p in positions]
    
    analyses = analyze_stocks(codes, names)
    
    # 合并持仓信息
    for analysis, position in zip(analyses, positions):
        analysis["amount"] = position.get("amount", position.get("shares", 0))
        analysis["cost"] = position.get("cost", position.get("avg_cost", 0))
        
        # 计算盈亏
        if analysis.get("price") and analysis.get("cost"):
            analysis["profit_pct"] = (analysis["price"] - analysis["cost"]) / analysis["cost"] * 100
        else:
            analysis["profit_pct"] = 0
    
    # 汇总统计
    summary = {
        "total": len(analyses),
        "bullish": sum(1 for a in analyses if "多头排列" in a.get("position", "")),
        "bearish": sum(1 for a in analyses if "空头排列" in a.get("position", "")),
        "buy_signals": sum(1 for a in analyses if a.get("signal") == "BUY"),
        "sell_signals": sum(1 for a in analyses if a.get("signal") == "SELL"),
    }
    
    return {
        "positions": analyses,
        "summary": summary,
    }


# ── 推荐生成 ─────────────────────────────────────────────────────────────────

def generate_recommendations(analysis_results: List[Dict], top_n: int = 10) -> Dict:
    """
    生成选股推荐。
    
    Args:
        analysis_results: 分析结果列表
        top_n: 返回推荐数量
    
    Returns:
        {
            "buy_recommendations": List[Dict],  # 买入推荐
            "hold_recommendations": List[Dict],  # 持有推荐
            "etf_recommendations": List[Dict],   # ETF推荐
        }
    """
    # 买入信号
    buy_recs = [
        r for r in analysis_results 
        if r.get("signal") in ["BUY", "HOLD_BULL"] 
        and r.get("trend_diff_pct", 0) > 1
    ]
    buy_recs.sort(key=lambda x: x.get("trend_diff_pct", 0), reverse=True)
    
    # 持有推荐（多头排列但暂无买入信号）
    hold_recs = [
        r for r in analysis_results
        if r.get("signal") == "HOLD_NEUTRAL"
        and "多头排列" in r.get("position", "")
    ]
    
    # ETF推荐
    etf_recs = [r for r in buy_recs if r.get("is_etf")]
    
    return {
        "buy_recommendations": buy_recs[:top_n],
        "hold_recommendations": hold_recs[:top_n],
        "etf_recommendations": etf_recs[:top_n],
    }


if __name__ == "__main__":
    # 测试代码
    print("[知行趋势线] 测试分析贵州茅台...")
    result = analyze_stock("600519", "贵州茅台")
    print(f"信号: {result.get('signal')}")
    print(f"短期趋势线: {result.get('short_trend')}")
    print(f"多空趋势线: {result.get('long_trend')}")
    print(f"排列状态: {result.get('position')}")
    print(f"KDJ: K={result.get('kdj_k')}, D={result.get('kdj_d')}, J={result.get('kdj_j')}")


# ── 综合评分系统 ─────────────────────────────────────────────────────────────

def comprehensive_score(df: pd.DataFrame) -> Dict:
    """
    计算持仓ETF综合评分（基于Z哥战法）。
    
    评分维度：
    1. 趋势（40%）：金叉+40，死叉-30，多头排列+20
    2. KDJ位置（30%）：J<-10超卖+30，J<0超卖+15，J>80超买-10
    3. 回踩白线（20%）：-3%~0%回踩附近+20，跌破-10
    4. 趋势强度（10%）：trend_diff_pct>5%+10，<0%-10
    
    Args:
        df: 包含知行趋势线指标的DataFrame
    
    Returns:
        {
            "total_score": int,           # 总分 (0-100)
            "rating": str,                # 评级 BUY_STRONG/BUY/HOLD/SELL
            "trend_score": int,           # 趋势得分
            "kdj_score": int,             # KDJ得分
            "pullback_score": int,        # 回踩得分
            "strength_score": int,         # 强度得分
            "trend_detail": str,           # 趋势详情
            "kdj_detail": str,            # KDJ详情
            "pullback_detail": str,        # 回踩详情
            "strength_detail": str,        # 强度详情
        }
    """
    if df is None or len(df) < 10:
        return {"total_score": 0, "rating": "数据不足", "error": "数据不足"}
    
    result = calculate_zhixing(df)
    if result is None:
        return {"total_score": 0, "rating": "计算失败", "error": "计算失败"}
    
    latest = result.iloc[-1]
    prev = result.iloc[-2] if len(result) >= 2 else latest
    
    # ── 1. 趋势得分 (40%) ────────────────────────────────────────────────
    signal = generate_signal(df)
    golden_cross, dead_cross = detect_crossover(result["short_trend"], result["long_trend"])
    
    trend_score = 0
    trend_detail = ""
    
    if golden_cross.iloc[-1]:
        trend_score = 40
        trend_detail = "✅ 金叉买入信号"
    elif dead_cross.iloc[-1]:
        trend_score = -30
        trend_detail = "⚠️ 死叉卖出信号"
    elif "多头排列" in latest.get("position", ""):
        trend_score = 20
        trend_detail = f"📈 多头排列（差值{latest['trend_diff_pct']:.2f}%）"
    elif "空头排列" in latest.get("position", ""):
        trend_score = -20
        trend_detail = "📉 空头排列"
    else:
        trend_score = 0
        trend_detail = "⚪ 纠缠整理"
    
    # ── 2. KDJ得分 (30%) ─────────────────────────────────────────────────
    j_value = latest["kdj_j"]
    
    kdj_score = 0
    kdj_detail = ""
    
    if j_value < -10:
        kdj_score = 30
        kdj_detail = f"🔥 严重超卖（J={j_value:.1f}）"
    elif j_value < 0:
        kdj_score = 15
        kdj_detail = f"📉 超卖区间（J={j_value:.1f}）"
    elif j_value > 80:
        kdj_score = -10
        kdj_detail = f"📈 超买区间（J={j_value:.1f}）"
    else:
        kdj_score = 0
        kdj_detail = f"中性区间（J={j_value:.1f}）"
    
    # ── 3. 回踩白线得分 (20%) ─────────────────────────────────────────────
    # 前提：白线必须在黄线之上（多头排列），回踩才有意义
    is_bullish = "多头排列" in latest.get("position", "")
    
    # 白线 = 短期趋势线 (short_trend)
    white_line = latest["short_trend"]
    price = latest["close"]
    diff_pct = (price - white_line) / white_line * 100
    
    pullback_score = 0
    pullback_detail = ""
    
    if is_bullish:
        # 白线在黄线之上（多头排列），回踩白线有效
        if -3 <= diff_pct <= 0:
            pullback_score = 20
            pullback_detail = f"✅ 多头回踩白线（{diff_pct:.2f}%）"
        elif diff_pct < -3:
            pullback_score = -10
            pullback_detail = f"⚠️ 跌破白线（{diff_pct:.2f}%）"
        else:
            pullback_score = 5
            pullback_detail = f"📈 远离白线（+{diff_pct:.2f}%）"
    else:
        # 白线在黄线之下（空头排列/纠缠），回踩白线无效
        pullback_score = -5
        pullback_detail = f"⚠️ 白线在黄线之下，回踩无效（{diff_pct:.2f}%）"
    
    # ── 4. 趋势强度得分 (10%) ─────────────────────────────────────────────
    trend_diff_pct = latest["trend_diff_pct"]
    
    strength_score = 0
    strength_detail = ""
    
    if trend_diff_pct > 5:
        strength_score = 10
        strength_detail = f"💪 强势多头（{trend_diff_pct:.2f}%）"
    elif trend_diff_pct > 2:
        strength_score = 5
        strength_detail = f"📈 偏强（{trend_diff_pct:.2f}%）"
    elif trend_diff_pct < 0:
        strength_score = -10
        strength_detail = f"📉 趋势走弱（{trend_diff_pct:.2f}%）"
    else:
        strength_score = 0
        strength_detail = f"中性（{trend_diff_pct:.2f}%）"
    
    # ── 综合评分 ──────────────────────────────────────────────────────────
    total_score = trend_score + kdj_score + pullback_score + strength_score
    
    # 限制在合理范围
    total_score = max(-50, min(100, total_score))
    
    # 评级判定
    if total_score >= 70:
        rating = "🟢 强烈买入"
        rating_code = "BUY_STRONG"
    elif total_score >= 40:
        rating = "🟡 买入"
        rating_code = "BUY"
    elif total_score >= 0:
        rating = "⚪ 持有"
        rating_code = "HOLD"
    else:
        rating = "🔴 减仓/止损"
        rating_code = "SELL"
    
    return {
        "total_score": total_score,
        "rating": rating,
        "rating_code": rating_code,
        "trend_score": trend_score,
        "kdj_score": kdj_score,
        "pullback_score": pullback_score,
        "strength_score": strength_score,
        "trend_detail": trend_detail,
        "kdj_detail": kdj_detail,
        "pullback_detail": pullback_detail,
        "strength_detail": strength_detail,
    }


def analyze_position_with_score(position: Dict) -> Dict:
    """
    分析单个持仓（包含综合评分）。
    
    Args:
        position: 持仓信息 {"code", "name", "amount", "cost", ...}
    
    Returns:
        包含评分信息的分析结果
    """
    code = position.get("code", position.get("stock_code", ""))
    name = position.get("name", position.get("stock_name", ""))
    
    # 获取基础分析
    base_analysis = analyze_stock(code, name)
    
    if "error" in base_analysis:
        return {**position, **base_analysis}
    
    # 获取原始数据用于评分
    is_etf = code.startswith(("51", "15", "16", "50", "56"))
    if is_etf:
        df = fetch_etf_history(code)
    else:
        df = fetch_stock_history(code)
    
    if df is not None and not df.empty:
        score = comprehensive_score(df)
        base_analysis.update(score)
    
    # 合并持仓信息
    base_analysis["amount"] = position.get("amount", position.get("shares", 0))
    base_analysis["cost"] = position.get("cost", position.get("avg_cost", 0))
    
    # 计算盈亏
    if base_analysis.get("price") and base_analysis.get("cost"):
        base_analysis["profit_pct"] = (base_analysis["price"] - base_analysis["cost"]) / base_analysis["cost"] * 100
    else:
        base_analysis["profit_pct"] = 0
    
    return base_analysis


def analyze_positions_with_scores(positions: List[Dict]) -> Dict:
    """
    分析持仓列表（包含综合评分）。
    
    Args:
        positions: 持仓列表
    
    Returns:
        {
            "positions": List[Dict],
            "summary": {...},
        }
    """
    analyses = [analyze_position_with_score(p) for p in positions]
    
    # 汇总统计
    summary = {
        "total": len(analyses),
        "buy_strong": sum(1 for a in analyses if a.get("rating_code") == "BUY_STRONG"),
        "buy": sum(1 for a in analyses if a.get("rating_code") == "BUY"),
        "hold": sum(1 for a in analyses if a.get("rating_code") == "HOLD"),
        "sell": sum(1 for a in analyses if a.get("rating_code") == "SELL"),
        "avg_score": sum(a.get("total_score", 0) for a in analyses) / len(analyses) if analyses else 0,
    }
    
    # 按评分排序
    analyses.sort(key=lambda x: x.get("total_score", 0), reverse=True)
    
    return {
        "positions": analyses,
        "summary": summary,
    }
