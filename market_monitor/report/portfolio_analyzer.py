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

# ── 向后兼容别名 ─────────────────────────────────────────────────────────────
def generate_md_report(results: List[Dict], output_path: str = None) -> str:
    """生成专业版 Markdown 持仓分析报告（向后兼容别名，调用精简模式）"""
    return generate_report(results, mode="compact", output_path=output_path)


# ── 多模式报告生成 ──────────────────────────────────────────────────────────

def generate_report(results: List[Dict], mode: str = "compact", output_path: str = None) -> str:
    """
    生成持仓分析报告（支持多种展示模式）

    Args:
        results: 分析结果列表
        mode: 报告模式
            - "compact": 精简模式（默认）
            - "classic": 经典详表模式
            - "card": 卡片式布局
            - "chart": 图表可视化模式
            - "radar": 多维评分雷达模式
            - "matrix": 对比矩阵模式
        output_path: 可选，保存到的文件路径
    """
    generators = {
        "compact": _generate_compact_report,
        "classic": _generate_classic_report,
        "card": _generate_card_report,
        "chart": _generate_chart_report,
        "radar": _generate_radar_report,
        "matrix": _generate_matrix_report,
    }

    generator = generators.get(mode, _generate_compact_report)
    md = generator(results)

    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(md)

    return md


def _generate_compact_report(results: List[Dict]) -> str:
    """精简模式 - 80行版本"""
    beijing_tz = timezone(timedelta(hours=8))
    now = datetime.now(beijing_tz).strftime("%Y-%m-%d %H:%M")
    total = len(results)
    avg_score = sum(r.get("pattern_score", 0) for r in results) / total if total else 0

    strong_signals = [r for r in results if r.get("signal") == "STRONG"]
    watch_signals = [r for r in results if r.get("signal") == "WATCH"]
    danger_signals = [r for r in results if r.get("signal") == "DANGER"]
    oversold = [r for r in results if r.get("rsi14", 50) < 35]

    lines = []

    # 标题
    lines.append("# 📊 持仓ETF分析报告")
    lines.append(f"*{now}*\n")
    lines.append("---\n")

    # 持仓概览
    lines.append("## 📈 持仓概览\n")
    health_score = avg_score
    bar_len = 20
    filled = int(health_score / 100 * bar_len)
    bar = "█" * filled + "░" * (bar_len - filled)
    lines.append(f"**健康度**: `{bar}` {health_score:.0f}/100\n")

    lines.append("**信号分布**:\n")
    for sig_name, sig_list, emoji in [
        ("强势", strong_signals, "🟢"),
        ("观望", watch_signals, "🟡"),
        ("危险", danger_signals, "🔴"),
    ]:
        count = len(sig_list)
        pct = count / total * 100 if total > 0 else 0
        bar = "▓" * int(pct / 5) + "░" * (20 - int(pct / 5))
        lines.append(f"{emoji} {sig_name}: `{bar}` {count}只 ({pct:.0f}%)")

    lines.append("")
    lines.append("| 🟢强势 | 🟡观望 | 🔴危险 | 💡超跌 |")
    lines.append("|:-----:|:-----:|:-----:|:-----:|")
    lines.append(f"| {len(strong_signals)} | {len(watch_signals)} | {len(danger_signals)} | {len(oversold)} |\n")

    # 持仓明细
    lines.append("---\n")
    lines.append("## 📋 持仓明细\n")
    lines.append("| ETF | 跟踪指数 | 信号 | 评分 | RSI | 量价 | 位置 | 操作 |")
    lines.append("|:----|:--------|:----:|:----:|:---:|:----:|:----:|:----:|")

    sorted_results = sorted(results, key=lambda x: x.get("pattern_score", 0), reverse=True)
    for r in sorted_results:
        sig = r.get("signal", "")
        sig_emoji = {"STRONG": "🟢", "WATCH": "🟡", "DANGER": "🔴"}.get(sig, "⚪")
        rsi = r.get("rsi14", 50)
        rsi_emoji = "🔴" if rsi < 30 else ("🟢" if rsi > 70 else "")
        vol_ratio = r.get("vol_ratio", 1)
        vol_emoji = "↑" if vol_ratio > 1.2 else ("↓" if vol_ratio < 0.8 else "→")
        pos = r.get("price_pos_60d", 50)
        pos_emoji = "低" if pos < 30 else ("高" if pos > 70 else "中")
        action = _get_action_short(r)
        action_emoji = "➕" if "加仓" in action else ("➖" if "减仓" in action else ("⏸" if "等待" in action else "👀"))
        lines.append(f"| {r.get('etf_name', '')[:8]} | {r.get('index_name', '')[:6]} | {sig_emoji} | {r.get('pattern_score', 0):.0f} | {rsi_emoji}{rsi:.0f} | {vol_emoji} | {pos_emoji} | {action_emoji}{action} |")

    lines.append("")

    # 重点关注
    if strong_signals or danger_signals:
        lines.append("---\n")
        lines.append("## 🎯 重点关注\n")
        if strong_signals:
            lines.append("### 🟢 强势标的\n")
            for r in strong_signals:
                action = _get_action_short(r)
                rsi = r.get("rsi14", 0)
                lines.append(f"- **{r.get('etf_name', '')}**: {action}（RSI={rsi:.0f}）")
        if danger_signals:
            lines.append("\n### 🔴 危险标的\n")
            for r in danger_signals:
                action = _get_action_short(r)
                pos = r.get("price_pos_60d", 0)
                pos_desc = "低位" if pos < 30 else ("高位" if pos > 70 else "中性")
                lines.append(f"- **{r.get('etf_name', '')}**: {action}（{pos_desc}）")
        lines.append("")

    # 指标速查
    lines.append("---\n")
    lines.append("## 📖 指标速查\n")
    lines.append("| 指标 | 区间 | 含义 |")
    lines.append("|:----:|:----:|:----|")
    lines.append("| RSI | <30 / >70 | 🔴超卖 / 🟢超买 |")
    lines.append("| KDJ | <20 / >80 | 🔴超卖 / 🟢超买 |")
    lines.append("| MACD | 红柱/绿柱 | 🟢多头/🔴空头 |")
    lines.append("| 位置 | <20%/>80% | 🔴低位/🟢高位 |")
    lines.append("| 量价 | ↑放量/↓缩量 | 动能足/动能弱 |\n")

    # 风险提示
    lines.append("---\n")
    lines.append("**⚠️ 风险提示**: 本报告仅供参考，不构成投资建议。市场有风险，投资需谨慎。\n")
    lines.append(f"\n*报告生成时间: {now}*")

    return "\n".join(lines)


