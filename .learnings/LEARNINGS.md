# Learnings

Corrections, insights, and knowledge gaps captured during development.

**Categories**: correction | insight | knowledge_gap | best_practice
**Areas**: frontend | backend | infra | tests | docs | config
**Statuses**: pending | in_progress | resolved | wont_fix | promoted | promoted_to_skill

## Status Definitions

| Status | Meaning |
|--------|---------|
| `pending` | Not yet addressed |
| `in_progress` | Actively being worked on |
| `resolved` | Issue fixed or knowledge integrated |
| `wont_fix` | Decided not to address (reason in Resolution) |
| `promoted` | Elevated to CLAUDE.md, AGENTS.md, or copilot-instructions.md |
| `promoted_to_skill` | Extracted as a reusable skill |

## Skill Extraction Fields

When a learning is promoted to a skill, add these fields:

```markdown
**Status**: promoted_to_skill
**Skill-Path**: skills/skill-name
```

Example:
```markdown
## [LRN-20250115-001] best_practice

**Logged**: 2025-01-15T10:00:00Z
**Priority**: high
**Status**: promoted_to_skill
**Skill-Path**: skills/docker-m1-fixes
**Area**: infra

### Summary
Docker build fails on Apple Silicon due to platform mismatch
...
```

---

## [LRN-20260405-001] best_practice

**Logged**: 2026-04-05T23:30:00+08:00
**Priority**: medium
**Status**: resolved
**Area**: infra

### Summary
Python脚本硬编码路径导致跨平台权限问题

### Details
在安装和使用 mx-moni 技能时，脚本 `mx_moni.py` 中包含硬编码路径：
`OUTPUT_DIR = '/root/.openclaw/workspace/mx_data/output'`

在 macOS 系统上执行时，出现错误：
```
OSError: [Errno 30] Read-only file system: '/root'
```

原因：使用系统根目录 `/root`，该目录在非Linux系统和普通用户权限下不可访问。

### Solution
修改为使用用户家目录的路径：
```python
OUTPUT_DIR = os.path.expanduser('~/.openclaw/workspace/mx_data/output')
```

### Metadata
- Source: error_fix
- Related Files: /Users/liuyi/.codebuddy/skills/mx-moni/mx_moni.py
- Tags: cross-platform, path, python
- See Also: 

---

## [LRN-20260405-002] knowledge_gap

**Logged**: 2026-04-05T23:30:00+08:00
**Priority**: medium
**Status**: resolved
**Area**: backend

### Summary
妙想模拟组合查询需要账户绑定步骤

### Details
试图使用 mx-moni 技能查询持仓信息时，API返回：
```
错误码: 404
错误信息: 请先绑定账户~
```

这个错误在文档中有说明（需要绑定步骤），但在实际操作中忽视了前置要求。

### Solution
账户绑定流程：
1. 访问妙想Skills页面：https://dl.dfcfs.com/m/itc4
2. 创建模拟组合账户
3. 绑定模拟账户
4. 重新查询持仓

### Metadata
- Source: api_integration
- Related Files: /Users/liuyi/.codebuddy/skills/mx-moni/SKILL.md
- Tags: api, authentication, setup
- See Also: 

---

## [LRN1-20260405-003] best_practice

**Logged**: 2026-04-05T23:31:00+08:00
**Priority**: medium
**Status**: resolved
**Area**: docs

### Summary
使用 self-improving-agent 技能需要手动触发学习记录

### Details
学习了 self-improving-agent skill 的正确使用方法。该技能不会自动检测和记录学习点，而是：
1. 提供标准的记录格式模板
2. 定义清晰的分类系统
3. 需要人工判断何时记录
4. 提供手动和半自动的使用模式选择

### Solution
手动记录触发场景：
1. 命令/操作失败 → ERRORS.md
2. 被用户纠正 → LEARNINGS.md（类别：correction）
3. 用户需要缺失功能 → FEATURE_REQUESTS.md
4. 发现知识过时 → LEARNINGS.md（类别：knowledge_gap）
5. 发现更好方法 → LEARNINGS.md（类别：best_practice）

### Metadata
- Source: skill_learning
- Related Files: /Users/liuyi/.codebuddy/skills/self-improving-agent/SKILL.md
- Tags: skill, learning, documentation
- See Also: LRN-20260405-001, LRN-20260405-002

---


## [LRN-20260406-001] best_practice (test_module)

**Logged**: 2026-04-06T18:40:25.518084
**Priority**: medium
**Status**: pending
**Area**: finance_analysis

### Summary
测试自我改进集成

### Details
这是为了验证 dividend_monitor 和 market_monitor 集成自动化学习系统而创建的测试记录。

### Metadata
- Module: test_module
- Source: automatic_tracking
- Related Files: dividend_monitor/main.py, market_monitor/main.py
- Tags: automatic, learning, test_module

---

## [LRN-20260410-001] best_practice (dividend_monitor)

**Logged**: 2026-04-10T23:59:08.241521
**Priority**: low
**Status**: pending
**Area**: finance_analysis

### Summary
股息指数报告飞书推送成功

### Details
股息指数报告已成功推送到飞书机器人，推送时间: 2026-04-10 23:58

### Metadata
- Module: dividend_monitor
- Source: automatic_tracking
- Tags: automatic, learning, dividend_monitor

---

## [LRN-20260411-001] best_practice (dividend_monitor)

**Logged**: 2026-04-11T00:05:15.965129
**Priority**: low
**Status**: pending
**Area**: finance_analysis

### Summary
股息指数报告飞书推送成功

### Details
股息指数报告已成功推送到飞书机器人，推送时间: 2026-04-11 00:05

### Metadata
- Module: dividend_monitor
- Source: automatic_tracking
- Tags: automatic, learning, dividend_monitor

---

## [LRN-20260412-001] best_practice (dividend_monitor)

**Logged**: 2026-04-12T16:05:28.670395
**Priority**: low
**Status**: pending
**Area**: finance_analysis

### Summary
股息指数报告飞书推送成功

### Details
股息指数报告已成功推送到飞书机器人，推送时间: 2026-04-12 16:05

### Metadata
- Module: dividend_monitor
- Source: automatic_tracking
- Tags: automatic, learning, dividend_monitor

---

## [LRN-20260412-002] best_practice (dividend_monitor)

**Logged**: 2026-04-12T16:10:36.314003
**Priority**: low
**Status**: pending
**Area**: finance_analysis

### Summary
股息指数报告飞书推送成功

### Details
股息指数报告已成功推送到飞书机器人，推送时间: 2026-04-12 16:10

### Metadata
- Module: dividend_monitor
- Source: automatic_tracking
- Tags: automatic, learning, dividend_monitor

---

## [LRN-20260412-003] best_practice (dividend_monitor)

**Logged**: 2026-04-12T16:34:10.859603
**Priority**: low
**Status**: pending
**Area**: finance_analysis

### Summary
股息指数报告飞书推送成功

### Details
股息指数报告已成功推送到飞书机器人，推送时间: 2026-04-12 16:33

### Metadata
- Module: dividend_monitor
- Source: automatic_tracking
- Tags: automatic, learning, dividend_monitor

---
