# Stock-Signal Harness 使用指南

## 概述

Harness 是一个轻量级的执行框架，用于统一编排 `dividend_monitor` 和 `market_monitor` 的执行流程。

## 目录结构

```
tools/harness/
├── __init__.py              # 主入口
├── core.py                   # Harness 核心引擎
├── context.py                # 执行上下文管理
├── step.py                   # Step 抽象基类
├── executor.py               # 执行器（串行/并行）
├── memory_bridge.py          # 与 .learnings/ 集成
├── rule_engine.py            # 规则执行引擎
├── registry.py               # Step 注册表
├── dividend_harness.py       # 股息监控适配层
├── market_harness.py         # 市场监控适配层
├── portfolio_harness.py      # 持仓分析适配层
├── selector_harness.py       # 选股适配层
└── steps/                   # 预定义 Steps
    ├── __init__.py
    ├── data_fetch.py         # 数据采集 Steps
    ├── analysis.py           # 分析 Steps
    └── report.py             # 报告 Steps
```

## 快速开始

### 1. 基础使用

```python
from tools.harness import Harness, Step, StepConfig

# 创建 Harness
harness = Harness(name="my_task")

# 添加步骤
harness.add_step(MyCustomStep())

# 执行
context = harness.execute()
```

### 2. 使用预定义 Steps

```python
from tools.harness import Harness
from tools.harness.steps import FetchXalphaDataStep, KDJAnalysisStep

harness = Harness(name="stock_analysis")

# 添加数据获取步骤
harness.add_step(FetchXalphaDataStep(
    index_code="HKHSTECH",
    data_key="price_data"
))

# 添加分析步骤
harness.add_step(KDJAnalysisStep(
    data_key="price_data",
    output_key="kdj_signal"
))

# 执行
context = harness.execute()
```

### 3. 使用函数式 Step

```python
from tools.harness import Step, step

# 使用装饰器
@step(name="fetch_data")
def fetch_data(context):
    data = api_call()
    context.set("api_data", data)
    return data

harness.add_step(fetch_data)
```

## 核心概念

### Step（步骤）

步骤是执行的基本单元：

```python
from tools.harness import Step, StepConfig

class MyStep(Step):
    name = "my_step"

    def validate(self) -> bool:
        return True

    def execute(self, context) -> Any:
        # 业务逻辑
        result = do_something()
        context.set("result", result)
        return result

# 添加重试配置
config = StepConfig(
    max_retries=3,
    retry_delay=1.0,
    timeout=30.0,
    depends_on=["previous_step"],
    skip_if=lambda ctx: ctx.get("skip_flag"),
)
step = MyStep(config=config)
```

### ExecutionContext（执行上下文）

管理执行状态和数据传递：

```python
# 设置数据
context.set("key", value)

# 获取数据
value = context.get("key")

# 检查数据
if context.has("key"):
    ...

# 记录日志
context.info("操作成功")
context.warning("需要注意")
context.error("发生错误")

# 记录步骤结果
result = context.get_step_result("step_name")
```

### Executor（执行器）

支持多种执行策略：

```python
from tools.harness import SerialExecutor, ParallelExecutor

# 串行执行（默认）
harness = Harness(executor=SerialExecutor(stop_on_error=True))

# 并行执行
harness = Harness(executor=ParallelExecutor(max_workers=4))
```

## Hooks

在执行生命周期中添加回调：

```python
harness = Harness(name="my_task")

# 执行前
harness.before_all(lambda ctx: print("开始执行"))

# 步骤开始
harness.on_step_start(lambda step, ctx: print(f"开始: {step.name}"))

# 步骤结束
harness.on_step_end(lambda step, ctx: print(f"结束: {step.name}"))

# 执行后
harness.after_all(lambda ctx: print("执行完成"))

# 错误处理
harness.on_error(lambda err, ctx: print(f"错误: {err}"))
```

## 与现有系统集成

### MemoryBridge（记忆系统）

自动记录到 `.learnings/`：

```python
from tools.harness import Harness
from tools.harness.memory_bridge import MemoryBridge

bridge = MemoryBridge()

harness = Harness(name="my_task")

# 执行后自动记录
context = harness.execute()
bridge.record_execution(context)
```

### RuleEngine（规则引擎）

执行前后的规则检查：

```python
from tools.harness import RuleEngine, rule_name_exists

engine = RuleEngine()
engine.add_rule(rule_name_exists("required_data"))

# 评估规则
results = engine.evaluate_all(context)
```

## 预定义 Steps

### 数据采集

| Step | 说明 |
|------|------|
| `FetchDataStep` | 通用数据获取 |
| `FetchWindDataStep` | Wind 数据 |
| `FetchXalphaDataStep` | xalpha 指数数据 |
| `FetchCSVDataStep` | CSV 文件 |
| `FetchAPIDataStep` | HTTP API |

### 分析

