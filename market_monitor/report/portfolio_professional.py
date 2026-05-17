#!/usr/bin/env python3
"""
专业版ETF持仓分析报告生成器

精简版专业报告，包含：
- 持仓概览与信号分布
- 持仓明细（知行信号、技术指标、盈亏）
- 板块分布
- 操作建议
- 风险提示

使用方法：
    python3 -m market_monitor.report.portfolio_professional
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import json
import subprocess
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Dict, List

import pandas as pd
import xalpha as xa
import tushare as ts
import warnings
warnings.filterwarnings('ignore')

# 仓位管理模块
from market_monitor.analysis.position_manager import PositionManager, Market

# 估值数据源
from market_monitor.data_sources.valuation import fetch_market_valuation
from market_monitor.data_sources.hk_valuation import fetch_hk_valuation
from market_monitor.data_sources.hk_tech_valuation import fetch_hk_tech_valuation
from market_monitor.data_sources.shiller_api import fetch_us_cape_valuation

# ── ETF指数映射表（从 etf_index_mapping.csv 加载）─────────────────────────────
ETF_MAPPING = {
    "159202": {"name": "恒生互联网ETF", "index": "HKHSIII", "index_name": "恒生互联网科技业指数"},
    "159852": {"name": "软件ETF嘉实", "index": "ZZ930601", "index_name": "中证软件服务指数"},
    "506008": {"name": "科创板长城", "index": "SH000688", "index_name": "科创50指数"},
    "562500": {"name": "机器人ETF华夏", "index": "ZZH30590", "index_name": "中证机器人指数"},
    "159217": {"name": "港股通创新药ETF", "index": "GZ987018", "index_name": "恒生医疗保健指数"},
    "159869": {"name": "游戏ETF华夏", "index": "ZZ930901", "index_name": "中证游戏产业指数"},
    "513180": {"name": "恒生科技ETF华夏", "index": "HKHSTECH", "index_name": "恒生科技指数"},
    "513090": {"name": "香港证券ETF易方达", "index": "ZZ930709", "index_name": "中证香港证券指数"},
}

# ── 数据获取 ──────────────────────────────────────────────────────────────────

def get_index_data(index_code_xalpha: str) -> pd.DataFrame:
    """使用 xalpha 获取指数历史数据"""
    try:
        info = xa.indexinfo(code=index_code_xalpha)
        df = info.price.copy()

        if "date" not in df.columns:
            df = df.reset_index()
        df.columns = [c.lower() for c in df.columns]

        # 补全缺失列
        if "high" not in df.columns:
            df["high"] = df["close"]
        if "low" not in df.columns:
            df["low"] = df["close"]
        if "open" not in df.columns:
            df["open"] = df["close"]
        if "volume" not in df.columns:
            df["volume"] = 0.0

        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        return df
    except Exception as e:
        print(f"  [错误] 获取 {index_code_xalpha} 数据失败: {e}")
        return pd.DataFrame()


def calculate_technical(df: pd.DataFrame) -> pd.DataFrame:
    """计算技术指标"""
    if df.empty or len(df) < 60:
        return df

    result = df.copy()
    close = result["close"]

    # 均线
    result["ma5"] = close.rolling(window=5, min_periods=1).mean()
    result["ma10"] = close.rolling(window=10, min_periods=1).mean()
    result["ma14"] = close.rolling(window=14, min_periods=1).mean()
    result["ma20"] = close.rolling(window=20, min_periods=1).mean()
    result["ma28"] = close.rolling(window=28, min_periods=1).mean()
    result["ma57"] = close.rolling(window=57, min_periods=1).mean()
    result["ma60"] = close.rolling(window=60, min_periods=1).mean()
    result["ma114"] = close.rolling(window=114, min_periods=1).mean()

    # 知行趋势线
    # 短线: EMA(EMA(close,10),10) - 10日EMA的双重平滑
    ema10 = close.ewm(span=10, adjust=False).mean()
    result["zx_short"] = ema10.ewm(span=10, adjust=False).mean()
    # 长线: (MA14+MA28+MA57+MA114)/4 - 4条均线的平均
    result["zx_long"] = (result["ma14"] + result["ma28"] + result["ma57"] + result["ma114"]) / 4

    # KDJ
    low14 = result["low"].rolling(window=9, min_periods=1).min()
    high14 = result["high"].rolling(window=9, min_periods=1).max()
    diff = (high14 - low14).replace(0, 0.001)
    rsv = ((close - low14) / diff * 100).fillna(50)
    result["kdj_k"] = rsv.ewm(alpha=1/3, adjust=False).mean()
    result["kdj_d"] = result["kdj_k"].ewm(alpha=1/3, adjust=False).mean()
    result["kdj_j"] = 3 * result["kdj_k"] - 2 * result["kdj_d"]

    # MACD
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    result["macd_diff"] = ema12 - ema26
    result["macd_dea"] = result["macd_diff"].ewm(span=9, adjust=False).mean()
    result["macd_hist"] = (result["macd_diff"] - result["macd_dea"]) * 2

    # RSI
    delta = close.diff()
    gain = delta.where(delta > 0, 0)
    loss = (-delta).where(delta < 0, 0)
    avg_gain = gain.rolling(window=14, min_periods=1).mean()
    avg_loss = loss.rolling(window=14, min_periods=1).mean()
    rs = avg_gain / avg_loss.replace(0, 0.001)
    result["rsi14"] = 100 - (100 / (1 + rs))

    # 成交量
    result["ma_vol_5"] = result["volume"].rolling(window=5, min_periods=1).mean()
    result["ma_vol_60"] = result["volume"].rolling(window=60, min_periods=1).mean()
    result["vol_ratio"] = result["volume"] / result["ma_vol_5"].shift(1).replace(0, 1)
    result["price_change"] = close.pct_change()
    result["vol_match"] = (
        ((result["price_change"] > 0) & (result["vol_ratio"] > 1.0)) |
        ((result["price_change"] < 0) & (result["vol_ratio"] < 1.0))
    )

    # 价格位置
    rolling_high = close.rolling(window=60, min_periods=20).max()
    rolling_low = close.rolling(window=60, min_periods=20).min()
    result["price_pos_60d"] = (close - rolling_low) / (rolling_high - rolling_low).replace(0, 1) * 100

    return result


def analyze_etf(etf_code: str, etf_name: str, index_code: str, index_name: str) -> Dict:
    """分析单只ETF"""
    print(f"  [{etf_code}] {etf_name} -> {index_name}")

    # 获取数据
    df = get_index_data(index_code)
    if df.empty:
        return None

    # 计算技术指标
    df = calculate_technical(df)
    if len(df) < 60:
        return None

    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else latest

    # 知行趋势线
    short_trend = latest.get("zx_short", 0)   # EMA(EMA(close,10),10)
    long_trend = latest.get("zx_long", 0)     # (MA14+MA28+MA57+MA114)/4
    close_price = latest.get("close", 0)

    # 前一天数据（用于计算偏离变化）
    prev_short = prev.get("zx_short", 0)
    prev_long = prev.get("zx_long", 0)
    prev_close = prev.get("close", 0)

    # 信号判断（按您的公式）
    # 强势：短线 > 长线 且 收盘价 > 短线
    # 观望：短线 > 长线 且 收盘价 < 短线
    # 危险：短线 < 长线 或 收盘价 < 长线
    if short_trend > long_trend and close_price > short_trend:
        signal = "STRONG"       # 强势
    elif short_trend > long_trend and close_price <= short_trend:
        signal = "WATCH"        # 观望
    else:
        signal = "DANGER"       # 危险

    # 排列状态
    if short_trend > long_trend:
        position = "短线在长线之上"
    else:
        position = "短线在长线之下"

    # 偏离比例计算
    close_pct_short = ((close_price / short_trend) - 1) * 100 if short_trend != 0 else 0
    close_pct_long = ((close_price / long_trend) - 1) * 100 if long_trend != 0 else 0
    short_pct_long = ((short_trend / long_trend) - 1) * 100 if long_trend != 0 else 0

    # 前一天偏离度（用于判断偏离变化）
    prev_close_pct_short = ((prev_close / prev_short) - 1) * 100 if prev_short != 0 else 0
    close_deviation_change = close_pct_short - prev_close_pct_short  # 正=偏离扩大，负=偏离缩小

    # 三线位置关系（复合描述用）
    if close_price > short_trend > long_trend:
        line_position = "收盘>白线>黄线（三线多头）"
    elif short_trend > close_price > long_trend:
        line_position = "白线>收盘>黄线（偏弱反弹）"
    elif close_price > long_trend > short_trend:
        line_position = "收盘>黄线>白线（反弹整理）"
    elif long_trend > short_trend > close_price:
        line_position = "黄线>白线>收盘（空头排列）"
    elif long_trend > close_price > short_trend:
        line_position = "黄线>收盘>白线（弱势）"
    elif short_trend > long_trend > close_price:
        line_position = "白线>黄线>收盘（偏弱）"
    else:
        line_position = "三线纠缠"

    # 均线排列判断
    ma5 = latest.get("ma5", 0)
    ma10 = latest.get("ma10", 0)
    ma20 = latest.get("ma20", 0)
    ma60 = latest.get("ma60", 0)
    if ma5 > ma10 > ma20 > ma60:
        ma_pattern = "多头排列（强势上涨）"
    elif ma5 < ma10 < ma20 < ma60:
        ma_pattern = "空头排列（弱势下跌）"
    elif ma5 > ma20 and ma10 > ma20:
        ma_pattern = "偏多整理"
    elif ma5 < ma20 and ma10 < ma20:
        ma_pattern = "偏空整理"
    else:
        ma_pattern = "均线纠缠"

    # 异常量能
    abnormal = []
    price_pos = latest.get("price_pos_60d", 50)
    is_huge = latest.get("vol_ratio", 1) > 3

    if is_huge and price_pos < 30:
        abnormal.append({"type": "底部放巨量", "description": "低位出现巨量，可能预示反转", "severity": "positive"})
    if is_huge and price_pos > 70:
        price_change = latest.get("price_change", 0) * 100
        if price_change < 2:
            abnormal.append({"type": "顶部放量滞涨", "description": f"高位放量但涨幅仅{price_change:.2f}%", "severity": "warning"})
    if latest.get("vol_match", False) == False and latest.get("vol_ratio", 1) > 1.2:
        if price_pos > 60 and latest.get("price_change", 0) > 0:
            abnormal.append({"type": "顶背离", "description": "价涨量缩，上涨动力不足", "severity": "warning"})
        elif price_pos < 40 and latest.get("price_change", 0) < 0:
            abnormal.append({"type": "底背离", "description": "价跌量缩，可能企稳", "severity": "positive"})

    # 评分（基于知行信号）
    score = 0
    if signal == "STRONG":
        score += 50
    elif signal == "WATCH":
        score += 25
    else:  # DANGER
        score += 0

    # 均线辅助评分
    if latest.get("close", 0) > latest.get("ma20", 0):
        score += 10
    if latest.get("close", 0) > latest.get("ma60", 0):
        score += 10

    if latest.get("vol_match", False):
        score += 20
    elif latest.get("vol_ratio", 1) > 1.5:
        score += 10

    # RSI 辅助评分
    rsi = latest.get("rsi14", 50)
    if rsi < 30:
        score += 10  # 超卖可能反弹
    elif rsi > 80:
        score -= 10  # 超买注意风险

    return {
        "etf_code": etf_code,
        "etf_name": etf_name,
        "index_code": index_code,
        "index_name": index_name,
        "close": latest.get("close", 0),
        "zx_short": latest.get("zx_short", 0),
        "zx_long": latest.get("zx_long", 0),
        "ma5": latest.get("ma5", 0),
        "ma10": latest.get("ma10", 0),
        "ma14": latest.get("ma14", 0),
        "ma20": latest.get("ma20", 0),
        "ma28": latest.get("ma28", 0),
        "ma57": latest.get("ma57", 0),
        "ma60": latest.get("ma60", 0),
        "ma114": latest.get("ma114", 0),
        "kdj_k": latest.get("kdj_k", 0),
        "kdj_d": latest.get("kdj_d", 0),
        "kdj_j": latest.get("kdj_j", 0),
        "macd_diff": latest.get("macd_diff", 0),
        "macd_dea": latest.get("macd_dea", 0),
        "macd_hist": latest.get("macd_hist", 0),
        "rsi14": rsi,
        "vol_ratio": latest.get("vol_ratio", 1),
        "vol_match": latest.get("vol_match", False),
        "price_pos_60d": price_pos,
        "signal": signal,
        "position": position,
        "pattern_score": score,
        "abnormal_signals": abnormal,
        # 偏离比例
        "close_pct_short": close_pct_short,
        "close_pct_long": close_pct_long,
        "short_pct_long": short_pct_long,
        # 偏离变化
        "close_deviation_change": close_deviation_change,
        # 三线位置
        "line_position": line_position,
        # 均线排列
        "ma_pattern": ma_pattern,
    }


def get_realtime_price(codes: list) -> dict:
    """通过Tushare获取ETF实时价格"""
    try:
        df = ts.get_realtime_quotes(codes)
        prices = {}
        if not df.empty:
            for _, row in df.iterrows():
                code = row['code']
                price = float(row['price']) if row['price'] else 0
                prices[code] = price
        return prices
    except Exception as e:
        print(f"  [警告] Tushare获取实时价格失败: {e}")
        return {}


def get_etf_nav(code: str) -> tuple:
    """通过xalpha获取ETF净值和日期（作为参考）"""
    try:
        info = xa.FundInfo(code)
        if info and hasattr(info, 'price') and not info.price.empty:
            latest = info.price.iloc[-1]
            nav = float(latest['netvalue'])
            date = str(latest['date'])[:10]
            return nav, date
        return 0.0, None
    except Exception as e:
        print(f"  [警告] 获取 {code} 净值失败: {e}")
        return 0.0, None


class ProfessionalETFReportGenerator:
    """专业版ETF持仓分析报告生成器"""

    # 仓位展示样式常量
    PM_STYLE_COMPACT = "compact"    # 简洁总览
    PM_STYLE_MARKET = "market"      # 市场明细
    PM_STYLE_ACTION = "action"      # 行动聚焦（默认）

    def __init__(self, results: List[Dict], pm_style: str = None):
        self.results = results
        beijing_tz = timezone(timedelta(hours=8))
        self.now = datetime.now(beijing_tz)
        self.report_time = self.now.strftime("%Y-%m-%d %H:%M")
        self.report_date = self.now.strftime("%Y-%m-%d")
        # 仓位展示样式，默认使用行动聚焦
        self.pm_style = pm_style or self.PM_STYLE_ACTION

    def _escape(self, text: str) -> str:
        """转义XML特殊字符"""
        if not text:
            return ""
        return (text.replace('&', '&amp;')
                    .replace('<', '&lt;')
                    .replace('>', '&gt;'))

    def _fmt_profit(self, p: float) -> str:
        """格式化盈亏"""
        return ("🟢 " if p >= 0 else "🔴 ") + f"{p:+.2f}%"

    def _rsi_status(self, rsi: float):
        """RSI状态"""
        if rsi < 30: return f"🔴{rsi:.1f}", "超卖"
        elif rsi < 40: return f"🟠{rsi:.1f}", "偏弱"
        elif rsi < 60: return f"⚪{rsi:.1f}", "中性"
        elif rsi < 70: return f"🟡{rsi:.1f}", "偏强"
        else: return f"🟢{rsi:.1f}", "超买"

    def _pos_status(self, pos: float):
        """位置状态"""
        if pos < 20: return "🔴低位", f"{pos:.0f}%"
        elif pos < 40: return "🟠偏下", f"{pos:.0f}%"
        elif pos < 60: return "⚪中性", f"{pos:.0f}%"
        elif pos < 80: return "🟡偏上", f"{pos:.0f}%"
        else: return "🟢高位", f"{pos:.0f}%"

    def _zx_signal(self, r: dict):
        """知行信号状态"""
        zx_short = r.get('zx_short', 0)
        zx_long = r.get('zx_long', 0)
        close = r.get('close', 0)
        
        if zx_short > zx_long and close > zx_short:
            return "🟢强势", "白>黄，收在白线上"
        elif zx_short > zx_long and close <= zx_short:
            return "🟡观望", "白>黄，收在白线下"
        else:
            return "🔴危险", "白<黄，空头排列"

    def _kdj_status(self, r: dict):
        """KDJ状态"""
        k, d, j = r.get('kdj_k', 0), r.get('kdj_d', 0), r.get('kdj_j', 0)
        if k < 20: return f"🔴{k:.0f}", "超卖"
        elif k > 80: return f"🟢{k:.0f}", "超买"
        elif k > d and d > 50: return f"🟡{k:.0f}", "金叉"
        else: return f"⚪{k:.0f}", "中性"

    def _macd_status(self, r: dict):
        """MACD状态"""
        hist = r.get('macd_hist', 0)
        return ("🟢红柱", "多方") if hist > 0 else ("🔴绿柱", "空方")

    def _get_action(self, r: dict):
        """获取操作建议"""
        sig = r.get('signal', '')
        rsi = r.get('rsi14', 50)
        
        if sig == 'STRONG':
            if rsi > 70: return "持有/减仓"
            elif rsi < 30: return "加仓机会"
            return "持有"
        elif sig == 'WATCH':
            if rsi < 30: return "关注"
            return "观望"
        else:
            if rsi < 30: return "等待"
            return "减仓"

    def _fetch_realtime_valuations(self) -> dict:
        """
        实时获取各市场估值百分位。

        Returns:
            {
                "a_stock": {"percentile": float, "source": str, "error": str|None},
                "hk_stock": {"percentile": float, "source": str, "error": str|None},
                "us_stock": {"percentile": float, "source": str, "error": str|None},
            }
        """
        results = {}

        # 1. A股估值 - 万得全A PE/PB百分位
        print("  [仓位管理] 查询A股估值...")
        try:
            a_data = fetch_market_valuation()
            if a_data.get("error") or not a_data.get("data"):
                results["a_stock"] = {"percentile": None, "source": "N/A", "error": a_data.get("error", "无数据")}
            else:
                data = a_data["data"]
                # 综合PE和PB百分位（PE权重更高）
                pe_pct = data.get("pe_pct") or 50.0
                pb_pct = data.get("pb_pct") or 50.0
                # 如果只有PE百分位，PB百分位缺失，则使用PE百分位
                if data.get("pe_pct") is not None and data.get("pb_pct") is not None:
                    composite_pct = pe_pct * 0.6 + pb_pct * 0.4
                else:
                    composite_pct = pe_pct or 50.0
                results["a_stock"] = {
                    "percentile": composite_pct,
                    "source": f"万得全A (PE={data.get('pe')}, PB={data.get('pb')})",
                    "error": None,
                }
                print(f"           A股: PE百分位={data.get('pe_pct')}%, PB百分位={data.get('pb_pct')}%, 综合={composite_pct:.1f}%")
        except Exception as e:
            results["a_stock"] = {"percentile": None, "source": "N/A", "error": str(e)}
            print(f"           A股估值获取失败: {e}")

        # 2. 港股估值 - 恒生科技指数
        print("  [仓位管理] 查询港股估值...")
        try:
            hk_data = fetch_hk_tech_valuation()
            if hk_data.get("error") or not hk_data.get("pe"):
                # 降级到恒生指数
                hk_data = fetch_hk_valuation()
                if hk_data.get("error") or not hk_data.get("pe"):
                    results["hk_stock"] = {"percentile": None, "source": "N/A", "error": "获取失败"}
                else:
                    pct = hk_data.get("pct_10y") or 50.0
                    results["hk_stock"] = {
                        "percentile": pct,
                        "source": f"恒生指数 (PE={hk_data.get('pe')}, 10年分位={pct}%)",
                        "error": None,
                    }
                    print(f"           港股: PE={hk_data.get('pe')}, 10年分位={pct}%")
            else:
                # 使用恒生科技指数
                pe_pct = hk_data.get("pe_percentile") * 100 if hk_data.get("pe_percentile") else 50.0
                pb_pct = hk_data.get("pb_percentile") * 100 if hk_data.get("pb_percentile") else 50.0
                # 综合PE和PB百分位
                composite_pct = pe_pct * 0.6 + pb_pct * 0.4
                results["hk_stock"] = {
                    "percentile": composite_pct,
                    "source": f"恒生科技 (PE={hk_data.get('pe')}, PB={hk_data.get('pb')}, 综合={composite_pct:.1f}%)",
                    "error": None,
                }
                print(f"           港股: 恒生科技 PE={hk_data.get('pe')}, PE分位={pe_pct:.1f}%, PB分位={pb_pct:.1f}%, 综合={composite_pct:.1f}%")
        except Exception as e:
            results["hk_stock"] = {"percentile": None, "source": "N/A", "error": str(e)}
            print(f"           港股估值获取失败: {e}")

        # 3. 美股估值 - S&P 500 CAPE
        print("  [仓位管理] 查询美股估值...")
        try:
            us_data = fetch_us_cape_valuation()
            if us_data.get("error") or not us_data.get("cape"):
                results["us_stock"] = {"percentile": None, "source": "N/A", "error": us_data.get("error", "获取失败")}
            else:
                pct = us_data.get("cape_10y_pct") or 50.0
                results["us_stock"] = {
                    "percentile": pct,
                    "source": f"标普500 CAPE (CAPE={us_data.get('cape')}, 10年分位={pct}%)",
                    "error": None,
                }
                print(f"           美股: CAPE={us_data.get('cape')}, 10年分位={pct}%")
        except Exception as e:
            results["us_stock"] = {"percentile": None, "source": "N/A", "error": str(e)}
            print(f"           美股估值获取失败: {e}")

        return results

    def _calculate_position_manager(self) -> dict:
        """
        计算仓位管理建议。

        实时获取各市场的实际估值百分位，由 PositionManager 计算仓位配置。
        同时计算当前实际持仓分布用于对比。

        Returns:
            包含详细系数计算的仓位管理结果
        """
        if not self.results:
            return {"error": "无持仓数据"}

        try:
            pm = PositionManager()

            # 从持仓数据中推断市场分布
            # 港股相关ETF：513180(恒生科技), 159202(恒生互联网), 159217(港股创新药)
            # A股相关ETF：159852(软件), 159869(游戏), 562500(机器人)
            # 香港证券ETF：513090 归入港股
            hk_etfs = {"513180", "159202", "159217", "513090"}
            a_etfs = {"159852", "159869", "562500"}

            # 优先使用 market_value 字段，否则用 shares * cost_price 估算
            # 注意：持仓数据中 code 字段可能在 analyze_etf 后变成 etf_code
            hk_value = 0
            a_value = 0
            us_value = 0
            for r in self.results:
                code = r.get('code') or r.get('etf_code', '')
                if r.get('market_value'):
                    mv = r['market_value']
                else:
                    # 估算市值
                    shares = r.get('shares', 0)
                    current_price = r.get('current_price') or r.get('price', 0)
                    mv = shares * current_price
                
                if code in hk_etfs:
                    hk_value += mv
                elif code in a_etfs:
                    a_value += mv
            
            total_value = hk_value + a_value + us_value

            # 当前各市场实际仓位比例
            current_hk_ratio = hk_value / total_value if total_value else 0
            current_a_ratio = a_value / total_value if total_value else 0
            current_us_ratio = us_value / total_value if total_value else 0
            current_cash_ratio = 0  # 假设无现金，若有需单独计算

            # 根据持仓分布估算趋势信号
            strong_count = sum(1 for r in self.results if r.get('signal') == 'STRONG')
            watch_count = sum(1 for r in self.results if r.get('signal') == 'WATCH')
            danger_count = sum(1 for r in self.results if r.get('signal') == 'DANGER')

            # 整体趋势判断
            if danger_count >= len(self.results) * 0.6:
                overall_trend = "bearish"
            elif strong_count >= len(self.results) * 0.4:
                overall_trend = "bullish"
            else:
                overall_trend = "neutral"

            # 实时获取各市场估值百分位
            print("\n📊 实时估值查询:")
            valuation_data = self._fetch_realtime_valuations()

            # 构建估值字典（使用默认值50%作为兜底）
            default_val = 50.0
            valuations = {
                Market.A_STOCK: valuation_data.get("a_stock", {}).get("percentile") or default_val,
                Market.HK_STOCK: valuation_data.get("hk_stock", {}).get("percentile") or default_val,
                Market.US_STOCK: valuation_data.get("us_stock", {}).get("percentile") or default_val,
            }

            # 趋势方向
            from market_monitor.analysis.position_manager import TrendDirection
            trends = {
                Market.A_STOCK: TrendDirection.NEUTRAL,
                Market.HK_STOCK: TrendDirection(overall_trend) if overall_trend != "neutral" else TrendDirection.NEUTRAL,
                Market.US_STOCK: TrendDirection.NEUTRAL,
            }

            active_signals = {
                Market.A_STOCK: "neutral",
            }

            result = pm.get_market_allocation(valuations, trends, active_signals)

            # 添加估值数据来源信息
            result["valuation_sources"] = {
                "a_stock": valuation_data.get("a_stock", {}),
                "hk_stock": valuation_data.get("hk_stock", {}),
                "us_stock": valuation_data.get("us_stock", {}),
            }
            
            # 添加当前持仓对比信息
            market_alloc = result.get("market_allocations", {})

            # 实际持仓比例映射（基于市场ID）
            current_weights_map = {
                Market.A_STOCK.value: current_a_ratio,
                Market.HK_STOCK.value: current_hk_ratio,
                Market.US_STOCK.value: current_us_ratio,
            }

            # 计算当前市值对应的目标市值
            for market_id, data in market_alloc.items():
                # base_weight 显示实际持仓比例
                actual_weight = current_weights_map.get(market_id, 0)
                data["base_weight"] = actual_weight
                data["current_weight"] = actual_weight

                # 计算调整方向和金额
                target_w = data.get("target_weight", 0)
                current_w = data.get("current_weight", 0)
                data["weight_diff"] = target_w - current_w

                # 调整方向
                if data["weight_diff"] > 0.02:
                    data["action"] = "增配"
                elif data["weight_diff"] < -0.02:
                    data["action"] = "减配"
                else:
                    data["action"] = "持稳"
            
            # 添加额外信息
            result["analysis"] = {
                "total_value": total_value,
                "hk_value": hk_value,
                "a_value": a_value,
                "current_hk_ratio": current_hk_ratio,
                "current_a_ratio": current_a_ratio,
                "current_us_ratio": current_us_ratio,
                "signal_distribution": {
                    "strong": strong_count,
                    "watch": watch_count,
                    "danger": danger_count,
                },
                "overall_trend": overall_trend,
            }
            
            return result
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e)}

    def _build_pm_xml_block(self, pm_result: dict, style: str = "market") -> str:
        """
        构建仓位管理XML区块 - 简洁展示建议仓位与当前仓位对比。

        Args:
            pm_result: 仓位管理计算结果
            style: 展示样式
                - "compact": 简洁总览 + 调整方向
                - "market": 分市场当前 vs 建议对比
                - "action": 聚焦行动建议（增配/减配）
        """
        if not pm_result or "error" in pm_result:
            return ""

        total_equity = pm_result.get("total_equity_ratio", 0) * 100
        cash_ratio = pm_result.get("cash_ratio", 0) * 100
        total_value = pm_result.get("analysis", {}).get("total_value", 0)

        # 映射表
        val_level_map = {
            "extremely_low": "极度低估",
            "low": "低估",
            "fair": "合理",
            "high": "偏高",
            "extremely_high": "极度偏高",
        }
        trend_map = {
            "bullish": "🟢上涨",
            "bearish": "🔴下跌",
            "neutral": "🟡中性",
        }

        # 收集市场数据
        market_alloc = pm_result.get("market_allocations", {})
        market_details = []
        for market_id, data in market_alloc.items():
            name = data.get("name", market_id)
            val_level = data.get("valuation_level", "")
            val_label = val_level_map.get(val_level, val_level) if val_level else "?"
            val_pct = data.get("valuation_percentile", 0)
            trend = data.get("trend", "neutral")
            trend_icon = trend_map.get(trend, "🟡")
            target_w = data.get("target_weight", 0) * 100
            current_w = data.get("current_weight", 0) * 100
            diff = data.get("weight_diff", 0) * 100
            action = data.get("action", "持稳")

            market_details.append({
                "name": name,
                "val_label": val_label,
                "val_pct": val_pct,
                "trend_icon": trend_icon,
                "target_w": target_w,
                "current_w": current_w,
                "diff": diff,
                "action": action,
            })

        # ── 样式1: 简洁总览 ─────────────────────────────────────────────────────
        if style == "compact":
            xml = f"""
