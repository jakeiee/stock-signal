# 量化投资监控工具集

本仓库包含两个独立的监控模块：

| 模块 | 说明 |
|------|------|
| `dividend_monitor` | 红利指数监控——跟踪沪深红利类宽基指数的估值水位、技术形态与市场成交额，输出终端报告并可选推送飞书机器人，基于多维度评分给出动态仓位建议 |
| `market_monitor` | 股市交易分析监控——框架骨架（开发中），监控资金面、基本面、政策面、全球市场等维度，聚合为综合信号 |

---

## 一、红利指数监控 `dividend_monitor`

### 跟踪指数

| 指数名称 | 代码 |
|---------|------|
| 红利低波 | H30269 |
| 红利质量 | 931468 |
| 东证红利低波 | 931446 |

### 监控指标

**估值层**

- 股息率 TTM —— 当前值 + 全历史 max 百分位
- 市盈率 PETTM —— 当前值 + 全历史 max 百分位
- 风险溢价 = 1/PE × 100% − 无风险利率（10 年期国债 CN10Y）

**技术层**

- 周线 KDJ(9,3,3) —— 最新一周 K / D / J 值 + 信号标注（金叉/死叉/超买/超卖）

**市场温度层**

- **成交额**（turnover）—— 全市场当日实际成交金额（亿元，中证全指口径）
- **成交额日环比** —— 较前一交易日变化率（%）

**动态仓位建议**

综合三维度加权评分（−2 空头 ↔ +2 多头），映射为建议仓位区间：

| 维度 | 权重 | 逻辑 |
|------|------|------|
| 估值信号 | 50% | 股息率百分位越高 / PE 百分位越低 → 越便宜 → 正分 |
| 市场温度 | 30% | 成交额越低（市场越冷） → 安全边际越高 → 正分 |
| KDJ 技术 | 20% | J 值越低（超卖） → 加仓信号 → 正分 |

仓位档位：满仓（≥85%）/ 重仓（70–85%）/ 标配（50–70%）/ 轻仓（30–50%）/ 低配（10–30%）/ 空仓（<10%）

### 数据源策略

```
无风险利率：push2.eastmoney.com 实时接口（f43÷10000）
              └─ 备用：push2his.eastmoney.com 历史 K 线
              └─ 兜底：保底值 1.70%

估值数据：优先本地缓存（valuation_cache.json）
           └─ 缓存命中 → 直接使用（不消耗妙想配额）
           └─ 无缓存 → 妙想 API（东方财富 mkapi2.dfcfs.com）
              └─ 成功 → 写入缓存
              └─ status=113 配额用尽 / 其他失败 → 报告中标注"✗"

周线 KDJ：优先中证官网 OHLCV 自算（不消耗妙想配额）
           pandas resample('W-FRI') + KDJ(9,3,3) EMA 平滑
           └─ 自算失败 → 妙想 API（报告中标注"⚠ 妙想降级"）

全市场成交额：中证全指（000985）历史接口（csindex.com.cn）
               取最近两个交易日记录，计算成交额及日环比
```

### 目录结构

```
dividend_monitor/           # 主包
├── config.py               # 全局配置（API 密钥、指数列表、路径等）
├── cache.py                # 估值缓存 JSON 读写
├── main.py                 # 主入口，协调各模块
├── data_sources/
│   ├── bond.py             # 10 年期国债收益率（东方财富）
│   ├── miaoxiang.py        # 妙想 API 封装（含重试与配额识别）
│   └── csindex.py          # 中证官网 OHLCV 获取 + KDJ 自算 + 成交额历史
├── analysis/
│   ├── valuation.py        # 估值查询与历史百分位计算
│   ├── kdj.py              # KDJ 数据拉取与交易信号判断
│   └── position.py         # 动态仓位建议（三维度加权评分）
└── report/
    ├── terminal.py         # 终端字符报告（含仓位建议区块）
    └── feishu.py           # 飞书交互式卡片构建与发送
```

### 快速开始

```bash
pip install requests pandas numpy

# 仅终端输出
python3 -m dividend_monitor.main

# 终端输出 + 推送飞书
python3 -m dividend_monitor.main --feishu
```

### 报告示例

