#!/usr/bin/env python3
"""
市场监控日报 - 多方案生成器

基于目前的市场监控飞书卡片，生成飞书文档，支持多种日报方案。

方案说明：
  方案A（简洁版）：只包含核心指标和信号，适合快速浏览
  方案B（标准版）：包含完整的四维度分析，适合日常监控
  方案C（详细版）：包含四维度分析+持仓分析+解读，适合深度分析
  方案D（图文版）：包含估值图像等可视化内容，适合直观展示

用法：
  # 生成方案A（简洁版）
  python3 -m market_monitor.report.daily_report_schemes --scheme A --feishu
  
  # 生成方案B（标准版）
  python3 -m market_monitor.report.daily_report_schemes --scheme B --feishu
  
  # 生成方案C（详细版）
  python3 -m market_monitor.report.daily_report_schemes --scheme C --feishu
  
  # 生成方案D（图文版）
  python3 -m market_monitor.report.daily_report_schemes --scheme D --feishu
  
  # 预览所有方案（不发送）
  python3 -m market_monitor.report.daily_report_schemes --preview-all
"""

import sys
import os
import json
import subprocess
import argparse
from typing import Dict, Any, Optional, List
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from .feishu import build_cards, send_cards, FEISHU_WEBHOOK


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 方案A：简洁版日报
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def generate_scheme_a(report_data: dict) -> str:
    """
    方案A：简洁版日报
    
    内容结构：
      1. 综合结论 + 建议仓位
      2. 四维度得分概览
      3. 主要风险点（如有）
      
    特点：简洁明了，快速浏览
    """
    now = report_data.get("generated_at", "?")
    
    comp = report_data.get("composite", {})
    comp_s = comp.get("score", 0.0)
    comp_l = comp.get("label", "N/A")
    
    cap_dim = report_data.get("capital", {})
    fun_dim = report_data.get("fundamental", {})
    pol_dim = report_data.get("policy", {})
    glb_dim = report_data.get("global", {})
    
    cap_s = cap_dim.get("score", 0.0)
    fun_s = fun_dim.get("score", 0.0)
    pol_s = pol_dim.get("score", 0.0)
    glb_s = glb_dim.get("score", 0.0)
    
    # 建议仓位
    cap_data_raw = cap_dim.get("data", {})
    znz = cap_data_raw.get("znz_active_cap", {})
    znz_signal = znz.get("last_clear_signal") if znz and znz.get("error") is None else None
    
    # 简化版仓位建议
    if znz_signal == "incremental":
        pos_range = "30-40%"
        pos_reason = "增量资金入场"
    elif znz_signal == "exit":
        pos_range = "0-10%"
        pos_reason = "资金离场警示"
    else:
        pos_range = "20%"
        pos_reason = "观望"
    
    # 风险点（简化）
    risks = []
    if cap_s < -0.3:
        risks.append("资金面偏弱")
    if fun_s < -0.3:
        risks.append("基本面偏弱")
    if glb_s < -0.3:
        risks.append("全球市场偏弱")
    
    risk_text = "、".join(risks) if risks else "暂无显著风险"
    
    # 生成XML
    xml = f"""<title>市场监控日报（简洁版） {now}</title>

<h1>一、综合结论</h1>

<p><b>综合评分：</b>{comp_s:+.2f} · {comp_l}</p>
<p><b>建议仓位：</b>{pos_range}</p>
<p><b>判断依据：</b>{pos_reason}</p>

<h1>二、四维度得分</h1>

<table>
  <thead><tr><th>维度</th><th>得分</th><th>权重</th></tr></thead>
  <tbody>
    <tr><td>资金面</td><td>{cap_s:+.2f}</td><td>30%</td></tr>
    <tr><td>基本面</td><td>{fun_s:+.2f}</td><td>40%</td></tr>
    <tr><td>政策面</td><td>{pol_s:+.2f}</td><td>10%</td></tr>
    <tr><td>全球市场</td><td>{glb_s:+.2f}</td><td>20%</td></tr>
  </tbody>
</table>

<h1>三、风险提示</h1>

<p>⚠️ {risk_text}</p>

<call-out emoji="ℹ️" background-color="light-blue" border-color="blue">
  <p>本报告为简洁版，仅包含核心指标。详细分析请查看标准版或详细版报告。</p>
</call-out>

<p>报告时间：{datetime.now().strftime("%Y-%m-%d %H:%M")} 北京时间</p>"""
    
    return xml


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 方案B：标准版日报
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def generate_scheme_b(report_data: dict) -> str:
    """
    方案B：标准版日报
    
    内容结构：
      1. 交易决策区（综合结论 + 建议仓位 + 主要风险点）
      2. 四维度快览（各维度得分 + 标签 + 一句话摘要）
      3. 资金面详情
      4. 基本面详情
      5. 政策面详情
      6. 全球市场详情
      
    特点：完整全面，适合日常监控
    """
    now = report_data.get("generated_at", "?")
    
    comp = report_data.get("composite", {})
    comp_s = comp.get("score", 0.0)
    comp_l = comp.get("label", "N/A")
    
    cap_dim = report_data.get("capital", {})
    fun_dim = report_data.get("fundamental", {})
    pol_dim = report_data.get("policy", {})
    glb_dim = report_data.get("global", {})
    
    cap_s = cap_dim.get("score", 0.0)
    fun_s = fun_dim.get("score", 0.0)
    pol_s = pol_dim.get("score", 0.0)
    glb_s = glb_dim.get("score", 0.0)
    
    # 建议仓位（完整版）
    cap_data_raw = cap_dim.get("data", {})
    znz = cap_data_raw.get("znz_active_cap", {})
    znz_signal = znz.get("last_clear_signal") if znz and znz.get("error") is None else None
    
    if znz_signal == "incremental":
        pos_range = "30-40%"
        pos_reason = "指南针活跃市值单日涨幅≥+4%，增量资金入场信号"
    elif znz_signal == "exit":
        pos_range = "0-10%"
        pos_reason = "指南针活跃市值单日跌幅≤-2.3%，资金离场警示信号"
    else:
        pos_range = "20%"
        pos_reason = "指南针活跃市值震荡，观望信号"
    
    # 风险点（完整）
    risks = []
    if cap_s < -0.3:
        risks.append("资金面偏弱，关注增量资金动向")
    if fun_s < -0.3:
        risks.append("基本面偏弱，关注经济数据变化")
    if pol_s < -0.3:
        risks.append("政策面偏弱，关注货币政策调整")
    if glb_s < -0.3:
        risks.append("全球市场偏弱，关注外部风险传导")
    
    # 各维度摘要
    from .feishu import _cap_summary, _fun_summary, _glb_summary
    
    cap_summ = _cap_summary(cap_dim)
    fun_summ = _fun_summary(fun_dim)
    pol_summ = "政策面摘要"  # 简化
    glb_summ = _glb_summary(glb_dim)
    
    # 生成XML
    xml = f"""<title>市场监控日报（标准版） {now}</title>

<h1>一、交易决策</h1>

<p><b>综合评分：</b>{comp_s:+.2f} · {comp_l}</p>
<p><b>建议仓位：</b>{pos_range}</p>
<p><b>判断依据：</b>{pos_reason}</p>

<h2>主要风险点</h2>
"""
    
    if risks:
        xml += "<ul>"
        for risk in risks:
            xml += f"<li>⚠️ {risk}</li>"
        xml += "</ul>"
    else:
        xml += "<p>暂无显著风险</p>"
    
    xml += f"""
<h1>二、四维度快览</h1>

<table>
  <thead><tr><th>维度</th><th>得分</th><th>摘要</th></tr></thead>
  <tbody>
    <tr><td>资金面</td><td>{cap_s:+.2f}</td><td>{cap_summ}</td></tr>
    <tr><td>基本面</td><td>{fun_s:+.2f}</td><td>{fun_summ}</td></tr>
    <tr><td>政策面</td><td>{pol_s:+.2f}</td><td>{pol_summ}</td></tr>
    <tr><td>全球市场</td><td>{glb_s:+.2f}</td><td>{glb_summ}</td></tr>
  </tbody>
</table>

<h1>三、资金面详情</h1>
"""
    
    # 资金面详情（简化版，避免过长）
    cap_data = cap_dim.get("data", {})
    if cap_data and "znz_active_cap" in cap_data:
        znz = cap_data["znz_active_cap"]
        if znz.get("error") is None:
            xml += f"""<p>指南针活跃市值：{znz.get('active_cap', '?')} 亿元</p>
<p>日变动：{znz.get('chg_pct', '?')}%</p>
<p>信号：{znz.get('signal', '?')}</p>"""
    
    xml += f"""
<h1>四、基本面详情</h1>
"""
    
    # 基本面详情（简化版）
    fun_data = fun_dim.get("data", {})
    if fun_data:
        gdp = fun_data.get("gdp", {})
        if gdp and gdp.get("error") is None:
            xml += f"""<p>GDP同比增速：{gdp.get('gdp_yoy', '?')}%</p>"""
        
        sd = fun_data.get("supply_demand", {})
        if sd and sd.get("error") is None:
            xml += f"""<p>制造业PMI：{sd.get('pmi_mfg', '?')}</p>
<p>CPI同比：{sd.get('cpi_yoy', '?')}%</p>
<p>PPI同比：{sd.get('ppi_yoy', '?')}%</p>"""
    
    xml += f"""
<h1>五、政策面详情</h1>
"""
    
    # 政策面详情（简化版）
    pol_data = pol_dim.get("data", {})
    if pol_data:
        monetary = pol_data.get("monetary", {})
        if monetary and monetary.get("error") is None:
            xml += f"""<p>货币信号：{monetary.get('signal', '?')}</p>
<p>10年国债收益率：{monetary.get('bond_10y', '?')}%</p>"""
    
    xml += f"""
<h1>六、全球市场详情</h1>
"""
    
    # 全球市场详情（简化版）
    glb_data = glb_dim.get("data", {})
    if glb_data:
        us = glb_data.get("us", {})
        if us and us.get("error") is None:
            xml += f"""<p>标普500：{us.get('SPX', {}).get('chg5d_pct', '?')}%（5日）</p>"""
        
        asia = glb_data.get("asia", {})
        if asia and asia.get("error") is None:
            xml += f"""<p>恒生指数：{asia.get('HSI', {}).get('chg5d_pct', '?')}%（5日）</p>"""
    
    xml += f"""
<call-out emoji="⚠️" background-color="light-yellow" border-color="yellow">
  <p>本报告仅供参考，不构成投资建议。市场有风险，投资需谨慎。</p>
</call-out>

<p>报告时间：{datetime.now().strftime("%Y-%m-%d %H:%M")} 北京时间</p>"""
    
    return xml


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 方案C：详细版日报
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def generate_scheme_c(report_data: dict) -> str:
    """
    方案C：详细版日报
    
    内容结构：
      1. 交易决策区（综合结论 + 建议仓位 + 主要风险点 + 近期关注）
      2. 四维度快览（各维度得分 + 标签 + 一句话摘要 + 关键指标）
      3. 资金面详情（全市场成交额/融资融券/新开户数）
      4. 基本面详情（GDP/人均可支配收入/宏观供需/PMI/宏观流动性）
      5. 政策面详情（货币政策/财政政策）
      6. 全球市场详情（美股/亚洲市场/新兴市场）
      7. 持仓分析（如有）
      8. LLM解读（如有）
      
    特点：深度分析，适合周末或重要时点
    """
    # 方案C在标准版基础上，增加持仓分析和LLM解读
    xml = generate_scheme_b(report_data)  # 先生成标准版内容
    
    # 在末尾添加持仓分析（如有）
    position_report = report_data.get("position_report")
    if position_report:
        xml += """
<h1>七、持仓分析</h1>
<p>持仓分析内容（待完善）</p>"""
    
    # 添加LLM解读（如有）
    xml += """
<h1>八、LLM解读</h1>
<p>LLM解读内容（待完善）</p>"""
    
    # 替换标题
    xml = xml.replace("标准版", "详细版")
    
    return xml


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 方案D：图文版日报
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def generate_scheme_d(report_data: dict) -> str:
    """
    方案D：图文版日报
    
    内容结构：
      1. 交易决策区（综合结论 + 建议仓位）
      2. 四维度得分（含估值图表）
      3. 全球市场估值图表
      4. 资金流向图表
      
    特点：图文并茂，适合直观展示
    """
    now = report_data.get("generated_at", "?")
    
    comp = report_data.get("composite", {})
    comp_s = comp.get("score", 0.0)
    comp_l = comp.get("label", "N/A")
    
    # 生成XML（图文版）
    xml = f"""<title>市场监控日报（图文版） {now}</title>

<h1>一、综合结论</h1>

<p><b>综合评分：</b>{comp_s:+.2f} · {comp_l}</p>

<h1>二、全球市场估值</h1>
<p>全球市场估值图表（待添加）</p>

<h1>三、资金流向</h1>
<p>资金流向图表（待添加）</p>

<call-out emoji="ℹ️" background-color="light-blue" border-color="blue">
  <p>本报告为图文版，包含可视化图表。由于飞书文档对图片的支持限制，部分图表可能需要查看原图。</p>
</call-out>

<p>报告时间：{datetime.now().strftime("%Y-%m-%d %H:%M")} 北京时间</p>"""
    
    return xml


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 通用函数：创建飞书文档
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def create_doc(xml_content: str, title: str = "市场监控日报") -> tuple:
    """
    创建飞书文档
    
    Args:
        xml_content: 文档XML内容
        title: 文档标题（可作为文件名）
        
    Returns:
        (doc_id, doc_url) 或 (None, None)
    """
    # 保存到临时文件
    temp_path = '/tmp/market_daily_report.xml'
    try:
        with open(temp_path, 'w', encoding='utf-8') as f:
            f.write(xml_content)
        
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