<h1>五、仓位管理建议</h1>

<table>
  <thead><tr><th>指标</th><th>当前</th><th>建议</th><th>调整</th></tr></thead>
  <tbody>
    <tr><td>权益仓位</td><td>{100 - cash_ratio:.0f}%</td><td>⚖️ {total_equity:.0f}%</td><td>{total_equity - (100 - cash_ratio):+.0f}%</td></tr>
    <tr><td>现金/债券</td><td>{cash_ratio:.0f}%</td><td>💵 {cash_ratio:.0f}%</td><td>—</td></tr>
  </tbody>
</table>

<h2>📊 各市场仓位对比</h2>
<table>
  <thead><tr><th>市场</th><th>当前仓位</th><th>目标仓位</th><th>调整比例</th><th>方向</th></tr></thead>
  <tbody>
"""
            for m in market_details:
                diff_emoji = "📈" if m['diff'] > 2 else ("📉" if m['diff'] < -2 else "➖")
                adjust_str = f"+{m['diff']:.1f}%" if m['diff'] > 0 else f"{m['diff']:.1f}%"
                xml += f"""    <tr>
      <td>{m['name']}</td>
      <td>{m['current_w']:.1f}%</td>
      <td><b>{m['target_w']:.1f}%</b></td>
      <td>{adjust_str}</td>
      <td>{diff_emoji} {m['action']}</td>
    </tr>