def _generate_classic_report(results: List[Dict]) -> str:
    """
    方案一：经典详表模式
    - 保留所有技术指标表格
    - 每只ETF完整展示知行信号、均线、KDJ、RSI、MACD、成交量
    - 数据最全面，适合深度分析
    """
    beijing_tz = timezone(timedelta(hours=8))
    now = datetime.now(beijing_tz).strftime("%Y-%m-%d %H:%M")
    total = len(results)
    avg_score = sum(r.get("pattern_score", 0) for r in results) / total if total else 0

    strong_signals = [r for r in results if r.get("signal") == "STRONG"]
    watch_signals = [r for r in results if r.get("signal") == "WATCH"]
    danger_signals = [r for r in results if r.get("signal") == "DANGER"]

    lines = []

    # 标题
    lines.append("# 📊 持仓ETF详细分析报告（经典详表版）")
    lines.append(f"*{now}*\n")
    lines.append("---\n")

    # 一、持仓概览
    lines.append("## 一、持仓概览\n")
    lines.append(f"**持仓数量**: {total} 只ETF")
    lines.append(f"**平均评分**: {avg_score:.1f}/100\n")

    lines.append("| 指标 | 强势 | 观望 | 危险 |")
    lines.append("|:----:|:----:|:----:|:----:|")
    lines.append(f"| 数量 | 🟢{len(strong_signals)} | 🟡{len(watch_signals)} | 🔴{len(danger_signals)} |\n")

    # 二、知行信号汇总表
    lines.append("---\n")
    lines.append("## 二、知行信号汇总\n")
    lines.append("| ETF名称 | 跟踪指数 | 信号 | 排列状态 | 评分 | 操作建议 |")
    lines.append("|:--------|:--------|:-----|:---------|:----:|:--------:|\n")

    sorted_results = sorted(results, key=lambda x: x.get("pattern_score", 0), reverse=True)
    for r in sorted_results:
        sig = r.get("signal", "")
        sig_map = {"STRONG": "🟢强势", "WATCH": "🟡观望", "DANGER": "🔴危险"}
        sig_text = sig_map.get(sig, "⚪未知")
        position = r.get("position", "纠缠")
        score = r.get("pattern_score", 0)
        action = _get_action_short(r)
        lines.append(f"| {r.get('etf_name', '')} | {r.get('index_name', '')[:10]} | {sig_text} | {position} | {score:.0f} | {action} |")

    lines.append("")

    # 三、详细技术分析
    lines.append("---\n")
    lines.append("## 三、详细技术分析\n")

    for i, r in enumerate(sorted_results, 1):
        lines.append(f"### {i}. {r.get('etf_name', '')} ({r.get('index_code', '')})\n")
        lines.append(f"**跟踪指数**: {r.get('index_name', '')}\n")

        # 知行趋势线
        lines.append("#### 📉 知行趋势线信号\n")
        zx_short = r.get("zx_short", 0)
        zx_long = r.get("zx_long", 0)
        close = r.get("close", 0)
        sig = r.get("signal", "")
        sig_map = {"STRONG": "🟢强势信号", "WATCH": "🟡观望信号", "DANGER": "🔴危险信号"}

        lines.append("| 指标 | 数值 | 解读 |")
        lines.append("|:----:|:----:|:----|")
        lines.append(f"| 知行信号 | {sig_map.get(sig, '⚪未知')} | - |")
        lines.append(f"| 白线(EMA) | {zx_short:.4f} | {'▲' if close > zx_short else '▼'} {abs((close/zx_short-1)*100):.2f}% |")
        lines.append(f"| 黄线(均线组) | {zx_long:.4f} | {'▲' if close > zx_long else '▼'} {abs((close/zx_long-1)*100):.2f}% |")
        lines.append(f"| 三线位置 | {r.get('line_position', '纠缠')} | - |")
        lines.append(f"| 均线排列 | {r.get('ma_pattern', '纠缠')} | - |\n")

        # 均线分析
        lines.append("#### 📊 均线分析\n")
        lines.append("| 均线 | 数值 | 价格对比 |")
        lines.append("|:----:|:----:|:--------:|\n")

        ma5 = r.get("ma5", 0)
        ma10 = r.get("ma10", 0)
        ma20 = r.get("ma20", 0)
        ma60 = r.get("ma60", 0)

        for ma_name, ma_val in [("MA5", ma5), ("MA10", ma10), ("MA20", ma20), ("MA60", ma60)]:
            if ma_val and ma_val != 0:
                diff = "▲" if close > ma_val else "▼"
                pct = f"{abs((close/ma_val-1)*100):.2f}%"
                lines.append(f"| {ma_name} | {ma_val:.4f} | {diff} {pct} |")

        lines.append("")

        # KDJ
        lines.append("#### 🎯 KDJ 指标\n")
        kdj_k = r.get("kdj_k", 0)
        kdj_d = r.get("kdj_d", 0)
        kdj_j = r.get("kdj_j", 0)

        if kdj_k < 20:
            kdj_status = "🔴 超卖区域"
        elif kdj_k > 80:
            kdj_status = "🟢 超买区域"
        elif kdj_k > kdj_d and kdj_d > 50:
            kdj_status = "🟡 强势区域"
        else:
            kdj_status = "⚪ 中性区域"

        lines.append("| 指标 | 数值 | 状态 |")
        lines.append("|:----:|:----:|:----|")
        lines.append(f"| K | {kdj_k:.2f} | {'偏高' if kdj_k > 70 else '偏低' if kdj_k < 30 else '正常'} |")
        lines.append(f"| D | {kdj_d:.2f} | - |")
        lines.append(f"| J | {kdj_j:.2f} | - |")
        lines.append(f"| **判断** | - | {kdj_status} |\n")

        # RSI
        lines.append("#### 📉 RSI 指标\n")
        rsi = r.get("rsi14", 50)
        if rsi < 30:
            rsi_status = "🔴 严重超卖"
        elif rsi < 40:
            rsi_status = "🟠 超卖区域"
        elif rsi < 60:
            rsi_status = "⚪ 中性区域"
        elif rsi < 70:
            rsi_status = "🟡 偏强区域"
        else:
            rsi_status = "🟢 超买区域"

        lines.append("| RSI(14) | 状态 |")
        lines.append("|:-------:|:----|")
        lines.append(f"| **{rsi:.2f}** | {rsi_status} |\n")

        # MACD
        lines.append("#### 📉 MACD 指标\n")
        macd_diff = r.get("macd_diff", 0)
        macd_dea = r.get("macd_dea", 0)
        macd_hist = r.get("macd_hist", 0)

        macd_status = "🟢 红柱（多方主导）" if macd_hist > 0 else "🔴 绿柱（空方主导）"

        lines.append("| 指标 | 数值 |")
        lines.append("|:----:|:----:|")
        lines.append(f"| DIF | {macd_diff:.6f} |")
        lines.append(f"| DEA | {macd_dea:.6f} |")
        lines.append(f"| MACD柱 | {macd_hist:.6f} |")
        lines.append(f"| **状态** | {macd_status} |\n")

        # 成交量
        lines.append("#### 📊 成交量分析\n")
        vol_ratio = r.get("vol_ratio", 1)
        vol_match = r.get("vol_match", False)
        price_pos = r.get("price_pos_60d", 50)

        if vol_ratio > 2:
            vol_status = "🔴 巨量放大"
        elif vol_ratio > 1.5:
            vol_status = "🟡 明显放量"
        elif vol_ratio < 0.5:
            vol_status = "🟢 地量萎缩"
        else:
            vol_status = "⚪ 量能正常"

        lines.append("| 指标 | 数值 | 解读 |")
        lines.append("|:----:|:----:|:----|")
        lines.append(f"| 放量倍数 | {vol_ratio:.2f}x | {vol_status} |")
        lines.append(f"| 量价配合 | {'是' if vol_match else '否'} | {'✅健康' if vol_match else '⚠️背离'} |")
        lines.append(f"| 60日价格位置 | {price_pos:.1f}% | {'低位' if price_pos < 30 else '高位' if price_pos > 70 else '中性'} |\n")

        # 异常信号
        abnormal = r.get("abnormal_signals", [])
        if abnormal:
            lines.append("#### ⚠️ 异常信号\n")
            for sig in abnormal:
                sig_type = sig.get("type", "")
                desc = sig.get("description", "")
                severity = sig.get("severity", "")
                emoji = "🔴" if severity == "warning" else "🟡" if severity == "positive" else "🟢"
                lines.append(f"- {emoji} **{sig_type}**: {desc}")
            lines.append("")

        lines.append("---\n")

    # 四、综合建议
    lines.append("## 四、综合操作建议\n")
    if strong_signals:
        lines.append("### 🟢 重点关注（强势信号）\n")
        for r in strong_signals:
            lines.append(f"- **{r.get('etf_name', '')}**: 出现强势信号，可适当关注")
        lines.append("")
    if watch_signals:
        lines.append("### 🟡 观望标的\n")
        for r in watch_signals:
            lines.append(f"- **{r.get('etf_name', '')}**: 趋势未明，等待方向确认")
        lines.append("")
    if danger_signals:
        lines.append("### 🔴 谨慎对待（危险信号）\n")
        for r in danger_signals:
            action = _get_action_short(r)
            lines.append(f"- **{r.get('etf_name', '')}**: {action}")
        lines.append("")

    # 五、风险提示
    lines.append("---\n")
    lines.append("## 五、风险提示\n")
    lines.append("1. 📊 本报告仅供参考，不构成投资建议")
    lines.append("2. ⚠️ 市场有风险，投资需谨慎")
    lines.append("3. 📈 过往业绩不代表未来表现")
    lines.append("4. 🔄 建议定期复盘，动态调整持仓\n")
    lines.append(f"\n*报告生成时间: {now}*")

    return "\n".join(lines)


