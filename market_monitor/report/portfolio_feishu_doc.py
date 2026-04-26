#!/usr/bin/env python3
"""
持仓ETF分析报告 - 飞书原生组件版

支持多种方案展示技术分析数据：
- 方案1: 表格+高亮框+分栏布局（XML原生组件）
- 方案2: 嵌入电子表格（Sheet）
- 方案3: 嵌入多维表格（Bitable）
- 方案4: Mermaid图表可视化

使用方法：
    python3 market_monitor/report/portfolio_feishu_doc.py --mode xml
    python3 market_monitor/report/portfolio_feishu_doc.py --mode sheet
    python3 market_monitor/report/portfolio_feishu_doc.py --mode bitable
    python3 market_monitor/report/portfolio_feishu_doc.py --mode mermaid
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import json
import argparse
from datetime import datetime, timezone, timedelta
from typing import Dict, List

from market_monitor.report.portfolio_analyzer import ETF_MAPPING, analyze_etf


# ── 飞书文档生成器基类 ────────────────────────────────────────────────────────

class FeishuDocGenerator:
    """飞书文档生成器基类"""

    def __init__(self, results: List[Dict], title: str = "持仓ETF分析报告"):
        self.results = results
        self.title = title
        beijing_tz = timezone(timedelta(hours=8))
        self.now = datetime.now(beijing_tz).strftime("%Y-%m-%d %H:%M")

    def generate(self) -> str:
        """生成文档内容（子类实现）"""
        raise NotImplementedError

    def create_doc(self, content: str = None) -> tuple:
        """创建飞书文档"""
        import subprocess

        if content is None:
            content = self.generate()

        # 保存到当前目录的临时文件
        temp_path = './feishu_doc_temp.xml'
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                f.write(content)

            # 调用 lark-cli 创建文档
            result = subprocess.run(
                ['lark-cli', 'docs', '+create',
                 '--api-version', 'v2',
                 '--content', f'@{temp_path}'],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                import json
                output = json.loads(result.stdout)
                if output.get('ok'):
                    data = output.get('data', {})
                    doc_id = data.get('doc_id', '')
                    doc_url = data.get('doc_url', '')
                    print(f"✅ 飞书文档已创建: {doc_url}")
                    return doc_id, doc_url

            print(f"⚠ 创建文档失败: {result.stderr}")
            return None, None

        except Exception as e:
            print(f"⚠ 创建飞书文档出错: {e}")
            return None, None
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


# ── 方案1: XML原生组件版 ─────────────────────────────────────────────────────

class XMLDocGenerator(FeishuDocGenerator):
    """
    方案1：表格+高亮框+分栏布局
    使用飞书原生XML组件：表格、高亮框、分栏、进度条
    """

    def _escape_text(self, text: str) -> str:
        """转义XML特殊字符"""
        if not text:
            return ""
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;'))

    def _get_signal_emoji(self, sig: str) -> str:
        """获取信号emoji"""
        return {"STRONG": "🟢", "WATCH": "🟡", "DANGER": "🔴"}.get(sig, "⚪")

    def _get_action_short(self, r: dict) -> str:
        """获取操作建议"""
        sig = r.get("signal", "")
        rsi = r.get("rsi14", 50)
        pos = r.get("price_pos_60d", 50)

        if sig == "STRONG":
            if rsi > 70:
                return "持有/减仓"
            elif rsi < 30:
                return "加仓机会"
            return "持有"
        elif sig == "WATCH":
            if rsi < 30:
                return "关注"
            return "观望"
        else:
            if rsi < 30:
                return "等待"
            elif pos < 40:
                return "关注"
            return "减仓"

    def _build_summary_blocks(self) -> str:
        """构建汇总区块"""
        total = len(self.results)
        avg_score = sum(r.get("pattern_score", 0) for r in self.results) / total if total else 0

        strong = [r for r in self.results if r.get("signal") == "STRONG"]
        watch = [r for r in self.results if r.get("signal") == "WATCH"]
        danger = [r for r in self.results if r.get("signal") == "DANGER"]

        # 概览高亮框
        blocks = f"""
