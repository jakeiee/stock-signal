# Feature Requests

This file logs user-requested capabilities and enhancements.

---

## [FEAT-20260405-001] portfolio-management

**Logged**: 2026-04-05T23:31:00+08:00
**Priority**: high
**Status**: pending
**Area**: backend

### Requested Capability
完整的持仓管理系统

### User Context
用户多次查询"持仓信息"，表明需求：
1. 获取当前系统的仓位建议
2. 管理实际的投资组合持仓
3. 集成持仓与市场分析数据

### Complexity Estimate
complex

### Suggested Implementation
1. **持仓数据存储**：
   - 支持CSV/JSON格式导入
   - 数据库存储（SQLite）
   - 实时盈亏计算
   
2. **仓位建议集成**：
   - 连接动态仓位建议模块
   - 根据持仓评估风险
   
3. **多数据源支持**：
   - 模拟组合（mx-moni）
   - 实际持仓文件
   - 实时行情对接

### Metadata
- Frequency: recurring
- Related Features: dividend_monitor, market_monitor, position_suggestion

---

## [FEAT-20260405-002] self-improvement-automation

**Logged**: 2026-04-05T23:31:00+08:00
**Priority**: medium
**Status**: pending
**Area**: config

### Requested Capability
self-improving-agent技能的自动化集成

### User Context
用户询问该技能是否需要手动添加记录，表明希望：
1. 减少手动操作的负担
2. 提高学习记录的完整性
3. 简化技能使用流程

### Complexity Estimate
medium

### Suggested Implementation
1. **配置自动化Hook**：
   ```json
   # .claude/settings.json
   {
     "hooks": {
       "UserPromptSubmit": [{
         "matcher": "",
         "hooks": [{
           "type": "command",
           "command": "echo '考虑记录学习？检查 .learnings/'"
         }]
       }]
     }
   }
   ```
   
2. **创建辅助脚本**：
   - 交互式学习记录工具
   - 定期回顾提醒
   
3. **项目文件集成**：
   - 在README中添加说明
   - 在主程序中添加提醒

### Metadata
- Frequency: first_time
- Related Features: self-improving-agent

---

