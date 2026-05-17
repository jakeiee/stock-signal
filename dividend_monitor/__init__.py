"""
dividend_monitor 包初始化
自动注册 DividendModule 到 ModuleRegistry
"""

from tools.harness.module_interface import BaseModule, ModuleMetadata, Step
from typing import List, Dict, Any


class DividendModule(BaseModule):
    """股息指数监控模块 - 实现BaseModule接口"""

    def __init__(self, feishu: bool = False):
        self.feishu = feishu
        self.metadata = ModuleMetadata(
            name="dividend_monitor",
            version="1.0.0",
            description="股息指数监控：KDJ信号 + 流动性分析 + 仓位建议",
            author="CodeBuddy",
            dependencies=["dividend_monitor"],
            tags=["finance", "dividend", "monitoring"]
        )

    def get_metadata(self) -> ModuleMetadata:
        """获取模块元数据"""
        return self.metadata

    def get_steps(self) -> List[Step]:
        """获取模块步骤列表"""
        from tools.harness.dividend_harness import (
            FetchBondYieldStep, FetchXalphaDataStep, ValuationDataStep,
            KDJSignalStep, LiquidityAnalysisStep, PositionRecommendationStep,
            MarkdownReportStep
        )
        from tools.harness.step import StepConfig

        return [
            FetchBondYieldStep(StepConfig(metadata={"data_key": "bond_yield"})),
            FetchXalphaDataStep(
                index_code="HKHSTECH",
                data_key="price_data",
                config=StepConfig(metadata={"description": "获取恒生科技指数数据"})
            ),
            ValuationDataStep(StepConfig(metadata={"data_key": "valuation_data"})),
            KDJSignalStep(StepConfig(metadata={"output_key": "kdj_signal"})),
            LiquidityAnalysisStep(StepConfig(metadata={"output_key": "liquidity_signal"})),
            PositionRecommendationStep(StepConfig(metadata={"output_key": "position_recommendation"})),
            MarkdownReportStep(
                output_path="/Users/liuyi/WorkBuddy/stock-signal/dividend_report.md",
                title="股息指数监控报告",
            ),
        ]

    def validate_config(self) -> bool:
        """验证模块配置"""
        return True

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """运行模块"""
        from tools.harness.dividend_harness import create_dividend_harness
        harness = create_dividend_harness()
        return harness.execute()

    def health_check(self) -> bool:
        """健康检查"""
        try:
            from pathlib import Path
            cache_path = Path("/Users/liuyi/WorkBuddy/stock-signal/dividend_monitor/valuation_cache.json")
            return cache_path.exists()
        except Exception:
            return False


# 自注册
from tools.harness.module_registry import register_module
register_module(DividendModule())