<callout emoji="📊" background-color="light-blue" border-color="blue">
  <p><b>持仓概览</b></p>
  <p>持仓数量: <b>{total}</b> 只ETF | 平均评分: <b>{avg_score:.0f}</b>/100</p>
</callout>

<h2>信号分布</h2>

<table>
  <colgroup><col span="1" width="150"/><col span="1" width="150"/><col span="1" width="150"/></colgroup>
  <thead><tr>
    <th background-color="green"><b><span text-color="white">🟢 强势 ({len(strong)})</span></b></th>
    <th background-color="yellow"><b><span text-color="gray">🟡 观望 ({len(watch)})</span></b></th>
    <th background-color="red"><b><span text-color="white">🔴 危险 ({len(danger)})</span></b></th>
  </tr></thead>
</table>
"""
        return blocks

    def _build_detail_table(self) -> str:
        """构建持仓明细表格"""
        sorted_results = sorted(self.results, key=lambda x: x.get("pattern_score", 0), reverse=True)

        rows = ""
        for r in sorted_results:
            name = self._escape_text(r.get('etf_name', '')[:10])
            index = self._escape_text(r.get('index_name', '')[:8])
            sig = r.get("signal", "")
            sig_emoji = self._get_signal_emoji(sig)
            score = r.get("pattern_score", 0)
            rsi = r.get("rsi14", 50)
            rsi_str = f"{rsi:.1f}"
            action = self._get_action_short(r)

            # 根据信号设置行背景色
            if sig == "STRONG":
                bg = "light-green"
            elif sig == "WATCH":
                bg = "light-yellow"
            else:
                bg = "light-red"

            rows += f"""
<tr>
  <td background-color="{bg}"><b>{name}</b></td>
  <td>{index}</td>
  <td>{sig_emoji} {sig}</td>
  <td><b>{score:.0f}</b></td>
  <td>{rsi_str}</td>
  <td>{action}</td>
</tr>"""

        return f"""
<h2>持仓明细</h2>

<table>
  <colgroup>
    <col span="1" width="120"/>
    <col span="1" width="100"/>
    <col span="1" width="80"/>
    <col span="1" width="60"/>
    <col span="1" width="60"/>
    <col span="1" width="80"/>
  </colgroup>
  <thead>
    <tr>
      <th background-color="gray"><b><span text-color="white">ETF名称</span></b></th>
      <th background-color="gray"><b><span text-color="white">跟踪指数</span></b></th>
      <th background-color="gray"><b><span text-color="white">信号</span></b></th>
      <th background-color="gray"><b><span text-color="white">评分</span></b></th>
      <th background-color="gray"><b><span text-color="white">RSI</span></b></th>
      <th background-color="gray"><b><span text-color="white">操作</span></b></th>
    </tr>
  </thead>
  <tbody>
    {rows}
  </tbody>
