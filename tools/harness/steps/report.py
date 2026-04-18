"""
预定义报告步骤

封装报告生成和发送逻辑。
"""

from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from pathlib import Path

from ..step import Step, StepConfig
from ..context import ExecutionContext


class ReportStep(Step):
    """
    通用报告生成步骤

    根据上下文数据生成报告。
    """

    name = "generate_report"

    def __init__(
        self,
        template: Optional[str] = None,
        output_key: str = "report",
        output_path: Optional[str] = None,
        format_func: Optional[Callable[[ExecutionContext], str]] = None,
        config: Optional[StepConfig] = None,
    ):
        """
        Args:
            template: 报告模板字符串
            output_key: 报告存储的上下文键名
            output_path: 报告输出文件路径
            format_func: 自定义格式化函数
        """
        super().__init__(config)
        self.template = template
        self.output_key = output_key
        self.output_path = output_path
        self.format_func = format_func

    def validate(self) -> bool:
        return self.template is not None or self.format_func is not None

    def execute(self, context: ExecutionContext) -> str:
        """生成报告"""
        # 生成报告内容
        if self.format_func:
            content = self.format_func(context)
        else:
            content = self._format_from_template(context)

        # 保存到上下文
        context.set(self.output_key, content)

        # 保存到文件
        if self.output_path:
            Path(self.output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(self.output_path).write_text(content, encoding="utf-8")
            context.info(f"Report saved to: {self.output_path}")

        return content

    def _format_from_template(self, context: ExecutionContext) -> str:
        """使用模板格式化报告"""
        # 简单模板替换
        content = self.template

        # 替换基本变量
        content = content.replace("{{name}}", context.name)
        content = content.replace("{{date}}", datetime.now().strftime("%Y-%m-%d"))
        content = content.replace("{{time}}", datetime.now().strftime("%H:%M:%S"))

        # 替换数据变量
        for key, value in context.data.items():
            placeholder = f"{{{{data.{key}}}}}"
            if placeholder in content:
                content = content.replace(placeholder, str(value))

        # 替换步骤结果变量
        results = context.step_results
        for name, result in results.items():
            placeholder = f"{{{{step.{name}.status}}}}"
            if placeholder in content:
                content = content.replace(placeholder, result.status)

        return content


class FeishuReportStep(Step):
    """
    飞书报告发送步骤

    生成并发送报告到飞书。
    """

    name = "send_feishu_report"

    def __init__(
        self,
        webhook_url: str,
        content_key: str = "report",
        title: str = "监控报告",
        message_type: str = "interactive",
        config: Optional[StepConfig] = None,
    ):
        """
        Args:
            webhook_url: 飞书机器人 Webhook URL
            content_key: 报告内容的上下文键名
            title: 报告标题
            message_type: 消息类型 (text, interactive)
        """
        super().__init__(config)
        self.webhook_url = webhook_url
        self.content_key = content_key
        self.title = title
        self.message_type = message_type

    def validate(self) -> bool:
        return bool(self.webhook_url)

    def execute(self, context: ExecutionContext) -> Dict[str, Any]:
        """发送飞书报告"""
        import requests

        content = context.get(self.content_key)
        if content is None:
            raise ValueError(f"No content found at key: {self.content_key}")

        # 构建消息
        if self.message_type == "text":
            payload = self._build_text_message(content)
        else:
            payload = self._build_card_message(content)

        # 发送请求
        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30,
            )

            result = {
                "success": response.status_code == 200,
                "status_code": response.status_code,
                "response": response.text,
            }

            context.set("feishu_send_result", result)
            return result

        except Exception as e:
            context.error(f"Failed to send Feishu message: {str(e)}")
            raise

    def _build_text_message(self, content: str) -> Dict[str, Any]:
        """构建文本消息"""
        return {
            "msg_type": "text",
            "content": {
                "text": content,
            },
        }

    def _build_card_message(self, content: str) -> Dict[str, Any]:
        """构建卡片消息"""
        return {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": self.title,
                    },
                    "template": "blue",
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": content,
                        },
                    },
                ],
            },
        }


class MarkdownReportStep(ReportStep):
    """
    Markdown 报告生成步骤

    生成格式化的 Markdown 报告。
    """

    name = "generate_markdown_report"

    def __init__(
        self,
        output_path: Optional[str] = None,
        title: str = "监控报告",
        sections: Optional[List[Dict[str, str]]] = None,
        config: Optional[StepConfig] = None,
    ):
        """
        Args:
            output_path: 报告输出路径
            title: 报告标题
            sections: 报告章节列表 [{"title": "", "content_key": ""}]
        """
        super().__init__(output_path=output_path, config=config)
        self.title = title
        self.sections = sections or []

    def execute(self, context: ExecutionContext) -> str:
        """生成 Markdown 报告"""
        lines = []

        # 标题
        lines.append(f"# {self.title}\n")
        lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        lines.append(f"**执行名称**: {context.name}\n")
        lines.append("---\n")

        # 执行摘要
        lines.append("## 执行摘要\n")
        lines.append(f"- **状态**: {context.status.value}")
        lines.append(f"- **总步骤数**: {len(context.step_results)}")
        lines.append(f"- **成功**: {sum(1 for r in context.step_results.values() if r.status == 'success')}")
        lines.append(f"- **失败**: {sum(1 for r in context.step_results.values() if r.status == 'failed')}")
        lines.append(f"- **耗时**: {context.duration:.2f}秒\n")

        # 步骤详情
        lines.append("## 步骤详情\n")
        for name, result in context.step_results.items():
            status_icon = "✅" if result.status == "success" else "❌" if result.status == "failed" else "⏭️"
            lines.append(f"### {status_icon} {name}\n")
            lines.append(f"- **状态**: {result.status}")
            lines.append(f"- **耗时**: {result.duration:.2f}秒")
            if result.error:
                lines.append(f"- **错误**: {result.error}")
            if result.output:
                lines.append(f"- **输出**: {result.output}")
            lines.append("")

        # 数据摘要
        if context.data:
            lines.append("## 数据摘要\n")
            for key, value in context.data.items():
                if not key.startswith("_"):  # 跳过内部数据
                    lines.append(f"- **{key}**: {value}")
            lines.append("")

        # 日志摘要
        if context.logs:
            lines.append("## 日志摘要\n")
            error_logs = [l for l in context.logs if l["level"] == "ERROR"]
            if error_logs:
                lines.append("### 错误日志\n")
                for log in error_logs[-5:]:  # 只显示最后5条
                    lines.append(f"- [{log['timestamp']}] {log['message']}")
            lines.append("")

        content = "\n".join(lines)

        # 保存
        context.set(self.output_key or "report", content)
        if self.output_path:
            Path(self.output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(self.output_path).write_text(content, encoding="utf-8")
            context.info(f"Markdown report saved to: {self.output_path}")

        return content
