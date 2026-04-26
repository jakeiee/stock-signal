# stock-signal

ETF/股票量化交易分析与监控系统，支持 **持仓分析**、**红利指数监控**、**宏观择时** 三大模块。

---

## 项目结构

```
stock-signal/
├── market_monitor/           # 股票/ETF 监控模块
│   ├── main.py               # 主入口（宏观择时报告）
│   ├── config.py              # 飞书/LLM 配置
│   ├── data_sources/          # 数据源（资金面/估值/政策/全球市场）
│   │   ├── capital.py        # 新开户数、两融、北向资金
│   │   ├── valuation.py      # A股估值（妙想API）
│   │   ├── hk_valuation.py   # 港股估值
│   │   ├── policy.py         # 政策事件
│   │   └── global_mkt.py     # 全球市场数据
│   ├── analysis/             # 信号分析
│   │   ├── signal.py         # 综合信号生成
│   │   └── position_monitor.py  # 动态仓位计算
│   └── report/                # 报告输出
│       ├── terminal.py       # 终端输出
│       ├── feishu.py         # 飞书推送
│       └── portfolio_analyzer.py  # ETF持仓分析
│
├── dividend_monitor/         # 红利指数监控模块
│   ├── main.py               # 主入口（红利指数报告）
│   ├── send_dividend_report_to_feishu.py  # 备用：直接发送红利日报
│   ├── config.py              # 指数配置
│   ├── data_sources/          # 数据源
│   │   ├── bond.py           # 国债收益率
│   │   └── csindex.py        # 中证官网
│   ├── analysis/             # 分析模块
│   │   ├── valuation.py      # 估值计算（股息率/PE/PB）
│   │   ├── kdj.py            # 周线KDJ
│   │   └── position.py       # 仓位建议
│   └── report/               # 报告输出
│       ├── terminal.py       # 终端输出
│       └── feishu.py         # 飞书推送
│
├── data/                     # 个人数据目录
│   ├── positions.json        # 持仓数据（手动维护）
│   └── trading_log.csv       # 交易记录（CSV格式）
└── tools/                    # 工具脚本
    └── self_improvement_integration.py  # 自我改进学习系统
```

---

## 快速开始

### 1. 安装依赖

```bash
pip install xalpha pandas requests dashscope
```

### 2. 配置环境变量

```bash
# 飞书 Webhook（用于推送消息）
export FEISHU_WEBHOOK="https://open.feishu.cn/open-apis/bot/v2/hook/YOUR-WEBHOOK-ID"

# 通义千问 API Key（用于 LLM 解析）
export DASHSCOPE_API_KEY="your-api-key"
```

### 3. 启动监控

#### 宏观择时报告（market_monitor）

```bash
# 基础运行
python3 -m market_monitor

# 推送到飞书
python3 -m market_monitor --feishu

# 生成 HTML 宏观报告
python3 -m market_monitor --macro

# 手动传入新开户数（万戸）
python3 -m market_monitor --new-accounts 450

# 手动传入两融数据
python3 -m market_monitor --margin "2026-03-13,26517.11,..."
```

#### 红利指数报告（dividend_monitor）

```bash
# 基础运行
python3 -m dividend_monitor

# 推送到飞书
python3 -m dividend_monitor --feishu
```

#### ETF 持仓分析报告

```bash
# 混合模式（原生组件 + Mermaid图表）
python3 -m market_monitor.report.portfolio_feishu_doc --mode hybrid

# 仅原生组件模式
python3 -m market_monitor.report.portfolio_feishu_doc --mode xml

# 仅 Mermaid 图表模式
python3 -m market_monitor.report.portfolio_feishu_doc --mode mermaid
```

---

## 持仓管理

### data/positions.json

手动维护当前持仓，包含：ETF代码、名称、数量、成本价、现价。

```json
[
  {
    "code": "513020",
    "name": "港股通科技ETF",
    "shares": 99100,
    "market_value": 62234.80,
    "current_price": 0.628,
    "cost_price": 0.774
  }
]
```

### data/trading_log.csv

记录所有交易操作（买入/卖出），格式：

```
date,etf_code,etf_name,action,shares,price,amount,note
2026-04-26,513020,港股通创新药ETF,买入,1000,1.29,1290,新增买入
```

记录交易后会自动同步到 `data/positions.json`。

---

## 持仓分析信号说明

| 信号 | 含义 | 操作建议 |
|:---|:---|:---|
| 🔴 DANGER | 风险警示 | 谨慎持有或减仓 |
| 🟡 WATCH | 观望 | 等待时机 |
| 🟢 STRONG | 强烈买入 | 可考虑加仓 |

### 知行信号（均线形态）

| 形态 | 含义 |
|:---|:---|
| 空头排列 | MA5/MA20/MA60 均在收盘价上方，看跌 |
| 弱势 | 黄线 > 收盘 > 白线，趋势偏弱 |
| 反弹整理 | 收盘 > 黄线 > 白线，有反弹迹象 |
| 短线在长线上 | 短线均线在长线均线上方，偏多整理 |

---

## 飞书文档报告

执行持仓分析后会自动生成飞书文档，报告包含：

1. **执行摘要** - 总盈亏、信号分布
2. **持仓明细** - 各ETF技术指标、盈亏幅度
3. **板块分布** - 港股/A股仓位占比
4. **技术指标分析** - RSI / KDJ / MACD / 偏离度
5. **风险评估** - 核心风险提示
6. **操作建议** - 分优先级给出操作意见
7. **后市展望** - 技术面/资金面/政策面分析

---

## 数据源

| 模块 | 数据源 | 说明 |
|:---|:---|:---|
| A股估值 | 妙想API / 本地缓存 | PE/PB/股债利差 |
| 港股估值 | 妙想API | 恒生指数估值 |
| 资金面 | 东方财富接口 | 新开户/两融/北向 |
| 指数数据 | 新浪财经 | 指数历史行情 |
| ETF净值 | xalpha | ETF实时净值 |
| 政策事件 | 妙想API | 重大政策新闻 |
| 全球市场 | 妙想API | 美股/VIX/商品 |

---

## 文件说明

| 文件 | 说明 |
|:---|:---|
| `data/positions.json` | 当前持仓数据 |
| `data/trading_log.csv` | 交易记录 |
| `market_monitor/data/` | 资金面数据、北向资金等 |
| `dividend_monitor/dividend_index_valuation.csv` | 红利指数估值数据 |
| `wind_app_recorded_data/` | Wind App 录制数据 |
| `protected_data_sources/` | 保护的数据源 |

---

## 技术栈

- **数据采集**: xalpha, requests, pandas
- **数据缓存**: JSON/CSV 本地文件
- **LLM 解析**: 通义千问（dashscope）
- **消息推送**: 飞书 Webhook + lark-cli
- **报告生成**: 飞书原生组件文档格式（XML）
