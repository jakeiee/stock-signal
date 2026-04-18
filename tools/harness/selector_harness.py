"""
选股 Harness - ETF初筛 + 知行趋势线二次筛选。

使用示例：
    from tools.harness.selector_harness import run_stock_selector

    # 基本运行（KDJ超卖策略）
    context = run_stock_selector()

    # 强势策略
    context = run_stock_selector(strategy="strong")

    # 自定义策略
    context = run_stock_selector(
        strategy="custom",
        etf_types=["行业主题", "宽基指数"],
        min_diff_pct=2,
        max_results=20
    )

    # 程序化使用
    from tools.harness.selector_harness import create_selector_harness
    harness = create_selector_harness(strategy="kdj_oversold", feishu=True)
    context = harness.execute()
"""

import os
import sys
import argparse
from datetime import datetime
from typing import List, Dict, Optional

# 导入 Harness 核心
from .core import Harness
from .context import ExecutionContext, StepResult
from .step import Step, StepStatus

# 导入选股模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from market_monitor.analysis.stock_selector import (
    StockSelector,
    ETFPreFilter,
    TrendFilter,
    quick_screen,
    print_selector_report,
    get_selector_report_for_feishu,
)


# ── 预设策略配置 ───────────────────────────────────────────────────────────────

STRATEGIES = {
    "kdj_oversold": {
        "name": "KDJ超卖策略",
        "description": "筛选KDJ超卖且知行趋势线多头的ETF",
        "etf_filter": {
            "types": ["行业主题", "宽基指数"],
            "kdj_op": "<",
            "kdj_value": 30,
        },
        "trend_filter": {
            "signal_filter": ["BUY", "HOLD_BULL"],
            "min_diff_pct": 1,
        }
    },
    "strong": {
        "name": "强势策略",
        "description": "筛选知行趋势线强势信号的ETF",
        "etf_filter": {
            "types": ["行业主题", "宽基指数"],
            "scale_min": 5000,
        },
        "trend_filter": {
            "signal_filter": ["BUY"],
            "position_filter": ["多头排列"],
            "min_diff_pct": 2,
        }
    },
    "oversold_rebound": {
        "name": "超跌反弹策略",
        "description": "筛选超跌后可能反弹的ETF",
        "etf_filter": {
            "types": ["行业主题", "宽基指数"],
            "kdj_op": "<",
            "kdj_value": 20,
        },
        "trend_filter": {
            "signal_filter": ["BUY", "HOLD_BULL", "WATCH"],
            "min_diff_pct": 0,
            "trend_direction": "上升",
        }
    },
}


# ── Step 定义 ─────────────────────────────────────────────────────────────────

class PreFilterStep(Step):
    """Step 1: ETF预筛选"""
    
    def __init__(self, etf_filter: Dict):
        super().__init__(
            name="pre_filter",
            description="ETF初筛"
        )
        self.etf_filter = etf_filter
    
    def execute(self, ctx: ExecutionContext) -> StepResult:
        try:
            print("[预筛选] 开始ETF初筛...")
            
            pre_filter = ETFPreFilter()
            
            # 设置类型
            if self.etf_filter.get("types"):
                pre_filter.set_types(self.etf_filter["types"])
            
            # 设置规模
            if self.etf_filter.get("scale_min"):
                pre_filter.set_scale_min(self.etf_filter["scale_min"])
            
            # 设置KDJ条件
            if self.etf_filter.get("kdj_op") and self.etf_filter.get("kdj_value") is not None:
                pre_filter.set_kdj_condition(
                    self.etf_filter["kdj_op"],
                    self.etf_filter["kdj_value"]
                )
            
            # 执行预筛选
            result = pre_filter.execute()
            
            if "error" in result:
                return StepResult(
                    step_name=self.name,
                    status=StepStatus.FAILED,
                    message=f"预筛选失败: {result['error']}"
                )
            
            etfs = result.get("etfs", [])
            ctx.set("pre_filter_etfs", etfs)
            ctx.set("pre_filter_count", len(etfs))
            
            print(f"[预筛选] 得到 {len(etfs)} 只ETF")
            
            return StepResult(
                step_name=self.name,
                status=StepStatus.SUCCESS,
                message=f"预筛选得到 {len(etfs)} 只ETF",
                data={"etfs": etfs}
            )
        except Exception as e:
            return StepResult(
                step_name=self.name,
                status=StepStatus.FAILED,
                message=f"预筛选失败: {e}"
            )


