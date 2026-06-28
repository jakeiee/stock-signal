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

# 加载 .env 文件（确保 CODEBUDDY_API_KEY 等变量可用）
def _load_env():
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env')
    if not os.path.exists(env_path):
        return
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path)
    except ImportError:
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, _, value = line.partition('=')
                    key, value = key.strip(), value.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = value
_load_env()

import json
import subprocess
import re
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

# 统一ETF映射（从唯一数据源导入）
from market_monitor.data.etf_index_mapping import (
    lookup_by_etf_code as _lookup_etf, is_unsupported_index,
)

# 知行趋势线（唯一指标计算源）— 替代本文件中所有重复计算
from market_monitor.analysis.zhixing import compute_all_indicators as _compute_indicators
from market_monitor.analysis.zhixing import get_trend_status as _get_trend_status
from market_monitor.analysis.zhixing import comprehensive_score as _comprehensive_score

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
    """计算技术指标（调用 zhixing 统一入口，向后兼容包装器）"""
    return _compute_indicators(df)


# ── 信号兼容映射（三级→五级） ─────────────────────────────────────────────────
# 旧的 STRONG/WATCH/DANGER 统一到五级信号体系
_SIGNAL_COMPAT = {"STRONG": "BUY", "WATCH": "HOLD_BULL", "DANGER": "HOLD_BEAR"}