| Step | 说明 |
|------|------|
| `KDJAnalysisStep` | KDJ 指标分析 |
| `MACDAnalysisStep` | MACD 指标分析 |
| `ValuationAnalysisStep` | 估值分析 |

### 报告

| Step | 说明 |
|------|------|
| `ReportStep` | 通用报告生成 |
| `MarkdownReportStep` | Markdown 报告 |
| `FeishuReportStep` | 飞书消息发送 |

## dividend_monitor 示例

```python
from tools.harness.dividend_harness import create_dividend_harness

# 创建 Harness
harness = create_dividend_harness()

# 执行
context = harness.execute()

# 获取结果
recommendation = context.get("position_recommendation")
```

## market_monitor 示例

```python
from tools.harness.market_harness import run_market_monitor

# 运行完整监控
context = run_market_monitor()

# 带参数运行
context = run_market_monitor(
    feishu=True,           # 启用飞书推送
    macro=True,            # 生成宏观报告
    znz_override={"date": "2026-04-18", "active_cap": 186349.4},
)

# 程序化使用
from tools.harness.market_harness import create_market_harness

harness = create_market_harness(feishu=False, macro=False)
context = harness.execute()
```

## portfolio_harness 示例

```python
from tools.harness.portfolio_harness import run_portfolio_analysis

# 基本运行
context = run_portfolio_analysis()

# 发送飞书
context = run_portfolio_analysis(feishu=True)

# 指定持仓文件
context = run_portfolio_analysis(positions_file="./my_positions.json")

# 程序化使用
from tools.harness.portfolio_harness import create_portfolio_harness

harness = create_portfolio_harness(
    positions_file="./positions.json",
    output_dir=".",
    feishu=True
)
context = harness.execute()
```

**执行流程**：
| Step | 说明 |
|------|------|
| `load_positions` | 加载持仓ETF列表 |
| `analyze_etf` | 分析每只ETF技术指标 |
| `aggregate_signal` | 聚合持仓信号 |
| `terminal_output` | 终端输出汇总 |
| `generate_report` | 生成分析报告 |
| `feishu_push` | 飞书推送（可选） |

## selector_harness 示例

```python
from tools.harness.selector_harness import run_stock_selector

# KDJ超卖策略（默认）
context = run_stock_selector(strategy="kdj_oversold")

# 强势策略
context = run_stock_selector(strategy="strong")

# 超跌反弹策略
context = run_stock_selector(strategy="oversold_rebound")

# 发送飞书
context = run_stock_selector(strategy="kdj_oversold", feishu=True)

# 程序化使用
from tools.harness.selector_harness import create_selector_harness

harness = create_selector_harness(
    strategy="kdj_oversold",
    feishu=True,
    max_batch=50
)
context = harness.execute()
```

**内置策略**：
| 策略 | 说明 |
|------|------|
| `kdj_oversold` | KDJ超卖+知行趋势线多头 |
| `strong` | 强势信号+多头排列 |
| `oversold_rebound` | 超跌反弹+上升趋势 |

**执行流程**：
| Step | 说明 |
|------|------|
| `pre_filter` | ETF预筛选（类型/规模/KDJ） |
| `trend_filter` | 知行趋势线二次筛选 |
| `terminal_output` | 终端输出选股结果 |
| `feishu_push` | 飞书推送（可选） |

## CLI 使用

```bash
# 持仓分析
python3 tools/harness/portfolio_harness.py --positions ./positions.json --feishu

# 选股
python3 tools/harness/selector_harness.py --strategy strong --feishu

# 市场监控
python3 tools/harness/market_harness.py --feishu --macro

# 股息监控
python3 tools/harness/dividend_harness.py
```

## 验证和计划

```python
# 验证配置
is_valid, errors = harness.validate()
if not is_valid:
    print("配置错误:", errors)

# 模拟执行（不实际运行）
plan = harness.dry_run()
for p in plan:
    print(f"  {p['name']} -> depends: {p['depends_on']}")
```

## 最佳实践

1. **步骤命名**：使用描述性的步骤名称
2. **错误处理**：配置 `max_retries` 和 `continue_on_error`
3. **日志记录**：在关键步骤添加日志
4. **数据传递**：使用明确的键名
5. **单元测试**：为自定义 Step 编写测试

## 扩展开发

### 创建自定义 Step

```python
class CustomStep(Step):
    name = "custom_step"

    def validate(self) -> bool:
        # 验证配置
        return True

    def execute(self, context) -> Any:
        # 业务逻辑
        pass

    def before_execute(self, context) -> None:
        # 前置处理
        pass

    def after_execute(self, context, output) -> Any:
        # 后置处理
        return output

    def on_error(self, context, error) -> None:
        # 错误处理
        pass
```

### 注册自定义 Step

```python
from tools.harness.registry import register_step

@register_step("my_custom_step")
class MyCustomStep(Step):
    ...
```