class TrendFilterStep(Step):
    """Step 2: 知行趋势线二次筛选"""
    
    def __init__(self, trend_filter: Dict, max_batch: int = 50):
        super().__init__(
            name="trend_filter",
            description="知行趋势线二次筛选"
        )
        self.trend_filter = trend_filter
        self.max_batch = max_batch
    
    def execute(self, ctx: ExecutionContext) -> StepResult:
        try:
            etfs = ctx.get("pre_filter_etfs", [])
            if not etfs:
                return StepResult(
                    step_name=self.name,
                    status=StepStatus.FAILED,
                    message="无预筛选结果"
                )
            
            print("[趋势筛选] 开始知行趋势线分析...")
            
            # 创建选股器
            selector = StockSelector()
            
            # 设置最大批次
            selector.set_max_batch(self.max_batch)
            
            # 设置ETF过滤
            if self.trend_filter.get("types"):
                selector.set_etf_filter(types=self.trend_filter["types"])
            
            # 设置趋势过滤
            trend_cfg = {}
            if self.trend_filter.get("signal_filter"):
                trend_cfg["signal_filter"] = self.trend_filter["signal_filter"]
            if self.trend_filter.get("position_filter"):
                trend_cfg["position_filter"] = self.trend_filter["position_filter"]
            if self.trend_filter.get("min_diff_pct") is not None:
                trend_cfg["min_diff_pct"] = self.trend_filter["min_diff_pct"]
            if self.trend_filter.get("trend_direction"):
                trend_cfg["trend_direction"] = self.trend_filter["trend_direction"]
            
            if trend_cfg:
                selector.set_trend_filter(**trend_cfg)
            
            # 执行选股
            result = selector.execute()
            
            ctx.set("selector_result", result)
            ctx.set("selected_count", result.get("count", 0))
            
            print(f"[趋势筛选] 选中 {result.get('count', 0)} 只ETF")
            
            return StepResult(
                step_name=self.name,
                status=StepStatus.SUCCESS,
                message=f"趋势筛选选中 {result.get('count', 0)} 只ETF",
                data=result
            )
        except Exception as e:
            return StepResult(
                step_name=self.name,
                status=StepStatus.FAILED,
                message=f"趋势筛选失败: {e}"
            )


class QuickScreenStep(Step):
    """快速筛选 Step（替代方案）"""
    
    def __init__(self, strategy: str = "kdj_oversold"):
        super().__init__(
            name="quick_screen",
            description=f"快速筛选: {strategy}"
        )
        self.strategy = strategy
    
    def execute(self, ctx: ExecutionContext) -> StepResult:
        try:
            print(f"[快速筛选] 使用策略: {self.strategy}")
            
            result = quick_screen(self.strategy)
            
            ctx.set("selector_result", result)
            ctx.set("selected_count", result.get("count", 0))
            
            print(f"[快速筛选] 选中 {result.get('count', 0)} 只ETF")
            
            return StepResult(
                step_name=self.name,
                status=StepStatus.SUCCESS,
                message=f"快速筛选选中 {result.get('count', 0)} 只ETF",
                data=result
            )
        except Exception as e:
            return StepResult(
                step_name=self.name,
                status=StepStatus.FAILED,
                message=f"快速筛选失败: {e}"
            )


class TerminalOutputStep(Step):
    """Step 3: 终端输出"""
    
    def __init__(self):
        super().__init__(
            name="terminal_output",
            description="终端输出选股结果"
        )
    
    def execute(self, ctx: ExecutionContext) -> StepResult:
        try:
            result = ctx.get("selector_result", {})
            
            # 打印选股报告
            print_selector_report(result)
            
            ctx.set("selector_report", get_selector_report_for_feishu(result))
            
            return StepResult(
                step_name=self.name,
                status=StepStatus.SUCCESS,
                message="选股结果已输出"
            )
        except Exception as e:
            return StepResult(
                step_name=self.name,
                status=StepStatus.FAILED,
                message=f"输出失败: {e}"
            )


