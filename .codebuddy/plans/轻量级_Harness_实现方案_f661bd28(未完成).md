---
name: 轻量级 Harness 实现方案
overview: 为 stock-signal 项目设计轻量级 Harness 框架，统一编排 dividend_monitor 和 market_monitor 的执行流程，集成现有的 Self-Improvement 系统和 Rule 系统
todos:
  - id: design-core-interfaces
    content: 设计 Harness 核心接口（Harness, Context, Step, Executor）
    status: pending
  - id: implement-core-engine
    content: 实现 Harness 核心引擎和上下文管理
    status: pending
    dependencies:
      - design-core-interfaces
  - id: implement-step-base
    content: 实现 Step 抽象基类和注册表
    status: pending
    dependencies:
      - design-core-interfaces
  - id: implement-executor
    content: 实现串行执行器和错误处理策略
    status: pending
    dependencies:
      - implement-core-engine
  - id: implement-memory-bridge
    content: 实现与 .learnings/ 的 MemoryBridge
    status: pending
    dependencies:
      - implement-core-engine
  - id: implement-rule-engine
    content: 实现与 .codebuddy/rules/ 的 RuleEngine
    status: pending
    dependencies:
      - implement-core-engine
  - id: implement-learning-bridge
    content: 实现与 Self-Improvement 的 LearningBridge
    status: pending
    dependencies:
      - implement-core-engine
      - implement-memory-bridge
  - id: implement-predefined-steps
    content: 实现预定义 Steps（DataFetch, Analysis, Report）
    status: pending
    dependencies:
      - implement-step-base
  - id: implement-dividend-adapter
    content: 实现 dividend_monitor 适配器
    status: pending
    dependencies:
      - implement-predefined-steps
      - implement-learning-bridge
  - id: implement-market-adapter
    content: 实现 market_monitor 适配器
    status: pending
    dependencies:
      - implement-predefined-steps
      - implement-learning-bridge
  - id: test-harness
    content: 测试 Harness 框架与现有模块集成
    status: pending
    dependencies:
      - implement-dividend-adapter
      - implement-market-adapter
  - id: add-documentation
    content: 编写 Harness 使用文档和示例
    status: pending
    dependencies:
      - test-harness
---

## 产品概述

为 stock-signal 项目设计并实现一个轻量级 Harness 框架，用于统一编排 dividend_monitor 和 market_monitor 的执行流程。

## 核心功能

1. **统一执行编排**: 将硬编码的执行流程抽象为可配置的 Step 链
2. **步骤抽象与复用**: 定义 Step 基类，支持数据采集、分析、报告等通用步骤
3. **执行上下文管理**: 管理步骤间的数据传递和状态共享
4. **与现有系统集成**: 

- 与 `.learnings/` Memory 系统桥接
- 与 `.codebuddy/rules/` Rule 系统集成
- 与 `tools/self_improvement_integration.py` Self-Improvement 系统协作

5. **错误处理与恢复**: 统一的错误捕获、重试、降级机制
6. **可观测性**: 执行日志、性能监控、状态追踪

## 设计约束

- 轻量级实现，不引入外部依赖
- 兼容现有代码，通过适配层集成
- 支持渐进式迁移，可先在一个模块试点

## 技术栈

- **语言**: Python 3.9+
- **依赖**: 仅使用标准库和项目现有依赖（typing, dataclasses, pathlib, datetime 等）
- **架构**: 分层架构（核心引擎层、步骤抽象层、适配层）

## 实现方案

