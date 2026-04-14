---
name: stock-signal-enhancement
overview: 为 stock-signal 项目添加板块分析模块和知行趋势线选股指标
todos:
  - id: create-sector-module
    content: 创建 sector.py 板块数据获取模块，支持东方财富/同花顺板块数据
    status: completed
  - id: create-etf-selector
    content: 创建 etf_selector.py 封装东方财富ETF筛选API
    status: completed
  - id: create-zhixing-indicator
    content: 创建 zhixing.py 实现知行趋势线指标计算
    status: completed
  - id: create-position-monitor
    content: 创建 position_monitor.py 持仓监控模块
    status: completed
    dependencies:
      - create-zhixing-indicator
  - id: create-stock-selector
    content: 创建 stock_selector.py ETF初筛+趋势线二次筛选
    status: completed
    dependencies:
      - create-zhixing-indicator
      - create-etf-selector
  - id: integrate-feishu-report
    content: 修改 feishu.py 增加持仓监控和选股建议卡片
    status: completed
    dependencies:
      - create-sector-module
      - create-position-monitor
  - id: integrate-main-entry
    content: 修改 main.py 增加新模块的命令行入口
    status: completed
---

## 产品需求

为 stock-signal 项目增加三个核心功能模块：

### 1. 板块分析模块

- 从东方财富/同花顺获取行业板块和概念板块的涨跌排行、资金流向数据
- 支持按板块筛选和排序
- 集成到现有飞书日报中

### 2. 知行趋势线选股指标

基于用户提供的通达信公式，实现选股功能：

- **短期趋势线**：EMA(EMA(C,10),10) - 双重EMA平滑
- **多空趋势线**：(MA(C,14)+MA(C,28)+MA(C,57)+MA(C,114))/4 - 4周期均线平均

选股信号：

- **买入信号**：短期趋势线上穿多空趋势线（金叉）
- **卖出信号**：短期趋势线下穿多空趋势线（死叉）
- **多头排列**：短期 > 多空 且 价 > 短期

### 3. 持仓监控模块

- 通过妙想API获取用户持仓列表
- 对持仓个股计算知行趋势线状态
- 生成持仓分析报告和操作建议

### 数据源

| 数据类型 | 来源 | 接口/方法 |
| --- | --- | --- |
| 持仓列表 | 妙想API | mx_data skill |
| ETF初筛 | 东方财富 | `np-tjxg-b.eastmoney.com/api/smart-tag/etf/v3/pw/search-code` |
| 板块数据 | AkShare | `ak.stock_board_industry_name_em()` |
| 个股历史 | AkShare | `ak.stock_zh_a_hist()` |


### 更新频率

日终更新（收盘后），可配置定时任务自动执行

### 输出

- 飞书卡片推送：持仓监控报告 + 选股建议
- 终端输出：简版分析结果

## 技术方案

### 技术栈

- Python 3.x + pandas + requests
- AkShare（板块数据、个股历史数据）
- 妙想API（持仓数据，已有 dividend_monitor/miaoxiang.py 可复用）
- 飞书Webhook（报告推送）

### 目录结构

```
market_monitor/
├── data_sources/
│   ├── sector.py              # [NEW] 板块数据获取
│   └── etf_selector.py        # [NEW] 东方财富ETF筛选接口
├── analysis/
│   ├── zhixing.py            # [NEW] 知行趋势线指标计算
│   ├── position_monitor.py    # [NEW] 持仓监控
│   ├── stock_selector.py      # [NEW] 选股器
│   ├── scorer.py              # [MODIFY] 增加板块评分
│   └── signal.py              # [MODIFY] 集成新信号
└── report/
    ├── feishu.py              # [MODIFY] 增加持仓/选股卡片
    └── terminal.py            # [MODIFY] 增加终端输出
```

### 核心模块设计

#### zhixing.py - 知行趋势线指标

```python
def calculate_short_trend(df, period=10):
    """短期趋势线：双重EMA"""
    return df['close'].ewm(span=period).mean().ewm(span=period).mean()

def calculate_long_trend(df, m1=14, m2=28, m3=57, m4=114):
    """多空趋势线：4周期MA平均"""
    return (df['close'].rolling(m1).mean() + 
            df['close'].rolling(m2).mean() + 
            df['close'].rolling(m3).mean() + 
            df['close'].rolling(m4).mean()) / 4

def generate_signal(df):
    """生成交易信号：买入/卖出/持有"""
    short = calculate_short_trend(df)
    long = calculate_long_trend(df)
    # 金叉/死叉判断逻辑
    return signal  # "BUY" | "SELL" | "HOLD"
```

#### etf_selector.py - ETF筛选接口

```python
def fetch_etf_screening(params: dict):
    """调用东方财富ETF筛选API"""
    url = "https://np-tjxg-b.eastmoney.com/api/smart-tag/etf/v3/pw/search-code"
    # 解析用户提供的API参数格式
    return parse_response()
```

#### position_monitor.py - 持仓监控

```python
def get_positions_from_miaoxiang() -> list:
    """通过妙想API获取持仓"""
    # 复用 dividend_monitor/miaoxiang.py 的调用方式
    pass

def analyze_positions(positions: list) -> dict:
    """分析持仓，输出每只股票的状态和建议"""
    pass
```

### 性能优化

- ETF筛选：直接调用东方财富API，按KDJ等指标预筛
- 个股分析：批量获取历史数据，使用pandas向量化计算
- 缓存机制：历史数据本地缓存，避免重复请求

## 使用的扩展

### Skill

- **mx-data**: 获取妙想API持仓数据，解析持仓股票列表
- **mx-selfselect**: 查询东方财富自选股（备用持仓来源）