# 代码安全规范

## Git分支策略

### 修改前自动创建分支

```bash
# 修改前自动执行
git checkout -b ai-edit-$(date +%Y%m%d-%H%M%S)
```

### 修改后等待用户确认再合并

```bash
# 测试通过后
git checkout main
git merge ai-edit-xxx
```

## 修改影响分析

### 使用 `tools/safe_edit.py` 分析修改影响

```bash
python tools/safe_edit.py --file path/to/file.py
```

### 风险等级评估

- **HIGH**：核心模块（analysis/*, report/*）修改
- **MEDIUM**：配置文件、工具脚本修改
- **LOW**：文档、注释修改

### 核心模块修改必须测试

```
修改 analysis/* 或 report/* → 必须运行测试 → 测试通过才能合并
```

## 自动回滚机制

### 测试失败时自动回滚

```bash
python -m pytest tests/
if [ $? -ne 0 ]; then
    git reset --hard HEAD~1
fi
```

## 代码修改安全铁律

1. **修改前必读**：先读取完整文件内容
2. **单次修改≤100行**：大改动分批进行
3. **核心功能保护**：修改 analysis/*, report/* 必须先测试
4. **Git安全网**：重要修改前创建分支

## 用户偏好设置

代码修改时需要打印：
1. 涉及修改代码的原数据
2. 数据加工步骤
3. 输出结果

方便用户查验和追溯。
