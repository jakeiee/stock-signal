"""
仓位管理系统 - Position Management System

基于估值、趋势、止损的仓位配置引擎

核心功能：
1. 市场仓位配置（A股/港股/美股）
2. 风格仓位配置（高弹性/高分红/均衡）
3. 估值仓位算法（替代凯利公式）
4. 止损规则引擎
5. 动态调仓建议

使用示例：
    from market_monitor.analysis.position_manager import PositionManager, MarketAllocation, StyleAllocation

    # 初始化管理器
    pm = PositionManager()

    # 获取市场仓位建议
    market_alloc = pm.get_market_allocation()

    # 获取风格仓位建议
    style_alloc = pm.get_style_allocation()

    # 计算止损建议
    stop_loss = pm.calculate_stop_loss(current_loss_pct=0.08)

    # 生成调仓建议
    rebalance = pm.suggest_rebalance(positions, valuations)
"""

import json
import os
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

# ── 枚举定义 ──────────────────────────────────────────────────────────────────

class Market(Enum):
    """市场枚举"""
    A_STOCK = "a_stock"      # A股
    HK_STOCK = "hk_stock"     # 港股
    US_STOCK = "us_stock"     # 美股
    CASH = "cash"             # 现金/债券


class Style(Enum):
    """风格枚举"""
    HIGH_ELASTICITY = "high_elasticity"  # 高弹性（科技/成长）
    HIGH_DIVIDEND = "high_dividend"      # 高分红（价值/红利）
    BALANCED = "balanced"                # 均衡配置


class ValuationLevel(Enum):
    """估值水平枚举"""
    EXTREMELY_LOW = "extremely_low"   # 极度低估
    LOW = "low"                       # 低估
    FAIR = "fair"                     # 合理
    HIGH = "high"                     # 偏高
    EXTREMELY_HIGH = "extremely_high" # 极度偏高


class TrendDirection(Enum):
    """趋势方向枚举（基于知行信号）"""
    BULLISH = "bullish"      # 知行买入/知行持有
    BEARISH = "bearish"      # 知行卖出
    NEUTRAL = "neutral"      # 知行观望


# ── 数据类定义 ────────────────────────────────────────────────────────────────

@dataclass
class MarketConfig:
    """市场配置"""
    name: str
    market: Market
    max_allocation: float       # 最大仓位上限
    valuation_metric: str        # 估值指标 (PE/PB/CAPE)
    low_threshold: float         # 低估阈值
    high_threshold: float        # 高估阈值

    # 估值调整系数（基于估值百分位）
    coef_extremely_low: float = 1.5
    coef_low: float = 1.2
    coef_fair: float = 1.0
    coef_high: float = 0.7
    coef_extremely_high: float = 0.4

    # 趋势系数
    coef_bullish: float = 1.2
    coef_bearish: float = 0.7
    coef_neutral: float = 1.0

    # 活跃市值信号配置（仅A股使用）
    active_market_cap_signal: str = "neutral"  # bullish/neutral/bearish
    active_market_cap_csv_path: str = ""       # CSV文件路径


@dataclass
class StyleConfig:
    """风格配置"""
    name: str
    style: Style
    max_allocation: float       # 最大仓位上限
    volatility_level: str       # 波动等级 (high/medium/low)
    description: str = ""


@dataclass
class StopLossRule:
    """止损规则"""
    loss_pct: float             # 亏损比例
    action: str                 # 动作 (watch/reduce/quit/double_down)
    description: str = ""
    position_scale: float = 0   # 加仓比例（仅适用于加仓场景）


@dataclass
class PositionAllocation:
    """仓位配置结果"""
    code: str
    name: str
    market: Market
    style: Style

    current_weight: float       # 当前权重
    target_weight: float        # 目标权重
    adjustment: float           # 调整幅度 (+/-)

    valuation_level: ValuationLevel = ValuationLevel.FAIR
    valuation_percentile: float = 50.0
    trend: TrendDirection = TrendDirection.NEUTRAL

    current_loss_pct: float = 0.0
    stop_loss_action: str = ""

    # 估值仓位计算详情
    base_weight: float = 0.0     # 基础仓位
    valuation_coef: float = 1.0  # 估值系数
    trend_coef: float = 1.0     # 趋势系数


@dataclass
class AllocationSummary:
    """配置汇总"""
    generated_at: str
    total_value: float

    # 市场配置
    market_allocations: Dict[str, float] = field(default_factory=dict)
    market_targets: Dict[str, float] = field(default_factory=dict)

    # 风格配置
    style_allocations: Dict[str, float] = field(default_factory=dict)
    style_targets: Dict[str, float] = field(default_factory=dict)

    # 组合指标
    total_equity_ratio: float = 0.0   # 权益仓位占比
    cash_ratio: float = 0.0           # 现金仓位占比
    expected_volatility: float = 0.0   # 预期波动率
    risk_level: str = "medium"         # 风险等级

    # 调仓建议
    rebalance_needed: bool = False
    rebalance_items: List[Dict] = field(default_factory=list)