def _generate_card_report(results: List[Dict]) -> str:
    """
    方案二：卡片式布局
    - 每只ETF用卡片形式展示
    - 左上：信号评分 | 右上：操作建议
    - 下方：关键指标一览
    - 视觉清晰，便于快速浏览
    """
    beijing_tz = timezone(timedelta(hours=8))
    now = datetime.now(beijing_tz).strftime("%Y-%m-%d %H:%M")
    total = len(results)
    avg_score = sum(r.get("pattern_score", 0) for r in results) / total if total else 0

    lines = []

    # 标题
    lines.append("# 📊 持仓ETF分析报告（卡片版）")
    lines.append(f"*{now}*\n")
    lines.append("---\n")

    # 概览统计
    lines.append("## 📈 持仓概览\n")

    strong = len([r for r in results if r.get("signal") == "STRONG"])
    watch = len([r for r in results if r.get("signal") == "WATCH"])
    danger = len([r for r in results if r.get("signal") == "DANGER"])

    bar_len = 20
    filled = int(avg_score / 100 * bar_len)
    bar = "█" * filled + "░" * (bar_len - filled)

    lines.append(f"**整体健康度**: `{bar}` {avg_score:.0f}/100\n")
    lines.append(f"| 🟢强势: {strong} | 🟡观望: {watch} | 🔴危险: {danger} |\n")

    # ETF卡片
    lines.append("---\n")
    lines.append("## 📋 持仓卡片\n")

    sorted_results = sorted(results, key=lambda x: x.get("pattern_score", 0), reverse=True)

    for r in sorted_results:
        sig = r.get("signal", "")
        score = r.get("pattern_score", 0)
        action = _get_action_short(r)

        # 卡片边框颜色
        border_color = {"STRONG": "🟢", "WATCH": "🟡", "DANGER": "🔴"}.get(sig, "⚪")

        lines.append(f"### {border_color} {r.get('etf_name', '')}\n")
        lines.append(f"| **跟踪指数** | {r.get('index_name', '')} |")
        lines.append(f"| **知行信号** | {sig} |")
        lines.append(f"| **综合评分** | {score:.0f}/100 |")
        lines.append(f"| **操作建议** | {action} |\n")

        # 关键指标网格
        lines.append("| 指标 | 数值 | 状态 |")
        lines.append("|:----:|:----:|:----|")

        rsi = r.get("rsi14", 50)
        rsi_emoji = "🔴" if rsi < 30 else ("🟢" if rsi > 70 else "⚪")
        rsi_status = "超卖" if rsi < 30 else "超买" if rsi > 70 else "正常"
        lines.append(f"| RSI(14) | {rsi:.1f} | {rsi_emoji} {rsi_status} |")

        kdj_k = r.get("kdj_k", 0)
        kdj_emoji = "🔴" if kdj_k < 20 else ("🟢" if kdj_k > 80 else "⚪")
        lines.append(f"| KDJ(K) | {kdj_k:.1f} | {kdj_emoji} |")

        macd_hist = r.get("macd_hist", 0)
        macd_emoji = "🟢" if macd_hist > 0 else "🔴"
        lines.append(f"| MACD柱 | {macd_hist:.4f} | {macd_emoji} |")

        vol_ratio = r.get("vol_ratio", 1)
        vol_emoji = "📈" if vol_ratio > 1.2 else ("📉" if vol_ratio < 0.8 else "➡️")
        lines.append(f"| 量能 | {vol_ratio:.2f}x | {vol_emoji} |")

        price_pos = r.get("price_pos_60d", 50)
        pos_emoji = "🔴" if price_pos < 30 else ("🟢" if price_pos > 70 else "⚪")
        pos_desc = "低位" if price_pos < 30 else "高位" if price_pos > 70 else "中性"
        lines.append(f"| 60日位置 | {price_pos:.0f}% | {pos_emoji} {pos_desc} |\n")

        # 均线状态
        lines.append("**均线状态**: " + r.get('ma_pattern', '纠缠') + "\n")
        lines.append("**三线位置**: " + r.get('line_position', '纠缠') + "\n")

        # 异常信号
        abnormal = r.get("abnormal_signals", [])
        if abnormal:
            lines.append("**⚠️ 异常**: " + " | ".join([f"{s.get('type', '')}" for s in abnormal]) + "\n")

        lines.append("---\n")

    # 风险提示
    lines.append("**⚠️ 风险提示**: 本报告仅供参考，不构成投资建议。市场有风险，投资需谨慎。\n")
    lines.append(f"\n*报告生成时间: {now}*")

    return "\n".join(lines)


