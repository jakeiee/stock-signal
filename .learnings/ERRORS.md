# Errors

This file logs command failures, exceptions, and operational errors for continuous improvement.

---

## [ERR-20260405-001] mx-moni-python-script

**Logged**: 2026-04-05T23:30:00+08:00
**Priority**: medium
**Status**: resolved
**Area**: infra

### Summary
Python脚本执行失败：硬编码路径权限问题

### Error
```
Traceback (most recent call last):
  File "/Users/liuyi/.codebuddy/skills/mx-moni/mx_moni.py", line 16, in <module>
    os.makedirs(OUTPUT_DIR, exist_ok=True)
  File "/Library/Frameworks/Python.framework/Versions/3.9/lib/python3.9/os.py", line 215, in makedirs
    makedirs(head, exist_ok=exist_ok)
  File "/Library/Frameworks/Python.framework/Versions/3.9/lib/python3.9/os.py", line 215, in makedirs
    makedirs(head, exist_ok=exist_ok)
  File "/Library/Frameworks/Python.framework/Versions/3.9/lib/python3.9/os.py", line 225, in makedirs
    mkdir(name, mode)
OSError: [Errno 30] Read-only file system: '/root'
```

### Context
- 执行的命令：`python3 mx_moni.py "查询持仓"`
- 脚本位置：`/Users/liuyi/.codebuddy/skills/mx-moni/`
- Python版本：3.9.13
- 操作系统：macOS

### Suggested Fix
修改脚本中的硬编码路径：
```python
# 错误的：
OUTPUT_DIR = '/root/.openclaw/workspace/mx_data/output'

# 正确的：
OUTPUT_DIR = os.path.expanduser('~/.openclaw/workspace/mx_data/output')
```

### Metadata
- Reproducible: yes
- Related Files: /Users/liuyi/.codebuddy/skills/mx-moni/mx_moni.py
- See Also: LRN-20260405-001

---

## [ERR-20260405-002] mx-moni-api-404

**Logged**: 2026-04-05T23:30:00+08:00
**Priority**: medium
**Status**: resolved
**Area**: backend

### Summary
模拟组合API返回404错误：需要账户绑定

### Error
```
错误码: 404
错误信息: 请先绑定账户~
```

### Context
- API请求：mx-moni模拟组合持仓查询
- API端点：POST /finskillshub 路径
- 环境变量：MX_APIKEY已正确配置
- 错误场景：尝试查询持仓信息，但账户未绑定

### Suggested Fix
前置步骤：
1. 访问 https://dl.dfcfs.com/m/itc4
2. 创建模拟组合账户
3. 绑定模拟账户
4. 重新查询

### Metadata
- Reproducible: yes
- Related Files: /Users/liuyi/.codebuddy/skills/mx-moni/SKILL.md
- See Also: LRN-20260405-002

---


## [ERR-20260406-001] test_script (test_module)

**Logged**: 2026-04-06T18:40:25.518313
**Priority**: low
**Status**: pending
**Area**: finance_analysis

### Summary
测试错误记录

### Error
```
This is a test error message for integration testing
```

### Context
Testing error logging in self-improvement system

### Suggested Fix
This is just a test, no fix needed

### Metadata
- Module: test_module
- Reproducible: yes
- Tags: automatic, error, test_module

---

## [ERR-20260414-001] wind_app.update_valuation_cache (dividend_monitor)

**Logged**: 2026-04-14T00:22:24.535460
**Priority**: medium
**Status**: pending
**Area**: finance_analysis

### Summary
Wind APP专业估值数据更新失败

### Error
```
attempted relative import with no known parent package
```

### Context
在 main() 函数开始时尝试更新Wind APP估值缓存

### Suggested Fix
检查网络连接或Wind APP数据源配置

### Metadata
- Module: dividend_monitor
- Reproducible: yes
- Tags: automatic, error, dividend_monitor

---

## [ERR-20260414-002] kdj.fetch (dividend_monitor)

**Logged**: 2026-04-14T00:22:31.616714
**Priority**: medium
**Status**: pending
**Area**: finance_analysis

