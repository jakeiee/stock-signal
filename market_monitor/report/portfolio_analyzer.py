#!/usr/bin/env python3
"""
持仓ETF详细分析报告 - 使用 xalpha 数据源。

使用方法：
    python3 market_monitor/report/portfolio_analyzer.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List

import pandas as pd
import xalpha as xa


# ── ETF指数映射表（从 etf_index_mapping.csv 加载）─────────────────────────────
ETF_MAPPING = {
    "513130": {"name": "恒生互联网ETF", "index": "HKHSIII", "index_name": "恒生互联网科技业指数"},
    "159890": {"name": "软件ETF嘉实", "index": "ZZ930601", "index_name": "中证软件服务指数"},
    "588260": {"name": "科创板50ETF", "index": "SH000688", "index_name": "科创50指数"},
    "562800": {"name": "机器人ETF华夏", "index": "ZZH30590", "index_name": "中证机器人指数"},
    "159567": {"name": "港股通创新药ETF", "index": "GZ987018", "index_name": "恒生医疗保健指数"},
    "516010": {"name": "游戏ETF华夏", "index": "ZZ930901", "index_name": "中证游戏产业指数"},
    "513020": {"name": "港股通科技ETF", "index": "HKHSTECH", "index_name": "恒生科技指数"},
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


# ── 报告生成 ──────────────────────────────────────────────────────────────────

# ── 指标说明 ─────────────────────────────────────────────────────────────────
INDICATOR_GUIDE = """
## 📖 指标说明

### 📊 评分体系 (0-100分)

| 评分范围 | 含义 | 操作建议 |
|:--------:|:----:|:--------:|
| 80-100 | 强势上涨 | 可适当加仓 |
| 60-79 | 多头排列 | 持有为主 |
| 40-59 | 中性偏多 | 谨慎持有 |
| 20-39 | 偏弱整理 | 控制仓位 |
| 0-19 | 弱势明显 | 观望为主 |

### 📉 知行信号

| 信号 | 含义 | 说明 |
|:----:|:----:|:-----|
| 🟢买入 | MA5上穿MA20 | 短期趋势转多，可关注 |
| 🔴卖出 | MA5下穿MA20 | 短期趋势转空，谨慎 |
| 🟡持多 | 多头排列中 | 均线多头，持有 |
| 🟠持空 | 空头排列中 | 均线空头，观望 |
| ⚪观望 | 趋势不明 | 等待方向明确 |

### 📈 均线排列

| 排列 | 含义 | 信号强度 |
|:----:|:----:|:--------:|
| 多头排列 | MA5 > MA10 > MA20 > MA60 | 上涨趋势较强 |
| 空头排列 | MA5 < MA10 < MA20 < MA60 | 下跌趋势较强 |
| 纠缠整理 | 均线相互交织 | 趋势不明 |

### 🎯 KDJ 随机指标

| 区间 | 含义 | 市场状态 |
|:----:|:----:|:--------:|
| K/D < 20 | 超卖 | 可能企稳反弹 |
| K/D > 80 | 超买 | 可能回调 |
| K > D 且 > 50 | 金叉 | 短期偏多 |
| K < D 且 < 50 | 死叉 | 短期偏空 |

> J值敏感度高，K值次之，D值最稳定

### 📉 RSI 相对强弱指标

| RSI区间 | 含义 | 操作建议 |
|:-------:|:----:|:--------:|
| < 30 | 🔴严重超卖 | 关注超跌反弹机会 |
| 30-40 | 🟠超卖区域 | 可开始关注 |
| 40-60 | ⚪中性区间 | 趋势不明 |
| 60-70 | 🟡偏强区域 | 谨慎追高 |
| > 70 | 🟢超买区域 | 注意回调风险 |

> RSI=50为多空平衡点，>50偏强，<50偏弱

### 📉 MACD 指数平滑异同平均线

| 状态 | 含义 | 信号 |
|:----:|:----:|:----:|
| DIF > DEA 且红柱 | 多头 | 看涨信号 |
| DIF < DEA 且绿柱 | 空头 | 看跌信号 |
| DIF 上穿 DEA | 金叉 | 短期转多 |
| DIF 下穿 DEA | 死叉 | 短期转空 |

> DIF线对价格变化敏感，DEA线更稳定

### 📉 量价关系

| 量价状态 | 含义 | 信号强度 |
|:--------:|:----:|:--------:|
| ✅放量上涨 | 资金推动 | 积极信号 |
| 📈温和放量 | 正常换手 | 中性偏好 |
| 📉缩量上涨 | 动能不足 | 警惕 |
| 📉缩量下跌 | 抛压减轻 | 可能企稳 |