def _generate_chart_report(results: List[Dict]) -> str:
    """
    方案三：图表可视化模式
    - ASCII条形图展示评分
    - 指标仪表盘
    - 趋势箭头可视化
    - 视觉效果突出，便于快速对比
    """
    beijing_tz = timezone(timedelta(hours=8))
    now = datetime.now(beijing_tz).strftime("%Y-%m-%d %H:%M")
    total = len(results)
    avg_score = sum(r.get("pattern_score", 0) for r in results) / total if total else 0

    lines = []

    # 标题
    lines.append("# 📊 持仓ETF分析报告（图表示例版）")
    lines.append(f"*{now}*\n")
    lines.append("---\n")

    # 整体健康度仪表盘
    lines.append("## 📈 整体健康度仪表盘\n")
    lines.append("```\n")

    score = avg_score
    filled = int(score / 5)  # 20格，每格5分
    bar = "█" * filled + "░" * (20 - filled)

    if score >= 60:
        gauge = "🟢"
    elif score >= 40:
        gauge = "🟡"
    else:
        gauge = "🔴"

    lines.append(f"  0%  10%  20%  30%  40%  50%  60%  70%  80%  90% 100%")
    lines.append(f"  │   │   │   │   │   │   │   │   │   │   │")
    lines.append(f"  └────────────────────────────────────────┘")
    lines.append(f"  {bar}")
    lines.append(f"  │{' '*filled}{gauge}{' '*max(0, 19-filled)}│")
    lines.append(f"  └────────────────────────────────────────┘")
    lines.append(f"                            {score:.0f}/100")
    lines.append("```\n")

    # 信号分布饼图（ASCII版）
    lines.append("## 📊 信号分布\n")
    strong = len([r for r in results if r.get("signal") == "STRONG"])
    watch = len([r for r in results if r.get("signal") == "WATCH"])
    danger = len([r for r in results if r.get("signal") == "DANGER"])

    lines.append("```")
    lines.append(f"         持仓信号分布")
    lines.append(f"        ┌─────────────┐")
    lines.append(f"       ╱               ╲")
    lines.append(f"      │    🟢 {strong} 只    │")
    lines.append(f"      │   ╱       ╲     │")
    lines.append(f"      │ 🟡{watch}      🔴{danger}│")
    lines.append(f"       ╲               ╱")
    lines.append(f"        └─────────────┘")
    lines.append("```\n")

    # 各ETF评分条形图
    lines.append("---\n")
    lines.append("## 📉 各ETF评分对比\n")

    sorted_results = sorted(results, key=lambda x: x.get("pattern_score", 0), reverse=True)

    for r in sorted_results:
        name = r.get('etf_name', '')[:8]
        score = r.get("pattern_score", 0)
        sig = r.get("signal", "")

        filled = int(score / 5)  # 20格
        color = "🟢" if sig == "STRONG" else ("🟡" if sig == "WATCH" else "🔴")

        bar = "█" * filled + "░" * (20 - filled)
        lines.append(f"{color} {name:<8} │{bar}│ {score:.0f}")

    lines.append("")

    # 指标仪表盘
    lines.append("---\n")
    lines.append("## 🎯 关键指标仪表盘\n")

    lines.append("```")
    lines.append("┌─────────────────────────────────────────────────────────┐")
    lines.append("│                    RSI 相对强弱指标                      │")
    lines.append("├─────────────────────────────────────────────────────────┤")

    for r in sorted_results:
        name = r.get('etf_name', '')[:6]
        rsi = r.get("rsi14", 50)

        # RSI条形
        rsi_bar_len = 30
        rsi_pos = int(rsi / 100 * rsi_bar_len)
        rsi_bar = "█" * rsi_pos + "░" * (rsi_bar_len - rsi_pos)

        rsi_color = "🔴" if rsi < 30 else ("🟢" if rsi > 70 else "⚪")
        lines.append(f"│ {name:<6} │{rsi_bar}│ {rsi:>5.1f} {rsi_color} │")

    lines.append("│          └──0──────30──────50──────70──────100──→      │")
    lines.append("└─────────────────────────────────────────────────────────┘")
    lines.append("```\n")

    # KDJ 状态矩阵
    lines.append("```")
    lines.append("┌─────────────────────────────────────────────────────────┐")
    lines.append("│                    KDJ 随机指标                          │")
    lines.append("├─────────────────────────────────────────────────────────┤")
    lines.append("│ ETF      │ K值      │ D值      │ 状态                    │")
    lines.append("├──────────┼──────────┼──────────┼─────────────────────────┤")

    for r in sorted_results:
        name = r.get('etf_name', '')[:6]
        k = r.get("kdj_k", 0)
        d = r.get("kdj_d", 0)

        if k < 20:
            status = "🔴超卖"
        elif k > 80:
            status = "🟢超买"
        elif k > d and d > 50:
            status = "🟡强势"
        else:
            status = "⚪中性"

        lines.append(f"│ {name:<8} │ {k:>6.1f}   │ {d:>6.1f}   │ {status:<20} │")

    lines.append("└─────────────────────────────────────────────────────────┘")
    lines.append("```\n")

    # MACD 红绿柱
    lines.append("```")
    lines.append("┌─────────────────────────────────────────────────────────┐")
    lines.append("│                    MACD 指标                            │")
    lines.append("├─────────────────────────────────────────────────────────┤")

    for r in sorted_results:
        name = r.get('etf_name', '')[:6]
        hist = r.get("macd_hist", 0)

        bar_len = 20
        if hist > 0:
            filled = min(int(abs(hist) * 1000), bar_len)
            bar = " " * (bar_len - filled) + "█" * filled
            status = f"🟢 {bar} +{hist:.4f}"
        else:
            filled = min(int(abs(hist) * 1000), bar_len)
            bar = "░" * filled + " " * (bar_len - filled)
            status = f"🔴 {bar} {hist:.4f}"

        lines.append(f"│ {name:<6} │ {status} │")

    lines.append("│          └──红柱(多方)        绿柱(空方)──→              │")
    lines.append("└─────────────────────────────────────────────────────────┘")
    lines.append("```\n")

    # 操作建议矩阵
    lines.append("---\n")
    lines.append("## 📋 操作建议矩阵\n")

    lines.append("| ETF | 信号 | 评分 | RSI | MACD | 量能 | 操作 |")
    lines.append("|:----|:----:|:----:|:---:|:----:|:----:|:----:|")

    for r in sorted_results:
        name = r.get('etf_name', '')[:8]
        sig = r.get("signal", "")
        score = r.get("pattern_score", 0)
        rsi = r.get("rsi14", 50)
        rsi_emoji = "🔴" if rsi < 30 else ("🟢" if rsi > 70 else "⚪")
        macd_hist = r.get("macd_hist", 0)
        macd_emoji = "🟢" if macd_hist > 0 else "🔴"
        vol_ratio = r.get("vol_ratio", 1)
        vol_emoji = "📈" if vol_ratio > 1.2 else ("📉" if vol_ratio < 0.8 else "➡️")
        action = _get_action_short(r)
        sig_emoji = {"STRONG": "🟢", "WATCH": "🟡", "DANGER": "🔴"}.get(sig, "⚪")

        lines.append(f"| {name} | {sig_emoji} | {score:.0f} | {rsi_emoji}{rsi:.0f} | {macd_emoji} | {vol_emoji} | {action} |")

    lines.append("")

    # 风险提示
    lines.append("---\n")
    lines.append("**⚠️ 风险提示**: 本报告仅供参考，不构成投资建议。市场有风险，投资需谨慎。\n")
    lines.append(f"\n*报告生成时间: {now}*")

    return "\n".join(lines)


