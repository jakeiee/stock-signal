#!/usr/bin/env python3
"""
专业版ETF持仓分析报告生成器

精简版专业报告，包含：
- 持仓概览与信号分布
- 持仓明细（知行信号、技术指标、盈亏）
- 板块分布
- 操作建议
- 风险提示

使用方法：
    python3 -m market_monitor.report.portfolio_professional
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import json
import subprocess
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Dict, List

import pandas as pd
import xalpha as xa
import tushare as ts
import warnings
warnings.filterwarnings('ignore')

from market_monitor.report.portfolio_analyzer import ETF_MAPPING, analyze_etf


def get_realtime_price(codes: list) -> dict:
    """通过Tushare获取ETF实时价格"""
    try:
        df = ts.get_realtime_quotes(codes)
        prices = {}
        if not df.empty:
            for _, row in df.iterrows():
                code = row['code']
                price = float(row['price']) if row['price'] else 0
                prices[code] = price
        return prices
    except Exception as e:
        print(f"  [警告] Tushare获取实时价格失败: {e}")
        return {}


def get_etf_nav(code: str) -> tuple:
    """通过xalpha获取ETF净值和日期（作为参考）"""
    try:
        info = xa.FundInfo(code)
        if info and hasattr(info, 'price') and not info.price.empty:
            latest = info.price.iloc[-1]
            nav = float(latest['netvalue'])
            date = str(latest['date'])[:10]
            return nav, date
        return 0.0, None
    except Exception as e:
        print(f"  [警告] 获取 {code} 净值失败: {e}")
        return 0.0, None


class ProfessionalETFReportGenerator:
    """专业版ETF持仓分析报告生成器"""

    def __init__(self, results: List[Dict]):
        self.results = results
        beijing_tz = timezone(timedelta(hours=8))
        self.now = datetime.now(beijing_tz)
        self.report_time = self.now.strftime("%Y-%m-%d %H:%M")
        self.report_date = self.now.strftime("%Y-%m-%d")

    def _escape(self, text: str) -> str:
        """转义XML特殊字符"""
        if not text:
            return ""
        return (text.replace('&', '&amp;')
                    .replace('<', '&lt;')
                    .replace('>', '&gt;'))

    def _fmt_profit(self, p: float) -> str:
        """格式化盈亏"""
        return ("🟢 " if p >= 0 else "🔴 ") + f"{p:+.2f}%"

    def _rsi_status(self, rsi: float):
        """RSI状态"""
        if rsi < 30: return f"🔴{rsi:.1f}", "超卖"
        elif rsi < 40: return f"🟠{rsi:.1f}", "偏弱"
        elif rsi < 60: return f"⚪{rsi:.1f}", "中性"
        elif rsi < 70: return f"🟡{rsi:.1f}", "偏强"
        else: return f"🟢{rsi:.1f}", "超买"

    def _pos_status(self, pos: float):
        """位置状态"""
        if pos < 20: return "🔴低位", f"{pos:.0f}%"
        elif pos < 40: return "🟠偏下", f"{pos:.0f}%"
        elif pos < 60: return "⚪中性", f"{pos:.0f}%"
        elif pos < 80: return "🟡偏上", f"{pos:.0f}%"
        else: return "🟢高位", f"{pos:.0f}%"

    def _zx_signal(self, r: dict):
        """知行信号状态"""
        zx_short = r.get('zx_short', 0)
        zx_long = r.get('zx_long', 0)
        close = r.get('close', 0)
        
        if zx_short > zx_long and close > zx_short:
            return "🟢强势", "白>黄，收在白线上"
        elif zx_short > zx_long and close <= zx_short:
            return "🟡观望", "白>黄，收在白线下"
        else:
            return "🔴危险", "白<黄，空头排列"

    def _kdj_status(self, r: dict):
        """KDJ状态"""
        k, d, j = r.get('kdj_k', 0), r.get('kdj_d', 0), r.get('kdj_j', 0)
        if k < 20: return f"🔴{k:.0f}", "超卖"
        elif k > 80: return f"🟢{k:.0f}", "超买"
        elif k > d and d > 50: return f"🟡{k:.0f}", "金叉"
        else: return f"⚪{k:.0f}", "中性"

    def _macd_status(self, r: dict):
        """MACD状态"""
        hist = r.get('macd_hist', 0)
        return ("🟢红柱", "多方") if hist > 0 else ("🔴绿柱", "空方")

    def _get_action(self, r: dict):
        """获取操作建议"""
        sig = r.get('signal', '')
        rsi = r.get('rsi14', 50)
        
        if sig == 'STRONG':
            if rsi > 70: return "持有/减仓"
            elif rsi < 30: return "加仓机会"
            return "持有"
        elif sig == 'WATCH':
            if rsi < 30: return "关注"
            return "观望"
        else:
            if rsi < 30: return "等待"
            return "减仓"

    def generate(self) -> str:
        """生成完整报告"""
        total = len(self.results)
        avg_score = sum(r.get('pattern_score', 0) for r in self.results) / total if total else 0

        strong = [r for r in self.results if r.get('signal') == 'STRONG']
        watch = [r for r in self.results if r.get('signal') == 'WATCH']
        danger = [r for r in self.results if r.get('signal') == 'DANGER']

        strong_count, watch_count, danger_count = len(strong), len(watch), len(danger)
        strong_pct = strong_count / total * 100 if total else 0
        watch_pct = watch_count / total * 100 if total else 0
        danger_pct = danger_count / total * 100 if total else 0

        # 计算整体盈亏
        total_profit = sum(r.get('profit_pct', 0) for r in self.results) / total if total else 0
        
        # 权重
        total_weight = sum(r.get('weight', 0) for r in self.results)
        
        # 健康评级
        health = "优秀" if avg_score >= 70 else "良好" if avg_score >= 50 else "一般" if avg_score >= 30 else "较差"
        health_emoji = "🟢" if avg_score >= 50 else "🟡" if avg_score >= 30 else "🔴"
        
        status = "整体偏弱" if danger_count > strong_count else "整体偏强" if strong_count > danger_count else "分化明显"

        # 计算总盈亏
        total_market_value = sum(r.get('market_value', 0) for r in self.results)
        total_cost_value = sum(r.get('cost_value', 0) for r in self.results)
        total_profit_value = total_market_value - total_cost_value
        total_profit_pct = (total_profit_value / total_cost_value * 100) if total_cost_value > 0 else 0

        # 持仓明细表格 - 按市值降序排列
        sorted_results = sorted(self.results, key=lambda x: x.get('market_value', 0), reverse=True)
        position_rows = ""
        for r in sorted_results:
            sig = r.get('signal', '')
            sig_emoji = {"STRONG": "🟢", "WATCH": "🟡", "DANGER": "🔴"}.get(sig, "⚪")
            
            zx_emoji, zx_desc = self._zx_signal(r)
            rsi_str, rsi_status = self._rsi_status(r.get('rsi14', 50))
            kdj_str, kdj_status = self._kdj_status(r)
            macd_str, macd_status = self._macd_status(r)
            pos_desc, pos_str = self._pos_status(r.get('price_pos_60d', 50))
            
            profit_pct = r.get('profit_pct', 0)
            action = self._get_action(r)
            
            # 格式化盈亏：仅显示比例
            profit_str = ("🟢 " if profit_pct >= 0 else "🔴 ") + f"{profit_pct:+.2f}%"
            
            position_rows += f"""<tr>
  <td>{r.get('etf_code', '')}</td>
  <td>{self._escape(r.get('index_name', ''))}</td>
  <td>{zx_emoji}</td>
  <td><b>{r.get('pattern_score', 0):.0f}</b></td>
  <td>{rsi_str}</td>
  <td>{kdj_str}</td>
  <td>{macd_str}</td>
  <td>{profit_str}</td>
  <td>{action}</td>
