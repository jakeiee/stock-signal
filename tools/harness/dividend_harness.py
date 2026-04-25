"""
Harness 适配层 - dividend_monitor

使用 Harness 框架重写的股息指数监控执行流程。
"""

from typing import Any, Dict, Optional
import sys
import traceback

# 添加项目路径
sys.path.insert(0, "/Users/liuyi/WorkBuddy/stock-signal")

from tools.harness import Harness, Step, StepConfig, ExecutionContext
from tools.harness.steps import FetchXalphaDataStep, ReportStep, MarkdownReportStep


class FetchBondYieldStep(Step):
    """
    获取国债收益率数据步骤

    从 Wind APP 记录数据或本地缓存获取国债收益率数据。
    """

    name = "fetch_bond_yield"

    def __init__(self, config: Optional[StepConfig] = None):
        super().__init__(config)
        self.data_key = self.config.metadata.get("data_key", "bond_yield")

    def validate(self) -> bool:
        return True

    def execute(self, context: ExecutionContext) -> Dict[str, Any]:
        """获取国债收益率数据"""
        import json
        from pathlib import Path

        try:
            # 优先从 Wind APP 估值缓存获取
            cache_path = Path("/Users/liuyi/WorkBuddy/stock-signal/dividend_monitor/valuation_cache.json")
            if cache_path.exists():
                with open(cache_path, 'r', encoding='utf-8') as f:
                    cache = json.load(f)
                # 尝试获取无风险利率
                for key, val in cache.items():
                    if isinstance(val, dict) and "risk_free_rate" in val:
                        data = {"risk_free_rate": val["risk_free_rate"], "source": "wind_app_cache"}
                        context.set(self.data_key, data)
                        return data

            # 回退到默认值
            data = {"risk_free_rate": 1.8, "source": "default"}
            context.set(self.data_key, data)
            return data

        except Exception as e:
            context.error(f"Failed to fetch bond yield: {str(e)}")
            # 使用默认值而不是抛出异常
            data = {"risk_free_rate": 1.8, "source": "default"}
            context.set(self.data_key, data)
            return data


class ValuationDataStep(Step):
    """
    获取估值数据步骤

    从本地缓存文件获取股息指数估值数据。
    """

    name = "fetch_valuation_data"

    def __init__(self, config: Optional[StepConfig] = None):
        super().__init__(config)
        self.data_key = self.config.metadata.get("data_key", "valuation_data")

    def validate(self) -> bool:
        return True

    def execute(self, context: ExecutionContext) -> Dict[str, Any]:
        """获取估值数据"""
        import pandas as pd
        from pathlib import Path

        try:
            cache_path = Path("/Users/liuyi/WorkBuddy/stock-signal/valuation_cache.csv")

            if cache_path.exists():
                df = pd.read_csv(cache_path)
                # 获取最新数据
                latest = df.iloc[-1].to_dict()
                context.set(self.data_key, latest)
                return latest
            else:
                context.warning("Valuation cache file not found")
                return {}

        except Exception as e:
            context.error(f"Failed to fetch valuation data: {str(e)}")
            raise


class KDJSignalStep(Step):
    """
    KDJ 信号计算步骤

    计算股息指数的 KDJ 指标并生成信号。
    """

    name = "calculate_kdj_signal"

    def __init__(self, config: Optional[StepConfig] = None):
        super().__init__(config)
        self.output_key = self.config.metadata.get("output_key", "kdj_signal")

    def validate(self) -> bool:
        return True

    def execute(self, context: ExecutionContext) -> Dict[str, Any]:
        """计算 KDJ 信号"""
        try:
            from dividend_monitor.analysis.kdj import _calc_kdj_from_df

            # 获取价格数据
            price_data = context.get("price_data")
            if price_data and "price" in price_data:
                df = price_data["price"]
                kdj_result = _calc_kdj_from_df(df)
                if kdj_result:
                    result = {
                        "signal": kdj_result.get("signal", "hold"),
                        "K": kdj_result.get("K"),
                        "D": kdj_result.get("D"),
                        "J": kdj_result.get("J"),
                    }
                else:
                    result = {"signal": "hold", "reason": "KDJ calculation returned None"}
            else:
                result = {"signal": "hold", "reason": "No price data available"}

            context.set(self.output_key, result)
            return result

        except Exception as e:
            context.error(f"Failed to calculate KDJ: {str(e)}")
            raise


class LiquidityAnalysisStep(Step):
    """
    流动性分析步骤

    分析成交额数据和市场流动性。
    """

    name = "analyze_liquidity"

    def __init__(self, config: Optional[StepConfig] = None):
        super().__init__(config)
        self.output_key = self.config.metadata.get("output_key", "liquidity_signal")

    def validate(self) -> bool:
        return True

    def execute(self, context: ExecutionContext) -> Dict[str, Any]:
        """分析流动性"""
        import pandas as pd
        from pathlib import Path

        try:
            # 读取成交额数据
            liquidity_path = Path("/Users/liuyi/WorkBuddy/stock-signal/market_monitor/data/liquidity.csv")

            if liquidity_path.exists():
                df = pd.read_csv(liquidity_path)
                latest = df.iloc[-1] if len(df) > 0 else {}

                result = {
                    "liquidity": latest.get("liquidity_level", "unknown"),
                    "trend": latest.get("trend", "unknown"),
                    "signal": "bullish" if latest.get("trend") == "increasing" else "neutral",
                }
            else:
                result = {"signal": "neutral", "reason": "No liquidity data available"}

            context.set(self.output_key, result)
            return result

        except Exception as e:
            context.error(f"Failed to analyze liquidity: {str(e)}")
            raise