def analyze_etf(etf_code: str, etf_name: str, index_code: str, index_name: str) -> Dict:
    """分析单只ETF（使用 zhixing 统一指标计算和信号系统）"""
    print(f"  [{etf_code}] {etf_name} -> {index_name}")

    # 获取数据
    df = get_index_data(index_code)
    if df.empty:
        return None

    # 计算技术指标（zhixing 统一入口）
    df = calculate_technical(df)
    if len(df) < 60:
        return None

    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else latest

    # 使用 zhixing 五级信号体系
    trend_status = _get_trend_status(df)
    if "error" in trend_status:
        return None
    signal = trend_status["signal"]  # BUY/HOLD_BULL/HOLD_NEUTRAL/HOLD_BEAR/SELL
    position = trend_status["position"]  # 多头排列/空头排列/纠缠整理

    # 综合评分
    score_result = _comprehensive_score(df)
    pattern_score = score_result.get("total_score", 0)

    # 知行趋势线
    short_trend = latest.get("zx_short", 0)
    long_trend = latest.get("zx_long", 0)
    close_price = latest.get("close", 0)

    # 前一天数据（用于计算偏离变化）
    prev_short = prev.get("zx_short", 0)
    prev_close = prev.get("close", 0)

    # 偏离比例（从 DataFrame 直接取）
    close_pct_short = latest.get("close_pct_short", 0) or ((close_price / short_trend) - 1) * 100 if short_trend else 0
    close_pct_long = latest.get("close_pct_long", 0) or ((close_price / long_trend) - 1) * 100 if long_trend else 0
    short_pct_long = latest.get("short_pct_long", 0) or ((short_trend / long_trend) - 1) * 100 if long_trend else 0
    prev_close_pct = ((prev_close / prev_short) - 1) * 100 if prev_short else 0
    close_deviation_change = close_pct_short - prev_close_pct

    # 三线位置 / 均线排列（从 DataFrame 直接取）
    line_position = latest.get("line_position", "三线纠缠")
    ma_pattern = latest.get("ma_pattern", "均线纠缠")

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
    if not latest.get("vol_match", False) and latest.get("vol_ratio", 1) > 1.2:
        if price_pos > 60 and latest.get("price_change", 0) > 0:
            abnormal.append({"type": "顶背离", "description": "价涨量缩，上涨动力不足", "severity": "warning"})
        elif price_pos < 40 and latest.get("price_change", 0) < 0:
            abnormal.append({"type": "底背离", "description": "价跌量缩，可能企稳", "severity": "positive"})

    return {
        "etf_code": etf_code,
        "etf_name": etf_name,
        "index_code": index_code,
        "index_name": index_name,
        "close": close_price,
        "zx_short": short_trend,
        "zx_long": long_trend,
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
        "rsi14": latest.get("rsi14", 50),
        "vol_ratio": latest.get("vol_ratio", 1),
        "vol_match": latest.get("vol_match", False),
        "price_pos_60d": price_pos,
        "signal": signal,
        "position": position,
        "pattern_score": pattern_score,
        "abnormal_signals": abnormal,
        "close_pct_short": close_pct_short,
        "close_pct_long": close_pct_long,
        "short_pct_long": short_pct_long,
        "close_deviation_change": close_deviation_change,
        "line_position": line_position,
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

    def __init__(self, results: List[Dict], pm_style: str = None, enable_selection: bool = False):
        self.results = results
        beijing_tz = timezone(timedelta(hours=8))
        self.now = datetime.now(beijing_tz)
        self.report_time = self.now.strftime("%Y-%m-%d %H:%M")
        self.report_date = self.now.strftime("%Y-%m-%d")
        # 仓位展示样式，默认使用行动聚焦
        self.pm_style = pm_style or self.PM_STYLE_ACTION
        # 是否启用选股推荐模块
        self.enable_selection = enable_selection
        self._selection_cache = None  # 缓存选股结果，避免重复计算

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
            return "🟢金叉多头", "白>黄，收在白线上"
        elif zx_short > zx_long and close <= zx_short:
            return "🟡偏弱多头", "白>黄，收在白线下"
        else:
            return "🔴空头排列", "白<黄"

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
        
        if sig == 'BUY':
            if rsi > 70: return "持有/减仓"
            elif rsi < 30: return "加仓机会"
            return "持有"
        elif sig == 'HOLD_BULL':
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
            buy_count = sum(1 for r in self.results if r.get('signal') == 'BUY')
            bull_count = sum(1 for r in self.results if r.get('signal') == 'HOLD_BULL')
            bear_count = sum(1 for r in self.results if r.get('signal') == 'HOLD_BEAR')

            # 整体趋势判断
            if bear_count >= len(self.results) * 0.6:
                overall_trend = "bearish"
            elif buy_count >= len(self.results) * 0.4:
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
                    "buy": buy_count,
                    "bull": bull_count,
                    "bear": bear_count,
                },
                "overall_trend": overall_trend,
            }
            
            return result
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e)}

    def _generate_selection_section(self) -> str:
        """
        选股推荐模块 - 运行ETF筛选流水线并生成XML内容。
        
        仅展示初筛结果和前10只候选标的，完整分析存入本地文件。
        """
        if not self.enable_selection:
            return ""
        
        if self._selection_cache is not None:
            return self._selection_cache
        
        print("\n  🔍 [选股模块] 运行ETF筛选流水线...")
        section_parts = []
        
        try:
            from market_monitor.data_sources.etf_selector import get_selection_etfs
            from market_monitor.analysis.zhixing import fetch_index_history_xalpha, get_trend_status, comprehensive_score
            from market_monitor.data.etf_index_mapping import lookup_by_index_name
            
            # Phase 1: 初筛
            result1 = get_selection_etfs(scale_min=5000)
            total_count = result1.get("total", 0)
            etfs = result1.get("etfs", [])
            
            # 排除已持仓的ETF
            held_codes = {r.get('etf_code', '') for r in self.results}
            new_etfs = [e for e in etfs if e['code'] not in held_codes]
            
            # Phase 2: 知行分析（前10只新ETF）
            analyses = []
            for etf in new_etfs[:10]:
                track = etf.get('track_target', '')
                xa_code = lookup_by_index_name(track)
                if not xa_code:
                    continue
                
                df = fetch_index_history_xalpha(xa_code)
                if df is None or df.empty or len(df) < 20:
                    continue
                
                a = get_trend_status(df)
                if 'error' in a:
                    continue
                
                score = comprehensive_score(df)
                a.update(score)
                a['code'] = etf['code']
                a['name'] = etf['name']
                a['etf_type'] = etf.get('type', '')
                a['price'] = etf.get('price', 0)
                a['premium'] = etf.get('premium', 0)
                a['scale'] = etf.get('scale', 0)
                a['kdj_j'] = a.get('kdj_j', etf.get('kdj_value', 0))
                a['track_target'] = track
                analyses.append(a)
            
            # 统计
            signal_map = {'BUY': '🟢金叉买入', 'HOLD_BULL': '🟡多头持有', 
                         'HOLD_NEUTRAL': '⚪中性', 'HOLD_BEAR': '🔴空头'}
            signal_count = {}
            for a in analyses:
                s = a.get('signal', '?')
                signal_count[s] = signal_count.get(s, 0) + 1
            
            # 买入候选
            buy_candidates = [a for a in analyses if a.get('signal') == 'BUY' and a.get('total_score', 0) >= 40]
            watch_candidates = [a for a in analyses if a.get('signal') == 'HOLD_BULL' and a.get('total_score', 0) >= 40]
            high_score = sorted([a for a in analyses if a.get('total_score', 0) >= 30],
                               key=lambda x: x.get('total_score', 0), reverse=True)[:5]
            
            # 构建XML
            section_parts.append(f'<h1>六、选股推荐</h1>')
            section_parts.append(f'<p>筛选条件：KDJ&lt;0, 规模&gt;5000万, 5大类ETF</p>')
            section_parts.append(f'<p>初筛：<b>{total_count}</b> 只 → 新建仓候选（去重）：<b>{len(new_etfs)}</b> 只 → 知行分析：<b>{len(analyses)}</b> 只</p>')
            
            # 信号分布
            section_parts.append('<h2>信号分布</h2>')
            section_parts.append('<table><thead><tr><th>信号</th><th>数量</th></tr></thead><tbody>')
            for s, label in [('BUY','🟢金叉买入'), ('HOLD_BULL','🟡多头持有'), 
                            ('HOLD_NEUTRAL','⚪中性'), ('HOLD_BEAR','🔴空头')]:
                cnt = signal_count.get(s, 0)
                if cnt > 0:
                    section_parts.append(f'<tr><td>{label}</td><td>{cnt} 只</td></tr>')
            section_parts.append('</tbody></table>')
            
            # 买入推荐
            if buy_candidates:
                section_parts.append('<h2>🟢 买入推荐（金叉 + 评分≥40）</h2>')
                section_parts.append('<table><thead><tr><th>代码</th><th>名称</th><th>类型</th><th>评分</th><th>KDJ_J</th><th>溢价%</th></tr></thead><tbody>')
                for b in buy_candidates:
                    section_parts.append(
                        f'<tr><td>{b["code"]}</td><td>{self._escape(b["name"])}</td>'
                        f'<td>{b.get("etf_type","")}</td><td><b>{b.get("total_score",0):.0f}</b></td>'
                        f'<td>{b.get("kdj_j",0):.1f}</td><td>{b.get("premium",0):.2f}%</td></tr>')
                section_parts.append('</tbody></table>')
            
            if watch_candidates:
                section_parts.append('<h2>🟡 关注列表（多头持有 + 评分≥40）</h2>')
                section_parts.append('<table><thead><tr><th>代码</th><th>名称</th><th>类型</th><th>评分</th><th>KDJ_J</th></tr></thead><tbody>')
                for w in watch_candidates:
                    section_parts.append(
                        f'<tr><td>{w["code"]}</td><td>{self._escape(w["name"])}</td>'
                        f'<td>{w.get("etf_type","")}</td><td><b>{w.get("total_score",0):.0f}</b></td>'
                        f'<td>{w.get("kdj_j",0):.1f}</td></tr>')
                section_parts.append('</tbody></table>')
            
            # 知行分析明细（始终展示，方便查看所有候选ETF的具体指标）
            if analyses:
                section_parts.append('<h2>📊 知行分析明细</h2>')
                section_parts.append('<table><thead><tr><th>代码</th><th>名称</th><th>类型</th><th>评分</th><th>信号</th><th>排列</th><th>KDJ_J</th></tr></thead><tbody>')
                sorted_analyses = sorted(analyses, key=lambda x: x.get('total_score', 0), reverse=True)
                for a in sorted_analyses:
                    sig = a.get('signal', '')
                    sig_emoji = {'BUY': '🟢', 'HOLD_BULL': '🟡', 'HOLD_NEUTRAL': '⚪', 'HOLD_BEAR': '🔴'}.get(sig, '⚪')
                    section_parts.append(
                        f'<tr><td>{a["code"]}</td><td>{self._escape(a["name"])}</td>'
                        f'<td>{a.get("etf_type","")}</td><td>{a.get("total_score",0):.0f}</td>'
                        f'<td>{sig_emoji} {sig}</td><td>{a.get("position","")}</td>'
                        f'<td>{a.get("kdj_j",0):.1f}</td></tr>')
                section_parts.append('</tbody></table>')
            
            # 高评分候选（评分≥30）
            if high_score and not buy_candidates:
                section_parts.append('<h2>📊 高评分候选（评分≥30，待观察）</h2>')
                section_parts.append('<table><thead><tr><th>代码</th><th>名称</th><th>类型</th><th>评分</th><th>信号</th><th>KDJ_J</th></tr></thead><tbody>')
                for h in high_score:
                    sig = signal_map.get(h.get('signal',''), h.get('signal',''))
                    section_parts.append(
                        f'<tr><td>{h["code"]}</td><td>{self._escape(h["name"])}</td>'
                        f'<td>{h.get("etf_type","")}</td><td><b>{h.get("total_score",0):.0f}</b></td>'
                        f'<td>{sig}</td><td>{h.get("kdj_j",0):.1f}</td></tr>')
                section_parts.append('</tbody></table>')
            
            # 无买入候选时的提示
            if not buy_candidates and not watch_candidates:
                section_parts.append('<p>⚠️ 当前无评分≥40的达标标的，详见上方知行分析明细表。</p>')
            
            result = "\n".join(section_parts)
            print(f"  ✅ 选股分析完成: {len(analyses)} 只候选")
            
        except Exception as e:
            print(f"  ⚠ 选股模块运行失败: {e}")
            result = f'<p>⚠ 选股模块运行异常: {self._escape(str(e))}</p>'
        
        self._selection_cache = result
        return result

    def _generate_history_section(self) -> str:
        """生成历史对比章节（本周vs上周信号变化）。"""
        try:
            from market_monitor.data.portfolio_db import get_db
            db = get_db()
            changes = db.get_signal_changes(self.report_date)
            
            if not changes:
                return ""
            
            lines = ["", "<h1>三.2、信号变化（vs上期）</h1>", "",
                     "<table>", "<thead><tr><th>ETF</th><th>上期信号</th><th>本期信号</th><th>评分变化</th></tr></thead>",
                     "<tbody>"]
            
            for c in changes:
                prev = c['prev_signal']
                curr = c['curr_signal']
                direction = "📈" if c['score_change'] > 0 else "📉" if c['score_change'] < 0 else "➖"
                lines.append(
                    f"<tr><td>{self._escape(c['etf_name'])}</td>"
                    f"<td>{prev}</td><td><b>{curr}</b></td>"
                    f"<td>{direction} {c['score_change']:+.0f}</td></tr>"
                )
            
            lines.append("</tbody></table>")
            return "\n".join(lines)
        except Exception:
            return ""
    
    def _generate_portfolio_analysis_section(self) -> str:
        """生成组合分析章节（板块集中度+权重分布）。"""
        try:
            from market_monitor.analysis.portfolio_analyzer import PortfolioAnalyzer
            analyzer = PortfolioAnalyzer(self.results)
            summary = analyzer.summary()
            
            lines = ["", "<h1>三.3、组合分析</h1>"]
            
            # 板块集中度
            sector = summary.get("sector_concentration", {})
            if sector:
                lines.append("<h2>板块集中度</h2>")
                lines.append("<table><thead><tr><th>板块</th><th>数量</th><th>权重</th></tr></thead><tbody>")
                for name, info in sector.items():
                    lines.append(f"<tr><td>{name}</td><td>{info['count']}只</td><td>{info['weight']:.1f}%</td></tr>")
                lines.append("</tbody></table>")
            
            # 市场权重分布
            wd = summary.get("weight_distribution", {})
            if wd:
                lines.append("<h2>市场权重分布</h2>")
                lines.append("<table><thead><tr><th>市场</th><th>占比</th></tr></thead><tbody>")
                for market, pct in wd.items():
                    lines.append(f"<tr><td>{market}</td><td>{pct}%</td></tr>")
                lines.append("</tbody></table>")
            
            return "\n".join(lines)
        except Exception:
            return ""
    
    def _generate_tracking_section(self) -> str:
        """生成选股追踪统计章节。"""
        try:
            from market_monitor.report.selection_tracker import SelectionTracker
            tracker = SelectionTracker()
            stats = tracker.get_tracking_stats()
            
            if stats.get("total_checked", 0) == 0:
                return ""
            
            lines = ["", "<h1>七、选股追踪统计</h1>", "",
                     "<table><thead><tr><th>指标</th><th>数值</th></tr></thead><tbody>",
                     f"<tr><td>累计检查</td><td>{stats['total_checked']} 条</td></tr>",
                     f"<tr><td>命中率</td><td>{stats['hit_rate']:.0f}% ({stats['hits']}/{stats['total_checked']})</td></tr>",
                     f"<tr><td>平均7日收益</td><td>{stats['avg_return_7d']:+.2f}%</td></tr>",
                     "</tbody></table>"]
            return "\n".join(lines)
        except Exception:
            return ""

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