def send_feishu_card(doc_url: str, scheme_name: str) -> bool:
    """
    发送飞书卡片消息
    
    Args:
        doc_url: 飞书文档URL
        scheme_name: 方案名称（用于消息内容）
        
    Returns:
        是否发送成功
    """
    try:
        if not FEISHU_WEBHOOK:
            print("⚠ 飞书 Webhook 未配置")
            return False
        
        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": f"📊 市场监控日报（{scheme_name}）"},
                    "template": "blue"
                },
                "elements": [
                    {"tag": "div", "text": {"tag": "lark_md", "content": f"**报告已生成**\n\n请点击下方按钮查看完整报告"}},
                    {
                        "tag": "action",
                        "actions": [{
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "📄 查看完整报告"},
                            "type": "primary",
                            "url": doc_url
                        }]
                    }
                ]
            }
        }
        
        response = requests.post(
            FEISHU_WEBHOOK,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("code") == 0:
                print(f"✅ 飞书卡片消息已发送")
                return True
            else:
                print(f"⚠ 发送飞书消息失败: {result.get('msg', '未知错误')}")
                return False
        else:
            print(f"⚠ 发送飞书消息失败: HTTP {response.status_code}")
            return False
    
    except Exception as e:
        print(f"⚠ 发送飞书消息出错: {e}")
        return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 主函数
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main():
    parser = argparse.ArgumentParser(description="市场监控日报 - 多方案生成器")
    parser.add_argument("--scheme", "-s", type=str, choices=['A', 'B', 'C', 'D'], 
                        default='B', help="选择日报方案（A=简洁版，B=标准版，C=详细版，D=图文版）")
    parser.add_argument("--feishu", "-f", action="store_true", help="发送飞书机器人")
    parser.add_argument("--preview-all", "-p", action="store_true", help="预览所有方案（不发送）")
    args = parser.parse_args()
    
    # 加载报告数据（从 main.py 传入或读取缓存）
    # 这里简化为从标准输入读取JSON
    try:
        report_data = json.load(sys.stdin)
    except:
        print("⚠ 未提供报告数据，使用模拟数据")
        report_data = {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "composite": {"score": 0.5, "label": "中性"},
            "capital": {"score": 0.3, "data": {}},
            "fundamental": {"score": 0.5, "data": {}},
            "policy": {"score": 0.0, "data": {}},
            "global": {"score": 0.2, "data": {}},
        }
    
    # 预览所有方案
    if args.preview_all:
        print("=" * 60)
        print("市场监控日报 - 方案预览")
        print("=" * 60)
        
        for scheme in ['A', 'B', 'C', 'D']:
            print(f"\n方案{scheme}：")
            if scheme == 'A':
                print("  名称：简洁版")
                print("  特点：只包含核心指标和信号，适合快速浏览")
                print("  内容：综合结论 + 四维度得分 + 风险提示")
            elif scheme == 'B':
                print("  名称：标准版")
                print("  特点：包含完整的四维度分析，适合日常监控")
                print("  内容：交易决策 + 四维度快览 + 各维度详情")
            elif scheme == 'C':
                print("  名称：详细版")
                print("  特点：包含四维度分析+持仓分析+解读，适合深度分析")
                print("  内容：标准版内容 + 持仓分析 + LLM解读")
            elif scheme == 'D':
                print("  名称：图文版")
                print("  特点：包含估值图像等可视化内容，适合直观展示")
                print("  内容：综合结论 + 全球市场估值图表 + 资金流向图表")
        
        print("\n" + "=" * 60)
        print("请选择方案（A/B/C/D），然后重新运行并指定 --scheme 参数")
        print("=" * 60)
        return
    
    # 生成选定方案的报告
    print(f"\n📊 生成市场监控日报（方案{args.scheme}）...")
    
    if args.scheme == 'A':
        xml_content = generate_scheme_a(report_data)
        scheme_name = "简洁版"
    elif args.scheme == 'B':
        xml_content = generate_scheme_b(report_data)
        scheme_name = "标准版"
    elif args.scheme == 'C':
        xml_content = generate_scheme_c(report_data)
        scheme_name = "详细版"
    elif args.scheme == 'D':
        xml_content = generate_scheme_d(report_data)
        scheme_name = "图文版"
    else:
        print(f"⚠ 未知方案: {args.scheme}")
        return
    
    # 创建飞书文档
    print(f"📄 创建飞书文档（{scheme_name}）...")
    doc_id, doc_url = create_doc(xml_content, f"市场监控日报（{scheme_name}）")
    
    if doc_id and doc_url:
        print(f"✅ 文档已创建: {doc_url}")
        
        # 发送飞书消息
        if args.feishu:
            print("📤 发送飞书消息...")
            send_feishu_card(doc_url, scheme_name)
    else:
        print("❌ 创建文档失败")
        return
    
    print(f"\n{'=' * 60}\n")


if __name__ == "__main__":
    main()