# ── 默认配置 ──────────────────────────────────────────────────────────────────

# 配置文件路径
CONFIG_FILE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "position_config.json"
)

# 全局配置缓存
_config_cache: Dict = {}

DEFAULT_MARKET_CONFIGS: Dict[Market, MarketConfig] = {
    Market.A_STOCK: MarketConfig(
        name="A股（万得全A除金融石油石化）",
        market=Market.A_STOCK,
        max_allocation=0.35,
        valuation_metric="wind_a_ex_fin_oil_pe_percentile",
        low_threshold=0.30,
        high_threshold=0.70,
    ),
    Market.HK_STOCK: MarketConfig(
        name="港股（恒生科技）",
        market=Market.HK_STOCK,
        max_allocation=0.35,
        valuation_metric="hst_tech_pe_percentile",
        low_threshold=0.30,
        high_threshold=0.70,
    ),
    Market.US_STOCK: MarketConfig(
        name="美股（标普500）",
        market=Market.US_STOCK,
        max_allocation=0.35,
        valuation_metric="cape",
        low_threshold=20.0,
        high_threshold=30.0,
    ),
}

DEFAULT_STYLE_CONFIGS: Dict[Style, StyleConfig] = {
    Style.HIGH_ELASTICITY: StyleConfig(
        name="高弹性（科技/成长）",
        style=Style.HIGH_ELASTICITY,
        max_allocation=0.40,
        volatility_level="high",
        description="包含科技、互联网、创新药、机器人等高增长赛道",
    ),
    Style.HIGH_DIVIDEND: StyleConfig(
        name="高分红（价值/红利）",
        style=Style.HIGH_DIVIDEND,
        max_allocation=0.30,
        volatility_level="low",
        description="包含红利ETF、金融、公用事业等稳健分红标的",
    ),
    Style.BALANCED: StyleConfig(
        name="均衡配置（宽基）",
        style=Style.BALANCED,
        max_allocation=0.50,
        volatility_level="medium",
        description="包含沪深300、标普500等宽基指数",
    ),
}

DEFAULT_STOP_LOSS_RULES: List[StopLossRule] = [
    StopLossRule(loss_pct=0.05, action="watch", description="预警观察"),
    StopLossRule(loss_pct=0.10, action="reduce", description="减仓50%", position_scale=0.50),
    StopLossRule(loss_pct=0.15, action="quit", description="强制止损"),
    StopLossRule(loss_pct=0.20, action="quit", description="完全离场"),
]

# 亏损加仓规则（定投补仓）
LOSS_DOLLAR_COST_AVGING: Dict[float, float] = {
    0.05: 0.20,   # 亏损5% → 加仓20%
    0.10: 0.33,   # 亏损10% → 加仓33%
    0.15: 0.50,   # 亏损15% → 加仓50%
    0.20: 1.00,   # 亏损20% → 翻倍补仓
    0.30: 1.50,   # 亏损30% → 谨慎加仓150%
}


# ── 核心类 ────────────────────────────────────────────────────────────────────

