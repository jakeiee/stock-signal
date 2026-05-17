# 项目架构规则

## 核心架构概述

本项目由**三大核心模块**组成，后续可能新增：

```
stock-signal/
├── dividend_monitor/     # 模块1: 红利指数监控
├── market_monitor/       # 模块2: 市场监控
│   └── report/          #   └── 持仓分析（子模块）
└── tools/               # 公共工具层
    └── harness/         #   └── 模块编排框架
```

---

## 模块1: dividend_monitor（红利指数监控）

### 职责
监控红利指数的估值、分红数据，生成投资建议。

### 核心功能
- 指数估值分析（PE/PB/股息率百分位）
- KDJ技术指标分析（日线+周线）
- 动态仓位建议（基于估值+技术面）
- 飞书报告推送

### 运行方式
```bash
# 终端输出
python3 -m dividend_monitor

# 终端输出 + 飞书推送
python3 -m dividend_monitor --feishu
```

### 关键文件
- `dividend_monitor/main.py` - 主入口
- `dividend_monitor/analysis/` - 分析逻辑
- `dividend_monitor/report/feishu.py` - 飞书推送
- `dividend_monitor/send_dividend_report_to_feishu.py` - 独立发送脚本

### 数据源
- 指数估值：Wind APP → 妙想API
- 无风险利率：东财实时 → 东财历史 → 保底1.70%
- KDJ指标：中证官网自算 → 妙想API

---

## 模块2: market_monitor（市场监控）

### 职责
监控全市场资金面、基本面、政策面、全球市场，生成综合信号。

### 核心功能
- 资金面监控（成交额、融资融券、北向资金）
- 基本面监控（全市场PE/PB/股息率）
- 政策面监控（货币政策、财政政策）
- 全球市场监控（美股、VIX、原油、黄金）
- **持仓分析**（子模块，见下文）

### 运行方式
```bash
# 终端输出
python3 -m market_monitor

# 终端输出 + 飞书推送
python3 -m market_monitor --feishu

# 生成宏观分析报告（HTML）
python3 -m market_monitor --macro
```

### 关键文件
- `market_monitor/main.py` - 主入口
- `market_monitor/data_sources/` - 数据采集
- `market_monitor/analysis/` - 信号分析
- `market_monitor/report/` - 报告生成

### 数据源
- 全市场估值：万得Wind API → CSV缓存
- 资金面：东方财富接口
- 全球市场：Yahoo Finance / 公开API

---

## 子模块: 持仓分析（在 market_monitor/report/ 下）

### 职责
分析持仓ETF的技术指标和趋势信号，生成持仓报告。

### 核心功能
- ETF技术指标分析（MA、KDJ、MACD、RSI、布林带）
- 知行趋势线信号判断（强势/观望/危险）
- 多维度评分和对比
- 飞书报告推送（支持Markdown和卡片）

### 运行方式

#### 方式: 使用 portfolio_professional.py（专业分析）
```bash
# 生成专业报告
python3 market_monitor/report/portfolio_professional.py

# 生成报告 + 飞书推送
python3 market_monitor/report/portfolio_professional.py --feishu
```

### 关键文件
- `market_monitor/report/portfolio_professional.py` - 专业分析（核心）
- `data/positions.json` - 持仓配置文件

### 数据源
- ETF行情和技术指标：xalpha
- 指数映射表：`market_monitor/data/etf_index_mapping.csv`

---

## 仓位管理规则（持仓分析核心逻辑）

### 核心公式

```
目标仓位 = 基础仓位 × 估值调整系数 × 趋势系数 × 活跃市值系数
```

### 系数体系

| 系数 | 数据来源 | 档位说明 |
|:---|:---|:---|
| **基础仓位** | 市场配置 | A股40%、港股30%、美股25% |
| **估值调整系数** | PE/PB百分位 | 极度低估1.5 → 极度偏高0.4 |
| **趋势系数** | 知行信号 | 买入1.2、观望1.0、卖出0.7 |
| **活跃市值系数** | A股专用 | 多头1.2、中性1.0、空头0.7 |

### 估值调整系数详情

| 百分位区间 | 估值水平 | 调整系数 | 操作建议 |
|:---|:---|:---|:---|
| < 20% | 极度低估 | **1.5** | 强烈加仓 |
| 20-40% | 低估 | **1.2** | 适度加仓 |
| 40-60% | 合理 | **1.0** | 保持仓位 |
| 60-80% | 偏高 | **0.7** | 适度减仓 |
| > 80% | 极度偏高 | **0.4** | 强烈减仓 |