"""
            xml += "  </tbody>\n</table>"
            return xml

        # ── 样式2: 市场明细对比 ───────────────────────────────────────────────
        elif style == "market":
            xml = f"""
<h1>五、仓位管理建议</h1>

<h2>📊 各市场仓位对比</h2>
<table>
  <thead><tr><th>市场</th><th>估值</th><th>趋势</th><th>当前仓位</th><th>目标仓位</th><th>调整比例</th></tr></thead>
  <tbody>
"""
            for m in market_details:
                diff_str = f"+{m['diff']:.1f}%" if m['diff'] >= 0 else f"{m['diff']:.1f}%"
                xml += f"""    <tr>
      <td>{m['name']}</td>
      <td>{m['val_label']} ({m['val_pct']:.0f}%)</td>
      <td>{m['trend_icon']}</td>
      <td>{m['current_w']:.1f}%</td>
      <td><b>{m['target_w']:.1f}%</b></td>
      <td>{diff_str}</td>
    </tr>
"""
            xml += f"""  </tbody>
</table>

<h2>📌 目标仓位总览</h2>
<table>
  <thead><tr><th>类型</th><th>建议比例</th></tr></thead>
  <tbody>
    <tr><td>权益仓位</td><td>⚖️ {total_equity:.0f}%</td></tr>
    <tr><td>现金/债券</td><td>💵 {cash_ratio:.0f}%</td></tr>
  </tbody>