### Summary
获取 红利低波 KDJ数据为空

### Error
```
API返回空数据
```

### Context
指数代码: H30269，KDJ数据源可能有问题

### Metadata
- Module: dividend_monitor
- Reproducible: yes
- Tags: automatic, error, dividend_monitor

---

## [ERR-20260414-003] kdj.fetch (dividend_monitor)

**Logged**: 2026-04-14T00:22:34.995372
**Priority**: medium
**Status**: pending
**Area**: finance_analysis

### Summary
获取 红利质量 KDJ数据为空

### Error
```
API返回空数据
```

### Context
指数代码: 931468，KDJ数据源可能有问题

### Metadata
- Module: dividend_monitor
- Reproducible: yes
- Tags: automatic, error, dividend_monitor

---

## [ERR-20260414-004] kdj.fetch (dividend_monitor)

**Logged**: 2026-04-14T00:22:38.419165
**Priority**: medium
**Status**: pending
**Area**: finance_analysis

### Summary
获取 东证红利低波 KDJ数据为空

### Error
```
API返回空数据
```

### Context
指数代码: 931446，KDJ数据源可能有问题

### Metadata
- Module: dividend_monitor
- Reproducible: yes
- Tags: automatic, error, dividend_monitor

---

## [ERR-20260414-005] wind_app.update_valuation_cache (dividend_monitor)

**Logged**: 2026-04-14T00:23:58.648677
**Priority**: medium
**Status**: pending
**Area**: finance_analysis

### Summary
Wind APP专业估值数据更新失败

### Error
```
attempted relative import with no known parent package
```

### Context
在 main() 函数开始时尝试更新Wind APP估值缓存

### Suggested Fix
检查网络连接或Wind APP数据源配置

### Metadata
- Module: dividend_monitor
- Reproducible: yes
- Tags: automatic, error, dividend_monitor

---

## [ERR-20260414-006] kdj.fetch (dividend_monitor)

**Logged**: 2026-04-14T14:40:24.423566
**Priority**: medium
**Status**: pending
**Area**: finance_analysis

### Summary
获取 东证红利低波 KDJ数据为空

### Error
```
API返回空数据
```

### Context
指数代码: 931446，KDJ数据源可能有问题

### Metadata
- Module: dividend_monitor
- Reproducible: yes
- Tags: automatic, error, dividend_monitor

---

## [ERR-20260414-007] _fetch_market_turnover (dividend_monitor)

**Logged**: 2026-04-14T14:40:24.425230
**Priority**: medium
**Status**: pending
**Area**: finance_analysis

### Summary
获取全市场成交额失败

### Error
```
中证全指接口无数据
```

### Context
通过中证全指接口获取成交额数据

### Suggested Fix
检查中证官网接口是否可用或网络连接

### Metadata
- Module: dividend_monitor
- Reproducible: yes
- Tags: automatic, error, dividend_monitor

---

## [ERR-20260414-008] feishu.send (dividend_monitor)

**Logged**: 2026-04-14T14:40:24.425527
**Priority**: low
**Status**: pending
**Area**: finance_analysis

### Summary
股息指数报告飞书推送失败

### Error
```
飞书API调用失败
```

### Context
推送时间: 2026-04-14 14:35

### Suggested Fix
检查飞书机器人配置和网络连接

### Metadata
- Module: dividend_monitor
- Reproducible: yes
- Tags: automatic, error, dividend_monitor

---

## [ERR-20260414-009] wind_app.update_valuation_cache (dividend_monitor)

**Logged**: 2026-04-14T21:42:25.724725
**Priority**: medium
**Status**: pending
**Area**: finance_analysis

### Summary
Wind APP专业估值数据更新失败

### Error
```
attempted relative import with no known parent package
```

### Context
在 main() 函数开始时尝试更新Wind APP估值缓存

### Suggested Fix
检查网络连接或Wind APP数据源配置

### Metadata
- Module: dividend_monitor
- Reproducible: yes
- Tags: automatic, error, dividend_monitor

