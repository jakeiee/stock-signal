# 模块开发规范

## 标准模块接口

所有模块必须实现 `BaseModule` 接口：

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

## 模块自注册机制

模块必须使用 `ModuleRegistry` 自注册：

```python
from tools.harness.module_registry import ModuleRegistry

registry = ModuleRegistry()
registry.register(MyModule())
```

## 步骤化设计

模块必须实现为多个 `Step`，每个 Step 负责一个独立任务：

```python
class MyStep(Step):
    def execute(self, context: Dict[str, Any]) -> StepResult:
        # 执行逻辑
        return StepResult(success=True, data=...)
```

## 独立可测

每个模块必须包含独立的测试文件：

```
my_module/
├── __init__.py
├── main.py
├── analysis.py
├── report.py
└── tests/
    ├── test_main.py
    ├── test_analysis.py
    └── test_report.py
```

## 技术实现规范

### Python代码规范
- 使用类型注解（Type Hints）
- 函数文档字符串遵循 Google 风格
- 异常处理要有明确的错误信息
- 关键操作要添加日志输出

### 数据缓存策略
- 估值数据缓存到 `valuation_cache.json`
- 缓存有效期：1天
- 缓存命中时直接使用，不消耗API配额
- 配额用尽时降级到缓存或自算

### API调用规范
- 使用重试机制（最多3次）
- 捕获配额用尽错误（status=113）
- 超时设置：10秒
- 失败时提供降级方案

### KDJ算法规范
- 使用标准参数：KDJ(9,3,3)
- 日线 → 周线重采样：`pandas resample('W-FRI')`
- RSV = (close - min_low_9w) / (max_high_9w - min_low_9w) × 100
- K = 2/3 × prev_K + 1/3 × RSV（初值50）
- D = 2/3 × prev_D + 1/3 × K（初值50）
- J = 3K - 2D