```
════════════════════════════════════════════════════════════════════
  📊 红利指数监控  |  2026-03-15 10:00
  无风险利率: 1.8316%（实时 CN10Y (2026-03-14)）
════════════════════════════════════════════════════════════════════

  ▌ 红利低波（H30269）  数据日期: 2026-03-13  [缓存]
    股息率  5.120%  [████████░░] 78.3%
    市盈率  12.45   [███░░░░░░░] 28.1%
    风险溢价  +6.20%
    周KDJ  K=68.3  D=51.6  J=101.6  ⚠ J>100 超买  （2026-03-13）

────────────────────────────────────────────────────────────────────
  💡 动态仓位建议
────────────────────────────────────────────────────────────────────
  市场成交额  成交额 23,697亿  较前日 -1.70%（前日 24,106亿）  截至 2026-03-13

  评分维度（-2 空头 ←→ +2 多头）：
    市场温度  [░░░██┼░░░░░] -1.0  偏热
    估值信号  [░░░░░┼███░░] +1.5  低估/偏冷
    技术信号  [░░░██┼░░░░░] -1.0  高估/偏热
    综合得分  [░░░░░┼█░░░░] +0.4

  ▶ 建议仓位  47%–67%（中枢 57.0%）  【标配】

  ─ 权重：估值50%  市场温度30%  KDJ技术20%
  ─ 市场温度使用全市场成交额（中证全指口径）作为评分依据
  ─ 本建议仅供参考，不构成投资建议，请结合自身风险承受能力决策
════════════════════════════════════════════════════════════════════
```

### 信号说明

| 信号 | 含义 |
|------|------|
| ⚠ J>100 超买 | J 值超过 100，短期超买风险 |
| ⚠ J<0 极度超卖 | J 值低于 0，可能存在反弹机会 |
| ✦ 金叉 | K 线上穿 D 线，可能趋势转强 |
| ↓ 死叉 | K 线下穿 D 线，可能趋势转弱 |
| 高位 | K>80 且 D>80 |
| 低位 | K<20 且 D<20 |

### 仓位建议评分阈值

| 成交额 | 市场温度评分 |
|--------|-------------|
| >25000 亿 | −2（极热，大幅降仓） |
| 15000–25000 亿 | −1（偏热） |
| 8000–15000 亿 | 0（正常） |
| 5000–8000 亿 | +1（偏冷） |
| ≤5000 亿 | +2（极冷，加仓机会） |

| J 值范围 | KDJ 评分 |
|---------|---------|
| J < 10 | +2（强烈超卖） |
| 10 ≤ J < 20 | +1（超卖） |
| 20 ≤ J ≤ 80 | 0（中性） |
| 80 < J ≤ 100 | −1（超买） |
| J > 100 | −2（极度超买） |

### KDJ 算法说明

中证官网自算路径采用标准 KDJ(9,3,3)：

1. 日线 OHLCV → `pandas resample('W-FRI')` 重采样为周线
2. RSV = (close − min_low_9w) / (max_high_9w − min_low_9w) × 100
3. K = 2/3 × prev_K + 1/3 × RSV（初值 50）
4. D = 2/3 × prev_D + 1/3 × K（初值 50）
5. J = 3K − 2D

### 注意事项

- **妙想 API 配额**：免费版每日调用次数有限，配额用尽（status=113）时自动降级缓存/自算，次日配额重置后自动恢复并更新缓存。
- **缓存文件**：`valuation_cache.json` 保存在包目录下，可手动删除以强制重新获取。
- **中证官网限速**：`csindex.com.cn` 未设置认证，偶发超时属正常现象，重试一次即可。
- **仓位建议免责**：本模型为量化参考工具，不构成任何投资建议。评分阈值基于历史经验设定，需结合实际市场环境动态调整。

---

## 二、股市交易分析监控 `market_monitor`

> **状态：框架骨架，各维度数据接口均为占位（TODO），可正常运行但输出中性占位值。**

### 监控维度

| 维度 | 权重 | 指标（规划中） |
|------|------|--------------|
| 资金面 | 30% | 全市场成交额、北向资金净流入、融资融券余额、换手率 |
| 基本面 | 40% | 全市场 PE/PB/股息率及历史百分位、风险溢价 |
| 政策面 | 10% | 央行货币政策事件、财政政策、经济数据日历 |
| 全球市场 | 20% | 美股三大指数、VIX、美元指数、原油/黄金、港股、日股 |

### 目录结构

```
market_monitor/                  # 主包（开发中）
├── __init__.py
├── __main__.py                  # 支持 python3 -m market_monitor
├── config.py                    # 全局配置
├── main.py                      # 主入口
├── data_sources/
│   ├── capital.py               # 资金面：成交额/北向/融资融券（TODO）
│   ├── valuation.py             # 基本面：全市场 PE/PB/股息率（TODO）
│   ├── policy.py                # 政策面：政策事件/经济日历（TODO）
│   └── global_mkt.py            # 全球市场：美股/商品/汇率/亚太（TODO）
├── analysis/
│   ├── scorer.py                # 各维度评分逻辑（TODO）
│   └── signal.py                # 综合信号聚合（框架已完成）
└── report/
    ├── terminal.py              # 终端输出（框架已完成）
    └── feishu.py                # 飞书卡片推送（框架已完成）
```

