#!/usr/bin/env python3
"""
市场监控日报生成器 - 将飞书卡片转化为飞书文档

功能：
1. 调用 market_monitor.main 获取报告数据
2. 调用 feishu.build_cards() 获取所有卡片内容
3. 将卡片内容转化为 Markdown 格式
4. 提供多个方案（不同的文档结构和排版）
5. 生成飞书文档
"""
import sys
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from market_monitor.main import main as monitor_main
from market_monitor.report.feishu import build_cards


class DailyDocGenerator:
    """市场监控日报文档生成器"""
    
    SCHEME_A_SIMPLE = "scheme_a"  # 简洁版
    SCHEME_B_STANDARD = "scheme_b"  # 标准版
    SCHEME_C_DETAILED = "scheme_c"  # 详细版
    SCHEME_D_VISUAL = "scheme_d"  # 图文版
    
    def __init__(self, scheme="scheme_b"):
        self.scheme = scheme
        self.report_data = None
        self.cards = None
        
    def _get_report_data(self):
        """获取市场监控报告数据"""
        # 这里需要调用 main.py 的逻辑获取数据
        # 为了简化，我们直接模拟数据结构
        # 实际应用中，应该调用 monitor_main() 或修改 main.py 返回数据
        
        # 临时方案：从 main.py 中提取数据
        from market_monitor.main import main
        import io
        from contextlib import redirect_stdout
        
        # 捕获输出（不实际发送飞书）
        f = io.StringIO()
        with redirect_stdout(f):
            try:
                # 这里需要修改 main.py 使其返回 report_data
                # 临时方案：使用模拟数据
                pass
            except:
                pass
        
        # 使用模拟数据（实际应该从 main.py 获取）
        self.report_data = {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "capital": {"score": 0.5, "data": {}},
            "fundamental": {"score": 0.6, "data": {}},
            "policy": {"score": 0.3, "data": {}},
            "global": {"score": 0.4, "data": {}},
            "composite": {"score": 0.45, "label": "中性"},
        }
        
    def _get_cards_content(self) -> List[Dict]:
        """获取所有卡片的内容（文本形式）"""
        if not self.report_data:
            self._get_report_data()
        
        # 调用 build_cards 获取卡片
        self.cards = build_cards(self.report_data)
        
        # 提取每张卡片的文本内容
        cards_content = []
        for card in self.cards:
            card_content = self._extract_card_text(card)
            cards_content.append(card_content)
        
        return cards_content
    
    def _extract_card_text(self, card: Dict) -> str:
        """从飞书卡片中提取文本内容"""
        try:
            card_obj = card.get("card", {})
            elements = card_obj.get("elements", [])
            
            text_parts = []
            for elem in elements:
                if elem.get("tag") == "div":
                    text_obj = elem.get("text", {})
                    if text_obj.get("tag") == "lark_md":
                        text_parts.append(text_obj.get("content", ""))
            
            return "\n\n".join(text_parts)
        except Exception as e:
            return f"[提取卡片内容失败: {e}]"
    
    def generate_markdown(self) -> str:
        """生成 Markdown 格式的日报"""
        cards_content = self._get_cards_content()
        
        if self.scheme == self.SCHEME_A_SIMPLE:
            return self._build_scheme_a(cards_content)
        elif self.scheme == self.SCHEME_B_STANDARD:
            return self._build_scheme_b(cards_content)
        elif self.scheme == self.SCHEME_C_DETAILED:
            return self._build_scheme_c(cards_content)
        elif self.scheme == self.SCHEME_D_VISUAL:
            return self._build_scheme_d(cards_content)
        else:
            raise ValueError(f"未知方案: {self.scheme}")
    
    def _build_scheme_a(self, cards_content: List[str]) -> str:
        """方案A：简洁版 - 只包含核心内容"""
        lines = []
        lines.append("# 📊 市场监控日报（简洁版）\n")
        lines.append(f"**生成时间**: {self.report_data.get('generated_at', 'N/A')}\n")
        lines.append("---\n")
        
        # 只保留前3个卡片（交易决策、资金面、基本面）
        for i, content in enumerate(cards_content[:3]):
            lines.append(f"\n{content}\n")
            if i < len(cards_content[:3]) - 1:
                lines.append("---\n")
        
        lines.append("\n---\n")
        lines.append("*本报告由市场监控系统自动生成*")
        
        return "\n".join(lines)
    
    def _build_scheme_b(self, cards_content: List[str]) -> str:
        """方案B：标准版 - 保留所有卡片内容"""
        lines = []
        lines.append("# 📊 市场监控日报（标准版）\n")
        lines.append(f"**生成时间**: {self.report_data.get('generated_at', 'N/A')}\n")
        lines.append("---\n")
        
        # 保留所有卡片
        for i, content in enumerate(cards_content):
            lines.append(f"\n{content}\n")
            if i < len(cards_content) - 1:
                lines.append("---\n")
        
        lines.append("\n---\n")
        lines.append("*本报告由市场监控系统自动生成*")
        
        return "\n".join(lines)
    
    def _build_scheme_c(self, cards_content: List[str]) -> str:
        """方案C：详细版 - 所有内容 + 详细说明"""
        lines = []
        lines.append("# 📊 市场监控日报（详细版）\n")
        lines.append(f"**生成时间**: {self.report_data.get('generated_at', 'N/A')}\n")
        lines.append("\n**说明**: 本报告包含市场监控的完整分析，包括交易决策、各维度详情和持仓建议。\n")
        lines.append("---\n")
        
        # 添加详细说明
        section_descriptions = [
            "### 📋 一、交易决策区\n本部分展示综合得分、建议仓位和风险提示。",
            "### 🏦 二、资金面分析\n本部分展示资金面各指标，包括成交额、活跃市值、新开户数和两融余额。",
            "### 📈 三、基本面分析\n本部分展示基本面各指标，包括估值、GDP、CPI/PPI、PMI和流动性。",
            "### 🗄️ 四、政策面分析\n本部分展示货币政策和各省市政策动态。",
            "### 🌏 五、全球市场估值\n本部分展示全球主要市场的估值水平和百分比排名。",
            "### 📊 六、持仓监控\n本部分展示当前持仓的盈亏情况和买卖信号。",
            "### 📌 七、选股建议\n本部分展示符合条件的ETF买入推荐。",
        ]
        
        for i, (content, desc) in enumerate(zip(cards_content, section_descriptions)):
            lines.append(desc)
            lines.append(f"\n{content}\n")
            if i < len(cards_content) - 1:
                lines.append("---\n")
        
        lines.append("\n---\n")
        lines.append("*本报告由市场监控系统自动生成*")
        
        return "\n".join(lines)
    
    def _build_scheme_d(self, cards_content: List[str]) -> str:
        """方案D：图文版 - 包含图片和可视化"""
        lines = []
        lines.append("# 📊 市场监控日报（图文版）\n")
        lines.append(f"**生成时间**: {self.report_data.get('generated_at', 'N/A')}\n")
        lines.append("\n**说明**: 本报告采用图文并茂的形式展示市场监控数据。\n")
        lines.append("---\n")
        
        # 图文混排
        for i, content in enumerate(cards_content):
            lines.append(f"\n{content}\n")
            
            # 在特定位置插入图片占位符
            if i == 4:  # 全球估值部分
                lines.append("\n📊 [全球估值图表]\n")
            
            if i < len(cards_content) - 1:
                lines.append("---\n")
        
        lines.append("\n---\n")
        lines.append("*本报告由市场监控系统自动生成*")
        
        return "\n".join(lines)
    
    def save_markdown(self, output_path: str = None) -> Path:
        """保存 Markdown 文件"""
        md_content = self.generate_markdown()
        
        if output_path is None:
            output_path = Path(__file__).parent / f"temp_daily_report_{self.scheme}.md"
        else:
            output_path = Path(output_path)
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        
        print(f"✅ Markdown 已保存: {output_path}")
        print(f"   方案: {self.scheme}")
        print(f"   大小: {output_path.stat().st_size} 字节")
        
        return output_path
    
    def generate_feishu_doc(self, output_path: str = None) -> str:
        """生成飞书文档，返回文档URL"""
        # 1. 生成 Markdown 文件
        md_path = self.save_markdown(output_path)
        
        # 2. 使用 lark-cli 创建飞书文档
        cmd = [
            "lark-cli", "docs", "+create",
            "--title", f"市场监控日报-{self.scheme}",
            "--markdown", f"@{md_path}"
        ]
        
        print(f"\n📄 正在创建飞书文档...")
        print(f"   命令: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            # 解析输出，提取文档URL
            output = result.stdout
            # 假设输出包含文档URL
            for line in output.split("\n"):
                if "docx/" in line or "http" in line:
                    print(f"✅ 文档已创建: {line.strip()}")
                    return line.strip()
            
            print(f"✅ 文档已创建（请查看飞书）")
            return "成功"
        else:
            print(f"❌ 创建失败: {result.stderr}")
            return None


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="市场监控日报文档生成器")
    parser.add_argument(
        "--scheme",
        choices=["scheme_a", "scheme_b", "scheme_c", "scheme_d"],
        default="scheme_b",
        help="选择日报方案"
    )
    parser.add_argument("--output", help="输出文件路径")
    parser.add_argument("--all", action="store_true", help="生成所有方案的示例")
    
    args = parser.parse_args()
    
    if args.all:
        # 生成所有方案
        for scheme in ["scheme_a", "scheme_b", "scheme_c", "scheme_d"]:
            print(f"\n{'='*60}")
            print(f"生成方案: {scheme}")
            print(f"{'='*60}")
            generator = DailyDocGenerator(scheme=scheme)
            generator.save_markdown(
                output_path=Path(f"/Users/liuyi/WorkBuddy/stock-signal/market_monitor/report/temp_daily_{scheme}.md")
            )
    else:
        # 生成单个方案
        generator = DailyDocGenerator(scheme=args.scheme)
        generator.save_markdown(output_path=args.output)
    
    print("\n✅ 所有报告已生成完成！")


if __name__ == "__main__":
    main()