</table>
"""

    def _build_technical_details(self) -> str:
        """构建详细技术分析（分栏布局）"""
        sorted_results = sorted(self.results, key=lambda x: x.get("pattern_score", 0), reverse=True)

        blocks = "<h2>详细技术分析</h2>\n"

        # 每2个ETF一行分栏
        for i in range(0, len(sorted_results), 2):
            pair = sorted_results[i:i+2]

            blocks += "<grid>\n"

            for r in pair:
                name = self._escape_text(r.get('etf_name', ''))
                sig = r.get("signal", "")
                sig_emoji = self.get_signal_emoji(sig)
                score = r.get("pattern_score", 0)
                rsi = r.get("rsi14", 50)
                kdj_k = r.get("kdj_k", 0)
                macd_hist = r.get("macd_hist", 0)
                vol_ratio = r.get("vol_ratio", 1)
                price_pos = r.get("price_pos_60d", 50)
                action = self._get_action_short(r)

                macd_emoji = "🟢" if macd_hist > 0 else "🔴"
                pos_desc = "低位" if price_pos < 30 else ("高位" if price_pos > 70 else "中性")

                # 信号颜色
                if sig == "STRONG":
                    border_color = "green"
                    bg_color = "light-green"
                elif sig == "WATCH":
                    border_color = "yellow"
                    bg_color = "light-yellow"
                else:
                    border_color = "red"
                    bg_color = "light-red"

                blocks += f"""
  <column width-ratio="0.5">
    <callout emoji="{sig_emoji}" background-color="{bg_color}" border-color="{border_color}">
      <p><b>{name}</b></p>
      <p>评分: <b>{score:.0f}</b>/100 | {action}</p>
      <hr/>
      <p>RSI(14): <b>{rsi:.1f}</b></p>
      <p>KDJ(K): <b>{kdj_k:.1f}</b></p>
      <p>MACD柱: {macd_emoji} <b>{macd_hist:.4f}</b></p>
      <p>量比: <b>{vol_ratio:.2f}x</b></p>
      <p>60日位置: <b>{price_pos:.0f}%</b> ({pos_desc})</p>
    </callout>
  </column>
"""

            blocks += "</grid>\n\n"

        return blocks

    def _build_action_summary(self) -> str:
        """构建操作建议汇总"""
        strong = [r for r in self.results if r.get("signal") == "STRONG"]
        danger = [r for r in self.results if r.get("signal") == "DANGER"]
        oversold = [r for r in self.results if r.get("rsi14", 50) < 35]

        blocks = "<h2>操作建议</h2>\n"

        if strong:
            names = ", ".join([r.get('etf_name', '') for r in strong])
            blocks += f"""
<callout emoji="🟢" background-color="light-green" border-color="green">
  <p><b>重点关注（强势信号）</b></p>
  <p>{names}</p>
</callout>
"""

        if danger:
            blocks += "<h3>谨慎对待</h3>\n<ul>\n"
            for r in danger:
                action = self._get_action_short(r)
                blocks += f"<li>{r.get('etf_name', '')}: {action}</li>\n"
            blocks += "</ul>\n"

        if oversold:
            names = ", ".join([r.get('etf_name', '') for r in oversold])
            blocks += f"""
<callout emoji="💡" background-color="light-yellow" border-color="yellow">
  <p><b>超跌关注</b></p>
  <p>{names}</p>
</callout>
"""

        return blocks

    def get_signal_emoji(self, sig: str) -> str:
        return self._get_signal_emoji(sig)

    def generate(self) -> str:
        """生成XML文档"""
        content = f"""<title>{self.title}（原生组件版）</title>

<h1>📊 {self.title}</h1>
<p><i>生成时间: {self.now}</i></p>
<hr/>

{self._build_summary_blocks()}

{self._build_detail_table()}

{self._build_technical_details()}

{self._build_action_summary()}

<hr/>
<callout emoji="⚠️" background-color="light-gray" border-color="gray">
  <p><b>风险提示</b></p>
  <p>本报告仅供参考，不构成投资建议。市场有风险，投资需谨慎。</p>