> 放量配合涨跌方向为量价配合；量价背离需警惕

### 📊 价格位置 (60日区间)

| 位置 | 含义 | 操作参考 |
|:----:|:----:|:--------:|
| < 20% | 🔴低位 | 关注超跌反弹 |
| 20-40% | 🟠偏下 | 可分批布局 |
| 40-60% | ⚪中性 | 观望为主 |
| 60-80% | 🟡偏上 | 注意追高风险 |
| > 80% | 🟢高位 | 谨慎追涨 |

---
"""

def generate_md_report(results: List[Dict], output_path: str = None) -> str:
    """生成 Markdown 报告"""
    beijing_tz = timezone(timedelta(hours=8))
    now = datetime.now(beijing_tz).strftime("%Y-%m-%d %H:%M")
    total = len(results)
    avg_score = sum(r.get("pattern_score", 0) for r in results) / total if total else 0

    # 按新信号分类
    strong_signals = [r for r in results if r.get("signal") == "STRONG"]
    watch_signals = [r for r in results if r.get("signal") == "WATCH"]
    danger_signals = [r for r in results if r.get("signal") == "DANGER"]
    oversold = [r for r in results if r.get("rsi14", 50) < 35]

    lines = []
    lines.append("# 📊 持仓ETF详细分析报告")
    lines.append(f"\n**报告生成时间**: {now}\n")
    lines.append("---\n")

    # 0. 综合建议（放在开头）- 分层判断法
    # 第一层：知行信号为首要
    # 第二层：RSI + KDJ + MACD 交叉验证
    # 第三层：量价配合 + 位置确认

    def get_comprehensive_level(r):
        """分层判断综合等级"""
        signal = r.get("signal", "")
        rsi = r.get("rsi14", 50)
        kdj_k = r.get("kdj_k", 50)
        kdj_d = r.get("kdj_d", 50)
        macd_hist = r.get("macd_hist", 0)
        vol_match = r.get("vol_match", False)
        pos = r.get("price_pos_60d", 50)

        # 第一层：知行信号
        if signal == "STRONG":
            level = "🟢强势"
        elif signal == "WATCH":
            level = "🟡观望"
        else:
            level = "🔴危险"

        # 第二层：辅助指标交叉验证
        indicators = []
        if rsi < 30:
            indicators.append("RSI超卖")
        elif rsi > 70:
            indicators.append("RSI超买")
        if kdj_k < 20:
            indicators.append("KDJ超卖")
        elif kdj_k > 80:
            indicators.append("KDJ超买")
        if macd_hist > 0:
            indicators.append("MACD多头")
        else:
            indicators.append("MACD空头")

        # 第三层：量价位置确认
        confirm = []
        if vol_match and r.get("price_change", 0) > 0:
            confirm.append("量价配合")
        if pos < 30:
            confirm.append("低位")

        return level, indicators, confirm

    lines.append("## 1️⃣ 综合建议\n")

    if strong_signals:
        lines.append("### 🟢 强势\n")
        for r in strong_signals:
            close_pct_short = r.get("close_pct_short", 0)
            deviation_change = r.get("close_deviation_change", 0)
            line_pos = r.get("line_position", "三线纠缠")
            deviation_status = "偏离扩大" if deviation_change > 0.2 else ("偏离缩小" if deviation_change < -0.2 else "偏离稳定")
            if close_pct_short > 2:
                risk_note = "偏离较大，注意回踩"
            elif close_pct_short > 0.5:
                risk_note = "偏离正常，持有"
            else:
                risk_note = "贴近短线，关注支撑"
            desc = f"{line_pos}，收盘偏离短线{close_pct_short:+.2f}%，{deviation_status}，{risk_note}"
            lines.append(f"- **{r.get('etf_name', '')}**: {desc}")
        lines.append("")

    if watch_signals:
        lines.append("### 🟡 观望\n")
        for r in watch_signals:
            close_pct_short = r.get("close_pct_short", 0)
            deviation_change = r.get("close_deviation_change", 0)
            deviation_status = "偏离扩大" if deviation_change > 0.2 else ("偏离缩小" if deviation_change < -0.2 else "偏离稳定")
            if abs(close_pct_short) < 1:
                risk_note = "紧贴短线，回踩不破可加仓，跌破则减仓"
            else:
                risk_note = "低于短线，关注回踩压力"
            desc = f"收盘在白线下方，偏离短线{close_pct_short:+.2f}%，{deviation_status}，{risk_note}"
            lines.append(f"- **{r.get('etf_name', '')}**: {desc}")
        lines.append("")

    if oversold:
        lines.append("### 💡 超跌关注\n")
        for r in oversold:
            if r.get("signal") not in ["STRONG", "WATCH"]:
                short_pct_long = r.get("short_pct_long", 0)
                rsi = r.get("rsi14", 0)
                if short_pct_long < -2:
                    desc = f"RSI={rsi:.0f}超卖，短线偏离长线{short_pct_long:.2f}%，等待止跌信号"
                else:
                    desc = f"RSI={rsi:.0f}超卖，{r.get('ma_pattern', '均线纠缠')}，等待企稳"
                lines.append(f"- **{r.get('etf_name', '')}**: {desc}")
        lines.append("")

    if danger_signals:
        lines.append("### 🔴 危险\n")
        for r in danger_signals:
            short_pct_long = r.get("short_pct_long", 0)
            close_pct_long = r.get("close_pct_long", 0)
            deviation_change = r.get("close_deviation_change", 0)
            deviation_status = "偏离扩大" if deviation_change > 0.2 else ("偏离缩小" if deviation_change < -0.2 else "偏离稳定")
            if short_pct_long < -3:
                risk_note = "偏离较大，等待止跌"
            elif close_pct_long < -3:
                risk_note = "远离长线，关注反弹"
            else:
                risk_note = "偏弱，关注能否企稳"
            desc = f"空头排列，短线偏离长线{short_pct_long:+.2f}%，收盘偏离长线{close_pct_long:+.2f}%，{deviation_status}，{risk_note}"
            lines.append(f"- **{r.get('etf_name', '')}**: {desc}")
        lines.append("")

    if not strong_signals and not watch_signals and not danger_signals:
        lines.append("### ⚪ 暂无信号\n")
        lines.append("- 等待明确趋势信号\n")

    # 概览统计
    lines.append("### 📈 持仓统计\n")
    lines.append("| 指标 | 数值 |")
    lines.append("|:-----|:-----|")
    lines.append(f"| 持仓数量 | {total} 只 |")
    lines.append(f"| 平均评分 | {avg_score:.0f}/100 |")
    lines.append(f"| 🟢 强势 | {len(strong_signals)} 只 |")
    lines.append(f"| 🟡 观望 | {len(watch_signals)} 只 |")
    lines.append(f"| 🔴 危险 | {len(danger_signals)} 只 |")
    lines.append(f"| 💡 超跌 | {len(oversold)} 只 |\n")
    lines.append("---\n")

    # 1. 持仓明细
    lines.append("## 2️⃣ 持仓明细\n")

    # 2. 明细
    lines.append("### 📋 持仓明细\n")
    lines.append("| ETF | 跟踪指数 | 信号 | 评分 | RSI | 量价 | 位置 | 操作建议 |")
    lines.append("|:----|:--------|:----:|:----:|:---:|:----:|:----:|:--------:|")

    sorted_results = sorted(results, key=lambda x: x.get("pattern_score", 0), reverse=True)
    for r in sorted_results:
        # 信号
        sig = r.get("signal", "")
        if sig == "STRONG":
            sig_icon = "🟢强势"
        elif sig == "WATCH":
            sig_icon = "🟡观望"
        elif sig == "DANGER":
            sig_icon = "🔴危险"
        else:
            sig_icon = "⚪未知"

        # RSI
        rsi = r.get("rsi14", 50)
        if rsi < 30:
            rsi_icon = f"🔴{rsi:.0f}"
        elif rsi > 70:
            rsi_icon = f"🟢{rsi:.0f}"
        else:
            rsi_icon = f"{rsi:.0f}"

        # 量价
        vol_match = r.get("vol_match", False)
        vol_ratio = r.get("vol_ratio", 1)
        if vol_match:
            vol_icon = f"✅{vol_ratio:.1f}x"
        elif vol_ratio > 1.5:
            vol_icon = f"📈{vol_ratio:.1f}x"
        elif vol_ratio < 0.7:
            vol_icon = "📉缩"
        else:
            vol_icon = "➡️"

        # 位置
        pos = r.get("price_pos_60d", 50)
        if pos < 20:
            pos_icon = "🔴低位"
        elif pos < 40:
            pos_icon = "🟠偏下"
        elif pos > 80:
            pos_icon = "🟢高位"
        elif pos > 60:
            pos_icon = "🟡偏上"
        else:
            pos_icon = "⚪中"

        # 操作建议
        action = ""
        if sig == "STRONG":
            if rsi > 70:
                action = "持有/减仓"
            elif rsi < 30:
                action = "加仓机会"
            else:
                action = "持有"
        elif sig == "WATCH":
            if rsi < 30:
                action = "关注"
            else:
                action = "观望"
        else:  # DANGER
            if rsi < 30:
                action = "等待"
            elif pos < 40:
                action = "关注"
            else:
                action = "减仓"

        lines.append(f"| {r.get('etf_name', '')[:8]} | {r.get('index_name', '')[:6]} | {sig_icon} | {r.get('pattern_score', 0):.0f} | {rsi_icon} | {vol_icon} | {pos_icon} | {action} |")

    lines.append("")

    # 2. 详细分析
    lines.append("---\n")
    lines.append("## 3️⃣ 详细技术分析\n")

    for i, r in enumerate(sorted_results, 1):
        lines.append(f"### {i}. {r.get('etf_name', '')}\n")
        lines.append(f"**跟踪指数**: {r.get('index_name', '')}\n")

        # 知行信号 - 增加偏离比例和趋势描述
        lines.append("#### 📉 知行信号\n")
        sig = r.get("signal", "")
        sig_text = {"STRONG": "🟢强势", "WATCH": "🟡观望", "DANGER": "🔴危险"}.get(sig, "⚪未知")
        close = r.get("close", 0) or 0
        short_trend = r.get("zx_short", 0) or 0
        long_trend = r.get("zx_long", 0) or 0
        close_pct_short = r.get("close_pct_short", 0)
        close_pct_long = r.get("close_pct_long", 0)
        short_pct_long = r.get("short_pct_long", 0)
        deviation_change = r.get("close_deviation_change", 0)

        lines.append(f"| 知行信号 | {sig_text} |")
        lines.append(f"| {r.get('line_position', '三线纠缠')} |")
        lines.append(f"| 收盘偏离短线 | {close_pct_short:+.2f}% | 偏离变化 | {deviation_change:+.2f}% |")
        lines.append(f"| 收盘偏离长线 | {close_pct_long:+.2f}% | 短线偏离长线 | {short_pct_long:+.2f}% |\n")

        # 趋势描述 - 方案C：复合描述
        deviation_status = "偏离扩大" if deviation_change > 0.2 else ("偏离缩小" if deviation_change < -0.2 else "偏离稳定")
        
        if sig == "STRONG":
            if close_pct_short > 3:
                risk_note = "偏离过大，注意回踩风险"
            elif close_pct_short > 1:
                risk_note = "偏离正常，持有观察"
            else:
                risk_note = "贴近短线，关注是否跌破"
            trend_desc = f"三线多头排列，收盘偏离短线{close_pct_short:+.2f}%，{deviation_status}，{risk_note}"
        elif sig == "WATCH":
            if abs(close_pct_short) < 1:
                risk_note = "紧贴短线，回踩不破可能形成支撑，跌破则转弱"
            else:
                risk_note = "低于短线，关注回踩测试压力"
            trend_desc = f"白线在长线上方但收盘在短线下方，收盘偏离短线{close_pct_short:+.2f}%，{deviation_status}，{risk_note}"
        else:
            if short_pct_long < -3:
                risk_note = "偏离较大，等待止跌信号"
            elif close_pct_short < -3:
                risk_note = "股价远离短线，关注反弹机会"
            else:
                risk_note = "偏弱运行，关注是否重新站上"
            trend_desc = f"三线空头排列，短线偏离长线{short_pct_long:+.2f}%，收盘偏离长线{close_pct_long:+.2f}%，{deviation_status}，{risk_note}"
        lines.append(f"**趋势判断**: {trend_desc}\n")

        # 均线 - 一句话描述
        lines.append("#### 📊 均线\n")
        lines.append(f"**均线系统**: {r.get('ma_pattern', '均线纠缠')}\n")

        # KDJ
        lines.append("#### 🎯 KDJ\n")
        k, d, j = r.get("kdj_k", 0), r.get("kdj_d", 0), r.get("kdj_j", 0)
        if k < 20:
            status = "🔴超卖"
        elif k > 80:
            status = "🟢超买"
        elif k > d and d > 50:
            status = "🟡强势"
        else:
            status = "⚪中性"
        lines.append(f"| K | {k:.2f} |")
        lines.append(f"| D | {d:.2f} |")
        lines.append(f"| J | {j:.2f} |")
        lines.append(f"| **判断** | {status} |\n")

        # RSI
        rsi = r.get("rsi14", 50)
        if rsi < 30:
            rsi_status = "🔴严重超卖，可能企稳"
        elif rsi < 40:
            rsi_status = "🟠超卖区域"
        elif rsi < 60:
            rsi_status = "⚪中性"
        elif rsi < 70:
            rsi_status = "🟡偏强"
        else:
            rsi_status = "🟢超买，注意风险"
        lines.append(f"#### 📉 RSI: **{rsi:.2f}** - {rsi_status}\n")

        # MACD
        lines.append("#### 📉 MACD\n")
        hist = r.get("macd_hist", 0)
        macd_status = "🟢红柱" if hist > 0 else "🔴绿柱"
        lines.append(f"| DIF | {r.get('macd_diff', 0):.6f} |")
        lines.append(f"| DEA | {r.get('macd_dea', 0):.6f} |")
        lines.append(f"| 柱 | {hist:.6f} |")
        lines.append(f"| **状态** | {macd_status} |\n")

        # 异常量能
        abnormal = r.get("abnormal_signals", [])
        if abnormal:
            lines.append("#### ⚠️ 异常量能\n")
            for sig in abnormal:
                emoji = "🔴" if sig.get("severity") == "warning" else "🟡"
                lines.append(f"- {emoji} **{sig.get('type', '')}**: {sig.get('description', '')}")
            lines.append("")

        lines.append("---\n")

    # 3. 指标说明（放在末尾）
    lines.append("---\n")
    lines.append("## 4️⃣ 指标说明\n")
    lines.append(INDICATOR_GUIDE)

    # 4. 风险提示
    lines.append("\n## 5️⃣ 风险提示\n")
    lines.append("1. 本报告仅供参考，不构成投资建议")
    lines.append("2. 市场有风险，投资需谨慎")

    lines.append("\n---\n")
    lines.append(f"*报告生成时间: {now}*")

    md = "\n".join(lines)

    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(md)

    return md


def main():
    print(f"\n{'='*60}")
    print(f"📊 持仓ETF详细分析报告")
    print(f"{'='*60}\n")

    # 加载持仓
    positions_file = "./positions.json"
    if os.path.exists(positions_file):
        with open(positions_file, 'r', encoding='utf-8') as f:
            positions = json.load(f)
        print(f"📂 从 {positions_file} 加载持仓\n")
    else:
        print(f"❌ 持仓文件不存在: {positions_file}")
        return

    # 分析每只ETF
    results = []
    for p in positions:
        code = p.get("code", "")
        name = p.get("name", "")

        if code in ETF_MAPPING:
            mapping = ETF_MAPPING[code]
            result = analyze_etf(
                etf_code=code,
                etf_name=name or mapping["name"],
                index_code=mapping["index"],
                index_name=mapping["index_name"],
            )
            if result:
                results.append(result)
        else:
            print(f"  [跳过] {code} {name} - 未配置映射")

    print(f"\n✅ 分析完成: {len(results)}/{len(positions)} 只ETF")

    if not results:
        print("❌ 无有效分析结果")
        return

    # 生成报告
    beijing_tz = timezone(timedelta(hours=8))
    date_str = datetime.now(beijing_tz).strftime("%Y-%m-%d")
    output_path = f"./portfolio_report_{date_str}.md"

    md = generate_md_report(results, output_path)
    print(f"\n📄 报告已保存: {output_path}")

    # 发送到飞书
    send_to_feishu(output_path)


def send_to_feishu(md_file_path: str):
    """发送 MD 报告到飞书"""
    try:
        import requests
        from market_monitor.config import FEISHU_WEBHOOK

        if not FEISHU_WEBHOOK:
            print("⚠ 飞书 Webhook 未配置，跳过发送")
            return False

        # 读取 MD 文件
        with open(md_file_path, 'r', encoding='utf-8') as f:
            md_content = f.read()

        # 限制内容长度（飞书卡片单条消息有限制）
        max_len = 4000
        if len(md_content) > max_len:
            md_content = md_content[:max_len] + "\n\n...（内容过长，已截断）"

        # 构建飞书卡片消息
        payload = {
            "msg_type": "interactive",
            "card": {
                "config": {
                    "wide_screen_mode": True
                },
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": "📊 持仓分析报告"
                    },
                    "template": "blue"
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": md_content
                        }
                    },
                    {
                        "tag": "note",
                        "elements": [
                            {
                                "tag": "plain_text",
                                "content": f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 北京时间"
                            }
                        ]
                    }
                ]
            }
        }

        # 发送请求
        response = requests.post(
            FEISHU_WEBHOOK,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )

        result = response.json()
        if result.get('code') == 0:
            print("✅ 报告已发送到飞书")
            return True
        else:
            print(f"⚠ 飞书发送失败: {result}")
            return False

    except Exception as e:
        print(f"⚠ 发送到飞书时出错: {e}")
        return False


if __name__ == "__main__":
    main()