### 1. 核心架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                    Harness 核心架构                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Application Layer (应用层)                          │   │
│  │  • dividend_monitor/main.py (适配后)                 │   │
│  │  • market_monitor/main.py (适配后)                   │   │
│  │  • 新的监控模块...                                   │   │
│  └──────────────────────┬──────────────────────────────┘   │
│                         │                                   │
│  ┌──────────────────────▼──────────────────────────────┐   │
│  │  Harness Core (编排层)                               │   │
│  │  • Harness: 主引擎，管理执行流程                     │   │
│  │  • Executor: 执行器（串行/并行）                     │   │
│  │  • Context: 执行上下文，状态共享                     │   │
│  │  • Step: 步骤抽象基类                                │   │
│  └──────────────────────┬──────────────────────────────┘   │
│                         │                                   │
│  ┌──────────────────────▼──────────────────────────────┐   │
│  │  Integration Layer (集成层)                          │   │
│  │  • MemoryBridge: 连接 .learnings/                   │   │
│  │  • RuleEngine: 执行 .codebuddy/rules/               │   │
│  │  • LearningBridge: 连接 Self-Improvement            │   │
│  └──────────────────────┬──────────────────────────────┘   │
│                         │                                   │
│  ┌──────────────────────▼──────────────────────────────┐   │
│  │  Step Registry (步骤层)                              │   │
│  │  • DataFetchStep: 数据采集步骤                       │   │
│  │  • AnalysisStep: 分析计算步骤                        │   │
│  │  • ReportStep: 报告生成步骤                          │   │
│  │  • 自定义业务步骤...                                 │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2. 核心组件设计

#### Harness 引擎 (core.py)

- 管理 Step 注册表
- 协调执行流程
- 处理全局错误
- 维护执行状态

#### 执行上下文 (context.py)

- 步骤间数据传递
- 执行状态追踪
- 元数据管理

#### Step 抽象 (step.py)

- 统一的 execute() 接口
- 前置/后置钩子
- 错误处理策略
- 重试机制

#### 执行器 (executor.py)

- 串行执行（默认）
- 并行执行支持（未来扩展）
- 超时控制

### 3. 与现有系统集成

#### MemoryBridge (memory_bridge.py)

```python
# 读取 .learnings/LEARNINGS.md 和 ERRORS.md
# 提供 get_learnings(), log_execution() 等方法
```

#### RuleEngine (rule_engine.py)

```python
# 读取 .codebuddy/rules/project.md
# 提供 validate(), get_rule() 等方法
```

#### LearningBridge (learning_bridge.py)

```python
# 连接 tools/self_improvement_integration.py
# 自动记录执行错误和学习点
```

### 4. 目录结构

```
tools/harness/
├── __init__.py              # 主入口，导出核心类
├── core.py                  # Harness 引擎
├── context.py               # 执行上下文
├── step.py                  # Step 抽象基类
├── executor.py              # 执行器
├── registry.py              # Step 注册表
├── memory_bridge.py         # Memory 系统桥接
├── rule_engine.py           # Rule 引擎
├── learning_bridge.py       # Self-Improvement 桥接
├── steps/                   # 预定义 Steps
│   ├── __init__.py
│   ├── base.py              # 基础 Step 实现
│   ├── data_fetch.py        # 数据采集 Steps
│   ├── analysis.py          # 分析 Steps
│   └── report.py            # 报告 Steps
└── adapters/                # 现有模块适配器
    ├── __init__.py
    ├── dividend_adapter.py  # dividend_monitor 适配
    └── market_adapter.py    # market_monitor 适配
```

### 5. 关键技术决策

| 决策点 | 选择 | 理由 |
| --- | --- | --- |
| 执行模式 | 串行优先 | 金融数据依赖关系强，串行更可控 |
| 错误处理 | 策略模式 | 支持重试、降级、终止等多种策略 |
| 状态持久化 | 内存 + 可选文件 | 默认内存，支持断点恢复时持久化 |
| 配置方式 | Python 代码 | 与现有项目风格一致，无需引入配置解析 |
| 日志集成 | 与 Self-Improvement 桥接 | 复用现有学习系统 |


### 6. 性能考虑

- **低开销**: 纯 Python 实现，无额外依赖
- **惰性加载**: Step 和适配器按需加载
- **缓存友好**: 与现有 valuation_cache.json 兼容
- **超时控制**: 每个 Step 可配置超时时间

## Agent Extensions

### Skill

- **self-improving-agent**: 用于在 Harness 执行过程中自动记录错误和学习点，与现有 Self-Improvement 系统集成
- Purpose: 在 Step 执行失败时自动记录到 .learnings/ERRORS.md
- Expected outcome: 形成执行错误到学习系统的闭环

### SubAgent

- **code-explorer**: 用于在实现过程中探索现有代码库，理解 dividend_monitor 和 market_monitor 的具体实现细节
- Purpose: 分析现有模块的执行流程，设计适配层
- Expected outcome: 准确理解现有代码，设计兼容的适配器