</tr>"""

        # 风险评估
        risk_items = []
        if danger_count > total // 2:
            risk_items.append(f"多数标的处于危险信号（{danger_count}只，{danger_pct:.0f}%）")
        if avg_score < 40:
            risk_items.append("整体评分偏低，技术面偏弱")
        if any(r.get('rsi14', 0) > 70 for r in self.results):
            risk_items.append("部分标的RSI超买，注意回调风险")
        if any(r.get('rsi14', 0) < 30 for r in self.results):
            risk_items.append("部分标的超卖，存在反弹机会")
        
        risk_content = "；".join(risk_items) if risk_items else "风险整体可控"

        # 操作建议
        advice_items = []
        if strong:
            strong_names = "、".join([r.get('index_name', '')[:6] for r in strong[:3]])
            advice_items.append(f"强势标的：{strong_names}")
        if watch:
            watch_names = "、".join([r.get('index_name', '')[:6] for r in watch[:2]])
            advice_items.append(f"观望标的：{watch_names}")
        if danger:
            danger_names = "、".join([r.get('index_name', '')[:6] for r in danger[:3]])
            advice_items.append(f"危险标的：{danger_names}")
        
        advice_content = "<ul>" + "".join([f"<li>{item}</li>" for item in advice_items]) + "</ul>" if advice_items else "<p>暂无明确操作建议</p>"

        # 生成XML
        xml = f"""<title>ETF持仓分析报告 {self.report_date}</title>

<h1>一、持仓概览</h1>