</table>"""
            return xml

        # ── 样式3: 行动聚焦 ───────────────────────────────────────────────────
        else:  # action
            xml = f"""
<h1>五、仓位调整建议</h1>

<table>
  <thead><tr><th>市场</th><th>当前仓位</th><th>目标仓位</th><th>调整比例</th><th>操作建议</th></tr></thead>
  <tbody>
"""
            for m in market_details:
                if m['diff'] > 2:
                    op = "📈 增配"
                elif m['diff'] < -2:
                    op = "📉 减配"
                else:
                    op = "➖ 持稳"

                if abs(m['diff']) > 5:
                    priority = "⭐"
                else:
                    priority = ""

                # 调整比例格式化
                if m['diff'] > 0:
                    adjust_ratio_str = f"+{m['diff']:.1f}%"
                else:
                    adjust_ratio_str = f"{m['diff']:.1f}%"

                xml += f"""    <tr>
      <td>{m['name']}</td>
      <td>{m['current_w']:.1f}%</td>
      <td><b>{m['target_w']:.1f}%</b></td>
      <td>{adjust_ratio_str}</td>
      <td>{op} {priority}</td>
    </tr>
"""
            xml += """  </tbody>
</table>

<p><i>* 当前仓位基于持仓市值计算，建议仓位基于模型配置</i></p>
<p><i>* ⭐ 表示调整幅度较大，建议优先处理</i></p>
"""
            return xml

    def _build_pm_feishu_block(self, pm_result: dict, style: str = "action") -> str:
        """
        构建仓位管理飞书卡片区块 - 简洁展示建议仓位与当前仓位对比。

        Args:
            pm_result: 仓位管理计算结果
            style: 展示样式
                - "compact": 简洁总览 + 调整方向
                - "market": 分市场当前 vs 建议对比
                - "action": 聚焦行动建议（增配/减配）
                - "mini": 迷你卡片（小巧紧凑）
        """
        if not pm_result or "error" in pm_result:
            return ""

        total_equity = pm_result.get("total_equity_ratio", 0) * 100
        cash_ratio = pm_result.get("cash_ratio", 0) * 100

        # 映射表
        val_level_map = {
            "extremely_low": "极度低估",
            "low": "低估",
            "fair": "合理",
            "high": "偏高",
            "extremely_high": "极度偏高",
        }
        trend_map = {
            "bullish": "🟢上涨",
            "bearish": "🔴下跌",
            "neutral": "🟡中性",
        }

        # 收集市场数据
        market_alloc = pm_result.get("market_allocations", {})
        market_details = []
        for market_id, data in market_alloc.items():
            name = data.get("name", market_id)
            val_level = data.get("valuation_level", "")
            val_label = val_level_map.get(val_level, val_level) if val_level else "?"
            val_pct = data.get("valuation_percentile", 0)
            trend = data.get("trend", "neutral")
            trend_icon = trend_map.get(trend, "🟡")
            target_w = data.get("target_weight", 0) * 100
            current_w = data.get("current_weight", 0) * 100
            diff = data.get("weight_diff", 0) * 100
            action = data.get("action", "持稳")

            market_details.append({
                "name": name,
                "val_label": val_label,
                "val_pct": val_pct,
                "trend_icon": trend_icon,
                "target_w": target_w,
                "current_w": current_w,
                "diff": diff,
                "action": action,
            })

        # ── 样式1: 简洁总览 ─────────────────────────────────────────────────────
        if style == "compact":
            lines = []
            lines.append("**📊 仓位管理建议**")
            lines.append(f"⚖️ 权益建议 **{total_equity:.0f}%** | 💵 现金 **{cash_ratio:.0f}%**")
            lines.append("")
            lines.append("**📈 各市场调整方向**")
            lines.append("| 市场 | 当前 | 目标 | 调整比例 | 方向 |")
            lines.append("|:---|:---:|:---:|:---:|:---|")
            for m in market_details:
                arrow = "↑" if m['diff'] > 2 else ("↓" if m['diff'] < -2 else "—")
                adjust_str = f"+{m['diff']:.0f}%" if m['diff'] > 0 else f"{m['diff']:.0f}%"
                lines.append(f"| {m['name']} | {m['current_w']:.0f}% | {m['target_w']:.0f}% | {adjust_str} | {arrow} {m['action']} |")
            return "\n".join(lines)

        # ── 样式2: 市场明细对比 ─────────────────────────────────────────────────
        elif style == "market":
            lines = []
            lines.append("**📊 各市场仓位对比**")
            lines.append("| 市场 | 估值 | 趋势 | 当前 | 目标 | 调整比例 |")
            lines.append("|:---|:---:|:---|:---:|:---:|:---:|")
            for m in market_details:
                diff_str = f"+{m['diff']:.1f}%" if m['diff'] >= 0 else f"{m['diff']:.1f}%"
                lines.append(
                    f"| {m['name']} | {m['val_label']} | {m['trend_icon']} | {m['current_w']:.1f}% | **{m['target_w']:.1f}%** | {diff_str} |"
                )
            return "\n".join(lines)

        # ── 样式3: 行动聚焦（默认）──────────────────────────────────────────────
        elif style == "action":
            lines = []
            lines.append("**📊 仓位调整建议**")
            lines.append("")
            for m in market_details:
                if m['diff'] > 2:
                    op = "📈增配"
                    adjust_desc = f"建议增配至 **{m['target_w']:.0f}%**（+{m['diff']:.0f}%）"
                elif m['diff'] < -2:
                    op = "📉减配"
                    adjust_desc = f"建议减配至 **{m['target_w']:.0f}%**（{m['diff']:.0f}%）"
                else:
                    op = "➖持稳"
                    adjust_desc = f"维持当前 **{m['target_w']:.0f}%**"
                lines.append(
                    f"• **{m['name']}**: {adjust_desc} {op}"
                )
            lines.append("")
            lines.append(f"⚖️ 目标仓位：权益 **{total_equity:.0f}%** / 现金 **{cash_ratio:.0f}%**")
            return "\n".join(lines)

        # ── 样式4: 迷你卡片 ─────────────────────────────────────────────────────
        else:  # mini
            lines = []
            lines.append("**仓位调整速览**")
            for m in market_details:
                if m['diff'] > 2:
                    icon = "🟢"
                    action_text = "可增配"
                elif m['diff'] < -2:
                    icon = "🔴"
                    action_text = "可减配"
                else:
                    icon = "⚪"
                    action_text = "持稳"
                lines.append(f"{icon} **{m['name']}**: {m['current_w']:.0f}%→{m['target_w']:.0f}% ({m['diff']:+.0f}%) {action_text}")
            return "\n".join(lines)

    def generate(self) -> str:
        """生成完整报告"""
        total = len(self.results)
        avg_score = sum(r.get('pattern_score', 0) for r in self.results) / total if total else 0

        strong = [r for r in self.results if r.get('signal') == 'STRONG']
        watch = [r for r in self.results if r.get('signal') == 'WATCH']
        danger = [r for r in self.results if r.get('signal') == 'DANGER']

        strong_count, watch_count, danger_count = len(strong), len(watch), len(danger)
        strong_pct = strong_count / total * 100 if total else 0
        watch_pct = watch_count / total * 100 if total else 0
        danger_pct = danger_count / total * 100 if total else 0

        # 计算整体盈亏
        total_profit = sum(r.get('profit_pct', 0) for r in self.results) / total if total else 0
        
        # 权重
        total_weight = sum(r.get('weight', 0) for r in self.results)
        
        # 健康评级
        health = "优秀" if avg_score >= 70 else "良好" if avg_score >= 50 else "一般" if avg_score >= 30 else "较差"
        health_emoji = "🟢" if avg_score >= 50 else "🟡" if avg_score >= 30 else "🔴"
        
        status = "整体偏弱" if danger_count > strong_count else "整体偏强" if strong_count > danger_count else "分化明显"

        # 计算总盈亏
        total_market_value = sum(r.get('market_value', 0) for r in self.results)
        total_cost_value = sum(r.get('cost_value', 0) for r in self.results)
        total_profit_value = total_market_value - total_cost_value
        total_profit_pct = (total_profit_value / total_cost_value * 100) if total_cost_value > 0 else 0

        # 持仓明细表格 - 按市值降序排列
        sorted_results = sorted(self.results, key=lambda x: x.get('market_value', 0), reverse=True)
        position_rows = ""
        for r in sorted_results:
            sig = r.get('signal', '')
            sig_emoji = {"STRONG": "🟢", "WATCH": "🟡", "DANGER": "🔴"}.get(sig, "⚪")
            
            zx_emoji, zx_desc = self._zx_signal(r)
            rsi_str, rsi_status = self._rsi_status(r.get('rsi14', 50))
            kdj_str, kdj_status = self._kdj_status(r)
            macd_str, macd_status = self._macd_status(r)
            pos_desc, pos_str = self._pos_status(r.get('price_pos_60d', 50))
            
            profit_pct = r.get('profit_pct', 0)
            action = self._get_action(r)
            
            # 格式化盈亏：仅显示比例
            profit_str = ("🟢 " if profit_pct >= 0 else "🔴 ") + f"{profit_pct:+.2f}%"
            
            position_rows += f"""<tr>
  <td>{r.get('etf_code', '')}</td>
  <td>{self._escape(r.get('index_name', ''))}</td>
  <td>{zx_emoji}</td>
  <td><b>{r.get('pattern_score', 0):.0f}</b></td>
  <td>{rsi_str}</td>
  <td>{kdj_str}</td>
  <td>{macd_str}</td>
  <td>{profit_str}</td>
  <td>{action}</td>