class PositionManager:
    """
    仓位管理器

    基于估值、趋势、止损的多维度仓位配置引擎

    算法说明：
    目标仓位 = 基础仓位 × 估值调整系数 × 趋势系数 × 活跃市值系数（A 股专用）

    估值调整系数：
    - PE/PB百分位 < 20%: 1.5 (极度低估)
    - PE/PB百分位 20-40%: 1.2 (低估)
    - PE/PB百分位 40-60%: 1.0 (合理)
    - PE/PB百分位 60-80%: 0.7 (偏高)
    - PE/PB百分位 > 80%: 0.4 (极度偏高)

    趋势系数（基于知行信号）：
    - 知行买入/知行持有: 1.2
    - 知行观望: 1.0
    - 知行卖出: 0.7

    活跃市值系数（仅 A 股，基于知行信号）：
    - 多头信号(bullish): 1.2 (大市值主导，流动性好)
    - 中性信号(neutral): 1.0
    - 空头信号(bearish): 0.7 (小市值主导)
    """

    def __init__(
        self,
        market_configs: Optional[Dict[Market, MarketConfig]] = None,
        style_configs: Optional[Dict[Style, StyleConfig]] = None,
        stop_loss_rules: Optional[List[StopLossRule]] = None,
    ):
        """
        初始化仓位管理器

        Args:
            market_configs: 市场配置字典，默认使用DEFAULT_MARKET_CONFIGS
            style_configs: 风格配置字典，默认使用DEFAULT_STYLE_CONFIGS
            stop_loss_rules: 止损规则列表，默认使用DEFAULT_STOP_LOSS_RULES
        """
        self.market_configs = market_configs or DEFAULT_MARKET_CONFIGS
        self.style_configs = style_configs or DEFAULT_STYLE_CONFIGS
        self.stop_loss_rules = stop_loss_rules or DEFAULT_STOP_LOSS_RULES

        # 加载配置文件中的系数
        self._load_coefficients()

    def _load_coefficients(self) -> None:
        """
        从配置文件加载系数，支持热更新
        """
        global _config_cache
        try:
            if os.path.exists(CONFIG_FILE_PATH):
                with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
                    _config_cache = json.load(f)
        except Exception as e:
            print(f"[仓位管理] 加载配置文件失败: {e}")

    def get_config_coefficients(self) -> Dict:
        """
        获取当前生效的系数配置

        Returns:
            包含所有系数配置的字典
        """
        # 重新加载以获取最新配置
        self._load_coefficients()
        return _config_cache

    def print_coefficients(self) -> None:
        """
        打印当前生效的仓位系数配置
        """
        config = self.get_config_coefficients()

        print("\n" + "=" * 60)
        print("📊 仓位系数配置")
        print("=" * 60)

        # 估值系数
        if "valuation_coefficients" in config:
            print("\n📈 估值系数（基于估值百分位）:")
            print("-" * 50)
            for level, data in config["valuation_coefficients"].items():
                coef = data.get("coefficient", 1.0)
                action = data.get("action", "")
                if "threshold_max" in data:
                    threshold = f"<{data['threshold_max']}%"
                else:
                    threshold = f">{data.get('threshold_min', 0)}%"
                print(f"  {level:>15} | 系数: {coef:.2f} | {threshold:>8} | {action}")

        # 趋势系数
        if "trend_coefficients" in config:
            print("\n📉 趋势系数（基于知行信号）:")
            print("-" * 50)
            for trend, data in config["trend_coefficients"].items():
                coef = data.get("coefficient", 1.0)
                cond = data.get("condition", "")
                print(f"  {trend:>10} | 系数: {coef:.2f} | {cond}")

        # 活跃市值系数（仅A股）
        if "market_configs" in config and "a_stock" in config["market_configs"]:
            a_stock = config["market_configs"]["a_stock"]
            if "active_market_cap_coefficients" in a_stock:
                print("\n💹 活跃市值系数（A股专用）:")
                print("-" * 50)
                for signal, data in a_stock["active_market_cap_coefficients"].items():
                    coef = data.get("coefficient", 1.0)
                    desc = data.get("description", "")
                    print(f"  {signal:>10} | 系数: {coef:.2f} | {desc}")

        # 止损规则
        if "stop_loss_rules" in config:
            print("\n🛑 止损规则:")
            print("-" * 50)
            for level, data in config["stop_loss_rules"].items():
                threshold = data.get("loss_threshold", 0) * 100
                action = data.get("action", "")
                desc = data.get("description", "")
                print(f"  {level:>10} | 亏损>{threshold:>5.1f}% | {action:>8} | {desc}")

        # 定投补仓规则
        if "dollar_cost_averaging" in config:
            print("\n💰 定投补仓规则:")
            print("-" * 50)
            for level, data in config["dollar_cost_averaging"].items():
                threshold = data.get("loss_threshold", 0) * 100
                add_scale = data.get("add_scale", 0) * 100
                desc = data.get("description", "")
                print(f"  亏损>{threshold:>5.1f}% → 加仓{add_scale:>5.0f}% | {desc}")

        print("\n" + "=" * 60)
        print(f"配置文件路径: {CONFIG_FILE_PATH}")
        print("=" * 60 + "\n")

    def get_valuation_coef(self, percentile: float) -> float:
        """
        根据估值百分位获取调整系数

        Args:
            percentile: 估值百分位 (0-100)

        Returns:
            估值调整系数
        """
        # 从配置文件获取系数
        if "valuation_coefficients" in _config_cache:
            for level, data in _config_cache["valuation_coefficients"].items():
                threshold_max = data.get("threshold_max")
                threshold_min = data.get("threshold_min")

                if threshold_max is not None and percentile < threshold_max:
                    return data.get("coefficient", 1.0)
                elif threshold_min is not None and percentile >= threshold_min:
                    continue  # 需要检查下一个档位

            # 查找最后一个匹配的档位（用于 >= threshold_min 的情况）
            matched_coef = 1.0
            for level, data in _config_cache["valuation_coefficients"].items():
                threshold_min = data.get("threshold_min")
                if threshold_min is not None and percentile >= threshold_min:
                    matched_coef = data.get("coefficient", 1.0)
            return matched_coef

        # 回退到硬编码默认值
        if percentile < 20:
            return 1.5   # 极度低估
        elif percentile < 40:
            return 1.2   # 低估
        elif percentile < 60:
            return 1.0   # 合理
        elif percentile < 80:
            return 0.7   # 偏高
        else:
            return 0.4   # 极度偏高

    def get_valuation_level(self, percentile: float) -> ValuationLevel:
        """
        根据估值百分位获取估值水平

        Args:
            percentile: 估值百分位 (0-100)

        Returns:
            估值水平枚举
        """
        if percentile < 20:
            return ValuationLevel.EXTREMELY_LOW
        elif percentile < 40:
            return ValuationLevel.LOW
        elif percentile < 60:
            return ValuationLevel.FAIR
        elif percentile < 80:
            return ValuationLevel.HIGH
        else:
            return ValuationLevel.EXTREMELY_HIGH

    def get_trend_coef(self, trend: TrendDirection) -> float:
        """
        根据趋势方向获取趋势系数

        Args:
            trend: 趋势方向

        Returns:
            趋势系数
        """
        # 从配置文件获取系数
        if "trend_coefficients" in _config_cache:
            trend_key = trend.value
            if trend_key in _config_cache["trend_coefficients"]:
                return _config_cache["trend_coefficients"][trend_key].get("coefficient", 1.0)

        # 回退到硬编码默认值
        if trend == TrendDirection.BULLISH:
            return 1.2
        elif trend == TrendDirection.BEARISH:
            return 0.7
        else:
            return 1.0

    def get_stop_loss_action(self, loss_pct: float) -> Tuple[str, float]:
        """
        根据亏损比例获取止损动作

        Args:
            loss_pct: 亏损比例（负数表示盈利）

        Returns:
            (动作描述, 加仓比例)
        """
        for rule in self.stop_loss_rules:
            if loss_pct <= -rule.loss_pct:
                return rule.action, rule.position_scale
        return "hold", 0.0

    def calculate_dollar_cost_averaging(self, loss_pct: float) -> float:
        """
        计算定投补仓比例

        Args:
            loss_pct: 亏损比例（正数）

        Returns:
            建议加仓比例（相对于原仓位）
        """
        # 找到最近的亏损档位
        for threshold, scale in sorted(LOSS_DOLLAR_COST_AVGING.items(), reverse=True):
            if loss_pct >= threshold:
                return scale
        return 0.0  # 亏损太小，不建议加仓

    def get_active_market_cap_coef(self, signal: str) -> float:
        """
        根据活跃市值信号获取调整系数

        Args:
            signal: 活跃市值信号 (bullish/neutral/bearish)

        Returns:
            活跃市值调整系数
        """
        # 从配置文件获取系数
        if "market_configs" in _config_cache:
            a_stock = _config_cache.get("market_configs", {}).get("a_stock", {})
            active_coefs = a_stock.get("active_market_cap_coefficients", {})
            if signal in active_coefs:
                return active_coefs[signal].get("coefficient", 1.0)

        # 回退到硬编码默认值
        if signal == "bullish":
            return 1.2   # 多头区间（大市值主导，流动性好）
        elif signal == "neutral":
            return 1.0   # 中性区间
        else:
            return 0.7   # 空头区间（小市值主导）

    def get_latest_active_market_cap_signal(self, csv_path: str) -> Tuple[str, Optional[str], Optional[float]]:
        """
        从CSV文件获取最新活跃市值信号（同步市场监控逻辑）

        入场/持有/离场周期判断逻辑：
        - chg_pct >= 4.0%：入场信号
        - chg_pct <= -2.3%：离场信号
        - 上一个明显信号为入场 → 多头区间(bullish)
        - 上一个明显信号为离场 → 空头区间(bearish)

        Args:
            csv_path: CSV文件路径

        Returns:
            (zone_type, active_cap, chg_pct): 区间类型、最新市值、涨跌幅
                zone_type: bullish/neutral/bearish
                active_cap: 最新的active_cap值（亿元）
                chg_pct: 涨跌幅百分比
        """
        try:
            import pandas as pd
            if not os.path.exists(csv_path):
                return "neutral", None, None
            
            df = pd.read_csv(csv_path)
            if df.empty or len(df) < 2:
                return "neutral", None, None
            
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            
            # 计算涨跌幅
            chg_pct = float(latest["chg_pct"]) if latest.get("chg_pct") is not None else None
            active_cap = float(latest["active_cap"]) if latest.get("active_cap") is not None else None
            
            # 查找最近一个明显信号（入场 >=4% 或 离场 <=-2.3%）
            last_clear_signal = None
            for idx in range(len(df) - 1, -1, -1):
                row = df.iloc[idx]
                cap_chg = float(row["chg_pct"]) if row.get("chg_pct") is not None else None
                if cap_chg is None:
                    continue
                if cap_chg >= 4.0:
                    last_clear_signal = "entry"
                    break
                elif cap_chg <= -2.3:
                    last_clear_signal = "exit"
                    break
            
            # 判断当前区间类型
            if last_clear_signal == "entry":
                zone_type = "bullish"  # 多头区间
            elif last_clear_signal == "exit":
                zone_type = "bearish"  # 空头区间
            else:
                zone_type = "neutral"  # 无明显信号
            
            return zone_type, active_cap, chg_pct
                
        except Exception:
            return "neutral", None, None

    def calculate_market_target_weight(
        self,
        market: Market,
        valuation_percentile: float,
        trend: TrendDirection = TrendDirection.NEUTRAL,
        active_market_cap_signal: str = "neutral",
    ) -> float:
        """
        计算单一市场的目标仓位

        Args:
            market: 市场枚举
            valuation_percentile: 估值百分位
            trend: 趋势方向
            active_market_cap_signal: 活跃市值信号（仅A股使用）：bullish/neutral/bearish

        Returns:
            目标仓位比例
        """
        config = self.market_configs.get(market)
        if not config:
            return 0.0

        # 基础仓位
        base_weight = config.max_allocation

        # 估值调整系数
        valuation_coef = self.get_valuation_coef(valuation_percentile)

        # 趋势系数
        trend_coef = self.get_trend_coef(trend)

        # 活跃市值调整系数（仅A股）
        active_coef = 1.0
        if market == Market.A_STOCK:
            active_coef = self.get_active_market_cap_coef(active_market_cap_signal)

        # 计算目标仓位
        target_weight = base_weight * valuation_coef * trend_coef * active_coef

        # 限制在0到最大仓位之间
        target_weight = max(0.0, min(target_weight, config.max_allocation))

        return round(target_weight, 4)

    def get_market_allocation(
        self,
        valuations: Dict[Market, float],
        trends: Optional[Dict[Market, TrendDirection]] = None,
        active_market_cap_signals: Optional[Dict[Market, str]] = None,
    ) -> Dict[str, Dict]:
        """
        获取多市场配置建议

        Args:
            valuations: 各市场估值百分位 {Market: percentile}
            trends: 各市场趋势方向（可选）
            active_market_cap_signals: 各市场活跃市值信号 {Market: signal}（仅A股使用）：bullish/neutral/bearish

        Returns:
            市场配置结果
        """
        if trends is None:
            trends = {m: TrendDirection.NEUTRAL for m in valuations.keys()}
        if active_market_cap_signals is None:
            active_market_cap_signals = {}

        # 先计算各市场的基础目标仓位
        raw_weights = {}
        for market, percentile in valuations.items():
            trend = trends.get(market, TrendDirection.NEUTRAL)
            config = self.market_configs.get(market)
            if not config:
                continue

            # 基础仓位
            base_weight = config.max_allocation

            # 估值调整系数
            valuation_coef = self.get_valuation_coef(percentile)

            # 趋势系数
            trend_coef = self.get_trend_coef(trend)

            # 活跃市值调整系数（仅A股）
            active_coef = 1.0
            active_signal = active_market_cap_signals.get(market, "neutral")
            if market == Market.A_STOCK:
                active_coef = self.get_active_market_cap_coef(active_signal)

            # 计算目标仓位（未限制）
            raw_weight = base_weight * valuation_coef * trend_coef * active_coef

            raw_weights[market] = {
                "name": config.name,
                "valuation_percentile": percentile,
                "valuation_level": self.get_valuation_level(percentile).value,
                "trend": trend.value,
                "base_weight": config.max_allocation,
                "valuation_coef": valuation_coef,
                "trend_coef": trend_coef,
                "active_market_cap_coef": active_coef,
                "raw_weight": raw_weight,
            }

        # 计算总权重并进行归一化
        total_raw = sum(w["raw_weight"] for w in raw_weights.values())

        # 最大权益仓位（保留20%现金）
        max_equity = 0.80

        # 归一化并限制最大仓位
        market_results = {}
        if total_raw > max_equity:
            # 需要归一化
            for market, data in raw_weights.items():
                # 按比例分配，但不超过单市场最大仓位
                normalized_weight = data["raw_weight"] / total_raw * max_equity
                data["target_weight"] = min(normalized_weight, self.market_configs[market].max_allocation)
                data["adjustment"] = data["target_weight"] - data["base_weight"]
        else:
            # 直接使用原始计算值，但限制最大仓位
            for market, data in raw_weights.items():
                data["target_weight"] = min(data["raw_weight"], self.market_configs[market].max_allocation)
                data["adjustment"] = data["target_weight"] - data["base_weight"]

        market_results = {market.value: data for market, data in raw_weights.items()}

        # 计算汇总
        total_equity = sum(w["target_weight"] for w in market_results.values())
        cash_weight = max(0.0, 1.0 - total_equity)

        return {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "market_allocations": market_results,
            "total_equity_ratio": round(total_equity, 4),
            "cash_ratio": round(cash_weight, 4),
            "total_ratio": round(total_equity + cash_weight, 4),
        }

    def get_style_allocation(
        self,
        high_elasticity_pct: float = 0.0,
        high_dividend_pct: float = 0.0,
        balanced_pct: float = 0.0,
    ) -> Dict[str, Dict]:
        """
        获取风格配置建议

        Args:
            high_elasticity_pct: 高弹性风格当前占比
            high_dividend_pct: 高分红风格当前占比
            balanced_pct: 均衡风格当前占比

        Returns:
            风格配置结果
        """
        style_results = {}

        for style, config in self.style_configs.items():
            current = locals().get(f"{style.value}_pct", 0.0)
            target = config.max_allocation
            adjustment = target - current

            style_results[style.value] = {
                "name": config.name,
                "description": config.description,
                "volatility_level": config.volatility_level,
                "current_weight": current,
                "max_weight": config.max_allocation,
                "target_weight": target,
                "adjustment": adjustment,
            }

        return {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "style_allocations": style_results,
        }

    def calculate_stop_loss(
        self,
        current_loss_pct: float,
        current_weight: float,
        total_value: float,
    ) -> Dict:
        """
        计算止损建议

        Args:
            current_loss_pct: 当前亏损比例（正数）
            current_weight: 当前持仓权重
            total_value: 组合总市值

        Returns:
            止损建议
        """
        action, reduce_scale = self.get_stop_loss_action(-current_loss_pct)

        # 计算定投补仓建议
        dca_scale = self.calculate_dollar_cost_averaging(current_loss_pct)
        dca_amount = current_weight * dca_scale * total_value if dca_scale > 0 else 0

        # 计算建议持仓
        if action == "reduce":
            suggested_weight = current_weight * (1 - reduce_scale)
        elif action == "quit":
            suggested_weight = 0.0
        else:
            suggested_weight = current_weight

        return {
            "current_loss_pct": current_loss_pct,
            "current_weight": current_weight,
            "action": action,
            "suggested_weight": suggested_weight,
            "adjustment": suggested_weight - current_weight,
            "reduce_scale": reduce_scale if action == "reduce" else None,
            "dca_recommendation": {
                "scale": dca_scale,
                "amount": round(dca_amount, 2),
                "description": f"亏损{current_loss_pct*100:.0f}%时建议加仓{dca_scale*100:.0f}%" if dca_scale > 0 else "无需加仓",
            },
            "risk_alert": current_loss_pct >= 0.15,  # 亏损15%以上触发风险警告
        }

    def suggest_rebalance(
        self,
        positions: List[Dict],
        valuations: Dict[str, Dict],
        trend_indicators: Optional[Dict[str, TrendDirection]] = None,
    ) -> AllocationSummary:
        """
        生成调仓建议

        Args:
            positions: 当前持仓列表 [{code, name, market, style, weight, loss_pct}]
            valuations: 各持仓估值数据 {code: {percentile, metric}}
            trend_indicators: 各持仓趋势指标 {code: TrendDirection}

        Returns:
            调仓汇总
        """
        if trend_indicators is None:
            trend_indicators = {}

        rebalance_items = []
        total_value = sum(p.get("value", 0) for p in positions)

        for pos in positions:
            code = pos.get("code", "")
            market_str = pos.get("market", Market.A_STOCK.value)

            # 解析市场
            try:
                market = Market(market_str)
            except ValueError:
                market = Market.A_STOCK

            # 获取估值
            val_data = valuations.get(code, {})
            percentile = val_data.get("percentile", 50.0)

            # 获取趋势
            trend = trend_indicators.get(code, TrendDirection.NEUTRAL)

            # 计算目标仓位
            target = self.calculate_market_target_weight(market, percentile, trend)
            current = pos.get("weight", 0.0)
            adjustment = target - current

            # 计算止损
            loss_pct = pos.get("loss_pct", 0.0)
            stop_loss = self.calculate_stop_loss(loss_pct, current, total_value)

            rebalance_items.append({
                "code": code,
                "name": pos.get("name", ""),
                "market": market.value,
                "style": pos.get("style", ""),
                "current_weight": round(current, 4),
                "target_weight": round(target, 4),
                "adjustment": round(adjustment, 4),
                "valuation_percentile": percentile,
                "valuation_level": self.get_valuation_level(percentile).value,
                "trend": trend.value,
                "loss_pct": loss_pct,
                "stop_loss_action": stop_loss["action"],
                "suggested_weight": stop_loss["suggested_weight"],
            })

        # 按调整幅度排序
        rebalance_items.sort(key=lambda x: abs(x["adjustment"]), reverse=True)

        # 计算每个市场的总目标仓位并限制在最大值内
        market_total_target = {}
        for item in rebalance_items:
            market = item["market"]
            market_total_target[market] = market_total_target.get(market, 0) + item["target_weight"]

        # 对超过市场最大仓位的标的进行缩减
        for market, total in market_total_target.items():
            try:
                market_enum = Market(market)
                max_alloc = self.market_configs[market_enum].max_allocation
            except (ValueError, KeyError):
                max_alloc = 0.30  # 默认30%

            if total > max_alloc:
                # 按比例缩减该市场的所有标的
                scale = max_alloc / total
                for item in rebalance_items:
                    if item["market"] == market:
                        item["target_weight"] = round(item["target_weight"] * scale, 4)
                        item["adjustment"] = round(item["target_weight"] - item["current_weight"], 4)

        # 如果总权益仓位超过上限，对所有目标仓位进行归一化
        max_equity_ratio = 0.80
        total_target_before_scale = sum(item["target_weight"] for item in rebalance_items)
        if total_target_before_scale > max_equity_ratio:
            scale_factor = max_equity_ratio / total_target_before_scale
            for item in rebalance_items:
                item["target_weight"] = round(item["target_weight"] * scale_factor, 4)
                item["adjustment"] = round(item["target_weight"] - item["current_weight"], 4)

        # 重新排序
        rebalance_items.sort(key=lambda x: abs(x["adjustment"]), reverse=True)

        # 汇总统计：基于当前持仓的市值比例计算目标仓位
        market_current = {}
        market_target = {}
        style_current = {}
        style_target = {}
        rebalance_needed = any(abs(item["adjustment"]) > 0.02 for item in rebalance_items)

        for item in rebalance_items:
            market = item["market"]
            style = item.get("style", "")
            current = item["current_weight"]
            target = item["target_weight"]

            # 市场统计（相对于权益仓位）
            market_current[market] = market_current.get(market, 0) + current
            market_target[market] = market_target.get(market, 0) + target

            # 风格统计
            if style:
                style_current[style] = style_current.get(style, 0) + current
                style_target[style] = style_target.get(style, 0) + target

        # 计算总和
        total_current = sum(market_current.values()) or 1.0
        total_target = sum(market_target.values()) or 1.0

        # 计算相对比例（确保总和为100%）
        market_summary = {}
        for market in set(list(market_current.keys()) + list(market_target.keys())):
            if total_target > 0:
                market_summary[market] = market_target.get(market, 0) / total_target
            else:
                market_summary[market] = 0

        style_summary = {}
        for style in set(list(style_current.keys()) + list(style_target.keys())):
            if total_target > 0:
                style_summary[style] = style_target.get(style, 0) / total_target
            else:
                style_summary[style] = 0

        # 计算最终的总权益仓位（实际目标仓位的总和）
        final_equity_ratio = sum(item["target_weight"] for item in rebalance_items)
        final_cash_ratio = 1.0 - final_equity_ratio

        # 将实际目标权重存储到summary中（用于显示组合占比）
        for i, item in enumerate(rebalance_items):
            rebalance_items[i]["portfolio_weight"] = item["target_weight"]

        # 计算市场配置（相对比例）
        if total_target > 0:
            market_alloc_summary = {m: t / total_target for m, t in market_target.items()}
        else:
            market_alloc_summary = {}

        return AllocationSummary(
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            total_value=total_value,
            market_allocations=market_alloc_summary,
            style_allocations=style_summary,
            total_equity_ratio=final_equity_ratio,
            cash_ratio=final_cash_ratio,
            rebalance_needed=rebalance_needed,
            rebalance_items=rebalance_items,
        )

    def generate_report(self, summary: AllocationSummary) -> str:
        """
        生成文本报告

        Args:
            summary: 配置汇总

        Returns:
            格式化的文本报告
        """
        lines = []
        lines.append("=" * 80)
        lines.append(f"📊 仓位管理报告 - {summary.generated_at}")
        lines.append("=" * 80)

        # 市场配置（基于汇总数据，显示权益仓位占比）
        lines.append("\n📈 市场配置建议（权益仓位内部分布）")
        lines.append("-" * 60)

        if summary.market_allocations:
            for market_id, ratio in summary.market_allocations.items():
                config = self.market_configs.get(Market(market_id)) if market_id in [m.value for m in Market] else None
                name = config.name if config else market_id
                # 组合占比 = 权益占比 × 总权益仓位
                portfolio_weight = ratio * summary.total_equity_ratio
                lines.append(
                    f"  {name:<20} 权益占比: {ratio*100:>6.1f}%  "
                    f"(组合占比: {portfolio_weight*100:.1f}%)"
                )
        else:
            for market, config in self.market_configs.items():
                lines.append(
                    f"  {config.name:<20} 权益占比: {'--':>6}  "
                    f"(组合占比: --)"
                )

        # 风格配置（显示权益仓位内部分布）
        lines.append("\n🎯 风格配置建议（权益仓位内部分布）")
        lines.append("-" * 60)
        if summary.style_allocations:
            for style_id, ratio in summary.style_allocations.items():
                config = self.style_configs.get(Style(style_id)) if style_id in [s.value for s in Style] else None
                name = config.name if config else style_id
                target_weight = ratio * summary.total_equity_ratio
                lines.append(
                    f"  {name:<20} 权益占比: {ratio*100:>6.1f}%  "
                    f"(组合占比: {target_weight*100:.1f}%)"
                )
        else:
            for style, config in self.style_configs.items():
                lines.append(
                    f"  {config.name:<20} 权益占比: {'--':>6}  "
                    f"(组合占比: --)"
                )

        # 汇总
        lines.append("\n📋 组合汇总")
        lines.append("-" * 60)
        lines.append(f"  权益仓位: {summary.total_equity_ratio*100:.1f}%")
        lines.append(f"  现金仓位: {summary.cash_ratio*100:.1f}%")

        # 调仓建议
        if summary.rebalance_needed:
            lines.append("\n⚠️ 调仓建议")
            lines.append("-" * 60)
            lines.append(f"{'代码':<8} {'名称':<12} {'当前':<8} {'目标':<8} {'调整':<8} {'止损'}")
            lines.append("-" * 60)
            for item in summary.rebalance_items[:10]:
                adj_sign = "+" if item["adjustment"] >= 0 else ""
                lines.append(
                    f"{item['code']:<8} {item['name']:<12} "
                    f"{item['current_weight']*100:>6.1f}% {item['target_weight']*100:>6.1f}% "
                    f"{adj_sign}{item['adjustment']*100:>5.1f}% {item['stop_loss_action']}"
                )

        lines.append("\n" + "=" * 80)
        return "\n".join(lines)