class FeishuPushStep(Step):
    """Step 4: 飞书推送"""
    
    def __init__(self, report_key: str = "selector_report"):
        super().__init__(
            name="feishu_push",
            description="推送选股结果到飞书"
        )
        self.report_key = report_key
    
    def execute(self, ctx: ExecutionContext) -> StepResult:
        try:
            from market_monitor.config import FEISHU_WEBHOOK
            import requests
            
            if not FEISHU_WEBHOOK:
                return StepResult(
                    step_name=self.name,
                    status=StepStatus.SKIPPED,
                    message="飞书 Webhook 未配置"
                )
            
            report = ctx.get(self.report_key)
            if not report:
                return StepResult(
                    step_name=self.name,
                    status=StepStatus.SKIPPED,
                    message="无选股报告"
                )
            
            # 构建卡片
            payload = {
                "msg_type": "interactive",
                "card": {
                    "config": {"wide_screen_mode": True},
                    "header": {
                        "title": {"tag": "plain_text", "content": report.get("title", "选股建议")},
                        "template": "green"
                    },
                    "elements": [
                        {"tag": "div", "text": {"tag": "lark_md", "content": report.get("content", "暂无数据")}},
                        {"tag": "note", "elements": [
                            {"tag": "plain_text", "content": f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"}
                        ]}
                    ]
                }
            }
            
            response = requests.post(
                FEISHU_WEBHOOK,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            result = response.json()
            if result.get('code') == 0:
                return StepResult(
                    step_name=self.name,
                    status=StepStatus.SUCCESS,
                    message="选股结果已发送到飞书"
                )
            else:
                return StepResult(
                    step_name=self.name,
                    status=StepStatus.FAILED,
                    message=f"飞书发送失败: {result}"
                )
        except Exception as e:
            return StepResult(
                step_name=self.name,
                status=StepStatus.FAILED,
                message=f"飞书推送失败: {e}"
            )


# ── Harness 工厂 ───────────────────────────────────────────────────────────────

def create_selector_harness(
    strategy: str = "kdj_oversold",
    custom_config: Optional[Dict] = None,
    use_quick: bool = True,
    max_batch: int = 50,
    feishu: bool = False
) -> Harness:
    """创建选股 Harness"""
    harness = Harness(name=f"stock_selector_{strategy}")
    
    if use_quick:
        # 使用快速筛选
        harness.add_step(QuickScreenStep(strategy=strategy))
    else:
        # 使用自定义配置
        if custom_config is None:
            custom_config = STRATEGIES.get(strategy, STRATEGIES["kdj_oversold"])
        
        harness.add_step(PreFilterStep(etf_filter=custom_config.get("etf_filter", {})))
        
        trend_filter = TrendFilterStep(
            trend_filter=custom_config.get("trend_filter", {}),
            max_batch=max_batch
        )
        harness.add_step(trend_filter)
    
    harness.add_step(TerminalOutputStep())
    
    if feishu:
        harness.add_step(FeishuPushStep())
    
    return harness


def run_stock_selector(
    strategy: str = "kdj_oversold",
    custom_config: Optional[Dict] = None,
    use_quick: bool = True,
    max_batch: int = 50,
    feishu: bool = False
) -> ExecutionContext:
    """运行选股"""
    harness = create_selector_harness(
        strategy=strategy,
        custom_config=custom_config,
        use_quick=use_quick,
        max_batch=max_batch,
        feishu=feishu
    )
    
    print(f"\n{'='*50}")
    print(f"🎯 选股 Harness - {STRATEGIES.get(strategy, {}).get('name', strategy)}")
    print(f"{'='*50}\n")
    
    context = harness.execute()
    
    # 打印执行摘要
    print(f"\n{'='*50}")
    print(f"✅ 执行完成")
    print(f"{'='*50}")
    
    return context


# ── CLI 入口 ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="选股 Harness")
    parser.add_argument("--strategy", "-s", default="kdj_oversold",
                       choices=list(STRATEGIES.keys()),
                       help="选股策略")
    parser.add_argument("--feishu", "-f", action="store_true",
                       help="启用飞书推送")
    parser.add_argument("--max-batch", "-m", type=int, default=50,
                       help="最大分析批次")
    
    args = parser.parse_args()
    
    context = run_stock_selector(
        strategy=args.strategy,
        feishu=args.feishu,
        max_batch=args.max_batch
    )
