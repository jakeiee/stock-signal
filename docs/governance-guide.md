# 项目治理体系使用文档

## 一、概述

本项目治理体系旨在解决以下问题：
1. 上下文/规则/记忆/skill/agent 输出不稳定
2. 重大事故频发（核心功能被修改至无法运行）
3. 数据源接入不稳定
4. 问题识别准确性波动
5. 缺乏项目实践方案

治理体系包含以下核心组件：
- 工作空间治理
- 模块化架构（BaseModule 接口 + ModuleRegistry）
- 规则与记忆系统重构
- 代码安全网
- 自动调整机制

---

## 二、工作空间治理

### 工具：tools/workspace_cleanup.py

**功能**：清理 `/Users/liuyi/WorkBuddy/` 下的时间戳目录

**使用方法**：
```bash
# 预览模式（不实际删除）
python3 tools/workspace_cleanup.py

# 执行清理
python3 tools/workspace_cleanup.py --execute
```

**保留策略**：
- 保留最近 10 个会话
- 90 天前的归档到 `archived/`
- 无价值产物（无 md/py/csv/json 文件）的直接删除

**自动化**：已配置 CodeBuddy Automation，每周日凌晨 2:00 自动执行

---

## 三、模块化架构

### 核心接口：tools/harness/module_interface.py

**BaseModule 接口定义**：
```python
class BaseModule(ABC):
    @abstractmethod
    def get_metadata(self) -> ModuleMetadata: pass

    @abstractmethod
    def get_steps(self) -> List[Step]: pass

    @abstractmethod
    def validate_config(self) -> bool: pass

    @abstractmethod
    def run(self, context: Dict[str, Any]) -> Dict[str, Any]: pass
```

### 模块自注册：tools/harness/module_registry.py

**功能**：自动发现和注册模块

**使用方法**：
```python
from tools.harness import initialize

# 初始化框架（自动发现并注册所有模块）
initialize()

# 获取模块注册表
from tools.harness import get_module_registry
registry = get_module_registry()

# 列出所有注册的模块
print(registry.list_modules())

# 获取模块实例
module = registry.get_module("dividend_monitor")

# 健康检查所有模块
health = registry.health_check_all()
```

### 现有模块适配

已适配的模块：
1. `dividend_monitor` - 股息指数监控
2. `market_monitor` - 市场监控
3. `portfolio` - 持仓分析

每个模块都实现了 `BaseModule` 接口，并自注册到 `ModuleRegistry`。

---

## 四、规则与记忆系统

### 分层规则架构

**文件结构**：
```
.codebuddy/rules/
├── 00-CORE-PRINCIPLES.md      # 核心原则（≤50行，强制加载）
├── 01-MODULE-DEV.md            # 模块开发规范
├── 02-DATA-SOURCES.md          # 数据源管理
└── 03-CODE-SAFETY.md         # 代码安全规范
```

**核心原则（00-CORE-PRINCIPLES.md）**：
- 代码修改安全铁律
- 数据源管理铁律
- 记忆系统使用
- 模块开发规范
- 自动调整机制

### 记忆精炼工具：tools/memory_refiner.py

**功能**：识别重复记录，提取可提升到核心原则的记录

**使用方法**：
```bash
python3 tools/memory_refiner.py
```

**工作流程**：
1. 读取 `LEARNINGS.md`
2. 识别重复记录（Summary 相同且出现≥3 次）
3. 识别可提升到核心原则的记录
4. 询问用户是否清理重复记录

---

## 五、代码安全网

### 安全规范：.codebuddy/rules/03-CODE-SAFETY.md

**Git 分支策略**：
```bash
# 修改前自动执行
git checkout -b ai-edit-$(date +%Y%m%d-%H%M%S)
```

**修改影响分析工具：tools/safe_edit.py**

**功能**：分析代码修改的影响范围，评估风险等级

**使用方法**：
```bash
python3 tools/safe_edit.py <file_path>
```