<p><em>* 当前仓位基于持仓市值计算，建议仓位基于模型配置</em></p>
<p><em>* ⭐ 表示调整幅度较大，建议优先处理</em></p>
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

    def generate(self, llm_text: str = None) -> str:
        """生成完整报告"""
        self._llm_text = llm_text  # 缓存供子方法使用
        total = len(self.results)
        avg_score = sum(r.get('pattern_score', 0) for r in self.results) / total if total else 0

        buy_list = [r for r in self.results if r.get('signal') == 'BUY']
        bull_list = [r for r in self.results if r.get('signal') == 'HOLD_BULL']
        neutral_list = [r for r in self.results if r.get('signal') == 'HOLD_NEUTRAL']
        bear_list = [r for r in self.results if r.get('signal') == 'HOLD_BEAR']

        buy_count, bull_count, neutral_count, bear_count = len(buy_list), len(bull_list), len(neutral_list), len(bear_list)
        buy_pct = buy_count / total * 100 if total else 0
        bull_pct = bull_count / total * 100 if total else 0
        neutral_pct = neutral_count / total * 100 if total else 0
        bear_pct = bear_count / total * 100 if total else 0

        # 计算整体盈亏
        total_profit = sum(r.get('profit_pct', 0) for r in self.results) / total if total else 0
        
        # 权重
        total_weight = sum(r.get('weight', 0) for r in self.results)
        
        # 健康评级
        health = "优秀" if avg_score >= 70 else "良好" if avg_score >= 50 else "一般" if avg_score >= 30 else "较差"
        health_emoji = "🟢" if avg_score >= 50 else "🟡" if avg_score >= 30 else "🔴"
        
        status = "整体偏弱" if bear_count > buy_count else "整体偏强" if buy_count > bear_count else "分化明显"

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
            sig_emoji = {"BUY": "🟢", "HOLD_BULL": "🟡", "HOLD_NEUTRAL": "⚪", "HOLD_BEAR": "🔴", "SELL": "🛑"}.get(sig, "⚪")
            
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
        if bear_count > total // 2:
            risk_items.append(f"多数标的处于空头信号（{bear_count}只，{bear_pct:.0f}%）")
        if avg_score < 40:
            risk_items.append("整体评分偏低，技术面偏弱")
        if any(r.get('rsi14', 0) > 70 for r in self.results):
            risk_items.append("部分标的RSI超买，注意回调风险")
        if any(r.get('rsi14', 0) < 30 for r in self.results):
            risk_items.append("部分标的超卖，存在反弹机会")
        
        risk_content = "；".join(risk_items) if risk_items else "风险整体可控"

        # 操作建议（含具体动作）
        advice_items = []
        for r in sorted_results:
            name = r.get('etf_name', r.get('index_name', '')[:15])
            action = self._get_action(r)
            sig = r.get('signal', '')
            sig_emoji = {"BUY": "🟢", "HOLD_BULL": "🟡", "HOLD_NEUTRAL": "⚪", "HOLD_BEAR": "🔴", "SELL": "🛑"}.get(sig, "⚪")
            advice_items.append(f"{sig_emoji} {name}：{action}")
        
        advice_content = "<ul>" + "".join([f"<li>{item}</li>" for item in advice_items]) + "</ul>" if advice_items else "<p>暂无明确操作建议</p>"

        # 仓位管理建议
        pm_result = self._calculate_position_manager()
        pm_block = self._build_pm_xml_block(pm_result, style=self.pm_style)

        # 选股推荐（可选）
        selection_section = self._generate_selection_section()

        # 历史对比
        history_section = self._generate_history_section()

        # 组合分析
        portfolio_analysis_section = self._generate_portfolio_analysis_section()

        # 选股追踪统计
        tracking_section = self._generate_tracking_section()

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