</tr>"""

        # 风险评估
        risk_items = []
        if danger_count > total // 2:
            risk_items.append(f"多数标的处于危险信号（{danger_count}只，{danger_pct:.0f}%）")
        if avg_score < 40:
            risk_items.append("整体评分偏低，技术面偏弱")
        if any(r.get('rsi14', 0) > 70 for r in self.results):
            risk_items.append("部分标的RSI超买，注意回调风险")
        if any(r.get('rsi14', 0) < 30 for r in self.results):
            risk_items.append("部分标的超卖，存在反弹机会")
        
        risk_content = "；".join(risk_items) if risk_items else "风险整体可控"

        # 操作建议
        advice_items = []
        if strong:
            strong_names = "、".join([r.get('index_name', '')[:6] for r in strong[:3]])
            advice_items.append(f"强势标的：{strong_names}")
        if watch:
            watch_names = "、".join([r.get('index_name', '')[:6] for r in watch[:2]])
            advice_items.append(f"观望标的：{watch_names}")
        if danger:
            danger_names = "、".join([r.get('index_name', '')[:6] for r in danger[:3]])
            advice_items.append(f"危险标的：{danger_names}")
        
        advice_content = "<ul>" + "".join([f"<li>{item}</li>" for item in advice_items]) + "</ul>" if advice_items else "<p>暂无明确操作建议</p>"

        # 仓位管理建议
        pm_result = self._calculate_position_manager()
        pm_block = self._build_pm_xml_block(pm_result, style=self.pm_style)

        # 生成XML
        xml = f"""<title>ETF持仓分析报告 {self.report_date}</title>