def _generate_radar_report(results: List[Dict]) -> str:
    """
    方案四：多维评分雷达模式
    - 趋势、动量、量能、位置四维度评分
    - 雷达图（文本版）
    - 便于快速识别各ETF的优劣势
    """
    beijing_tz = timezone(timedelta(hours=8))
    now = datetime.now(beijing_tz).strftime("%Y-%m-%d %H:%M")
    total = len(results)

    def calc_dimensions(r: dict) -> dict:
        """计算四个维度的评分"""
        # 趋势维度（基于知行信号）
        sig = r.get("signal", "")
        trend_score = 100 if sig == "STRONG" else (50 if sig == "WATCH" else 0)

        # 动量维度（RSI）
        rsi = r.get("rsi14", 50)
        if 40 <= rsi <= 60:
            momentum_score = 50
        elif rsi < 40:
            momentum_score = 30 + (40 - rsi)  # 超卖加分
        else:
            momentum_score = 50 - (rsi - 60)  # 超买减分
        momentum_score = max(0, min(100, momentum_score))

        # 量能维度
        vol_ratio = r.get("vol_ratio", 1)
        vol_match = r.get("vol_match", False)
        if vol_match:
            volume_score = 80
        elif vol_ratio > 1.5:
            volume_score = 70
        elif vol_ratio < 0.5:
            volume_score = 40
        else:
            volume_score = 60

        # 位置维度（60日位置）
        pos = r.get("price_pos_60d", 50)
        if 30 <= pos <= 70:
            position_score = 60
        elif pos < 30:
            position_score = 80  # 低位加分
        else:
            position_score = max(20, 80 - (pos - 70) * 2)

        return {
            "trend": trend_score,
            "momentum": momentum_score,
            "volume": volume_score,
            "position": position_score,
        }

    lines = []

    # 标题
    lines.append("# 📊 持仓ETF分析报告（多维雷达版）")
    lines.append(f"*{now}*\n")
    lines.append("---\n")

    # 概览
    lines.append("## 📈 持仓概览\n")
    lines.append("| ETF | 🧭趋势 | ⚡动量 | 📊量能 | 📍位置 | ⭐综合 |")
    lines.append("|:----|:-----:|:------:|:------:|:------:|:-----:|")

    sorted_results = sorted(results, key=lambda x: x.get("pattern_score", 0), reverse=True)

    for r in sorted_results:
        dims = calc_dimensions(r)
        name = r.get('etf_name', '')[:8]
        overall = (dims["trend"] + dims["momentum"] + dims["volume"] + dims["position"]) / 4

        trend_bar = "█" * int(dims["trend"] / 10) + "░" * (10 - int(dims["trend"] / 10))
        mom_bar = "█" * int(dims["momentum"] / 10) + "░" * (10 - int(dims["momentum"] / 10))
        vol_bar = "█" * int(dims["volume"] / 10) + "░" * (10 - int(dims["volume"] / 10))
        pos_bar = "█" * int(dims["position"] / 10) + "░" * (10 - int(dims["position"] / 10))

        lines.append(f"| **{name}** | {trend_bar} {dims['trend']:.0f} | {mom_bar} {dims['momentum']:.0f} | {vol_bar} {dims['volume']:.0f} | {pos_bar} {dims['position']:.0f} | **{overall:.0f}** |")

    lines.append("")

    # 雷达图（文本版）
    lines.append("---\n")
    lines.append("## 🎯 多维雷达图\n")
    lines.append("```")
    lines.append("                    🧭趋势")
    lines.append("                      ▲")
    lines.append("                     ╱ ╲")
    lines.append("                    ╱   ╲")

    # 绘制10个同心菱形
    for level in range(10, 0, -1):
        level_score = level * 10
        chars = []
        for r in sorted_results[:5]:  # 最多5个ETF
            dims = calc_dimensions(r)
            # 找到这个ETF在该维度的点
            if dims["trend"] >= level_score:
                chars.append("●")
            else:
                chars.append("○")

        indent = " " * (20 - len(chars) - level)
        lines.append(f"{indent}{'  '.join(chars)}")

    lines.append("                   ╱ ⚡动量  📊量能 ╲")
    lines.append("                  ╱─────────────────╲")
    lines.append("                 ◄─────────📍位置──────►")
    lines.append("```\n")

    lines.append("**图例**: ● = 该维度得分 │ ○ = 该维度未达此分数\n")

    # 综合评分排名
    lines.append("---\n")
    lines.append("## 🏆 综合评分排名\n")

    scored_results = []
    for r in sorted_results:
        dims = calc_dimensions(r)
        overall = (dims["trend"] + dims["momentum"] + dims["volume"] + dims["position"]) / 4
        scored_results.append((r, dims, overall))

    scored_results.sort(key=lambda x: x[2], reverse=True)

    for i, (r, dims, overall) in enumerate(scored_results, 1):
        name = r.get('etf_name', '')
        sig = r.get("signal", "")
        sig_emoji = {"STRONG": "🟢", "WATCH": "🟡", "DANGER": "🔴"}.get(sig, "⚪")

        medal = "🥇" if i == 1 else ("🥈" if i == 2 else ("🥉" if i == 3 else f"#{i}"))
        bar_len = int(overall / 5)
        bar = "█" * bar_len + "░" * (20 - bar_len)

        lines.append(f"{medal} **{name}** {sig_emoji}\n")
        lines.append(f"   综合: `{bar}` {overall:.0f}/100")
        lines.append(f"   趋势:{dims['trend']:.0f} 动量:{dims['momentum']:.0f} 量能:{dims['volume']:.0f} 位置:{dims['position']:.0f}\n")

    # 详细分析
    lines.append("---\n")
    lines.append("## 📖 维度分析说明\n")

    lines.append("| 维度 | 计算方式 | 评分说明 |")
    lines.append("|:----:|:--------|:--------|")
    lines.append("| 🧭趋势 | 知行信号 | 🟢强势=100 🟡观望=50 🔴危险=0 |")
    lines.append("| ⚡动量 | RSI指标 | 40-60=50基准，超卖加分超买减分 |")
    lines.append("| 📊量能 | 量价配合 | 配合=80,放量=70,正常=60,缩量=40 |")
    lines.append("| 📍位置 | 60日位置 | 低位30以下=80,中性=60,高位减分 |")

    lines.append("")

    # 风险提示
    lines.append("---\n")
    lines.append("**⚠️ 风险提示**: 本报告仅供参考，不构成投资建议。市场有风险，投资需谨慎。\n")
    lines.append(f"\n*报告生成时间: {now}*")

    return "\n".join(lines)