</callout>
"""

        return content


# ── 方案2: 嵌入电子表格版 ───────────────────────────────────────────────────

class SheetDocGenerator(FeishuDocGenerator):
    """
    方案2：嵌入电子表格
    创建飞书电子表格作为数据源，文档嵌入表格引用
    """

    def create_sheet_and_doc(self) -> tuple:
        """创建电子表格并嵌入文档"""
        import subprocess

        # 1. 创建电子表格
        print("📊 正在创建电子表格...")

        date_str = datetime.now().strftime("%Y-%m-%d")
        sheet_title = f"持仓ETF分析_{date_str}"

        try:
            result = subprocess.run(
                ['lark-cli', 'sheets', '+create',
                 '--title', sheet_title],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                import json
                output = json.loads(result.stdout)
                if output.get('ok'):
                    sheet_data = output.get('data', {})
                    sheet_token = sheet_data.get('sheet_token', '')
                    sheet_url = sheet_data.get('sheet_url', '')
                    print(f"✅ 电子表格已创建: {sheet_url}")

                    # 写入数据到表格
                    self._write_to_sheet(sheet_token)

                    # 2. 创建嵌入表格的文档
                    content = self._build_doc_with_sheet(sheet_token, sheet_title)

                    doc_result = subprocess.run(
                        ['lark-cli', 'docs', '+create',
                         '--api-version', 'v2',
                         '--title', f"{self.title}（表格版）",
                         '--content', f'@/tmp/feishu_doc_content.xml'],
                        capture_output=True,
                        text=True,
                        timeout=60
                    )

                    if doc_result.returncode == 0:
                        doc_output = json.loads(doc_result.stdout)
                        if doc_output.get('ok'):
                            doc_data = doc_output.get('data', {})
                            doc_url = doc_data.get('doc_url', '')
                            return sheet_token, doc_url

            print(f"⚠ 创建失败: {result.stderr}")
            return None, None

        except Exception as e:
            print(f"⚠ 出错: {e}")
            return None, None

    def _write_to_sheet(self, sheet_token: str):
        """写入数据到电子表格"""
        # TODO: 使用 lark-sheets API 写入数据
        print(f"📝 数据将写入表格: {sheet_token}")

    def _build_doc_with_sheet(self, sheet_token: str, sheet_title: str) -> str:
        """构建嵌入电子表格的文档"""
        content = f"""<title>{self.title}（表格版）</title>

<h1>📊 {self.title}</h1>
<p><i>生成时间: {self.now}</i></p>
<hr/>

<h2>数据总览</h2>
<p>详细数据请查看嵌入的电子表格：</p>

<sheet token="{sheet_token}"></sheet>

<h2>分析说明</h2>
<callout emoji="📖" background-color="light-blue" border-color="blue">
  <p><b>表格字段说明</b></p>
  <p>• 信号: STRONG=强势, WATCH=观望, DANGER=危险</p>
  <p>• 评分: 0-100分，越高越好</p>
  <p>• RSI: &lt;30超卖，&gt;70超买</p>
  <p>• MACD柱: 正值=红柱(多方)，负值=绿柱(空方)</p>
</callout>

<hr/>
<callout emoji="⚠️" background-color="light-gray" border-color="gray">
  <p><b>风险提示</b></p>
  <p>本报告仅供参考，不构成投资建议。市场有风险，投资需谨慎。</p>
</callout>
"""
        return content

    def generate(self) -> str:
        """生成文档（调用 create_sheet_and_doc）"""
        return self.create_sheet_and_doc()[1]


# ── 方案3: Mermaid图表版 ─────────────────────────────────────────────────────

class MermaidDocGenerator(FeishuDocGenerator):
    """
    方案4：Mermaid图表可视化
    使用Mermaid图表展示信号分布、评分对比等
    """

    def _build_signal_pie_chart(self) -> str:
        """构建信号分布饼图"""
        strong = len([r for r in self.results if r.get("signal") == "STRONG"])
        watch = len([r for r in self.results if r.get("signal") == "WATCH"])
        danger = len([r for r in self.results if r.get("signal") == "DANGER"])

        return f"""
<h2>信号分布</h2>

<whiteboard type="mermaid">
pie showData
    "🟢 强势 ({strong})" : {strong}
    "🟡 观望 ({watch})" : {watch}
    "🔴 危险 ({danger})" : {danger}