<h1>一、持仓概览</h1>

<table>
  <thead><tr><th>指标</th><th>数值</th></tr></thead>
  <tbody>
    <tr><td>持仓数量</td><td>{total} 只ETF</td></tr>
    <tr><td>综合评分</td><td>{health_emoji} {avg_score:.0f}/100（{health}）</td></tr>
    <tr><td>整体盈亏</td><td>{self._fmt_profit(total_profit_pct)}</td></tr>
    <tr><td>状态</td><td>{status}，{health}</td></tr>
  </tbody>
</table>

<h2>信号分布</h2>
<table>
  <thead><tr><th>信号</th><th>数量</th><th>占比</th></tr></thead>
  <tbody>
    <tr><td>🟢 强势</td><td>{strong_count} 只</td><td>{strong_pct:.0f}%</td></tr>
    <tr><td>🟡 观望</td><td>{watch_count} 只</td><td>{watch_pct:.0f}%</td></tr>
    <tr><td>🔴 危险</td><td>{danger_count} 只</td><td>{danger_pct:.0f}%</td></tr>
  </tbody>
</table>

<h1>二、持仓明细（按市值降序）</h1>
<table>
  <thead><tr>
    <th>代码</th>
    <th>跟踪指数</th>
    <th>知行信号</th>
    <th>评分</th>
    <th>RSI</th>
    <th>KDJ</th>
    <th>MACD</th>
    <th>盈亏</th>
    <th>建议</th>
  </tr></thead>
  <tbody>{position_rows}</tbody>