<table>
  <thead><tr><th>指标</th><th>数值</th></tr></thead>
  <tbody>
    <tr><td>持仓数量</td><td>{total} 只ETF</td></tr>
    <tr><td>综合评分</td><td>{health_emoji} {avg_score:.0f}/100（{health}）</td></tr>
    <tr><td>整体盈亏</td><td>{self._fmt_profit(total_profit_pct)}</td></tr>
    <tr><td>状态</td><td>{status}，{health}</td></tr>
  </tbody>
</table>

<h2>信号分布</h2>
<table>
  <thead><tr><th>信号</th><th>数量</th><th>占比</th></tr></thead>
  <tbody>
    <tr><td>🟢 强势</td><td>{strong_count} 只</td><td>{strong_pct:.0f}%</td></tr>
    <tr><td>🟡 观望</td><td>{watch_count} 只</td><td>{watch_pct:.0f}%</td></tr>
    <tr><td>🔴 危险</td><td>{danger_count} 只</td><td>{danger_pct:.0f}%</td></tr>
  </tbody>
</table>

<h1>二、持仓明细（按市值降序）</h1>
<table>
  <thead><tr>
    <th>代码</th>
    <th>跟踪指数</th>
    <th>知行信号</th>
    <th>评分</th>
    <th>RSI</th>
    <th>KDJ</th>
    <th>MACD</th>
    <th>盈亏</th>
    <th>建议</th>
  </tr></thead>
  <tbody>{position_rows}</tbody>
</table>

<h1>三、操作建议</h1>
{advice_content}

<h1>四、风险提示</h1>
<p>{risk_content}</p>

<callout emoji="⚠️" background-color="light-yellow" border-color="yellow">
  <p>本报告仅供参考，不构成投资建议。市场有风险，投资需谨慎。</p>
</callout>

