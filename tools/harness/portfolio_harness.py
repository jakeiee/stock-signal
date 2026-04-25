"""
持仓分析 Harness - 使用 xalpha 数据源。

使用示例：
    from tools.harness.portfolio_harness import run_portfolio_analysis

    # 基本运行
    context = run_portfolio_analysis()

    # 发送飞书
    context = run_portfolio_analysis(feishu=True)

    # 程序化使用
    from tools.harness.portfolio_harness import create_portfolio_harness
    harness = create_portfolio_harness(feishu=True)
    context = harness.execute()
"""

import os
import sys
import json
import argparse
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional

# 导入 Harness 核心
from .core import Harness
from .context import ExecutionContext, StepResult
from .step import Step, StepStatus

# 导入分析模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from market_monitor.report.portfolio_analyzer import (
    ETF_MAPPING,
    get_index_data,
    calculate_technical,
    analyze_etf,
    generate_md_report,
)


# ── Step 定义 ─────────────────────────────────────────────────────────────────

class LoadPositionsStep(Step):
    """Step 1: 加载持仓数据"""
    
    def __init__(self, positions_file: str = "./positions.json"):
        super().__init__()
        self.name = "load_positions"
        self.positions_file = positions_file
    
    def validate(self) -> bool:
        return True

    def execute(self, ctx: ExecutionContext) -> StepResult:
        try:
            if not os.path.exists(self.positions_file):
                return StepResult(
                    step_name=self.name,
                    status=StepStatus.FAILED.value,
                    error=f"持仓文件不存在: {self.positions_file}"
                )
            
            with open(self.positions_file, 'r', encoding='utf-8') as f:
                positions = json.load(f)
            
            ctx.set("positions", positions)
            ctx.set("positions_count", len(positions))
            
            return StepResult(
                step_name=self.name,
                status=StepStatus.SUCCESS.value,
                output={"positions": positions}
            )
        except Exception as e:
            return StepResult(
                step_name=self.name,
                status=StepStatus.FAILED.value,
                error=f"加载持仓失败: {e}"
            )


class AnalyzeETFStep(Step):
    """Step 2: 分析单只ETF"""
    
    def __init__(self, data_key: str = "positions"):
        super().__init__()
        self.name = "analyze_etf"
        self.data_key = data_key
    
    def validate(self) -> bool:
        return True

    def execute(self, ctx: ExecutionContext) -> StepResult:
        try:
            positions = ctx.get(self.data_key, [])
            if not positions:
                return StepResult(
                    step_name=self.name,
                    status=StepStatus.FAILED,
                    message="无持仓数据"
                )
            
            results = []
            failed = []
            
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
                        failed.append(code)
                else:
                    failed.append(code)
            
            ctx.set("etf_analysis", results)
            ctx.set("analysis_count", len(results))
            ctx.set("failed_count", len(failed))
            
            return StepResult(
                step_name=self.name,
                status=StepStatus.SUCCESS.value,
                output={
                    "results": results,
                    "failed": failed
                }
            )
        except Exception as e:
            return StepResult(
                step_name=self.name,
                status=StepStatus.FAILED.value,
                error=f"分析失败: {e}"
            )


class AggregateSignalStep(Step):
    """Step 3: 聚合信号"""
    
    def __init__(self, data_key: str = "etf_analysis"):
        super().__init__()
        self.name = "aggregate_signal"
        self.data_key = data_key
    
    def validate(self) -> bool:
        return True

    def execute(self, ctx: ExecutionContext) -> StepResult:
        try:
            results = ctx.get(self.data_key, [])
            if not results:
                return StepResult(
                    step_name=self.name,
                    status=StepStatus.FAILED.value,
                    error="无分析结果"
                )
            
            # 分类统计
            strong = [r for r in results if r.get("signal") == "STRONG"]
            watch = [r for r in results if r.get("signal") == "WATCH"]
            danger = [r for r in results if r.get("signal") == "DANGER"]
            oversold = [r for r in results if r.get("rsi14", 50) < 35]
            
            # 计算平均评分
            avg_score = sum(r.get("pattern_score", 0) for r in results) / len(results) if results else 0
            
            summary = {
                "total": len(results),
                "strong": len(strong),
                "watch": len(watch),
                "danger": len(danger),
                "oversold": len(oversold),
                "avg_score": avg_score,
            }
            
            ctx.set("signal_summary", summary)
            
            return StepResult(
                step_name=self.name,
                status=StepStatus.SUCCESS.value,
                output=summary
            )
        except Exception as e:
            return StepResult(
                step_name=self.name,
                status=StepStatus.FAILED.value,
                error=f"聚合失败: {e}"
            )


class GenerateReportStep(Step):
    """Step 4: 生成报告"""
    
    def __init__(self, output_dir: str = ".", feishu: bool = False):
        super().__init__()
        self.name = "generate_report"
        self.output_dir = output_dir
        self.feishu = feishu
    
    def validate(self) -> bool:
        return True

    def execute(self, ctx: ExecutionContext) -> StepResult:
        try:
            results = ctx.get("etf_analysis", [])
            if not results:
                return StepResult(
                    step_name=self.name,
                    status=StepStatus.FAILED.value,
                    error="无分析结果"
                )
            
            # 生成报告
            beijing_tz = timezone(timedelta(hours=8))
            date_str = datetime.now(beijing_tz).strftime("%Y-%m-%d")
            output_path = os.path.join(self.output_dir, f"portfolio_report_{date_str}.md")
            
            md_content = generate_md_report(results, output_path)
            
            ctx.set("report_path", output_path)
            ctx.set("report_content", md_content)
            
            return StepResult(
                step_name=self.name,
                status=StepStatus.SUCCESS.value,
                output={"path": output_path}
            )
        except Exception as e:
            return StepResult(
                step_name=self.name,
                status=StepStatus.FAILED.value,
                error=f"生成报告失败: {e}"
            )