</whiteboard>
"""

    def _build_score_bar_chart(self) -> str:
        """构建评分对比柱状图"""
        sorted_results = sorted(self.results, key=lambda x: x.get("pattern_score", 0), reverse=True)

        colors = {"STRONG": "green", "WATCH": "yellow", "DANGER": "red"}

        # 构建Mermaid数据
        chart_items = []
        for r in sorted_results[:5]:  # 最多5个
            name = r.get('etf_name', '')[:6]
            score = r.get("pattern_score", 0)
            sig = r.get("signal", "")
            color = colors.get(sig, "gray")
            height = max(int(score / 10), 1)
            chart_items.append(f'"{name} ({score:.0f})" "{color}" height={height}')

        chart_data = "\n        ".join(chart_items)

        mermaid = f"""
<h2>综合评分对比</h2>

<whiteboard type="mermaid">
block-beta
    columns 1
    block:chart
        {chart_data}
    end
</whiteboard>
"""
        return mermaid

    def _build_signal_flowchart(self) -> str:
        """构建信号分类流程图"""
        strong = [r.get('etf_name', '') for r in self.results if r.get("signal") == "STRONG"]
        watch = [r.get('etf_name', '') for r in self.results if r.get("signal") == "WATCH"]
        danger = [r.get('etf_name', '') for r in self.results if r.get("signal") == "DANGER"]

        flowchart = """
<h2>持仓信号分类</h2>

<whiteboard type="mermaid">
flowchart TD
    Start["📊 持仓分析"] --> Signal{信号判断}
    Signal -->|STRONG| Strong["🟢 强势标的"]
    Signal -->|WATCH| Watch["🟡 观望标的"]
    Signal -->|DANGER| Danger["🔴 危险标的"]

    Strong --> SA["持有/加仓"]
    Watch --> WA["观望/关注"]
    Danger --> DA{"RSI&lt;30?"}
    DA -->|是| DA1["等待企稳"]
    DA -->|否| DA2["减仓"]

    style Strong fill:#90EE90
    style Watch fill:#FFFACD
    style Danger fill:#FFB6C1
"""
        return flowchart

    def _build_radar_chart(self) -> str:
        """构建多维雷达图"""
        sorted_results = sorted(self.results, key=lambda x: x.get("pattern_score", 0), reverse=True)[:3]

        # 简化为雷达图
        return f"""
<h2>多维评分雷达（Top 3）</h2>

<whiteboard type="mermaid">
radar
    title 多维评分对比
    "趋势" "动量" "量能" "位置"
    {sorted_results[0].get('etf_name', '')[:6] if len(sorted_results) > 0 else "N/A"} {50} {50} {60} {60}
    {sorted_results[1].get('etf_name', '')[:6] if len(sorted_results) > 1 else "N/A"} {0} {42} {80} {80}
    {sorted_results[2].get('etf_name', '')[:6] if len(sorted_results) > 2 else "N/A"} {0} {35} {80} {60}
</whiteboard>
"""

    def generate(self) -> str:
        """生成Mermaid图表文档"""
        content = f"""<title>{self.title}（图表版）</title>

<h1>📊 {self.title}</h1>
<p><i>生成时间: {self.now}</i></p>
<hr/>

{self._build_signal_pie_chart()}

{self._build_score_bar_chart()}

{self._build_signal_flowchart()}

{self._build_radar_chart()}

<hr/>
<callout emoji="⚠️" background-color="light-gray" border-color="gray">
  <p><b>风险提示</b></p>
  <p>本报告仅供参考，不构成投资建议。市场有风险，投资需谨慎。</p>
</callout>
"""

        return content


# ── 方案4: 混合方案（推荐）──────────────────────────────────────────────────

class HybridDocGenerator(FeishuDocGenerator):
    """
    混合方案：综合使用表格、图表、分栏布局
    """

    def _escape_text(self, text: str) -> str:
        if not text:
            return ""
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;'))

    def generate(self) -> str:
        """生成混合文档"""
        sorted_results = sorted(self.results, key=lambda x: x.get("pattern_score", 0), reverse=True)
        total = len(self.results)
        avg_score = sum(r.get("pattern_score", 0) for r in self.results) / total if total else 0

        strong = len([r for r in self.results if r.get("signal") == "STRONG"])
        watch = len([r for r in self.results if r.get("signal") == "WATCH"])
        danger = len([r for r in self.results if r.get("signal") == "DANGER"])

        # 构建表格行
        table_rows = ""
        for r in sorted_results:
            sig = r.get("signal", "")
            sig_map = {"STRONG": "🟢强势", "WATCH": "🟡观望", "DANGER": "🔴危险"}
            sig_text = sig_map.get(sig, "⚪")

            bg = {"STRONG": "light-green", "WATCH": "light-yellow", "DANGER": "light-red"}.get(sig, "")

            table_rows += f"""