<h2>信号分布（五级知行信号）</h2>
<table>
  <thead><tr><th>信号</th><th>数量</th><th>占比</th></tr></thead>
  <tbody>
    <tr><td>🟢 金叉买入 (BUY)</td><td>{buy_count} 只</td><td>{buy_pct:.0f}%</td></tr>
    <tr><td>🟡 多头持有 (HOLD_BULL)</td><td>{bull_count} 只</td><td>{bull_pct:.0f}%</td></tr>
    <tr><td>⚪ 中性观望 (HOLD_NEUTRAL)</td><td>{neutral_count} 只</td><td>{neutral_pct:.0f}%</td></tr>
    <tr><td>🔴 空头持有 (HOLD_BEAR)</td><td>{bear_count} 只</td><td>{bear_pct:.0f}%</td></tr>
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

{history_section}

{portfolio_analysis_section}

<h1>四、风险提示</h1>
<p>{risk_content}</p>
{pm_block}
{selection_section}
{tracking_section}

<callout emoji="⚠️" background-color="light-yellow" border-color="yellow">
  <p>本报告仅供参考，不构成投资建议。市场有风险，投资需谨慎。</p>
</callout>

<h1>八、AI 解读</h1>
<p>{self._escape(self._llm_text) if self._llm_text else "（未启用 AI 解读，使用 --llm 参数启用）"}</p>

