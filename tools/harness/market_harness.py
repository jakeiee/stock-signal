"""
Harness 适配层 - market_monitor

使用 Harness 框架重写的股市交易分析监控执行流程。

执行流程：
  Step 1  采集资金面数据（新开户数 / 融资融券 / 成交额 / 北向资金）
  Step 2  采集基本面数据（GDP / CPI / PPI / PMI / M2）
  Step 3  采集政策面数据
  Step 4  采集全球市场数据（美股 / 商品 / 外汇 / 亚太）
  Step 5  采集估值数据
  Step 6  聚合信号，生成报告
  Step 7  终端输出
  Step 8  飞书推送（可选）
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
import traceback

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tools.harness import Harness, Step, StepConfig, ExecutionContext


class FetchCapitalDataStep(Step):
    """
    Step 1: 采集资金面数据

    包括：指南针活跃市值、新开户数、两融数据、成交额、北向资金
    """

    name = "fetch_capital_data"

    def __init__(
        self,
        znz_override: Optional[Dict] = None,
        new_accounts_override: Optional[float] = None,
        margin_override: Optional[Dict] = None,
        config: Optional[StepConfig] = None,
    ):
        super().__init__(config)
        self.znz_override = znz_override
        self.new_accounts_override = new_accounts_override
        self.margin_override = margin_override
        self.data_key = self.config.metadata.get("data_key", "capital_data")

    def validate(self) -> bool:
        return True

    def execute(self, context: ExecutionContext) -> Dict[str, Any]:
        """采集资金面数据"""
        from market_monitor.data_sources import capital

        context.info("采集资金面数据...")

        # 1.1 指南针活跃市值
        if self.znz_override:
            context.info(f"使用手动录入的指南针数据: {self.znz_override}")
            capital.save_znz_active_cap(**self.znz_override)

        znz_result = capital.fetch_znz_active_cap()

        # 1.2 新开户数
        na_result = capital.fetch_new_accounts(override=self.new_accounts_override)

        # 1.3 两融数据
        mg_result = capital.fetch_margin(override=self.margin_override)

        # 1.4 成交额
        turnover_result = capital.fetch_turnover()

        # 1.5 北向资金
        northbound_result = capital.fetch_northbound()

        data = {
            "znz_active_cap": znz_result,
            "new_accounts": na_result,
            "margin": mg_result,
            "turnover": turnover_result,
            "northbound": northbound_result,
        }

        context.set(self.data_key, data)

        # 提取关键指标用于日志
        if "error" not in znz_result:
            context.info(f"指南针活跃市值: {znz_result.get('active_cap', 0):,.0f}亿")

        if "error" not in na_result:
            context.info(f"新开户数: {na_result.get('new_accounts', 0):,.0f}万户")

        return data


class FetchFundamentalDataStep(Step):
    """
    Step 2: 采集基本面数据

    包括：GDP、人均收入、CPI/PPI/PMI、M2/国债收益率
    """

    name = "fetch_fundamental_data"

    def __init__(self, config: Optional[StepConfig] = None):
        super().__init__(config)
        self.data_key = self.config.metadata.get("data_key", "fundamental_data")

    def validate(self) -> bool:
        return True

    def execute(self, context: ExecutionContext) -> Dict[str, Any]:
        """采集基本面数据"""
        from market_monitor.data_sources import fundamental as fundamental_mod
        from market_monitor.data_sources.pmi_interpretation import fetch_pmi_with_interpretation
        from market_monitor.data_sources.cpi_ppi_interpretation import fetch_cpi_ppi_with_interpretation
        from market_monitor.data_sources.gdp_interpretation import fetch_gdp_with_interpretation
        from market_monitor.data_sources.income_interpretation import fetch_income_with_interpretation

        context.info("采集基本面数据...")

        # 2.1 GDP
        gdp_result = fundamental_mod.fetch_gdp()
        context.info(f"GDP: {gdp_result.get('gdp_yoy', 'N/A')}%")

        # 2.2 人均收入
        di_result = fundamental_mod.fetch_disposable_income()

        # 2.3 CPI/PPI/PMI
        sd_result = fundamental_mod.fetch_macro_supply_demand()
        context.info(f"CPI: {sd_result.get('cpi_yoy', 'N/A')}%, PPI: {sd_result.get('ppi_yoy', 'N/A')}%, PMI: {sd_result.get('pmi_mfg', 'N/A')}")

        # 2.4 M2/国债
        liq_result = fundamental_mod.fetch_macro_liquidity()

        # 2.5 官方解读
        pmi_interp = fetch_pmi_with_interpretation()
        cpi_ppi_interp = fetch_cpi_ppi_with_interpretation()
        gdp_interp = fetch_gdp_with_interpretation()
        income_interp = fetch_income_with_interpretation()

        data = {
            "gdp": gdp_result,
            "disposable_income": di_result,
            "supply_demand": sd_result,
            "liquidity": liq_result,
            "pmi_interpretation": pmi_interp if "error" not in pmi_interp else None,
            "cpi_ppi_interpretation": cpi_ppi_interp if "error" not in cpi_ppi_interp else None,
            "gdp_interpretation": gdp_interp if "error" not in gdp_interp else None,
            "income_interpretation": income_interp if "error" not in income_interp else None,
        }

        context.set(self.data_key, data)
        return data


class FetchPolicyDataStep(Step):
    """
    Step 3: 采集政策面数据
    """

    name = "fetch_policy_data"

    def __init__(self, config: Optional[StepConfig] = None):
        super().__init__(config)
        self.data_key = self.config.metadata.get("data_key", "policy_data")

    def validate(self) -> bool:
        return True

    def execute(self, context: ExecutionContext) -> Dict[str, Any]:
        """采集政策面数据"""
        from market_monitor.data_sources import policy

        context.info("采集政策面数据...")

        data = policy.fetch_policy_events()
        context.set(self.data_key, data)
        return data


class FetchGlobalMarketDataStep(Step):
    """
    Step 4: 采集全球市场数据

    包括：美股指数、七巨头估值、大宗商品、外汇、亚太市场、港科技估值
    """

    name = "fetch_global_market_data"

    def __init__(self, config: Optional[StepConfig] = None):
        super().__init__(config)
        self.data_key = self.config.metadata.get("data_key", "global_data")

    def validate(self) -> bool:
        return True

    def execute(self, context: ExecutionContext) -> Dict[str, Any]:
        """采集全球市场数据"""
        from market_monitor.data_sources import global_mkt

        context.info("采集全球市场数据...")

        # 4.1 美股指数
        us_result = global_mkt.fetch_us_market()
        context.info(f"美股 - 道指: {us_result.get('DJIA', {}).get('price', 'N/A')}")

        # 4.2 七巨头估值
        mags_result = global_mkt.fetch_mags_valuation()
        if "error" not in mags_result:
            context.info(f"七巨头 PE: {mags_result.get('pe', 'N/A')}")

        # 4.3 大宗商品
        commod_result = global_mkt.fetch_commodities()

        # 4.4 外汇
        forex_result = global_mkt.fetch_forex()

        # 4.5 亚太市场
        asia_result = global_mkt.fetch_asia_market()

        # 4.6 港科技估值
        techk_result = global_mkt.fetch_techk_valuation()
        if "error" not in techk_result:
            context.info(f"港科技 PE: {techk_result.get('pe', 'N/A')}")

        data = {
            "us_market": us_result,
            "mags_valuation": mags_result,
            "commodities": commod_result,
            "forex": forex_result,
            "asia_market": asia_result,
            "techk_valuation": techk_result,
        }

        context.set(self.data_key, data)
        return data


class FetchValuationDataStep(Step):
    """
    Step 5: 采集估值数据
    """

    name = "fetch_valuation_data"

    def __init__(self, config: Optional[StepConfig] = None):
        super().__init__(config)
        self.data_key = self.config.metadata.get("data_key", "valuation_data")

    def validate(self) -> bool:
        return True

    def execute(self, context: ExecutionContext) -> Dict[str, Any]:
        """采集估值数据"""
        from market_monitor.data_sources import valuation

        context.info("采集估值数据...")

        data = valuation.fetch_market_valuation()
        context.set(self.data_key, data)
        return data


class AggregateSignalStep(Step):
    """
    Step 6: 聚合信号，生成报告数据
    """

    name = "aggregate_signal"

    def __init__(self, config: Optional[StepConfig] = None):
        super().__init__(config)
        self.output_key = self.config.metadata.get("output_key", "report_data")

    def validate(self) -> bool:
        return True

    def execute(self, context: ExecutionContext) -> Dict[str, Any]:
        """聚合信号"""
        from market_monitor.analysis import signal as signal_mod

        context.info("聚合信号...")

        capital_data = context.get("capital_data", {})
        fundamental_data = context.get("fundamental_data", {})
        valuation_data = context.get("valuation_data", {})
        policy_data = context.get("policy_data", {})
        global_data = context.get("global_data", {})

        data = signal_mod.build_report(
            capital_data=capital_data,
            fundamental_data=fundamental_data,
            valuation_data=valuation_data,
            policy_data=policy_data,
            global_data=global_data,
        )

        context.set(self.output_key, data)
        return data


class TerminalOutputStep(Step):
    """
    Step 7: 终端输出报告
    """

    name = "terminal_output"

    def __init__(self, config: Optional[StepConfig] = None):
        super().__init__(config)

    def validate(self) -> bool:
        return True

    def execute(self, context: ExecutionContext) -> None:
        """终端输出"""
        from market_monitor.report import terminal

        context.info("输出报告到终端...")

        report_data = context.get("report_data", {})
        terminal.print_report(report_data)


class FeishuPushStep(Step):
    """
    Step 8: 飞书推送（可选）
    """

    name = "feishu_push"

    def __init__(self, enabled: bool = False, config: Optional[StepConfig] = None):
        super().__init__(config)
        self.enabled = enabled

    def validate(self) -> bool:
        return True

    def can_skip(self, context_data: Dict[str, Any]) -> bool:
        """如果未启用则跳过"""
        return not self.enabled

    def execute(self, context: ExecutionContext) -> bool:
        """发送飞书消息"""
        from market_monitor.report import feishu as feishu_mod

        context.info("推送飞书消息...")

        report_data = context.get("report_data", {})
        cards = feishu_mod.build_cards(report_data)
        ok = feishu_mod.send_cards(cards)

        if ok:
            context.info("飞书消息发送成功")
        else:
            context.warning("飞书消息发送失败")

        return ok


class MacroReportStep(Step):
    """
    Step 9: 生成宏观交易分析报告（HTML）
    """

    name = "macro_report"

    def __init__(
        self,
        enabled: bool = False,
        output_dir: Optional[str] = None,
        config: Optional[StepConfig] = None,
    ):
        super().__init__(config)
        self.enabled = enabled
        self.output_dir = output_dir or "/Users/liuyi/WorkBuddy/stock-signal/market_monitor/data"

    def validate(self) -> bool:
        return True

    def can_skip(self, context_data: Dict[str, Any]) -> bool:
        """如果未启用则跳过"""
        return not self.enabled

    def execute(self, context: ExecutionContext) -> str:
        """生成宏观报告"""
        from market_monitor.report import macro_report

        context.info("生成宏观交易分析报告...")

        capital_data = context.get("capital_data", {})
        fundamental_data = context.get("fundamental_data", {})
        valuation_data = context.get("valuation_data", {})
        policy_data = context.get("policy_data", {})
        global_data = context.get("global_data", {})

        html_path = macro_report.generate_and_save(
            capital_data=capital_data,
            fundamental_data=fundamental_data,
            valuation_data=valuation_data,
            policy_data=policy_data,
            global_data=global_data,
        )

        context.info(f"宏观报告已保存: {html_path}")
        context.set("macro_report_path", html_path)

        return html_path


def create_market_harness(
    feishu: bool = False,
    macro: bool = False,
    znz_override: Optional[Dict] = None,
    new_accounts_override: Optional[float] = None,
    margin_override: Optional[Dict] = None,
) -> Harness:
    """
    创建市场监控 Harness

    Args:
        feishu: 是否启用飞书推送
        macro: 是否生成宏观交易分析报告
        znz_override: 指南针数据手动覆盖
        new_accounts_override: 新开户数手动覆盖
        margin_override: 两融数据手动覆盖

    Returns:
        配置好的 Harness 实例
    """
    harness = Harness(
        name="market_monitor",
        config={
            "description": "股市交易分析监控",
            "feishu": feishu,
            "macro": macro,
        },
    )

    # Step 1: 资金面
    harness.add_step(FetchCapitalDataStep(
        znz_override=znz_override,
        new_accounts_override=new_accounts_override,
        margin_override=margin_override,
        config=StepConfig(
            metadata={"data_key": "capital_data", "description": "资金面数据"}
        )
    ))

    # Step 2: 基本面
    harness.add_step(FetchFundamentalDataStep(
        config=StepConfig(
            metadata={"data_key": "fundamental_data", "description": "基本面数据"}
        )
    ))

    # Step 3: 政策面
    harness.add_step(FetchPolicyDataStep(
        config=StepConfig(
            metadata={"data_key": "policy_data", "description": "政策面数据"}
        )
    ))

    # Step 4: 全球市场
    harness.add_step(FetchGlobalMarketDataStep(
        config=StepConfig(
            metadata={"data_key": "global_data", "description": "全球市场数据"}
        )
    ))

    # Step 5: 估值数据
    harness.add_step(FetchValuationDataStep(
        config=StepConfig(
            metadata={"data_key": "valuation_data", "description": "市场估值数据"}
        )
    ))

    # Step 6: 聚合信号
    harness.add_step(AggregateSignalStep(
        config=StepConfig(
            metadata={"output_key": "report_data", "description": "聚合信号生成报告"}
        )
    ))

    # Step 7: 终端输出
    harness.add_step(TerminalOutputStep(
        config=StepConfig(
            metadata={"description": "终端输出"}
        )
    ))

    # Step 8: 飞书推送（可选）
    harness.add_step(FeishuPushStep(
        enabled=feishu,
        config=StepConfig(
            metadata={"description": "飞书推送"}
        )
    ))

    # Step 9: 宏观报告（可选）
    harness.add_step(MacroReportStep(
        enabled=macro,
        output_dir="/Users/liuyi/WorkBuddy/stock-signal/market_monitor/data",
        config=StepConfig(
            metadata={"description": "宏观交易分析报告"}
        )
    ))

    return harness


def run_market_monitor(
    feishu: bool = False,
    macro: bool = False,
    znz_override: Optional[Dict] = None,
    new_accounts_override: Optional[float] = None,
    margin_override: Optional[Dict] = None,
) -> ExecutionContext:
    """
    运行市场监控

    Args:
        feishu: 是否启用飞书推送
        macro: 是否生成宏观交易分析报告
        znz_override: 指南针数据手动覆盖
        new_accounts_override: 新开户数手动覆盖
        margin_override: 两融数据手动覆盖

    Returns:
        执行上下文
    """
    harness = create_market_harness(
        feishu=feishu,
        macro=macro,
        znz_override=znz_override,
        new_accounts_override=new_accounts_override,
        margin_override=margin_override,
    )

    # 打印执行计划
    print("\n📋 市场监控执行计划:")
    for i, step in enumerate(harness.steps, 1):
        print(f"  {i}. {step.name}")

    print("\n⏳ 开始执行...\n")

    # 执行
    context = harness.execute()

    # 输出摘要
    print("\n" + "=" * 50)
    print("📊 执行摘要")
    print("=" * 50)
    print(f"  状态: {'✅ 成功' if context.status.value == 'completed' else '❌ 失败'}")
    print(f"  耗时: {context.duration:.2f}秒")
    print(f"  总步骤: {len(context.step_results)}")
    print(f"  成功: {sum(1 for r in context.step_results.values() if r.status == 'success')}")
    print(f"  失败: {sum(1 for r in context.step_results.values() if r.status == 'failed')}")
    print(f"  跳过: {sum(1 for r in context.step_results.values() if r.status == 'skipped')}")

    if context.get("macro_report_path"):
        print(f"\n📄 宏观报告: {context.get('macro_report_path')}")

    return context


def _parse_args() -> dict:
    """解析命令行参数"""
    args = sys.argv[1:]
    cfg = {
        "feishu": False,
        "macro": False,
        "new_accounts": None,
        "margin_override": None,
        "znz_override": None,
    }

    i = 0
    while i < len(args):
        if args[i] == "--feishu":
            cfg["feishu"] = True
        elif args[i] == "--macro":
            cfg["macro"] = True
        elif args[i] == "--new-accounts" and i + 1 < len(args):
            try:
                cfg["new_accounts"] = float(args[i + 1])
            except ValueError:
                pass
            i += 1
        elif args[i] == "--znz" and i + 1 < len(args):
            try:
                parts = [p.strip() for p in args[i + 1].split(",")]
                if len(parts) >= 2:
                    cfg["znz_override"] = {
                        "date": parts[0],
                        "active_cap": float(parts[1]),
                    }
                    if len(parts) >= 3:
                        cfg["znz_override"]["chg_pct"] = float(parts[2])
            except Exception:
                pass
            i += 1
        i += 1

    return cfg


if __name__ == "__main__":
    cfg = _parse_args()

    run_market_monitor(
        feishu=cfg["feishu"],
        macro=cfg["macro"],
        znz_override=cfg.get("znz_override"),
        new_accounts_override=cfg.get("new_accounts"),
        margin_override=cfg.get("margin_override"),
    )