class FeishuPushStep(Step):
    """Step 5: 飞书推送"""
    
    def __init__(self, report_key: str = "report_path"):
        super().__init__()
        self.name = "feishu_push"
        self.report_key = report_key
    
    def validate(self) -> bool:
        return True

    def execute(self, ctx: ExecutionContext) -> StepResult:
        try:
            from market_monitor.config import FEISHU_WEBHOOK
            import requests
            
            if not FEISHU_WEBHOOK:
                return StepResult(
                    step_name=self.name,
                    status=StepStatus.SKIPPED.value,
                    error="飞书 Webhook 未配置"
                )
            
            report_path = ctx.get(self.report_key)
            if not report_path or not os.path.exists(report_path):
                return StepResult(
                    step_name=self.name,
                    status=StepStatus.SKIPPED.value,
                    error="报告文件不存在"
                )
            
            with open(report_path, 'r', encoding='utf-8') as f:
                md_content = f.read()
            
            # 限制长度
            max_len = 4000
            if len(md_content) > max_len:
                md_content = md_content[:max_len] + "\n\n...（内容过长，已截断）"
            
            # 构建卡片
            payload = {
                "msg_type": "interactive",
                "card": {
                    "config": {"wide_screen_mode": True},
                    "header": {
                        "title": {"tag": "plain_text", "content": "📊 持仓分析报告"},
                        "template": "blue"
                    },
                    "elements": [
                        {"tag": "div", "text": {"tag": "lark_md", "content": md_content}},
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
                    status=StepStatus.SUCCESS.value,
                    output="报告已发送到飞书"
                )
            else:
                return StepResult(
                    step_name=self.name,
                    status=StepStatus.FAILED.value,
                    error=f"飞书发送失败: {result}"
                )
        except Exception as e:
            return StepResult(
                step_name=self.name,
                status=StepStatus.FAILED.value,
                error=f"飞书推送失败: {e}"
            )


class TerminalOutputStep(Step):
    """Step 6: 终端输出"""
    
    def __init__(self):
        super().__init__()
        self.name = "terminal_output"
    
    def validate(self) -> bool:
        return True

    def execute(self, ctx: ExecutionContext) -> StepResult:
        try:
            summary = ctx.get("signal_summary", {})
            
            lines = []
            lines.append("\n" + "=" * 50)
            lines.append("📊 持仓分析汇总")
            lines.append("=" * 50)
            lines.append(f"总持仓: {summary.get('total', 0)} 只")
            lines.append(f"平均评分: {summary.get('avg_score', 0):.0f}/100")
            lines.append(f"🟢 强势: {summary.get('strong', 0)} 只")
            lines.append(f"🟡 观望: {summary.get('watch', 0)} 只")
            lines.append(f"🔴 危险: {summary.get('danger', 0)} 只")
            lines.append(f"💡 超跌: {summary.get('oversold', 0)} 只")
            
            # 操作建议
            strong = ctx.get("etf_analysis", [])
            if summary.get('strong', 0) > 0:
                lines.append("\n【强势持仓】")
                for r in [x for x in strong if x.get("signal") == "STRONG"][:3]:
                    lines.append(f"  {r.get('etf_name')}: {r.get('line_position', '')}")
            
            print("\n".join(lines))
            
            return StepResult(
                step_name=self.name,
                status=StepStatus.SUCCESS.value,
                output="终端输出完成"
            )
        except Exception as e:
            return StepResult(
                step_name=self.name,
                status=StepStatus.FAILED.value,
                error=f"输出失败: {e}"
            )


# ── Harness 工厂 ───────────────────────────────────────────────────────────────

def create_portfolio_harness(
    positions_file: str = "./positions.json",
    output_dir: str = ".",
    feishu: bool = False
) -> Harness:
    """创建持仓分析 Harness"""
    harness = Harness(name="portfolio_analysis")
    
    # 添加步骤
    harness.add_step(LoadPositionsStep(positions_file=positions_file))
    harness.add_step(AnalyzeETFStep())
    harness.add_step(AggregateSignalStep())
    harness.add_step(TerminalOutputStep())
    harness.add_step(GenerateReportStep(output_dir=output_dir))
    
    if feishu:
        harness.add_step(FeishuPushStep())
    
    return harness


def run_portfolio_analysis(
    positions_file: str = "./positions.json",
    output_dir: str = ".",
    feishu: bool = False
) -> ExecutionContext:
    """运行持仓分析"""
    harness = create_portfolio_harness(
        positions_file=positions_file,
        output_dir=output_dir,
        feishu=feishu
    )
    
    print(f"\n{'='*50}")
    print(f"📊 持仓分析 Harness")
    print(f"{'='*50}\n")
    
    context = harness.execute()
    
    # 打印执行摘要
    print(f"\n{'='*50}")
    print(f"✅ 执行完成")
    print(f"{'='*50}")
    
    return context


# ── CLI 入口 ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="持仓分析 Harness")
    parser.add_argument("--positions", "-p", default="./positions.json",
                       help="持仓文件路径")
    parser.add_argument("--output", "-o", default=".",
                       help="输出目录")
    parser.add_argument("--feishu", "-f", action="store_true",
                       help="启用飞书推送")
    
    args = parser.parse_args()
    
    context = run_portfolio_analysis(
        positions_file=args.positions,
        output_dir=args.output,
        feishu=args.feishu
    )