**风险等级**：
- 🔴 HIGH：核心模块（analysis/*, report/*）修改
- 🟡 MEDIUM：配置文件、工具脚本修改
- 🟢 LOW：文档、注释修改

### 自动回滚机制

**工作流程**：
```bash
python -m pytest tests/
if [ $? -ne 0 ]; then
    git reset --hard HEAD~1
fi
```

---

## 六、自动调整机制

### 数据源自动故障转移：tools/auto_failover.py

**功能**：主数据源连续失败≥N 次时，自动切换到备用数据源

**使用方法**：
```python
from tools.auto_failover import auto_failover

@auto_failover(max_failures=3, key="valuation_api")
def fetch_valuation_data(*args, **kwargs):
    """主数据源"""
    # ...

def fetch_valuation_fallback(*args, **kwargs):
    """备用数据源"""
    # ...

# 调用（自动故障转移）
result = fetch_valuation_data(fallback_func=fetch_valuation_fallback)
```

### 模块性能监控

**功能**：在 `Harness.execute()` 中自动监控执行时间，超过阈值（60秒）自动告警

**配置**：
```python
harness = Harness(
    name="my_module",
    config={"perf_monitor": True}  # 启用性能监控（默认启用）
)
```

**告警**：超过阈值时自动记录到 `ERRORS.md`

### 规则自动提升：tools/rule_promotion.py

**功能**：监控规则使用频率，≥3 次使用自动提升到 `00-CORE-PRINCIPLES.md`

**使用方法**：
```bash
python3 tools/rule_promotion.py
```

---

## 七、最佳实践指南

### 1. 添加新模块

**步骤**：
1. 创建模块目录（如 `my_module/`）
2. 创建 `__init__.py`，定义 `MyModule(BaseModule)` 类
3. 实现 `get_metadata()`、`get_steps()`、`validate_config()`、`run()` 方法
4. 在文件末尾添加自注册代码：
   ```python
   from tools.harness.module_registry import register_module
   register_module(MyModule())
   ```
5. 运行 `initialize()` 验证自动发现

### 2. 接入新数据源

**步骤**：
1. 调研免费稳定的数据源（打印结果）
2. 分析对比（稳定性、完整性、响应速度）
3. 询问用户选择
4. 接入选定的数据源
5. 使用 `auto_failover` 装饰器添加故障转移

**禁止事项**：
- ❌ 不经调研直接接入新数据源
- ❌ 同一数据超过 2 个数据源
- ❌ 忽略数据源失效的根因排查

### 3. 修改核心功能

**步骤**：
1. 运行 `python3 tools/safe_edit.py <file_path>` 分析影响
2. 根据风险等级决定是否需要测试
3. 创建 Git 分支：`git checkout -b ai-edit-<timestamp>`
4. 进行修改
5. 运行测试：`python -m pytest tests/ -v`
6. 测试通过后合并分支

### 4. 记录学习内容

**触发场景**：
1. 命令/操作失败 → `ERRORS.md`
2. 被用户纠正 → `LEARNINGS.md`（类别：correction）
3. 用户需要缺失功能 → `FEATURE_REQUESTS.md`
4. 发现知识过时 → `LEARNINGS.md`（类别：knowledge_gap）
5. 发现更好方法 → `LEARNINGS.md`（类别：best_practice）

**每周清理**：
```bash
python3 tools/memory_refiner.py
```

---

## 八、故障排查

### 问题1：模块自动发现失败

**现象**：`initialize()` 后，`registry.list_modules()` 返回空列表

**解决方法**：
1. 检查模块目录是否有 `__init__.py`
2. 检查 `__init__.py` 中是否有自注册代码
3. 手动运行 `register_module(MyModule())`

### 问题2：性能告警频繁

**现象**：`ERRORS.md` 中频繁出现性能告警

**解决方法**：
1. 检查是否是数据源响应慢
2. 添加缓存机制
3. 调整性能阈值（`Harness.PERFORMANCE_THRESHOLD`）

### 问题3：规则自动提升不工作

**现象**：规则使用次数达到 3 次，但未提升到核心原则

**解决方法**：
1. 检查 `rule_promotion.json` 是否存在
2. 手动运行 `python3 tools/rule_promotion.py`
3. 检查规则名称是否匹配

---

## 九、总结

本项目治理体系提供了一套完整的项目管理最佳实践，包括：
- ✅ 工作空间自动清理
- ✅ 模块化架构（可扩展 + 自注册）
- ✅ 规则与记忆系统（精简 + 分层 + 自动提升）
- ✅ 代码安全网（Git 分支策略 + 修改影响分析 + 自动回滚）
- ✅ 自动调整机制（规则提升 + 数据源故障转移 + 性能监控）

**下一步**：
1. 为现有模块添加单元测试
2. 完善性能监控细节（每个步骤的执行时间）
3. 扩展规则自动提升功能（支持更多规则类型）