def _generate_matrix_report(results: List[Dict]) -> str:
    """
    方案五：对比矩阵模式
    - 多维度横向对比表格
    - 按信号分类分组
    - 便于快速对比同类ETF
    """
    beijing_tz = timezone(timedelta(hours=8))
    now = datetime.now(beijing_tz).strftime("%Y-%m-%d %H:%M")

    lines = []

    # 标题
    lines.append("# 📊 持仓ETF分析报告（对比矩阵版）")
    lines.append(f"*{now}*\n")
    lines.append("---\n")

    sorted_results = sorted(results, key=lambda x: x.get("pattern_score", 0), reverse=True)

    # 按信号分组
    strong_signals = [r for r in sorted_results if r.get("signal") == "STRONG"]
    watch_signals = [r for r in sorted_results if r.get("signal") == "WATCH"]
    danger_signals = [r for r in sorted_results if r.get("signal") == "DANGER"]

    # 强势标的矩阵
    if strong_signals:
        lines.append("## 🟢 强势标的矩阵\n")
        lines.append("| ETF | 评分 | RSI | KDJ | MACD | 量能 | 位置 | 偏离度 | 操作 |")
        lines.append("|:----|:----:|:---:|:---:|:----:|:----:|:----:|:------:|:----:|")

        for r in strong_signals:
            name = r.get('etf_name', '')[:8]
            score = r.get("pattern_score", 0)
            rsi = r.get("rsi14", 50)
            rsi_emoji = "🔴" if rsi < 30 else ("🟢" if rsi > 70 else "🟡")
            kdj_k = r.get("kdj_k", 0)
            kdj_emoji = "🔴" if kdj_k < 20 else ("🟢" if kdj_k > 80 else "🟡")
            macd_hist = r.get("macd_hist", 0)
            macd_emoji = "🟢" if macd_hist > 0 else "🔴"
            vol_ratio = r.get("vol_ratio", 1)
            vol_emoji = "📈" if vol_ratio > 1.2 else ("📉" if vol_ratio < 0.8 else "➡️")
            pos = r.get("price_pos_60d", 50)
            pos_desc = "🔴低" if pos < 30 else ("🟢高" if pos > 70 else "🟡中")
            close_pct = r.get("close_pct_short", 0)
            pct_desc = f"{'▲' if close_pct > 0 else '▼'}{abs(close_pct):.1f}%"
            action = _get_action_short(r)

            lines.append(f"| {name} | {score:.0f} | {rsi_emoji}{rsi:.0f} | {kdj_emoji}{kdj_k:.0f} | {macd_emoji} | {vol_emoji}{vol_ratio:.1f}x | {pos_desc}{pos:.0f}% | {pct_desc} | {action} |")

        lines.append("")

    # 观望标的矩阵
    if watch_signals:
        lines.append("---\n")
        lines.append("## 🟡 观望标的矩阵\n")
        lines.append("| ETF | 评分 | RSI | KDJ | MACD | 量能 | 位置 | 偏离度 | 操作 |")
        lines.append("|:----|:----:|:---:|:---:|:----:|:----:|:----:|:------:|:----:|")

        for r in watch_signals:
            name = r.get('etf_name', '')[:8]
            score = r.get("pattern_score", 0)
            rsi = r.get("rsi14", 50)
            rsi_emoji = "🔴" if rsi < 30 else ("🟢" if rsi > 70 else "🟡")
            kdj_k = r.get("kdj_k", 0)
            kdj_emoji = "🔴" if kdj_k < 20 else ("🟢" if kdj_k > 80 else "🟡")
            macd_hist = r.get("macd_hist", 0)
            macd_emoji = "🟢" if macd_hist > 0 else "🔴"
            vol_ratio = r.get("vol_ratio", 1)
            vol_emoji = "📈" if vol_ratio > 1.2 else ("📉" if vol_ratio < 0.8 else "➡️")
            pos = r.get("price_pos_60d", 50)
            pos_desc = "🔴低" if pos < 30 else ("🟢高" if pos > 70 else "🟡中")
            close_pct = r.get("close_pct_short", 0)
            pct_desc = f"{'▲' if close_pct > 0 else '▼'}{abs(close_pct):.1f}%"
            action = _get_action_short(r)

            lines.append(f"| {name} | {score:.0f} | {rsi_emoji}{rsi:.0f} | {kdj_emoji}{kdj_k:.0f} | {macd_emoji} | {vol_emoji}{vol_ratio:.1f}x | {pos_desc}{pos:.0f}% | {pct_desc} | {action} |")

        lines.append("")

    # 危险标的矩阵
    if danger_signals:
        lines.append("---\n")
        lines.append("## 🔴 危险标的矩阵\n")
        lines.append("| ETF | 评分 | RSI | KDJ | MACD | 量能 | 位置 | 偏离度 | 操作 |")
        lines.append("|:----|:----:|:---:|:---:|:----:|:----:|:----:|:------:|:----:|")

        for r in danger_signals:
            name = r.get('etf_name', '')[:8]
            score = r.get("pattern_score", 0)
            rsi = r.get("rsi14", 50)
            rsi_emoji = "🔴" if rsi < 30 else ("🟢" if rsi > 70 else "🟡")
            kdj_k = r.get("kdj_k", 0)
            kdj_emoji = "🔴" if kdj_k < 20 else ("🟢" if kdj_k > 80 else "🟡")
            macd_hist = r.get("macd_hist", 0)
            macd_emoji = "🟢" if macd_hist > 0 else "🔴"
            vol_ratio = r.get("vol_ratio", 1)
            vol_emoji = "📈" if vol_ratio > 1.2 else ("📉" if vol_ratio < 0.8 else "➡️")
            pos = r.get("price_pos_60d", 50)
            pos_desc = "🔴低" if pos < 30 else ("🟢高" if pos > 70 else "🟡中")
            close_pct = r.get("close_pct_short", 0)
            pct_desc = f"{'▲' if close_pct > 0 else '▼'}{abs(close_pct):.1f}%"
            action = _get_action_short(r)

            lines.append(f"| {name} | {score:.0f} | {rsi_emoji}{rsi:.0f} | {kdj_emoji}{kdj_k:.0f} | {macd_emoji} | {vol_emoji}{vol_ratio:.1f}x | {pos_desc}{pos:.0f}% | {pct_desc} | {action} |")

        lines.append("")

    # 均线对比
    lines.append("---\n")
    lines.append("## 📊 均线对比\n")
    lines.append("| ETF | MA5 | MA10 | MA20 | MA60 | 均线状态 |")
    lines.append("|:----|:---:|:----:|:----:|:----:|:--------:|")

    for r in sorted_results:
        name = r.get('etf_name', '')[:8]
        ma5 = r.get("ma5", 0)
        ma10 = r.get("ma10", 0)
        ma20 = r.get("ma20", 0)
        ma60 = r.get("ma60", 0)
        ma_pattern = r.get("ma_pattern", "纠缠")[:6]

        lines.append(f"| {name} | {ma5:.2f} | {ma10:.2f} | {ma20:.2f} | {ma60:.2f} | {ma_pattern} |")

    lines.append("")

    # 知行信号对比
    lines.append("---\n")
    lines.append("## 📉 知行信号对比\n")
    lines.append("| ETF | 白线(EMA) | 黄线(均线组) | 三线位置 | 偏离变化 |")
    lines.append("|:----|:---------:|:------------:|:--------:|:--------:|")

    for r in sorted_results:
        name = r.get('etf_name', '')[:8]
        zx_short = r.get("zx_short", 0)
        zx_long = r.get("zx_long", 0)
        line_pos = r.get("line_position", "纠缠")[:8]
        deviation_change = r.get("close_deviation_change", 0)
        change_emoji = "📈" if deviation_change > 0.5 else ("📉" if deviation_change < -0.5 else "➡️")

        lines.append(f"| {name} | {zx_short:.4f} | {zx_long:.4f} | {line_pos} | {change_emoji}{deviation_change:+.2f}% |")

    lines.append("")

    # 异常信号汇总
    abnormal_all = []
    for r in results:
        abnormal = r.get("abnormal_signals", [])
        for sig in abnormal:
            abnormal_all.append({
                "etf": r.get("etf_name", ""),
                "type": sig.get("type", ""),
                "desc": sig.get("description", ""),
                "severity": sig.get("severity", ""),
            })

    if abnormal_all:
        lines.append("---\n")
        lines.append("## ⚠️ 异常信号汇总\n")
        lines.append("| ETF | 异常类型 | 描述 | 级别 |")
        lines.append("|:----|:--------|:-----|:----:|")

        for sig in abnormal_all:
            emoji = "🔴" if sig["severity"] == "warning" else ("🟡" if sig["severity"] == "positive" else "🟢")
            lines.append(f"| {sig['etf'][:8]} | {sig['type']} | {sig['desc'][:20]} | {emoji} |")

        lines.append("")

    # 风险提示
    lines.append("---\n")
    lines.append("**⚠️ 风险提示**: 本报告仅供参考，不构成投资建议。市场有风险，投资需谨慎。\n")
    lines.append(f"\n*报告生成时间: {now}*")

    return "\n".join(lines)


