"""
Harness 规则执行引擎

与 .codebuddy/rules/ 目录集成，支持规则检查和执行。
"""

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
import re

from .context import ExecutionContext


class Rule:
    """
    规则定义

    表示一个可执行的规则条件。
    """

    def __init__(
        self,
        name: str,
        condition: Callable[[ExecutionContext], bool],
        action: Optional[Callable[[ExecutionContext], Any]] = None,
        description: str = "",
        severity: str = "warning",  # info, warning, error
    ):
        self.name = name
        self.condition = condition
        self.action = action
        self.description = description
        self.severity = severity

    def evaluate(self, context: ExecutionContext) -> Tuple[bool, Optional[Any]]:
        """
        评估规则

        Args:
            context: 执行上下文

        Returns:
            (是否通过, 执行结果)
        """
        try:
            passed = self.condition(context)
            result = None

            if passed and self.action:
                result = self.action(context)

            return passed, result

        except Exception as e:
            context.error(f"Rule '{self.name}' evaluation failed: {str(e)}")
            return False, None

    def __repr__(self) -> str:
        return f"<Rule name='{self.name}' severity='{self.severity}'>"


class RuleEngine:
    """
    规则引擎

    管理规则注册、评估和执行。
    """

    def __init__(self):
        self._rules: List[Rule] = []
        self._rule_files_dir: Optional[Path] = None

    def add_rule(self, rule: Rule) -> 'RuleEngine':
        """添加规则"""
        self._rules.append(rule)
        return self

    def remove_rule(self, name: str) -> bool:
        """移除规则"""
        for i, rule in enumerate(self._rules):
            if rule.name == name:
                self._rules.pop(i)
                return True
        return False

    def get_rule(self, name: str) -> Optional[Rule]:
        """获取规则"""
        for rule in self._rules:
            if rule.name == name:
                return rule
        return None

    def load_rules_from_dir(self, rules_dir: str) -> int:
        """
        从目录加载规则文件

        Args:
            rules_dir: 规则目录路径

        Returns:
            加载的规则数量
        """
        self._rule_files_dir = Path(rules_dir)
        count = 0

        if not self._rule_files_dir.exists():
            return 0

        for md_file in self._rule_files_dir.glob("*.md"):
            count += self._load_rule_file(md_file)

        return count

    def _load_rule_file(self, file_path: Path) -> int:
        """加载单个规则文件"""
        content = file_path.read_text(encoding="utf-8")
        count = 0

        # 简单的规则解析
        # 格式: ## rule:name
        #       描述...
        #       ```
        #       condition: ...
        #       ```

        pattern = r"## rule:(\w+)\s*\n(.*?)\n```(?:python)?\n(.*?)```"

        for match in re.finditer(pattern, content, re.DOTALL):
            name = match.group(1)
            description = match.group(2).strip()
            code = match.group(3).strip()

            # 创建规则
            rule = self._create_rule_from_code(name, description, code)
            if rule:
                self._rules.append(rule)
                count += 1

        return count

    def _create_rule_from_code(
        self,
        name: str,
        description: str,
        code: str,
    ) -> Optional[Rule]:
        """从代码字符串创建规则"""
        try:
            # 构建条件函数
            local_vars = {}

            # 添加 context 变量
            exec_globals = {"__builtins__": {}}

            # 解析 condition
            if "condition:" in code:
                condition_code = code.split("condition:")[1].split("\n")[0].strip()
                condition_func = eval(f"lambda context: {condition_code}", exec_globals, local_vars)
            else:
                condition_func = lambda ctx: True

            # 解析 action（如果有）
            action_func = None
            if "action:" in code:
                action_code = code.split("action:")[1].strip()
                action_func = eval(f"lambda context: {action_code}", exec_globals, local_vars)

            return Rule(
                name=name,
                condition=condition_func,
                action=action_func,
                description=description,
            )

        except Exception:
            return None

    def evaluate_all(
        self,
        context: ExecutionContext,
        stop_on_error: bool = False,
    ) -> Dict[str, Any]:
        """
        评估所有规则

        Args:
            context: 执行上下文
            stop_on_error: 遇到错误是否停止

        Returns:
            评估结果
        """
        results = {
            "passed": [],
            "failed": [],
            "errors": [],
        }

        for rule in self._rules:
            try:
                passed, result = rule.evaluate(context)

                if passed:
                    results["passed"].append({
                        "rule": rule.name,
                        "result": result,
                        "severity": rule.severity,
                    })
                else:
                    results["failed"].append({
                        "rule": rule.name,
                        "severity": rule.severity,
                        "description": rule.description,
                    })

            except Exception as e:
                if stop_on_error:
                    raise
                results["errors"].append({
                    "rule": rule.name,
                    "error": str(e),
                })

        return results

    def check_preconditions(self, context: ExecutionContext) -> Tuple[bool, List[str]]:
        """
        检查前置条件

        Args:
            context: 执行上下文

        Returns:
            (是否通过, 失败信息列表)
        """
        violations = []

        for rule in self._rules:
            if "precondition" in rule.name.lower():
                passed, _ = rule.evaluate(context)
                if not passed:
                    violations.append(rule.description)

        return len(violations) == 0, violations

    def check_postconditions(self, context: ExecutionContext) -> Tuple[bool, List[str]]:
        """
        检查后置条件

        Args:
            context: 执行上下文

        Returns:
            (是否通过, 失败信息列表)
        """
        violations = []

        for rule in self._rules:
            if "postcondition" in rule.name.lower():
                passed, _ = rule.evaluate(context)
                if not passed:
                    violations.append(rule.description)

        return len(violations) == 0, violations

    @property
    def rules(self) -> List[Rule]:
        """获取所有规则"""
        return self._rules.copy()

    def __len__(self) -> int:
        return len(self._rules)


# 预定义规则工厂函数

def rule_name_exists(field_name: str, data_key: str) -> Rule:
    """
    规则：检查数据中是否存在指定字段

    Args:
        field_name: 字段名称（用于规则名）
        data_key: 上下文数据键名

    Returns:
        Rule 实例
    """
    return Rule(
        name=f"data_{field_name}_exists",
        condition=lambda ctx: ctx.has(data_key),
        description=f"数据中必须包含 '{data_key}' 字段",
        severity="error",
    )


def rule_value_in_range(
    data_key: str,
    min_val: float,
    max_val: float,
) -> Rule:
    """
    规则：检查数值是否在指定范围内

    Args:
        data_key: 上下文数据键名
        min_val: 最小值
        max_val: 最大值

    Returns:
        Rule 实例
    """
    return Rule(
        name=f"value_in_range_{data_key}",
        condition=lambda ctx: (
            ctx.has(data_key) and
            min_val <= ctx.get(data_key) <= max_val
        ),
        description=f"'{data_key}' 值必须在 {min_val} 到 {max_val} 之间",
        severity="warning",
    )


def rule_step_succeeded(step_name: str) -> Rule:
    """
    规则：检查指定步骤是否成功执行

    Args:
        step_name: 步骤名称

    Returns:
        Rule 实例
    """
    return Rule(
        name=f"step_{step_name}_succeeded",
        condition=lambda ctx: (
            ctx.get_step_result(step_name) is not None and
            ctx.get_step_result(step_name).status == "success"
        ),
        description=f"步骤 '{step_name}' 必须成功执行",
        severity="error",
    )