<tr>
  <td background-color="{bg}"><b>{self._escape_text(r.get('etf_name', '')[:10])}</b></td>
  <td>{r.get('index_name', '')[:8]}</td>
  <td>{sig_text}</td>
  <td><b>{r.get('pattern_score', 0):.0f}</b></td>
  <td>{r.get('rsi14', 0):.1f}</td>
  <td>{r.get('kdj_k', 0):.1f}</td>
  <td>{"🟢" if r.get('macd_hist', 0) > 0 else "🔴"}</td>
  <td>{r.get('vol_ratio', 1):.2f}x</td>
</tr>"""

        content = f"""<title>{self.title}（综合版）</title>

<h1>📊 {self.title}</h1>
<p><i>生成时间: {self.now}</i></p>
<hr/>

<callout emoji="📊" background-color="light-blue" border-color="blue">
  <p><b>持仓健康度</b></p>
  <p>持仓数量: <b>{total}</b> 只 | 平均评分: <b>{avg_score:.0f}</b>/100</p>
  <p>信号分布: 🟢{strong} 🟡{watch} 🔴{danger}</p>
</callout>

<h2>持仓明细</h2>

<table>
  <colgroup>
    <col span="1" width="100"/>
    <col span="1" width="80"/>
    <col span="1" width="70"/>
    <col span="1" width="50"/>
    <col span="1" width="50"/>
    <col span="1" width="50"/>
    <col span="1" width="50"/>
    <col span="1" width="60"/>
  </colgroup>
  <thead>
    <tr>
      <th background-color="gray"><span text-color="white">ETF</span></th>
      <th background-color="gray"><span text-color="white">指数</span></th>
      <th background-color="gray"><span text-color="white">信号</span></th>
      <th background-color="gray"><span text-color="white">评分</span></th>
      <th background-color="gray"><span text-color="white">RSI</span></th>
      <th background-color="gray"><span text-color="white">KDJ</span></th>
      <th background-color="gray"><span text-color="white">MACD</span></th>
      <th background-color="gray"><span text-color="white">量比</span></th>
    </tr>
  </thead>
  <tbody>
    {table_rows}
  </tbody>
</table>

<h2>技术指标说明</h2>

<grid>
  <column width-ratio="0.33">
    <callout emoji="📈" background-color="light-green" border-color="green">
      <p><b>RSI 相对强弱</b></p>
      <p>&lt;30: 超卖，可能反弹</p>
      <p>40-60: 中性区间</p>
      <p>&gt;70: 超买，注意风险</p>
    </callout>
  </column>
  <column width-ratio="0.33">
    <callout emoji="🎯" background-color="light-blue" border-color="blue">
      <p><b>KDJ 随机指标</b></p>
      <p>&lt;20: 超卖区域</p>
      <p>&gt;80: 超买区域</p>
      <p>K&gt;D且&gt;50: 强势</p>
    </callout>
  </column>
  <column width-ratio="0.34">
    <callout emoji="📉" background-color="light-yellow" border-color="yellow">
      <p><b>MACD 趋势</b></p>
      <p>红柱: 多方主导</p>
      <p>绿柱: 空方主导</p>
      <p>金叉/死叉信号</p>
    </callout>
  </column>
</grid>

<h2>操作建议</h2>