### 快速开始

```bash
# 运行框架骨架（输出占位结构）
python3 -m market_monitor

# 带飞书推送
python3 -m market_monitor --feishu
```

### 报告示例（当前占位输出）

```
════════════════════════════════════════════════════════════════════
  📡 股市交易分析监控  |  2026-03-15 10:00
════════════════════════════════════════════════════════════════════

  ▌ 资金面    [░░░░░┼░░░░░] +0.0  N/A
      资金面数据待接入

  ▌ 基本面    [░░░░░┼░░░░░] +0.0  N/A
      基本面数据待接入

  ▌ 政策面    [░░░░░┼░░░░░] +0.0  N/A
      政策面数据待接入

  ▌ 全球市场  [░░░░░┼░░░░░] +0.0  N/A
      全球市场数据待接入

────────────────────────────────────────────────────────────────────
  综合信号  [░░░░░┼░░░░░] +0.0  中性
  ─ 权重：资金面30%  基本面40%  政策面10%  全球市场20%
  ─ 本报告仅供参考，不构成投资建议
════════════════════════════════════════════════════════════════════
```

### 开发计划

后续指标接入优先级（待用户补充具体需求后排期）：

1. **资金面**：全市场成交额（复用 `dividend_monitor.data_sources.csindex`） + 北向资金（东方财富接口）
2. **基本面**：全市场 PE/PB（中证全指历史数据）
3. **全球市场**：VIX + 美股三大指数（Yahoo Finance）
4. **政策面**：财经日历（东方财富）

---

## 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `MX_APIKEY` | 妙想 API Key（dividend_monitor 使用） | 脚本内置 |
| `FEISHU_WEBHOOK` | 飞书机器人 Webhook 地址（两个模块共用） | 脚本内置 |

```bash
export MX_APIKEY="your_api_key"
export FEISHU_WEBHOOK="https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
```

---

## 三、未使用文件清单

### 3.1 dividend_monitor 未使用文件

| 文件路径 | 说明 | 状态 |
|----------|------|------|
| `dividend_monitor/data_sources/mx_search.py` | 妙想资讯搜索模块（资金面消息搜索） | **未被调用**（独立模块，未在 main.py 中导入） |

### 3.2 market_monitor 未使用文件

| 文件路径 | 说明 | 状态 |
|----------|------|------|
| `market_monitor/data_sources/mx_search.py` | 妙想资讯搜索模块 | **未被调用** |
| `market_monitor/data_sources/trendonify_scraper.js` | Trendonify 全球指数估值爬虫 | **未被直接调用**（trendonify.py 中有引用但未在主流程使用） |

### 3.3 backup 目录（全部未使用）

`backup/` 目录下共 **44 个文件**，均为历史调试脚本和备份文件，**均未在当前项目中使用**：

| 类别 | 文件 | 说明 |
|------|------|------|
| _margin 相关 | `_probe_margin*.py`, `_migrate_margin.py`, `_verify_margin.py` 等 | 两融数据探测脚本 |
| _probe 相关 | `_probe_income*.py`, `_probe_liquidity*.py`, `_probe_social_finance*.py` 等 | 各类数据探测脚本 |
| _test 相关 | `_test_eastmoney_sf*.py`, `_test_pbc.py`, `_test_stats_*.py` 等 | API 测试脚本 |
| 计算脚本 | `_calc_yoy.py`, `_calc_ytm.py`, `_find_codes.py` | 辅助计算脚本 |
| 其他 | `_tmp_analyze.py`, `dividend_monitor.py` | 临时脚本/旧版本 |
| 压缩包 | `mx_search.zip`, `mx_selfselect.zip`, `mx-data.zip` | 妙想功能备份 |

**建议**：如无需保留，可定期清理 `backup/` 目录以节省空间。

---

## 四、项目依赖

### 4.1 核心依赖

```
requests>=2.28.0
pandas>=1.5.0
numpy>=1.23.0
```

### 4.2 可选依赖（market_monitor 部分功能需要）

```
akshare>=1.12.0    # 宏观经济数据（LPR、存款准备金率等）
openai>=1.0.0      # LLM 客户端（如使用 AI 解读功能）
```

---

## 五、运行示例

### 5.1 dividend_monitor

