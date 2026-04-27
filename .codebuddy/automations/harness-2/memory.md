# 持仓分析 Harness 执行记录

## 2026-04-27 (周一)

### 执行状态
- **状态**: 成功（部分）
- **总持仓**: 8 只（分析 7 只，跳过 1 只）
- **强势**: 1 只
- **观望**: 1 只
- **危险**: 5 只
- **超跌**: 1 只
- **平均评分**: 34/100
- **分析失败**: 513090 香港证券ETF（无 ETF_MAPPING 映射）

### 强势持仓
- 科创板50ETF: 收盘>白线>黄线（三线多头，RSI=85）

### 危险持仓
- 港股通科技ETF、软件ETF、恒生互联网ETF、游戏ETF、机器人ETF

### 飞书推送
- 状态: 跳过（FEISHU_WEBHOOK 环境变量未在子进程生效）
- 报告已生成: portfolio_report_2026-04-27.md

### 步骤执行结果
1. load_positions: success
2. analyze_etf: success (7/8)
3. aggregate_signal: success
4. terminal_output: success
5. generate_report: success
6. feishu_push: skipped (FEISHU_WEBHOOK 未配置)

### 踩坑记录
- 持仓文件路径 `./positions.json` 不存在，实际在 `data/positions.json`
- 运行 harness 需使用 `python3 -m tools.harness.portfolio_harness` 避免相对导入错误
- FEISHU_WEBHOOK 在 shell 环境有值，但子进程无法继承（需写入 .env 文件）

---

## 2026-04-20 (周一)

### 执行状态
- **状态**: 成功
- **总持仓**: 7 只
- **强势**: 1 只
- **观望**: 0 只
- **危险**: 6 只
- **超跌**: 0 只
- **平均评分**: 34/100

### 强势持仓
- 港股通创新药ETF: 收盘>白线>黄线（三线多头）

### 飞书推送
- 状态: 成功
- 报告已发送到飞书

### 步骤执行结果
1. load_positions: success
2. analyze_etf: success
3. aggregate_signal: success
4. terminal_output: success
5. generate_report: success
6. feishu_push: success