# ── 便捷函数 ──────────────────────────────────────────────────────────────────

def quick_market_allocation(
    a_stock_pe: float,
    hk_pb: float,
    us_cape: float,
    trend: Optional[Dict[str, str]] = None,
) -> Dict:
    """
    快速获取市场配置建议

    Args:
        a_stock_pe: A股PE值
        hk_pb: 港股PB值
        us_cape: 美股CAPE值
        trend: 趋势方向 {'a_stock': 'bullish/bearish/neutral', ...}

    Returns:
        配置建议
    """
    # 简化的估值百分位估算（实际应使用历史数据）
    # 这里使用一个简化模型，实际使用时应该连接真实数据源
    a_stock_pct = min(100, max(0, (a_stock_pe - 8) / 30 * 100))  # 假设PE范围8-38
    hk_pb_pct = min(100, max(0, (hk_pb - 0.5) / 1.5 * 100))     # 假设PB范围0.5-2.0
    us_cape_pct = min(100, max(0, (us_cape - 10) / 30 * 100))   # 假设CAPE范围10-40

    pm = PositionManager()
    valuations = {
        Market.A_STOCK: a_stock_pct,
        Market.HK_STOCK: hk_pb_pct,
        Market.US_STOCK: us_cape_pct,
    }

    trends = {}
    if trend:
        for market_str, trend_str in trend.items():
            try:
                market = Market(market_str)
                trends[market] = TrendDirection(trend_str)
            except ValueError:
                pass

    return pm.get_market_allocation(valuations, trends)