<p>报告时间：{self.report_time} 北京时间</p>"""

        # 异步保存快照到 SQLite（不阻塞报告生成）
        try:
            from market_monitor.data.portfolio_db import get_db
            db = get_db()
            db.save_snapshot(self.report_date, self.results)
        except Exception:
            pass

        return xml

    def _get_feishu_token(self) -> str:
        """获取飞书 tenant_access_token"""
        import requests
        app_id = os.getenv('FEISHU_APP_ID', '')
        app_secret = os.getenv('FEISHU_APP_SECRET', '')
        # 调试：打印环境变量状态
        print(f"   [DEBUG] FEISHU_APP_ID 存在: {bool(app_id)}, 长度: {len(app_id) if app_id else 0}")
        print(f"   [DEBUG] FEISHU_APP_SECRET 存在: {bool(app_secret)}, 长度: {len(app_secret) if app_secret else 0}")
        if not app_id or not app_secret:
            print("   错误: FEISHU_APP_ID 或 FEISHU_APP_SECRET 未设置")
            return None
        resp = requests.post(
            'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
            json={'app_id': app_id, 'app_secret': app_secret},
            timeout=10
        )
        data = resp.json()
        if data.get('code') == 0:
            return data.get('tenant_access_token')
        print(f"   获取 token 失败: {data}")
        return None

    def create_doc(self) -> tuple:
        """创建飞书文档 - 使用 lark-cli XML 格式（原生支持表格/标题/粗体）"""
        print(f"📄 正在创建飞书文档...")
        
        content_xml = self.generate(llm_text=getattr(self, '_llm_text', None))
        
        try:
            # 通过 stdin 传入 XML 内容（避免命令行参数长度限制）
            result = subprocess.run(
                ['lark-cli', 'docs', '+create', '--api-version', 'v2',
                 '--content', '-', '--doc-format', 'xml'],
                capture_output=True, text=True, timeout=30,
                input=content_xml,
                cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            )
            
            if result.returncode == 0:
                try:
                    data = json.loads(result.stdout.strip())
                    if data.get('ok'):
                        doc_info = data.get('data', {}).get('document', {})
                        doc_id = doc_info.get('document_id', '')
                        doc_url = doc_info.get('url', '') or f'https://my.feishu.cn/docx/{doc_id}'
                        print(f"   文档创建成功（表格模式）: {doc_url}")
                        return doc_id, doc_url
                except json.JSONDecodeError:
                    pass
            
            print(f"   lark-cli 返回异常: {result.stderr[:200] if result.stderr else result.stdout[:200]}")
            return self._create_doc_raw()
        
        except FileNotFoundError:
            print("   ⚠ lark-cli 不可用，回退到 REST API")
            return self._create_doc_raw()
        except Exception as e:
            print(f"   lark-cli 异常: {e}")
            return self._create_doc_raw()
    
    def _create_doc_raw(self) -> tuple:
        """回退方案：使用 REST API 创建纯文本文档（无表格）"""
        import requests
        token = self._get_feishu_token()
        if not token:
            return None, None
        
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        
        create_resp = requests.post(
            'https://open.feishu.cn/open-apis/docx/v1/documents',
            headers=headers,
            json={'title': f'ETF持仓分析报告 {self.report_date}'},
            timeout=10
        )
        create_data = create_resp.json()
        if create_data.get('code') != 0:
            print(f"   创建文档失败: {create_data}")
            return None, None
        
        doc_id = create_data.get('data', {}).get('document', {}).get('document_id', '')
        doc_url = f"https://my.feishu.cn/docx/{doc_id}"
        
        # 用结构化 blocks 写入
        content_xml = self.generate(llm_text=getattr(self, '_llm_text', None))
        blocks = self._build_doc_blocks(content_xml)
        
        batch_size = 50
        for i in range(0, len(blocks), batch_size):
            batch = blocks[i:i + batch_size]
            write_resp = requests.post(
                f'https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children',
                headers=headers,
                json={'children': batch, 'index': -1},
                timeout=30
            )
            wd = write_resp.json()
            if wd.get('code') != 0:
                print(f"   写入第{i//batch_size + 1}批失败: {wd}")
                return doc_id, doc_url
        
        print(f"   文档创建成功（纯文本模式）: {doc_url}")
        return doc_id, doc_url

    # ── Block 构建方法 ────────────────────────────────────────────────────────
    
    @staticmethod
    def _make_text_block(content: str, bold: bool = False) -> dict:
        """创建普通文本块。"""
        style = {'bold': bold} if bold else {}
        return {
            'block_type': 2,
            'text': {
                'elements': [{'text_run': {'content': content, 'text_element_style': style}}],
                'style': {}
            }
        }
    
    @staticmethod
    def _make_heading_block(level: int, content: str) -> dict:
        """创建标题块 (level 1-9)。block_type: 3=H1, 4=H2, ... 11=H9"""
        return {
            'block_type': min(2 + level, 11),
            f'heading{min(level, 9)}': {
                'elements': [{'text_run': {'content': content}}],
                'style': {}
            }
        } if level <= 9 else ProfessionalETFReportGenerator._make_text_block(content)
    
    @staticmethod
    def _make_sep_block() -> dict:
        """创建分隔文本块（因 divider block_type=31 不支持作为 children）。"""
        return {'block_type': 2, 'text': {
            'elements': [{'text_run': {'content': '━━━━━━━━━━━━━━━━━━━━━━━━━━━━'}}],
            'style': {}
        }}
    
    @classmethod
    def _make_rich_text_block(cls, parts: list) -> dict:
        """创建富文本块（支持混合粗体/普通文本）。
        
        parts: [("普通文本", False), ("粗体文本", True), ...]
        """
        elements = []
        for text, bold in parts:
            elements.append({
                'text_run': {
                    'content': text,
                    'text_element_style': {'bold': bold} if bold else {}
                }
            })
        return {'block_type': 2, 'text': {'elements': elements, 'style': {}}}

    @classmethod
    def _build_simple_table(cls, headers: list, rows: list) -> list:
        """将表格转换为格式化文本块列表。
        
        headers: ["列1", "列2", ...]
        rows: [["r1c1", "r1c2"], ["r2c1", "r2c2"], ...]
        """
        if not headers or not rows:
            return []
        
        ncols = len(headers)
        
        # 计算每列宽度
        col_widths = [len(str(h)) for h in headers]
        for row in rows:
            for j, cell in enumerate(row[:ncols]):
                col_widths[j] = max(col_widths[j], min(len(str(cell)), 20))
        
        blocks = []
        
        # 表头块（加粗）
        header_parts = []
        for i, h in enumerate(headers):
            if i > 0:
                header_parts.append(('  ', False))
            header_parts.append((str(h), True))
        
        # 分隔线
        sep = '─' * (sum(col_widths) + (ncols - 1) * 2)
        
        blocks.append({
            'block_type': 2, 'text': {
                'elements': [{'text_run': {'content': txt, 'text_element_style': {'bold': bold}}} 
                           for txt, bold in header_parts],
                'style': {}
            }
        })
        blocks.append({'block_type': 2, 'text': {
            'elements': [{'text_run': {'content': sep}}], 'style': {}
        }})
        
        # 数据行（每5行一组）
        for row in rows:
            row_parts = []
            for j in range(ncols):
                if j > 0:
                    row_parts.append('  ')
                c = str(row[j]) if j < len(row) else ''
                row_parts.append(c[:col_widths[j]*3].ljust(col_widths[j]))
            blocks.append({'block_type': 2, 'text': {
                'elements': [{'text_run': {'content': ''.join(row_parts)}}],
                'style': {}
            }})
        
        return blocks
    
    @classmethod
    def _build_doc_blocks(cls, xml: str) -> list:
        """将报告XML转换为飞书Docx Block列表。"""
        blocks = []
        lines = xml.split('\n')
        i = 0
        
        in_table = False
        table_lines = []
        
        while i < len(lines):
            line = lines[i].strip()
            
            # 处理表格
            if '<table>' in line:
                in_table = True
                table_lines = [line]
                i += 1
                continue
            
            if in_table:
                table_lines.append(line)
                if '</table>' in line:
                    in_table = False
                    table_text = ' '.join(table_lines)
                    headers, rows = cls._parse_html_table(table_text)
                    if headers and rows:
                        blocks.extend(cls._build_simple_table(headers, rows))
                    table_lines = []
                i += 1
                continue
            
            # 处理标题（跳过，飞书文档已有独立标题，不重复添加 H1）
            title_match = re.match(r'<title>(.*)</title>', line)
            if title_match:
                i += 1
                continue
            
            h_match = re.match(r'<h1>(.*)</h1>', line)
            if h_match:
                blocks.append(cls._make_sep_block())
                blocks.append(cls._make_heading_block(2, h_match.group(1).strip()))
                i += 1
                continue
            
            h2_match = re.match(r'<h2>(.*)</h2>', line)
            if h2_match:
                blocks.append(cls._make_heading_block(3, h2_match.group(1).strip()))
                i += 1
                continue
            
            # 处理列表
            li_match = re.match(r'<li>(.*)</li>', line)
            if li_match:
                text = re.sub(r'<[^>]+>', '', li_match.group(1))
                blocks.append({'block_type': 2, 'text': {
                    'elements': [{'text_run': {'content': '• ' + text}}],
                    'style': {}
                }})
                i += 1
                continue
            
            # 处理 callout
            if '<callout' in line:
                i += 1
                callout_text = ''
                while i < len(lines) and '</callout>' not in lines[i]:
                    part = re.sub(r'<[^>]+>', '', lines[i]).strip()
                    if part:
                        callout_text += part + '\n'
                    i += 1
                if callout_text.strip():
                    blocks.append(cls._make_sep_block())
                    blocks.append(cls._make_text_block('⚠️ ' + callout_text.strip()))
                i += 1
                continue
            
            # 处理普通段落
            p_match = re.match(r'<p>(.*)</p>', line)
            if p_match:
                text = cls._parse_inline_text(p_match.group(1))
                blocks.append(text)
                i += 1
                continue
            
            # 空行跳过
            if not line:
                i += 1
                continue
            
            # 其他：作为普通文本
            clean = re.sub(r'<[^>]+>', '', line).strip()
            if clean and not clean.startswith('<'):
                blocks.append(cls._make_text_block(clean))
            
            i += 1
        
        # 末尾（XML 中已有免责声明+报告时间，不再重复添加）
        return blocks
    
    @classmethod
    def _parse_html_table(cls, html_text: str) -> tuple:
        """解析HTML表格，返回 (headers, rows)。"""
        # 提取表头
        headers = []
        th_match = re.findall(r'<th>(.*?)</th>', html_text, re.DOTALL)
        for h in th_match:
            headers.append(re.sub(r'<[^>]+>', '', h).strip())
        
        # 提取行
        rows = []
        tr_blocks = re.findall(r'<tr>(.*?)</tr>', html_text, re.DOTALL)
        for tr in tr_blocks:
            tds = re.findall(r'<td>(.*?)</td>', tr, re.DOTALL)
            if tds:
                row = [re.sub(r'<[^>]+>', '', td).strip() for td in tds]
                if any(row):  # 跳过全空行
                    rows.append(row)
        
        return headers, rows
    
    @classmethod
    def _parse_inline_text(cls, text: str):
        """解析内联文本（支持 <b>粗体</b> 和 <em>斜体</em>），并解码 HTML 实体。"""
        # 解码 HTML 实体
        text = text.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
        
        # 提取所有内联标签
        parts = []
        last_end = 0
        for m in re.finditer(r'<(b|em|i)>(.*?)</\1>', text):
            if m.start() > last_end:
                parts.append((text[last_end:m.start()], False))
            parts.append((m.group(2), True))  # bold or italic → bold
            last_end = m.end()
        if last_end < len(text):
            parts.append((text[last_end:], False))
        
        if not parts:
            return cls._make_text_block(text)
        
        return cls._make_rich_text_block(parts)

    def build_feishu_card(self, doc_url: str = None) -> dict:
        """构建飞书卡片消息 - 按五级知行信号分类"""
        # 分类
        buy_list = [r for r in self.results if r.get('signal') == 'BUY']
        bull_list = [r for r in self.results if r.get('signal') == 'HOLD_BULL']
        neutral_list = [r for r in self.results if r.get('signal') == 'HOLD_NEUTRAL']
        bear_list = [r for r in self.results if r.get('signal') == 'HOLD_BEAR']
        
        # 构建消息内容
        content_lines = []
        content_lines.append(f"**持仓概览** | {len(self.results)}只ETF | 🟢金叉{len(buy_list)} | 🟡多头{len(bull_list)} | ⚪中性{len(neutral_list)} | 🔴空头{len(bear_list)}")
        content_lines.append("")
        
        # 🟢 金叉买入
        if buy_list:
            content_lines.append("**🟢 金叉买入（短期上穿长期）**")
            for r in buy_list:
                rsi = r.get('rsi14', 50)
                rsi_status = "超买" if rsi > 70 else ("超卖" if rsi < 30 else "中性")
                content_lines.append(f"• {r.get('etf_name', '')} | RSI={rsi:.0f} {rsi_status}")
            content_lines.append("")
        
        # 🟡 多头持有
        if bull_list:
            content_lines.append("**🟡 多头持有（短期>长期，收在线下）**")
            for r in bull_list:
                rsi = r.get('rsi14', 50)
                pos = r.get('price_pos_60d', 50)
                pos_status = "低位" if pos < 30 else ("高位" if pos > 70 else "中性")
                content_lines.append(f"• {r.get('etf_name', '')} | RSI={rsi:.0f} | {pos_status}")
            content_lines.append("")
        
        # 🔴 空头持有
        if bear_list:
            content_lines.append("**🔴 空头持有（短期<长期）**")
            for r in bear_list:
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
        
        # ── 信号变化速览 ────────────────────────────────────────────────────────
        try:
            from market_monitor.data.portfolio_db import get_db
            db = get_db()
            changes = db.get_signal_changes(self.report_date)
            if changes:
                ch_lines = ["**📈 信号变化（vs上期）**", ""]
                for c in changes[:5]:
                    ch_lines.append(
                        f"• {c['etf_name']}: {c['prev_signal']} → **{c['curr_signal']}** "
                        f"({c['score_change']:+.0f})"
                    )
                elements.append({'tag': 'hr'})
                elements.append({'tag': 'div', 'text': {'tag': 'lark_md', 'content': '\n'.join(ch_lines)}})
        except Exception:
            pass
        
        # ── 选股追踪 ──────────────────────────────────────────────────────────────
        try:
            from market_monitor.report.selection_tracker import SelectionTracker
            tracker = SelectionTracker()
            tracking_text = tracker.get_tracking_summary_text()
            if tracking_text and "暂无" not in tracking_text:
                elements.append({'tag': 'hr'})
                elements.append({'tag': 'div', 'text': {'tag': 'lark_md', 'content': tracking_text}})
        except Exception:
            pass
        
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
    parser.add_argument("--positions", "-p", default="market_monitor/positions.json", help="持仓文件路径")
    parser.add_argument("--selection", "-S", action="store_true", 
                        help="启用选股推荐模块（嵌入选股候选到持仓报告中）")
    parser.add_argument("--llm", "-l", action="store_true",
                        help="启用 LLM 自然语言解读（需 CODEBUDDY_API_KEY）")
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

    # 获取ETF代码列表（从统一映射模块查询）
    etf_codes = [p.get('code', '') for p in positions if _lookup_etf(p.get('code', ''))]
    
    # 通过Tushare获取实时价格
    print("📡 通过Tushare获取实时价格...")
    realtime_prices = get_realtime_price(etf_codes)
    print(f"   获取到 {len(realtime_prices)} 只ETF的实时价格\n")

    # 分析每只ETF
    results = []
    for p in positions:
        code = p.get('code', '')
        name = p.get('name', '')

        mapping = _lookup_etf(code)
        if mapping:
            result = analyze_etf(
                etf_code=code,
                etf_name=name or mapping['name'],
                index_code=mapping['xa_code'],
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
    generator = ProfessionalETFReportGenerator(results, pm_style=pm_style, enable_selection=args.selection)
    
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
    
    # LLM 解读（先于文档创建，以便嵌入报告）
    llm_text = None
    if args.llm and results:
        print("\n💡 生成 LLM 自然语言解读...")
        from market_monitor.report.llm_interpreter import generate_interpretation
        llm_text = generate_interpretation(results, date=generator.report_date)
        if llm_text:
            print(f"   ✅ LLM 解读生成成功 ({len(llm_text)} 字符)")
        else:
            print("  ⚠ LLM 解读生成失败")

    doc_id, doc_url = generator.create_doc()

    if doc_url:
        print(f"\n📄 专业版报告已创建: {doc_url}")
    else:
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