def _get_action_short(r: dict) -> str:
    """获取简短操作建议"""
    sig = r.get("signal", "")
    rsi = r.get("rsi14", 50)
    pos = r.get("price_pos_60d", 50)

    if sig == "STRONG":
        if rsi > 70:
            return "持有/减仓"
        elif rsi < 30:
            return "加仓机会"
        else:
            return "持有"
    elif sig == "WATCH":
        if rsi < 30:
            return "关注"
        else:
            return "观望"
    else:  # DANGER
        if rsi < 30:
            return "等待"
        elif pos < 40:
            return "关注"
        else:
            return "减仓"


def main():
    import argparse

    parser = argparse.ArgumentParser(description="持仓ETF分析报告生成器")
    parser.add_argument("--mode", "-m", default="compact",
                        choices=["compact", "classic", "card", "chart", "radar", "matrix"],
                        help="报告模式: compact(精简) | classic(经典详表) | card(卡片式) | chart(图表可视化) | radar(多维雷达) | matrix(对比矩阵)")
    parser.add_argument("--positions", "-p", default="./positions.json",
                        help="持仓配置文件路径")
    parser.add_argument("--output", "-o", default=None,
                        help="输出文件路径")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"📊 持仓ETF分析报告 ({args.mode} 模式)")
    print(f"{'='*60}\n")

    # 模式说明
    mode_descriptions = {
        "compact": "精简模式：ASCII图表+信号分布图",
        "classic": "经典模式：完整技术指标表格",
        "card": "卡片模式：每只ETF卡片式展示",
        "chart": "图表模式：ASCII可视化图表",
        "radar": "雷达模式：多维度评分对比",
        "matrix": "矩阵模式：多维度横向对比",
    }
    print(f"📋 模式说明: {mode_descriptions.get(args.mode, '')}\n")

    # 加载持仓
    positions_file = args.positions
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

    if args.output:
        output_path = args.output
    else:
        output_path = f"./portfolio_report_{date_str}_{args.mode}.md"

    md = generate_report(results, mode=args.mode, output_path=output_path)
    print(f"\n📄 报告已保存: {output_path}")
    print(f"\n📊 报告预览 (前100行):")
    print("-" * 60)
    for line in md.split('\n')[:100]:
        print(line)
    print("-" * 60)
    print(f"\n💡 如需生成其他模式报告，使用:")
    print(f"   python -m market_monitor.report.portfolio_analyzer --mode classic")
    print(f"   python -m market_monitor.report.portfolio_analyzer --mode card")
    print(f"   python -m market_monitor.report.portfolio_analyzer --mode chart")
    print(f"   python -m market_monitor.report.portfolio_analyzer --mode radar")
    print(f"   python -m market_monitor.report.portfolio_analyzer --mode matrix")