# ── 配置文件格式 ──────────────────────────────────────────────────────────────

def load_config_from_json(filepath: str) -> Dict:
    """
    从JSON文件加载配置

    Args:
        filepath: 配置文件路径

    Returns:
        配置字典
    """
    if not os.path.exists(filepath):
        return {}

    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config_to_json(config: Dict, filepath: str) -> bool:
    """
    保存配置到JSON文件

    Args:
        config: 配置字典
        filepath: 配置文件路径

    Returns:
        是否成功
    """
    try:
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"保存配置失败: {e}")
        return False


# ── 测试代码 ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # 示例0: 打印当前系数配置
    print("=" * 80)
    print("示例0: 打印当前系数配置")
    print("=" * 80)
    pm = PositionManager()
    pm.print_coefficients()

    # 示例1: 快速市场配置
    print("=" * 80)
    print("示例1: 快速市场配置")
    print("=" * 80)
    result = quick_market_allocation(
        a_stock_pe=12.5,
        hk_pb=1.2,
        us_cape=28.0,
        trend={"a_stock": "bullish", "hk_stock": "neutral"},
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # 示例2: 完整配置
    print("\n" + "=" * 80)
    print("示例2: 完整仓位管理器")
    print("=" * 80)
    pm = PositionManager()

    # 市场估值
    valuations = {
        Market.A_STOCK: 35.0,    # A股低估
        Market.HK_STOCK: 55.0,   # 港股合理
        Market.US_STOCK: 75.0,   # 美股偏高
    }
    trends = {
        Market.A_STOCK: TrendDirection.BULLISH,
        Market.HK_STOCK: TrendDirection.NEUTRAL,
        Market.US_STOCK: TrendDirection.BEARISH,
    }

    market_result = pm.get_market_allocation(valuations, trends)
    print(json.dumps(market_result, indent=2, ensure_ascii=False))

    # 示例3: 止损计算
    print("\n" + "=" * 80)
    print("示例3: 止损建议")
    print("=" * 80)
    stop_loss = pm.calculate_stop_loss(
        current_loss_pct=0.08,
        current_weight=0.15,
        total_value=100000,
    )
    print(json.dumps(stop_loss, indent=2, ensure_ascii=False))

    # 示例4: 模拟调仓
    print("\n" + "=" * 80)
    print("示例4: 调仓建议")
    print("=" * 80)
    positions = [
        {"code": "513180", "name": "恒生科技ETF", "market": "hk_stock", "style": "high_elasticity", "weight": 0.25, "loss_pct": 0.05, "value": 25000},
        {"code": "159202", "name": "恒生互联网ETF", "market": "hk_stock", "style": "high_elasticity", "weight": 0.15, "loss_pct": -0.03, "value": 15000},
        {"code": "562500", "name": "机器人ETF", "market": "a_stock", "style": "high_elasticity", "weight": 0.10, "loss_pct": 0.12, "value": 10000},
    ]
    valuations_data = {
        "513180": {"percentile": 40.0, "metric": "pb"},
        "159202": {"percentile": 50.0, "metric": "pb"},
        "562500": {"percentile": 65.0, "metric": "pe"},
    }
    trends_data = {
        "513180": TrendDirection.BULLISH,
        "159202": TrendDirection.NEUTRAL,
        "562500": TrendDirection.BEARISH,
    }

    summary = pm.suggest_rebalance(positions, valuations_data, trends_data)
    print(pm.generate_report(summary))