<ul>
"""

        for r in sorted_results:
            sig = r.get("signal", "")
            if sig == "STRONG":
                content += f"<li><b>{r.get('etf_name', '')}</b>: 持有/关注（强势信号）</li>\n"
            elif sig == "WATCH":
                content += f"<li><b>{r.get('etf_name', '')}</b>: 观望（等待方向确认）</li>\n"
            else:
                rsi = r.get("rsi14", 50)
                if rsi < 30:
                    content += f"<li><b>{r.get('etf_name', '')}</b>: 等待（超卖，关注反弹）</li>\n"
                else:
                    content += f"<li><b>{r.get('etf_name', '')}</b>: 减仓（危险信号）</li>\n"

        content += "</ul>\n\n<hr/>\n\n"
        content += """
<callout emoji="⚠️" background-color="light-gray" border-color="gray">
  <p><b>风险提示</b></p>
  <p>本报告仅供参考，不构成投资建议。市场有风险，投资需谨慎。</p>
</callout>
"""

        return content


# ── 主程序 ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="持仓ETF分析报告 - 飞书原生组件版")
    parser.add_argument("--mode", "-m", default="hybrid",
                        choices=["xml", "sheet", "mermaid", "hybrid"],
                        help="文档模式: xml(原生组件) | sheet(嵌入表格) | mermaid(图表) | hybrid(综合)")
    parser.add_argument("--positions", "-p", default="data/positions.json",
                        help="持仓配置文件路径")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"📊 持仓ETF分析报告 - 飞书原生组件版")
    print(f"{'='*60}\n")

    # 模式说明
    mode_descriptions = {
        "xml": "原生组件版：表格+高亮框+分栏布局",
        "sheet": "表格嵌入版：创建电子表格并嵌入文档",
        "mermaid": "图表版：使用Mermaid展示可视化图表",
        "hybrid": "综合版（推荐）：综合使用所有组件",
    }
    print(f"📋 模式: {mode_descriptions.get(args.mode, '')}\n")

    # 加载持仓
    if os.path.exists(args.positions):
        with open(args.positions, 'r', encoding='utf-8') as f:
            positions = json.load(f)
        print(f"📂 从 {args.positions} 加载持仓\n")
    else:
        print(f"❌ 持仓文件不存在: {args.positions}")
        return

    # 分析每只ETF
    results = []
    for p in positions:
        code = p.get("code", "")
        name = p.get("name", "")

        if code in ETF_MAPPING:
            mapping = ETF_MAPPING[code]
            result = analyze_etf(
                etf_code=code,
                etf_name=name or mapping["name"],
                index_code=mapping["index"],
                index_name=mapping["index_name"],
            )
            if result:
                results.append(result)
        else:
            print(f"  [跳过] {code} {name} - 未配置映射")

    print(f"\n✅ 分析完成: {len(results)}/{len(positions)} 只ETF\n")

    if not results:
        print("❌ 无有效分析结果")
        return

    # 选择生成器
    generators = {
        "xml": XMLDocGenerator,
        "mermaid": MermaidDocGenerator,
        "hybrid": HybridDocGenerator,
        "sheet": SheetDocGenerator,
    }

    generator_class = generators.get(args.mode, HybridDocGenerator)
    generator = generator_class(results)

    # 生成并创建文档
    if args.mode == "sheet":
        sheet_token, doc_url = generator.create_sheet_and_doc()
        if doc_url:
            print(f"\n📄 文档已创建: {doc_url}")
    else:
        content = generator.generate()
        doc_id, doc_url = generator.create_doc(content)
        if doc_url:
            print(f"\n📄 文档已创建: {doc_url}")

    print(f"\n💡 如需其他模式报告，使用:")
    print(f"   python -m market_monitor.report.portfolio_feishu_doc --mode xml")
    print(f"   python -m market_monitor.report.portfolio_feishu_doc --mode mermaid")
    print(f"   python -m market_monitor.report.portfolio_feishu_doc --mode hybrid")


if __name__ == "__main__":
    main()