def create_feishu_doc(md_file_path: str) -> tuple:
    """创建飞书文档并返回 (doc_id, doc_url)"""
    try:
        import subprocess
        from market_monitor.config import FEISHU_WEBHOOK

        # 从文件名提取标题
        title = os.path.basename(md_file_path).replace('.md', '')

        # 调用 lark-cli 创建文档
        result = subprocess.run(
            ['lark-cli', 'docs', '+create', '--title', title, '--markdown', f'@{md_file_path}'],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode == 0:
            import json
            output = json.loads(result.stdout)
            if output.get('ok'):
                data = output.get('data', {})
                doc_id = data.get('doc_id', '')
                doc_url = data.get('doc_url', '')
                print(f"✅ 飞书文档已创建: {doc_url}")
                return doc_id, doc_url

        print(f"⚠ 创建文档失败: {result.stderr}")
        return None, None

    except Exception as e:
        print(f"⚠ 创建飞书文档出错: {e}")
        return None, None


def build_summary_message(results: list, doc_url: str = None) -> str:
    """构建中等版精简消息 - 按信号颜色分类"""
    lines = []

    # 分类统计
    strong_signals = [r for r in results if r.get("signal") == "STRONG"]
    watch_signals = [r for r in results if r.get("signal") == "WATCH"]
    danger_signals = [r for r in results if r.get("signal") == "DANGER"]

    # 汇总行
    total = len(results)
    lines.append(f"📊 **持仓汇总**: {total} 只 | 🟢强势{len(strong_signals)} | 🟡观望{len(watch_signals)} | 🔴危险{len(danger_signals)}")

    # 🟢 强势标的
    if strong_signals:
        lines.append("")
        lines.append("### 🟢 强势标的")
        names = [r.get('etf_name', '') for r in strong_signals]
        lines.append(f"- {', '.join(names)}")

    # 🟡 观望标的
    if watch_signals:
        lines.append("")
        lines.append("### 🟡 观望标的")
        names = [r.get('etf_name', '') for r in watch_signals]
        lines.append(f"- {', '.join(names)}")

    # 🔴 危险标的
    if danger_signals:
        lines.append("")
        lines.append("### 🔴 危险标的")
        names = [r.get('etf_name', '') for r in danger_signals]
        lines.append(f"- {', '.join(names)}")

    return "\n".join(lines)


def _get_action(r: dict) -> str:
    """获取单只ETF的操作建议"""
    sig = r.get("signal", "")
    rsi = r.get("rsi14", 50)
    pos = r.get("position_level", 50)

    if sig == "STRONG":
        if rsi > 70:
            return "持有/减仓"
        elif rsi < 30:
            return "加仓机会"
        else:
            return "持有"
    elif sig == "WATCH":
        if rsi < 30:
            return "关注"
        else:
            return "观望"
    else:  # DANGER
        if rsi < 30:
            return "等待"
        elif pos < 40:
            return "关注"
        else:
            return "减仓"


def send_to_feishu(md_file_path: str, doc_url: str = None, results: list = None):
    """发送精简报告到飞书"""
    try:
        import requests
        from market_monitor.config import FEISHU_WEBHOOK

        if not FEISHU_WEBHOOK:
            print("⚠ 飞书 Webhook 未配置，跳过发送")
            return False

        # 构建消息内容
        if results:
            content = build_summary_message(results, doc_url)
        else:
            # 降级：读取文件内容
            with open(md_file_path, 'r', encoding='utf-8') as f:
                md_content = f.read()
            max_len = 2000
            content = md_content[:max_len] + "\n\n...（内容过长，点击链接查看完整报告）"

        # 获取标题时间
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")

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
                        "content": f"📊 {date_str} 持仓分析报告"
                    },
                    "template": "blue"
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": content
                        }
                    }
                ]
            }
        }

        # 添加文档链接按钮
        if doc_url:
            payload["card"]["elements"].append({
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {
                            "tag": "plain_text",
                            "content": "📄 查看完整报告"
                        },
                        "type": "primary",
                        "url": doc_url
                    }
                ]
            })

        # 添加时间戳
        payload["card"]["elements"].append({
            "tag": "note",
            "elements": [
                {
                    "tag": "plain_text",
                    "content": f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 北京时间"
                }
            ]
        })

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