class PositionRecommendationStep(Step):
    """
    仓位建议步骤

    综合分析结果生成仓位建议。
    """

    name = "generate_position_recommendation"

    def __init__(self, config: Optional[StepConfig] = None):
        super().__init__(config)
        self.output_key = self.config.metadata.get("output_key", "position_recommendation")

    def validate(self) -> bool:
        return True

    def execute(self, context: ExecutionContext) -> Dict[str, Any]:
        """生成仓位建议"""
        try:
            # 收集各信号
            kdj_signal = context.get("kdj_signal", {})
            liquidity_signal = context.get("liquidity_signal", {})
            valuation_data = context.get("valuation_data", {})

            # 综合评分
            score = 0
            reasons = []

            # KDJ 信号
            kdj = kdj_signal.get("signal", "hold")
            if kdj == "buy":
                score += 3
                reasons.append("KDJ 金叉")
            elif kdj == "sell":
                score -= 3
                reasons.append("KDJ 死叉")

            # 流动性信号
            liq = liquidity_signal.get("signal", "neutral")
            if liq == "bullish":
                score += 2
                reasons.append("流动性改善")
            elif liq == "bearish":
                score -= 2
                reasons.append("流动性收紧")

            # 估值信号
            pe = valuation_data.get("pe", 0)
            if pe > 0:
                if pe < 10:
                    score += 2
                    reasons.append("PE 低估")
                elif pe > 20:
                    score -= 2
                    reasons.append("PE 高估")

            # 生成建议
            if score >= 4:
                recommendation = "加仓"
            elif score <= -4:
                recommendation = "减仓"
            else:
                recommendation = "持有"

            result = {
                "recommendation": recommendation,
                "score": score,
                "reasons": reasons,
                "kdj": kdj,
                "liquidity": liq,
                "pe": pe,
            }

            context.set(self.output_key, result)
            return result

        except Exception as e:
            context.error(f"Failed to generate recommendation: {str(e)}")
            raise


def create_dividend_harness() -> Harness:
    """
    创建股息指数监控 Harness

    Returns:
        配置好的 Harness 实例
    """
    harness = Harness(
        name="dividend_monitor",
        config={"description": "股息指数监控执行流程"},
    )

    # 添加步骤
    harness.add_step(
        FetchBondYieldStep(
            StepConfig(metadata={"data_key": "bond_yield"})
        )
    )

    harness.add_step(
        FetchXalphaDataStep(
            index_code="HKHSTECH",
            data_key="price_data",
            config=StepConfig(metadata={"description": "获取恒生科技指数数据"})
        )
    )

    harness.add_step(
        ValuationDataStep(
            StepConfig(metadata={"data_key": "valuation_data"})
        )
    )

    harness.add_step(
        KDJSignalStep(
            StepConfig(metadata={"output_key": "kdj_signal"})
        )
    )

    harness.add_step(
        LiquidityAnalysisStep(
            StepConfig(metadata={"output_key": "liquidity_signal"})
        )
    )

    harness.add_step(
        PositionRecommendationStep(
            StepConfig(metadata={"output_key": "position_recommendation"})
        )
    )

    harness.add_step(
        MarkdownReportStep(
            output_path="/Users/liuyi/WorkBuddy/stock-signal/dividend_report.md",
            title="股息指数监控报告",
        )
    )

    return harness


def run_dividend_monitor():
    """运行股息指数监控"""
    harness = create_dividend_harness()

    # 打印执行计划
    print("执行计划:")
    for i, step in enumerate(harness.steps, 1):
        print(f"  {i}. {step.name}")

    print("\n开始执行...\n")

    # 执行
    context = harness.execute()

    # 输出结果
    print("\n执行摘要:")
    print(f"  状态: {context.status.value}")
    print(f"  耗时: {context.duration:.2f}秒")
    print(f"  成功步骤: {sum(1 for r in context.step_results.values() if r.status == 'success')}")
    print(f"  失败步骤: {sum(1 for r in context.step_results.values() if r.status == 'failed')}")

    # 输出仓位建议
    recommendation = context.get("position_recommendation", {})
    if recommendation:
        print("\n仓位建议:")
        print(f"  推荐: {recommendation.get('recommendation')}")
        print(f"  评分: {recommendation.get('score')}")
        print(f"  理由: {', '.join(recommendation.get('reasons', []))}")

    return context


if __name__ == "__main__":
    run_dividend_monitor()