</table>

<h1>三、操作建议</h1>
{advice_content}

<h1>四、风险提示</h1>
<p>{risk_content}</p>
{pm_block}

<callout emoji="⚠️" background-color="light-yellow" border-color="yellow">
  <p>本报告仅供参考，不构成投资建议。市场有风险，投资需谨慎。</p>
</callout>

<p>报告时间：{self.report_time} 北京时间</p>"""

        return xml

    def create_doc(self) -> tuple:
        """创建飞书文档"""
        content = self.generate()

        # 保存到临时文件
        temp_path = './etf_report.xml'
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                f.write(content)

            # 调用 lark-cli 创建文档
            result = subprocess.run(
                ['lark-cli', 'docs', '+create',
                 '--api-version', 'v2',
                 '--content', f'@{temp_path}'],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                output = json.loads(result.stdout)
                if output.get('ok'):
                    data = output.get('data', {})
                    doc_data = data.get('document', {})
                    doc_id = doc_data.get('document_id', '')
                    doc_url = doc_data.get('url', '')
                    return doc_id, doc_url

            print(f"⚠ 创建文档失败: {result.stderr}")
            return None, None

        except Exception as e:
            print(f"⚠ 创建飞书文档出错: {e}")
            return None, None
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def build_feishu_card(self, doc_url: str = None) -> dict:
        """构建飞书卡片消息 - 按知行信号分类"""
        # 分类
        strong = [r for r in self.results if r.get('signal') == 'STRONG']
        watch = [r for r in self.results if r.get('signal') == 'WATCH']
        danger = [r for r in self.results if r.get('signal') == 'DANGER']
        
        # 构建消息内容
        content_lines = []
        content_lines.append(f"**持仓概览** | {len(self.results)}只ETF | 🟢强势{len(strong)} | 🟡观望{len(watch)} | 🔴危险{len(danger)}")
        content_lines.append("")
        
        # 🟢 强势
        if strong:
            content_lines.append("**🟢 知行强势（白>黄，收在白线上）**")
            for r in strong:
                rsi = r.get('rsi14', 50)
                rsi_status = "超买" if rsi > 70 else ("超卖" if rsi < 30 else "中性")
                content_lines.append(f"• {r.get('etf_name', '')} | RSI={rsi:.0f} {rsi_status}")
            content_lines.append("")
        
        # 🟡 观望
        if watch:
            content_lines.append("**🟡 知行观望（白>黄，收在白线下）**")
            for r in watch:
                rsi = r.get('rsi14', 50)
                pos = r.get('price_pos_60d', 50)
                pos_status = "低位" if pos < 30 else ("高位" if pos > 70 else "中性")
                content_lines.append(f"• {r.get('etf_name', '')} | RSI={rsi:.0f} | {pos_status}")
            content_lines.append("")
        
        # 🔴 危险
        if danger:
            content_lines.append("**🔴 知行危险（白<黄，空头排列）**")
            for r in danger:
                pos = r.get('price_pos_60d', 50)
                pos_status = "低位" if pos < 30 else ("高位" if pos > 70 else "中性")
                content_lines.append(f"• {r.get('etf_name', '')} | {pos_status}")
        
        content = "\n".join(content_lines)
        
        # 构建卡片
        elements = [
            {'tag': 'hr'},
            {'tag': 'div', 'text': {'tag': 'lark_md', 'content': content}}
        ]
        
        # ── 仓位管理区块 ────────────────────────────────────────────────────────
        pm_result = self._calculate_position_manager()
        if pm_result and "error" not in pm_result:
            pm_block = self._build_pm_feishu_block(pm_result, style=self.pm_style)
            if pm_block:
                elements.append({'tag': 'hr'})
                elements.append({'tag': 'div', 'text': {'tag': 'lark_md', 'content': pm_block}})
        
        # 添加文档链接按钮
        if doc_url:
            elements.append({
                'tag': 'action',
                'actions': [{
                    'tag': 'button',
                    'text': {'tag': 'plain_text', 'content': '📄 查看完整报告'},
                    'type': 'primary',
                    'url': doc_url
                }]
            })
        
        elements.append({
            'tag': 'note',
            'elements': [{'tag': 'plain_text', 'content': '⚠️ 本报告仅供参考，不构成投资建议'}]
        })
        
        return {
            'msg_type': 'interactive',
            'card': {
                'config': {'wide_screen_mode': True},
                'header': {
                    'title': {'tag': 'plain_text', 'content': '📊 ETF持仓分析报告'},
                    'subtitle': {'tag': 'plain_text', 'content': f'{self.report_date} | 知行信号分类'},
                    'template': 'blue'
                },
                'elements': elements
            }
        }

    def send_to_feishu(self, doc_url: str = None) -> bool:
        """发送飞书卡片消息"""
        try:
            from market_monitor.config import FEISHU_WEBHOOK
            import requests
            
            if not FEISHU_WEBHOOK:
                print("⚠ 飞书 Webhook 未配置")
                return False
            
            payload = self.build_feishu_card(doc_url)
            
            response = requests.post(
                FEISHU_WEBHOOK,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            result = response.json()
            if result.get('code') == 0:
                print("✅ 飞书卡片消息已发送")
                return True
            else:
                print(f"⚠ 飞书发送失败: {result}")
                return False
                
        except Exception as e:
            print(f"⚠ 发送到飞书失败: {e}")
            return False


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="ETF持仓专业分析报告")
    parser.add_argument("--feishu", "-f", action="store_true", help="发送飞书消息")
    parser.add_argument("--positions", "-p", default="data/positions.json", help="持仓文件路径")
    parser.add_argument("--pm-style", "-s", 
                        choices=["compact", "market", "action", "all"],
                        default="action",
                        help="仓位展示样式: compact=简洁总览, market=市场明细, action=行动聚焦(默认), all=全部样式")
    args = parser.parse_args()
    
    print(f"\n{'='*60}")
    print(f"📊 ETF持仓专业分析报告")
    print(f"{'='*60}\n")

    # 加载持仓
    positions_path = args.positions
    if os.path.exists(positions_path):
        with open(positions_path, 'r', encoding='utf-8') as f:
            positions = json.load(f)
        print(f"📂 加载持仓: {len(positions)} 只\n")
    else:
        print(f"❌ 持仓文件不存在: {positions_path}")
        return

    # 获取ETF代码列表
    etf_codes = [p.get('code', '') for p in positions if p.get('code', '') in ETF_MAPPING]
    
    # 通过Tushare获取实时价格
    print("📡 通过Tushare获取实时价格...")
    realtime_prices = get_realtime_price(etf_codes)
    print(f"   获取到 {len(realtime_prices)} 只ETF的实时价格\n")

    # 分析每只ETF
    results = []
    for p in positions:
        code = p.get('code', '')
        name = p.get('name', '')

        if code in ETF_MAPPING:
            mapping = ETF_MAPPING[code]
            result = analyze_etf(
                etf_code=code,
                etf_name=name or mapping['name'],
                index_code=mapping['index'],
                index_name=mapping['index_name'],
            )
            if result:
                # 合并持仓信息
                result['shares'] = p.get('shares', 0)
                result['cost_price'] = p.get('cost_price', 0)
                
                # 优先使用Tushare实时价格
                realtime_price = realtime_prices.get(code, 0)
                cost = result['cost_price']
                
                if realtime_price > 0:
                    result['current_price'] = realtime_price
                    result['price_source'] = '实时'
                else:
                    print(f"  [警告] {code} 无法获取实时价格")
                    continue
                
                current = result['current_price']
                
                # 计算市值和盈亏
                result['market_value'] = current * result['shares']  # 实时市值
                result['cost_value'] = cost * result['shares']  # 成本市值
                result['profit_pct'] = ((current - cost) / cost * 100) if cost > 0 else 0  # 盈亏比例
                result['profit_value'] = result['market_value'] - result['cost_value']  # 盈亏金额
                
                # 通过xalpha获取基金净值作为参考
                print(f"  [{code}] {mapping['name']}")
                print(f"         实时价: {current:.3f}, 成本: {cost:.3f}, 市值: {result['market_value']:.0f}元")
                print(f"         盈亏: {result['profit_pct']:+.2f}% ({result['profit_value']:+.0f}元)")
                
                nav, nav_date = get_etf_nav(code)
                if nav > 0:
                    result['nav'] = nav
                    result['nav_date'] = nav_date
                    print(f"         基金净值: {nav:.4f} ({nav_date})")

                results.append(result)

    print(f"\n✅ 分析完成: {len(results)} 只ETF\n")

    if not results:
        print("❌ 无有效分析结果")
        return

    # 根据参数确定仓位展示样式
    pm_style = args.pm_style if args.pm_style != "all" else ProfessionalETFReportGenerator.PM_STYLE_ACTION

    # 生成专业版报告
    generator = ProfessionalETFReportGenerator(results, pm_style=pm_style)
    
    # 如果选择 all 样式，生成多个版本的报告
    if args.pm_style == "all":
        styles = {
            "compact": "简洁总览版",
            "market": "市场明细版",
            "action": "行动聚焦版"
        }
        print(f"\n📋 仓位展示样式选择: 全部样式 (3个版本)")
        print("=" * 60)
        
        for style_name, style_desc in styles.items():
            print(f"\n【{style_desc}】")
            pm_result = generator._calculate_position_manager()
            if pm_result and "error" not in pm_result:
                # XML版
                xml_block = generator._build_pm_xml_block(pm_result, style=style_name)
                print(xml_block)
                print("-" * 40)
                # 飞书版
                feishu_block = generator._build_pm_feishu_block(pm_result, style=style_name)
                print(feishu_block)
            print()
        print("=" * 60)
        print("💡 请选择一个样式，使用 -s <style> 参数生成正式报告")
        print("   例如: python3 -m market_monitor.report.portfolio_professional -s action")
        return
    
    doc_id, doc_url = generator.create_doc()

    if doc_url:
        print(f"\n📄 专业版报告已创建: {doc_url}")
    else:
        # 输出XML内容供调试
        print("\n⚠ 文档创建失败，以下是报告内容预览:")
        print("-" * 60)
        print(generator.generate()[:2000])
        print("-" * 60)

    # 发送飞书消息
    if args.feishu:
        print()
        generator.send_to_feishu(doc_url)

    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    main()