```bash
# 仅终端输出
python3 -m dividend_monitor.main

# 终端输出 + 推送飞书
python3 -m dividend_monitor.main --feishu
```

### 5.2 market_monitor

```bash
# 运行监控（终端输出）
python3 -m market_monitor

# 推送飞书
python3 -m market_monitor --feishu

# 生成宏观分析报告（HTML）
python3 -m market_monitor --macro

# 生成 Markdown 日报
python3 -m market_monitor --md

# 手动录入数据
python3 -m market_monitor --new-accounts 450
python3 -m market_monitor --margin "2026-03-13,26517.11,..."
python3 -m market_monitor --znz "2026-03-23,186349.4,-2.94"
```

---

## 六、文件结构总览

```
stock-signal/
├── README.md                    # 本文件
├── requirements.txt            # 核心依赖
├── Dockerfile                  # Docker 配置
├── valuation_cache.json         # 红利指数估值缓存
├── valuation_cache.csv          # 备份估值缓存
│
├── dividend_monitor/           # 红利指数监控模块 ✅ 完成
│   ├── main.py                 # 主入口
│   ├── config.py               # 全局配置
│   ├── cache.py                # 估值缓存
│   ├── data_sources/
│   │   ├── bond.py             # 10年期国债收益率
│   │   ├── csindex.py          # 中证官网数据 + KDJ 计算
│   │   ├── miaoxiang.py        # 妙想 API 封装
│   │   └── mx_search.py        # ❌ 未使用
│   ├── analysis/
│   │   ├── valuation.py        # 估值分析
│   │   ├── kdj.py              # KDJ 指标
│   │   └── position.py         # 仓位建议
│   └── report/
│       ├── terminal.py         # 终端报告
│       └── feishu.py           # 飞书推送
│
├── market_monitor/             # 股市交易分析监控模块 🟡 大部分完成
│   ├── main.py                 # 主入口
│   ├── config.py                # 全局配置
│   ├── data_sources/
│   │   ├── capital.py          # 资金面（成交额/北向/两融/新开户/指南针）
│   │   ├── valuation.py        # 基本面（全市场 PE/PB）
│   │   ├── policy.py           # 政策面
│   │   ├── global_mkt.py       # 全球市场（美股/商品/外汇/亚太）
│   │   ├── fundamental.py     # 基本面（GDP/PMI/CPI/PPI/M2/社融）
│   │   ├── monetary_policy.py  # 货币政策数据
│   │   ├── pmi_interpretation.py     # PMI 官方解读
│   │   ├── cpi_ppi_interpretation.py # CPI/PPI 官方解读
│   │   ├── gdp_interpretation.py     # GDP 官方解读
│   │   ├── income_interpretation.py  # 人均收入解读
│   │   ├── trendonify.py       # 全球估值（用于飞书报告）
│   │   ├── trendonify_scraper.js  # ❌ 未直接使用
│   │   └── mx_search.py        # ❌ 未使用
│   ├── analysis/
│   │   ├── scorer.py           # 各维度评分
│   │   └── signal.py           # 综合信号聚合
│   ├── report/
│   │   ├── terminal.py         # 终端输出
│   │   ├── feishu.py           # 飞书多卡片推送
│   │   ├── macro_report.py     # 宏观分析 HTML 报告
│   │   ├── md_report.py        # Markdown 日报
│   │   ├── full_report_image.py # 全景图生成
│   │   ├── valuation_image.py  # 估值图生成
│   │   └── feishu_image.py     # 飞书图片生成
│   ├── utils/
│   │   ├── llm_client.py       # LLM 客户端（阿里云/DeepSeek/硅基流动）
│   │   └── web_search.py       # 网页搜索工具
│   └── data/                   # 本地数据缓存
│       ├── margin.csv          # 两融数据缓存
│       ├── new_accounts.csv   # 新开户数据缓存
│       ├── znz_active_cap.csv  # 指南针活跃市值
│       ├── gdp.csv             # GDP 数据
│       ├── supply_demand.csv   # 供需数据（CPI/PPI/PMI）
│       ├── liquidity.csv       # 流动性数据（M2/社融）
│       ├── monetary_policy.csv # 货币政策数据
│       ├── *.csv               # 其他缓存数据
│       ├── *.png               # 生成的图表
│       ├── *.html              # 生成的 HTML 报告
│       └── *.md                # 生成的 Markdown 报告
│
└── backup/                     # ❌ 历史备份文件（全部未使用）
    ├── _probe_*.py             # 数据探测脚本
    ├── _test_*.py             # API 测试脚本
    ├── _calc_*.py             # 辅助计算脚本
    └── *.zip                  # 备份压缩包
```
