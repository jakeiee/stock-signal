# Trendonify 港股估值补充方案调研报告

## 调研目标
为全球市场估值数据补充**港股（恒生指数）**的真实估值数据，解决 WorldPERatio 缺少港股直接数据的问题。

---

## Trendonify 人机验证分析

### 验证机制
- **类型**: Cloudflare Turnstile CAPTCHA
- **检测方式**: 
  - `navigator.webdriver` 属性检测
  - 浏览器指纹分析
  - 行为模式分析（鼠标移动、点击模式）
  - TLS 指纹检测

### 绕过方案调研

| 方案 | 可行性 | 复杂度 | 稳定性 | 成本 |
|------|--------|--------|--------|------|
| **Playwright + Stealth 插件** | ⚠️ 部分可行 | 高 | 低 | 免费 |
| **puppeteer-extra-plugin-stealth** | ⚠️ 部分可行 | 高 | 低 | 免费 |
| **2Captcha API 服务** | ✅ 可行 | 中 | 中 | $2.99/1000次 |
| **住宅代理 + 真实浏览器** | ✅ 可行 | 高 | 中 | $5-10/GB |
| **人工介入验证** | ✅ 可行 | 低 | 高 | 人工成本 |

### 技术实现参考
```python
# 方案1: Playwright + CDP 修改 webdriver
cdp_session = await page.context.new_cdp_session(page)
await cdp_session.send("Runtime.evaluate", {
    "expression": """
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        })
    """
})

# 方案2: 使用 cloudflare-bypass-playwright 库
from cloudflare_bypass import CloudflareBypasser
bypasser = CloudflareBypasser(api_key="YOUR_2CAPTCHA_KEY")
success = await bypasser.bypass_url("https://trendonify.com/pe-ratio")
```

### 结论
**Trendonify 不建议作为常规数据源**：
- Cloudflare 防护严格，自动化绕过成本高
- 需要第三方付费服务（2Captcha）
- 稳定性无法保证，可能随时失效

---

## 港股估值替代方案

### 推荐方案：亿牛网 (eniu.com)

| 属性 | 详情 |
|------|------|
| **网址** | https://eniu.com/gu/hkhsi |
| **覆盖指数** | 恒生指数 (HSI) |
| **数据字段** | PE、股息率、历史平均PE、最高/最低PE、多周期百分位 |
| **可抓取性** | ✅ 静态HTML，无防护 |
| **稳定性** | 高 |
| **成本** | 免费 |

### 数据质量对比

| 数据源 | 港股PE | 10年百分位 | 股息率 | 更新频率 |
|--------|--------|------------|--------|----------|
| **亿牛网** | 13.98 | 78.2% | 3.27% | 日更 |
| **WorldPERatio** | N/A (无港股) | N/A | N/A | - |
| **Trendonify** | 未知 | 未知 | 未知 | - |
| **HKCoding** | 13.65 | 57.6% | - | 延迟15分钟 |

### 当前港股估值数据 (2026-04-19)

| 指标 | 数值 | 说明 |
|------|------|------|
| **当前PE** | 13.98 | 市盈率 |
| **股息率** | 3.27% | 分红收益率 |
| **历史平均PE** | 13.82 | 长期平均水平 |
| **历史最高PE** | 43.56 | 1973年5月 |
| **历史最低PE** | 5.57 | 1982年11月 |
| **近3年百分位** | 98.5% | 接近3年高点 |
| **近10年百分位** | 78.2% | 中等偏高 |
| **历史百分位** | 55.9% | 中等水平 |

---

## 实施方案

### 已完成的接入

1. **新增港股估值模块** (`market_monitor/data_sources/hk_valuation.py`)
   - 从亿牛网抓取恒生指数PE数据
   - 支持PE、股息率、历史百分位等字段

2. **更新全球估值主模块** (`market_monitor/data_sources/trendonify.py`)
   - 优先使用 WorldPERatio 获取美股/日股/A股/韩股
   - 使用亿牛网获取港股真实数据
   - 原有回退逻辑保持不变

### 数据流

```
全球市场估值数据
├── 美股 (S&P 500) ← WorldPERatio
├── A股 (FTSE China 50) ← WorldPERatio  
├── 港股 (恒生指数 HSI) ← 亿牛网 (eniu.com) [NEW]
├── 日股 (MSCI Japan) ← WorldPERatio
└── 韩股 (MSCI EM 参考) ← WorldPERatio
```

---

## 最终结论

### Trendonify 评估
- **不建议接入**: Cloudflare 防护严格，绕过成本高且不稳定
- **替代价值**: 已有 WorldPERatio + 亿牛网 组合，数据覆盖更全面

### 港股估值方案
- **推荐**: 亿牛网 (eniu.com)
- **优势**: 免费、稳定、数据完整（PE + 股息率 + 历史百分位）
- **当前港股PE**: 13.98，处于近10年78.2%分位（中等偏高）

### 全球市场估值现状 (2026-04-19)

| 市场 | PE | 估值状态 | 数据源 |
|------|-----|----------|--------|
| **美股** | 27.09 | 🔴 昂贵 (+2.21σ) | WorldPERatio |
| **A股** | 10.13 | 🟡 合理 (-0.78σ) | WorldPERatio |
| **港股** | 13.98 | 🟠 高估 (78.2%分位) | 亿牛网 |
| **日股** | 17.46 | 🔴 昂贵 (+2.18σ) | WorldPERatio |
| **韩股** | 16.47 | 🔴 昂贵 (+2.63σ) | WorldPERatio |

---

*报告生成时间: 2026-04-19*
