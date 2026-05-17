#!/usr/bin/env python3
"""
市场监控日报 - 方案示例生成器（简化版）
直接生成示例Markdown文档，用于预览方案效果
"""
from datetime import datetime
from pathlib import Path


def generate_scheme_a_simple():
    """方案A：简洁版示例"""
    lines = []
    lines.append("# 📊 市场监控日报（方案A - 简洁版）\n")
    lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    lines.append("---\n")
    
    lines.append("## 📈 核心指标\n")
    lines.append("- **恒生科技指数**: 4500.23 (+1.2%)")
    lines.append("- **中证软件服务**: 6800.45 (-0.8%)")
    lines.append("- **中证机器人**: 9200.78 (+2.1%)")
    lines.append("- **港股通创新药**: 3400.56 (+0.5%)")
    lines.append("")
    
    lines.append("---\n")
    lines.append("## 🎯 交易信号\n")
    lines.append("1. ✅ 恒生科技指数：MACD金叉，建议买入")
    lines.append("2. ⚠️ 中证软件服务：KDJ超买，建议减仓")
    lines.append("")
    
    lines.append("---\n")
    lines.append("*本报告由市场监控系统自动生成*")
    
    return "\n".join(lines)


def generate_scheme_b_standard():
    """方案B：标准版示例"""
    lines = []
    lines.append("# 📊 市场监控日报（方案B - 标准版）\n")
    lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    lines.append("---\n")
    
    lines.append("## 📈 一、市场概况\n")
    lines.append("### 恒生科技指数")
    lines.append("- **当前价格**: 4500.23")
    lines.append("- **涨跌幅**: +1.2%")
    lines.append("- **成交额**: 120亿")
    lines.append("")
    lines.append("### 中证软件服务指数")
    lines.append("- **当前价格**: 6800.45")
    lines.append("- **涨跌幅**: -0.8%")
    lines.append("- **成交额**: 85亿")
    lines.append("")
    
    lines.append("---\n")
    
    lines.append("## 📊 二、技术指标分析\n")
    lines.append("### 恒生科技指数")
    lines.append("**均线系统**:")
    lines.append("  - MA5: 4480.50")
    lines.append("  - MA10: 4450.30")
    lines.append("  - MA20: 4400.80")
    lines.append("")
    lines.append("**MACD**:")
    lines.append("  - DIF: 15.2")
    lines.append("  - DEA: 12.8")
    lines.append("  - MACD: 2.4 (金叉)")
    lines.append("")
    
    lines.append("---\n")
    
    lines.append("## 💰 三、资金流向\n")
    lines.append("### 恒生科技指数")
    lines.append("- **主力净流入**: +5.2亿")
    lines.append("- **散户净流入**: -1.8亿")
    lines.append("")
    
    lines.append("---\n")
    
    lines.append("## 🎯 四、交易信号\n")
    lines.append("1. ✅ **恒生科技指数**: MACD金叉，建议买入")
    lines.append("2. ⚠️ **中证软件服务**: KDJ超买，建议减仓")
    lines.append("3. 📊 **中证机器人**: 突破MA20，可关注")
    lines.append("")
    
    lines.append("---\n")
    lines.append("*本报告由市场监控系统自动生成*")
    
    return "\n".join(lines)


def generate_scheme_c_detailed():
    """方案C：详细版示例"""
    # 先生成标准版内容
    content = generate_scheme_b_standard()
    lines = [content]
    
    lines.append("\n---")
    lines.append("\n## 💼 五、持仓分析\n")
    lines.append("### 恒生科技ETF华夏 (513180)")
    lines.append("- **持仓成本**: 0.774")
    lines.append("- **当前价格**: 0.628")
    lines.append("- **盈亏**: -18.86% (-14469元)")
    lines.append("")
    lines.append("### 香港证券ETF易方达 (513090)")
    lines.append("- **持仓成本**: 2.089")
    lines.append("- **当前价格**: 1.862")
    lines.append("- **盈亏**: -10.87% (-4563元)")
    lines.append("")
    
    lines.append("---\n")
    lines.append("## 📝 六、市场解读\n")
    lines.append("今日市场整体呈现结构性分化，科技板块表现强势，传统板块承压。")
    lines.append("\n**主要观点**:")
    lines.append("- 恒生科技指数MACD金叉，短期动能转强")
    lines.append("- 软件服务板块KDJ超买，需注意回调风险")
    lines.append("- 资金流向显示主力资金青睐科技龙头\n")
    
    lines.append("\n---\n")
    lines.append("*本报告由市场监控系统自动生成*")
    
    return "\n".join(lines)


def generate_scheme_d_visual():
    """方案D：图文版示例"""
    lines = []
    lines.append("# 📊 市场监控日报（方案D - 图文版）\n")
    lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    lines.append("---\n")
    
    lines.append("## 📈 市场概况\n")
    lines.append("### 恒生科技指数")
    lines.append("- **当前价格**: 4500.23 (+1.2%)")
    lines.append("- 📊 [查看K线图](#)")
    lines.append("")
    
    lines.append("---\n")
    lines.append("## 📊 技术指标可视化\n")
    lines.append("### MACD指标走势")
    lines.append("![MACD走势图](temp_macd.png)")
    lines.append("")
    lines.append("### KDJ指标走势")
    lines.append("![KDJ走势图](temp_kdj.png)")
    lines.append("")
    
    lines.append("---\n")
    lines.append("## 💰 资金流向可视化\n")
    lines.append("### 主力资金流向")
    lines.append("![资金流向图](temp_capital.png)")
    lines.append("")
    
    lines.append("---\n")
    lines.append("*本报告由市场监控系统自动生成*")
    
    return "\n".join(lines)


def main():
    """主函数 - 生成所有方案的示例文档"""
    output_dir = Path("/Users/liuyi/WorkBuddy/stock-signal/market_monitor/report")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    schemes = {
        "scheme_a_simple": generate_scheme_a_simple,
        "scheme_b_standard": generate_scheme_b_standard,
        "scheme_c_detailed": generate_scheme_c_detailed,
        "scheme_d_visual": generate_scheme_d_visual,
    }
    
    print("="*60)
    print("生成市场监控日报方案示例")
    print("="*60)
    
    for scheme_name, generator_func in schemes.items():
        print(f"\n📝 生成: {scheme_name}")
        content = generator_func()
        
        output_file = output_dir / f"temp_{scheme_name}.md"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(content)
        
        print(f"   ✅ 已保存: {output_file}")
        print(f"   📏 大小: {output_file.stat().st_size} 字节")
    
    print("\n" + "="*60)
    print("✅ 所有方案示例已生成完成！")
    print("="*60)
    print("\n📋 下一步:")
    print("1. 查看生成的Markdown文件")
    print("2. 使用 lark-cli 将Markdown转换为飞书文档")
    print("3. 查看飞书文档效果")
    print("4. 选择您喜欢的方案")
    print("5. 确认后，删除其他方案的临时文件")


if __name__ == "__main__":
    main()