### 趋势系数详情

| 知行信号 | 调整系数 | 说明 |
|:---|:---|:---|
| 买入 | **1.2** | 强烈看多 |
| 观望 | **1.0** | 中性观望 |
| 卖出 | **0.7** | 看空减仓 |

### 活跃市值系数详情（仅A股）

| 信号 | 调整系数 | 说明 |
|:---|:---|:---|
| 多头(bullish) | **1.2** | 大市值主导，流动性好 |
| 中性(neutral) | **1.0** | 中性区间 |
| 空头(bearish) | **0.7** | 小市值主导 |

### 止损规则

| 亏损幅度 | 执行动作 |
|:---|:---|
| > 5% | 预警观察 |
| > 10% | 减仓50% |
| > 15% | 强制止损 |
| > 20% | 完全离场 |

### 定投补仓规则

| 亏损幅度 | 加仓比例 |
|:---|:---|
| > 5% | +20% |
| > 10% | +33% |
| > 15% | +50% |
| > 20% | +100% |
| > 30% | +150% |

### 关键文件

- `market_monitor/analysis/position_manager.py` - 仓位管理器核心实现

### 更新记录

- 2026-05-05: 活跃市值系数调整为 多头1.2 / 中性1.0 / 空头0.7

---

## 公共工具层: tools/harness/

### 职责
提供模块编排框架，实现步骤化执行、错误处理、上下文管理。

### 核心组件
- `core.py` - Harness基类
- `context.py` - 执行上下文
- `step.py` - 步骤基类
- `dividend_harness.py` - 红利监控Harness
- `market_harness.py` - 市场监控Harness

### 使用方式
```python
from tools.harness.market_harness import create_market_harness

# 创建Harness
harness = create_market_harness(feishu=True)

# 执行
context = harness.execute()

# 获取结果
if context.has_error():
    print(f"执行失败: {context.get_errors()}")
else:
    print(f"执行成功: {context.get('report_path')}")
```

---

## 模块对比表

| 特性 | dividend_monitor | market_monitor | 持仓分析 |
|------|------------------|----------------|---------|
| **职责** | 红利指数监控 | 市场整体监控 | ETF持仓分析 |
| **位置** | `dividend_monitor/` | `market_monitor/` | `market_monitor/report/` |
| **飞书推送** | `--feishu` | `--feishu` | `--feishu` |
| **数据源** | Wind/妙想/东财 | Wind/东财/Yahoo | xalpha |
| **核心输出** | 估值+仓位建议 | 综合信号 | 技术指标+趋势信号 |
| **Harness** | `dividend_harness` | `market_harness` | - |

---

## 重要提示

### 1. 持仓分析不是独立模块
持仓分析是 **market_monitor 的子模块**，位于 `market_monitor/report/` 目录下。

### 2. 飞书推送频率限制
飞书机器人有频率限制（通常每分钟最多20条消息），发送失败时会提示 `11232 frequency limited`。

### 3. 数据源优先级
所有模块都遵循统一的数据源优先级策略：
```
主数据源 → 备用数据源 → 本地缓存 → 保底值
```

### 4. 模块扩展规范
新增模块时，必须：
1. 实现 `BaseModule` 接口（在 `tools/harness/module_interface.py`）
2. 创建对应的 Harness 类
3. 支持 `--feishu` 参数
4. 更新本文档

---

## 常见错误和解决方案

### 错误1: ModuleNotFoundError: No module named 'Step'
**原因**：未导入 `Step` 类
**解决**：在模块的 `__init__.py` 中添加：
```python
from tools.harness.module_interface import BaseModule, ModuleMetadata, Step
```

### 错误2: 飞书推送失败 (11232 frequency limited)
**原因**：发送频率超过限制
**解决**：等待1-2分钟后重试，或批量发送（使用卡片模式）

### 错误3: xalpha 数据获取失败
**原因**：指数代码格式错误
**解决**：检查 `ETF_MAPPING` 中的 `index_code_xalpha` 格式：
- A股中证：`ZZ930601`
- 港股：`HKHSTECH` / `HKHSIII`

---

## 更新记录

- 2026-04-29: 持仓分析模块重构，删除方式1(portfolio_analyzer.py)和方式2(portfolio_harness)，保留方式3(portfolio_professional.py)
- 2026-04-29: 初始版本，明确三大模块架构