---

## [ERR-20260414-010] wind_app.update_valuation_cache (dividend_monitor)

**Logged**: 2026-04-14T21:42:38.316135
**Priority**: medium
**Status**: pending
**Area**: finance_analysis

### Summary
Wind APP专业估值数据更新失败

### Error
```
attempted relative import with no known parent package
```

### Context
在 main() 函数开始时尝试更新Wind APP估值缓存

### Suggested Fix
检查网络连接或Wind APP数据源配置

### Metadata
- Module: dividend_monitor
- Reproducible: yes
- Tags: automatic, error, dividend_monitor

---

## [ERR-20260414-011] feishu.send (dividend_monitor)

**Logged**: 2026-04-14T21:42:40.505894
**Priority**: low
**Status**: pending
**Area**: finance_analysis

### Summary
股息指数报告飞书推送失败

### Error
```
飞书API调用失败
```

### Context
推送时间: 2026-04-14 21:42

### Suggested Fix
检查飞书机器人配置和网络连接

### Metadata
- Module: dividend_monitor
- Reproducible: yes
- Tags: automatic, error, dividend_monitor

---

## [ERR-20260414-012] feishu.send (dividend_monitor)

**Logged**: 2026-04-14T21:42:54.240191
**Priority**: low
**Status**: pending
**Area**: finance_analysis

### Summary
股息指数报告飞书推送失败

### Error
```
飞书API调用失败
```

### Context
推送时间: 2026-04-14 21:42

### Suggested Fix
检查飞书机器人配置和网络连接

### Metadata
- Module: dividend_monitor
- Reproducible: yes
- Tags: automatic, error, dividend_monitor

---

## [ERR-20260414-013] wind_app.update_valuation_cache (dividend_monitor)

**Logged**: 2026-04-14T21:44:54.277504
**Priority**: medium
**Status**: pending
**Area**: finance_analysis

### Summary
Wind APP专业估值数据更新失败

### Error
```
attempted relative import with no known parent package
```

### Context
在 main() 函数开始时尝试更新Wind APP估值缓存

### Suggested Fix
检查网络连接或Wind APP数据源配置

### Metadata
- Module: dividend_monitor
- Reproducible: yes
- Tags: automatic, error, dividend_monitor

---

## [ERR-20260414-014] wind_app.update_valuation_cache (dividend_monitor)

**Logged**: 2026-04-14T21:45:00.274015
**Priority**: medium
**Status**: pending
**Area**: finance_analysis

### Summary
Wind APP专业估值数据更新失败

### Error
```
attempted relative import with no known parent package
```

### Context
在 main() 函数开始时尝试更新Wind APP估值缓存

### Suggested Fix
检查网络连接或Wind APP数据源配置

### Metadata
- Module: dividend_monitor
- Reproducible: yes
- Tags: automatic, error, dividend_monitor

---

## [ERR-20260414-015] wind_app.update_valuation_cache (dividend_monitor)

**Logged**: 2026-04-14T21:48:59.098919
**Priority**: medium
**Status**: pending
**Area**: finance_analysis

### Summary
Wind APP专业估值数据更新失败

### Error
```
attempted relative import with no known parent package
```

### Context
在 main() 函数开始时尝试更新Wind APP估值缓存

### Suggested Fix
检查网络连接或Wind APP数据源配置

### Metadata
- Module: dividend_monitor
- Reproducible: yes
- Tags: automatic, error, dividend_monitor

---

## [ERR-20260414-016] wind_app.update_valuation_cache (dividend_monitor)

**Logged**: 2026-04-14T21:49:17.738840
**Priority**: medium
**Status**: pending
**Area**: finance_analysis

### Summary
Wind APP专业估值数据更新失败

### Error
```
attempted relative import with no known parent package
```

### Context
在 main() 函数开始时尝试更新Wind APP估值缓存

### Suggested Fix
检查网络连接或Wind APP数据源配置

### Metadata
- Module: dividend_monitor
- Reproducible: yes
- Tags: automatic, error, dividend_monitor

---