<p>报告时间：{self.report_time} 北京时间</p>"""

        return xml

    def create_doc(self) -> tuple:
        """创建飞书文档"""
        content = self.generate()

        # 保存到临时文件
        temp_path = './etf_report.xml'
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
                output = json.loads(result.stdout)
                if output.get('ok'):
                    data = output.get('data', {})
                    doc_data = data.get('document', {})
                    doc_id = doc_data.get('document_id', '')
                    doc_url = doc_data.get('url', '')
                    return doc_id, doc_url

            print(f"⚠ 创建文档失败: {result.stderr}")
            return None, None

        except Exception as e:
            print(f"⚠ 创建飞书文档出错: {e}")
            return None, None
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def build_feishu_card(self, doc_url: str = None) -> dict:
        """构建飞书卡片消息 - 按知行信号分类"""
        # 分类
        strong = [r for r in self.results if r.get('signal') == 'STRONG']
        watch = [r for r in self.results if r.get('signal') == 'WATCH']
        danger = [r for r in self.results if r.get('signal') == 'DANGER']
        
        # 构建消息内容
        content_lines = []
        content_lines.append(f"**持仓概览** | {len(self.results)}只ETF | 🟢强势{len(strong)} | 🟡观望{len(watch)} | 🔴危险{len(danger)}")
        content_lines.append("")
        
        # 🟢 强势
        if strong:
            content_lines.append("**🟢 知行强势（白>黄，收在白线上）**")
            for r in strong:
                rsi = r.get('rsi14', 50)
                rsi_status = "超买" if rsi > 70 else ("超卖" if rsi < 30 else "中性")
                content_lines.append(f"• {r.get('etf_name', '')} | RSI={rsi:.0f} {rsi_status}")
            content_lines.append("")
        
        # 🟡 观望
        if watch:
            content_lines.append("**🟡 知行观望（白>黄，收在白线下）**")
            for r in watch:
                rsi = r.get('rsi14', 50)
                pos = r.get('price_pos_60d', 50)
                pos_status = "低位" if pos < 30 else ("高位" if pos > 70 else "中性")
                content_lines.append(f"• {r.get('etf_name', '')} | RSI={rsi:.0f} | {pos_status}")
            content_lines.append("")
        
        # 🔴 危险
        if danger:
            content_lines.append("**🔴 知行危险（白<黄，空头排列）**")
            for r in danger:
                pos = r.get('price_pos_60d', 50)
                pos_status = "低位" if pos < 30 else ("高位" if pos > 70 else "中性")
                content_lines.append(f"• {r.get('etf_name', '')} | {pos_status}")
        
        content = "\n".join(content_lines)
        
        # 构建卡片
        elements = [
            {'tag': 'hr'},
            {'tag': 'div', 'text': {'tag': 'lark_md', 'content': content}}
        ]
        
        # 添加文档链接按钮
        if doc_url:
            elements.append({
                'tag': 'action',
                'actions': [{
                    'tag': 'button',
                    'text': {'tag': 'plain_text', 'content': '📄 查看完整报告'},
                    'type': 'primary',
                    'url': doc_url
                }]
            })
        
        elements.append({
            'tag': 'note',
            'elements': [{'tag': 'plain_text', 'content': '⚠️ 本报告仅供参考，不构成投资建议'}]
        })
        
        return {
            'msg_type': 'interactive',
            'card': {
                'config': {'wide_screen_mode': True},
                'header': {
                    'title': {'tag': 'plain_text', 'content': '📊 ETF持仓分析报告'},
                    'subtitle': {'tag': 'plain_text', 'content': f'{self.report_date} | 知行信号分类'},
                    'template': 'blue'
                },
                'elements': elements
            }
        }

    def send_to_feishu(self, doc_url: str = None) -> bool:
        """发送飞书卡片消息"""
        try:
            from market_monitor.config import FEISHU_WEBHOOK
            import requests
            
            if not FEISHU_WEBHOOK:
                print("⚠ 飞书 Webhook 未配置")
                return False
            
            payload = self.build_feishu_card(doc_url)
            
            response = requests.post(
                FEISHU_WEBHOOK,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            result = response.json()
            if result.get('code') == 0:
                print("✅ 飞书卡片消息已发送")
                return True
            else:
                print(f"⚠ 飞书发送失败: {result}")
                return False
                
        except Exception as e:
            print(f"⚠ 发送到飞书失败: {e}")
            return False


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="ETF持仓专业分析报告")
    parser.add_argument("--feishu", "-f", action="store_true", help="发送飞书消息")
    parser.add_argument("--positions", "-p", default="data/positions.json", help="持仓文件路径")
    args = parser.parse_args()
    
    print(f"\n{'='*60}")
    print(f"📊 ETF持仓专业分析报告")
    print(f"{'='*60}\n")

    # 加载持仓
    positions_path = args.positions
    if os.path.exists(positions_path):
        with open(positions_path, 'r', encoding='utf-8') as f:
            positions = json.load(f)
        print(f"📂 加载持仓: {len(positions)} 只\n")
    else:
        print(f"❌ 持仓文件不存在: {positions_path}")
        return

    # 获取ETF代码列表
    etf_codes = [p.get('code', '') for p in positions if p.get('code', '') in ETF_MAPPING]
    
    # 通过Tushare获取实时价格
    print("📡 通过Tushare获取实时价格...")
    realtime_prices = get_realtime_price(etf_codes)
    print(f"   获取到 {len(realtime_prices)} 只ETF的实时价格\n")

    # 分析每只ETF
    results = []
    for p in positions:
        code = p.get('code', '')
        name = p.get('name', '')

        if code in ETF_MAPPING:
            mapping = ETF_MAPPING[code]
            result = analyze_etf(
                etf_code=code,
                etf_name=name or mapping['name'],
                index_code=mapping['index'],
                index_name=mapping['index_name'],
            )
            if result:
                # 合并持仓信息
                result['shares'] = p.get('shares', 0)
                result['cost_price'] = p.get('cost_price', 0)
                
                # 优先使用Tushare实时价格
                realtime_price = realtime_prices.get(code, 0)
                cost = result['cost_price']
                
                if realtime_price > 0:
                    result['current_price'] = realtime_price
                    result['price_source'] = '实时'
                else:
                    print(f"  [警告] {code} 无法获取实时价格")
                    continue
                
                current = result['current_price']
                
                # 计算市值和盈亏
                result['market_value'] = current * result['shares']  # 实时市值
                result['cost_value'] = cost * result['shares']  # 成本市值
                result['profit_pct'] = ((current - cost) / cost * 100) if cost > 0 else 0  # 盈亏比例
                result['profit_value'] = result['market_value'] - result['cost_value']  # 盈亏金额
                
                # 通过xalpha获取基金净值作为参考
                print(f"  [{code}] {mapping['name']}")
                print(f"         实时价: {current:.3f}, 成本: {cost:.3f}, 市值: {result['market_value']:.0f}元")
                print(f"         盈亏: {result['profit_pct']:+.2f}% ({result['profit_value']:+.0f}元)")
                
                nav, nav_date = get_etf_nav(code)
                if nav > 0:
                    result['nav'] = nav
                    result['nav_date'] = nav_date
                    print(f"         基金净值: {nav:.4f} ({nav_date})")

                results.append(result)

    print(f"\n✅ 分析完成: {len(results)} 只ETF\n")

    if not results:
        print("❌ 无有效分析结果")
        return

    # 生成专业版报告
    generator = ProfessionalETFReportGenerator(results)
    doc_id, doc_url = generator.create_doc()

    if doc_url:
        print(f"\n📄 专业版报告已创建: {doc_url}")
    else:
        # 输出XML内容供调试
        print("\n⚠ 文档创建失败，以下是报告内容预览:")
        print("-" * 60)
        print(generator.generate()[:2000])
        print("-" * 60)

    # 发送飞书消息
    if args.feishu:
        print()
        generator.send_to_feishu(doc_url)

    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    main()
