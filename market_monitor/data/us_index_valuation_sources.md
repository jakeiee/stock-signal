# 美股指数估值数据源汇总

> 更新时间：2026-03-26

本文档收集了主流美股指数（标普500、纳斯达克100、道琼斯指数）的估值数据源，包含PE、PB等关键指标的历史数据。

---

## 📊 一、标普500 (S&P 500)

### 主要数据源

| 数据源 | 网址 | 特点 | 数据范围 |
|--------|------|------|----------|
| **Macrotrends** | https://www.macrotrends.net/2577/sp-500-pe-ratio-price-to-earnings-chart | 免费、交互式图表、历史悠久 | 1926年至今 |
| **GuruFocus** | https://www.gurufocus.com/economic_indicators/57/sp-500-pe-ratio | 提供多种估值指标 | 1990年至今 |
| **Multpl** | https://www.multpl.com/s-p-500-pe-ratio/table/by-year | 简洁年度数据 | 1900年至今 |
| **DQYDJ** | https://dqydj.com/sp-500-pe-ratio/ | 含最大值/最小值/中位数统计 | 1871年至今 |
| **StockMarketPERatio** | https://www.stockmarketperatio.com/ | 滚动TTM和远期PE | 近年数据 |
| **RealCPI** | https://www.realcpi.org/s-p-500-pe-ratio/ | 基于CPI调整的真实PE | 1988年至今 |
| **MacroMicro** | https://en.macromicro.me/series/1633/us-sp500-pe-ratio | 中英文双语 | 近年数据 |
| **FRED (美联储)** | https://fred.stlouisfed.org/series/SP500 | 官方数据、指数价格 | 1980年至今 |

---

## 📊 二、纳斯达克100 (NASDAQ 100)

### 主要数据源

| 数据源 | 网址 | 特点 | 数据范围 |
|--------|------|------|----------|
| **Macrotrends** | https://www.macrotrends.net/stocks/charts/NDAQ/nasdaq/pe-ratio | 免费图表 | 2012年至今 |
| **MacroMicro** | https://en.macromicro.me/series/23955/nasdaq-100-pe | 远期PE | 2005年至今 |
| **World PERatio** | https://worldperatio.com/index/nasdaq-100/ | 当前PE + 5年区间 | 近年数据 |
| **Trendonify** | https://trendonify.com/united-states/stock-market/nasdaq-100/pe-ratio | 当前PE + 5年中位数 | 近年数据 |
| **Trading Economics** | https://tradingeconomics.com/ndaq:us:pe | 季度数据 | 近年数据 |
| **Historical PERatio** | https://www.historicalperatio.com/nasdaq.html | 官方数据来源 | 近年数据 |
| **Fullratio** | https://fullratio.com/stocks/nasdaq-ndaq/pe-ratio | 10年平均统计 | 近年数据 |
| **YCharts** | https://ycharts.com/companies/NDAQ/pe_ratio | 专业金融平台 | 2002年至今 |

---

## 📊 三、道琼斯指数 (Dow Jones Industrial Average)

### 主要数据源

| 数据源 | 网址 | 特点 | 数据范围 |
|--------|------|------|----------|
| **World PERatio** | https://worldperatio.com/index/dow-jones/ | 当前PE + 5年区间 | 近年数据 |
| **Fullratio** | https://fullratio.com/stocks/nyse-dow/pe-ratio | 历史PE分析 | 7年数据 |
| **FRED** | https://fred.stlouisfed.org/series/DJIA/ | 官方指数数据 | 2016年至今 |
| **Historical PERatio** | https://www.historicalperatio.com/dow-pe-ratio-history.html | 历史PE记录 | 近年数据 |
| **Macrotrends** | https://www.macrotrends.net/1358/dow-jones-industrial-average-last-10-years | 10年价格图表 | 2016年至今 |

---

## 📊 四、综合性指数估值平台

以下平台提供多种美股指数的对比分析：

| 平台 | 网址 | 特点 |
|------|------|------|
| **World PERatio** | https://worldperatio.com/major-stock-index-pe-ratios/ | 主要指数PE对比 |
| **Multipl** | https://www.multpl.com/ | 多种指标历史数据 |
| **Trading Economics** | https://tradingeconomics.com/ | 宏观数据+图表 |

---

## 📊 五、数据说明

### 常用估值指标
- **PE (TTM)**：滚动12个月市盈率，基于过去12个月盈利
- **PE (Forward)**：远期市盈率，基于未来12个月预期盈利
- **PB**：市净率
- **Shiller PE**：周期调整市盈率（CAPE），基于10年平均盈利

### 数据更新频率
- 日度数据：主要通过收盘价计算
- 季度数据：财报发布后更新
- 年度数据：通常在年初更新

---

## 🔗 快速访问链接

```
标普500:
- https://www.macrotrends.net/2577/sp-500-pe-ratio-price-to-earnings-chart
- https://www.multpl.com/s-p-500-pe-ratio/table/by-year
- https://dqydj.com/sp-500-pe-ratio/

纳斯达克100:
- https://www.macrotrends.net/stocks/charts/NDAQ/nasdaq/pe-ratio
- https://worldperatio.com/index/nasdaq-100/
- https://trendonify.com/united-states/stock-market/nasdaq-100/pe-ratio

道琼斯:
- https://worldperatio.com/index/dow-jones/
- https://fred.stlouisfed.org/series/DJIA/

综合对比:
- https://worldperatio.com/major-stock-index-pe-ratios/
```

---

*数据仅供参考，投资决策请咨询专业人士*