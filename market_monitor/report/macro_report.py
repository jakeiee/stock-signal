"""
宏观交易分析报告 - HTML 格式生成模块。

生成与参考模板格式一致的 HTML 报告，包含：
- 头部：报告标题和生成时间
- 市场概览：4个关键指标卡片
- 资金面：核心资金指标、资金流入/流出渠道
- 基本面：宏观经济层、估值层
- 政策面：货币政策指标（待接入）
- 全球市场：美股、港股、大宗商品、外汇
- 综合判断：四维分析和交易提示

用法：
    python3 -m market_monitor --macro
    python3 -m market_monitor --macro --feishu  # 同时推送到飞书
"""

import os
from datetime import datetime
from typing import Any


def _format_number(val: Any, fmt: str = ".2f") -> str:
    """格式化数字"""
    if val is None:
        return "--"
    try:
        return f"{val:{fmt}}"
    except (TypeError, ValueError):
        return str(val)


def _format_pct(val: Any, show_sign: bool = True) -> str:
    """格式化百分比"""
    if val is None:
        return "--"
    try:
        if show_sign and val > 0:
            return f"+{val:.2f}%"
        return f"{val:.2f}%"
    except (TypeError, ValueError):
        return str(val)


def _get_signal_tag(value: float, thresholds: list, labels: list, default: str = "中性") -> tuple:
    """
    根据阈值返回信号标签和样式
    thresholds: [threshold1, threshold2, ...] 从大到小排序
    labels: ["标签1", "标签2", ...] 对应每个区间
    """
    if value is None:
        return default, "signal-neutral"
    
    for i, t in enumerate(thresholds):
        if value >= t:
            if i == 0:
                return labels[0], "signal-bullish"
            elif i == 1:
                return labels[1], "signal-neutral"
            else:
                return labels[2], "signal-bearish"
    return labels[-1] if labels else default, "signal-bearish"


def _format_change_class(chg: Any) -> str:
    """A股红色涨、绿色跌"""
    if chg is None:
        return ""
    try:
        if chg > 0:
            return "positive"  # 红色
        elif chg < 0:
            return "negative"  # 绿色
    except:
        pass
    return ""


def build_html_report(
    capital_data: dict,
    fundamental_data: dict,
    valuation_data: dict,
    policy_data: dict,
    global_data: dict,
) -> str:
    """
    构建完整的 HTML 报告
    """
    now = datetime.now()
    report_date = now.strftime("%Y年%m月%d日 %H:%M")
    today = now.strftime("%Y-%m-%d")
    
    # ─────────────────────────────────────────────────────────────────────────
    # 提取各维度数据
    # ─────────────────────────────────────────────────────────────────────────
    
    # 资金面数据
    znz = capital_data.get("znz_active_cap", {})
    znz_date = znz.get("date", "--")
    znz_cap = znz.get("active_cap")  # 亿元
    znz_chg = znz.get("chg_pct")
    znz_signal = znz.get("signal_desc", "")
    znz_pos = znz.get("position_suggest", "")
    
    new_accounts = capital_data.get("new_accounts", {})
    na_period = new_accounts.get("period", "--")
    na_val = new_accounts.get("new_accounts")
    na_mom = new_accounts.get("mom_pct")
    
    margin = capital_data.get("margin", {})
    mg_date = margin.get("date", "--")
    mg_bal = margin.get("total_bal")  # 亿元
    mg_chg = margin.get("bal_chg")
    mg_rz_mktcap = margin.get("rz_mktcap_ratio")  # 融资余额/流通市值
    mg_bal_mktcap = margin.get("bal_mktcap_ratio")  # 两融余额/流通市值
    mg_tratio = margin.get("turnover_ratio")  # 两融交易/成交额
    
    # 基本面数据
    gdp = fundamental_data.get("gdp", {})
    gdp_period = gdp.get("period", "--")
    gdp_yoy = gdp.get("gdp_yoy")
    
    # GDP 解读
    gdp_interp = fundamental_data.get("gdp_interpretation", {})
    gdp_interp_summary = gdp_interp.get("interpretation", {}).get("summary", "") if gdp_interp else ""
    
    di = fundamental_data.get("disposable_income", {})
    di_period = di.get("period", "--")
    di_yoy = di.get("income_yoy")
    
    # 收入解读
    income_interp = fundamental_data.get("income_interpretation", {})
    income_interp_summary = income_interp.get("interpretation", {}).get("summary", "") if income_interp else ""
    
    sd = fundamental_data.get("supply_demand", {})
    sd_period = sd.get("period", "--")
    cpi = sd.get("cpi_yoy")
    ppi = sd.get("ppi_yoy")
    ppi_cpi_spread = sd.get("ppi_cpi_spread")
    pmi_mfg = sd.get("pmi_mfg")
    pmi_svc = sd.get("pmi_svc")
    
    # CPI/PPI 解读
    cpi_ppi_interp = fundamental_data.get("cpi_ppi_interpretation", {})
    cpi_ppi_interp_summary = cpi_ppi_interp.get("interpretation", {}).get("summary", "") if cpi_ppi_interp else ""
    
    # PMI 解读
    pmi_interp = fundamental_data.get("pmi_interpretation", {})
    pmi_interp_summary = pmi_interp.get("interpretation", {}).get("summary", "") if pmi_interp else ""
    
    liq = fundamental_data.get("liquidity", {})
    liq_period = liq.get("period", "--")
    m2_yoy = liq.get("m2_yoy")
    bond_10y = liq.get("bond_10y")
    
    # 估值数据
    val = valuation_data.get("val", {})
    pe = val.get("pe")
    pe_pct = val.get("pe_pct")
    pb = val.get("pb")
    pb_pct = val.get("pb_pct")
    div = val.get("dividend")
    div_pct = val.get("dividend_pct")
    val_date = val.get("date", "--")
    
    # 全球市场数据
    us = global_data.get("us", {})
    us_date = us.get("date", "--")
    djia = us.get("DJIA", {})
    spx = us.get("SPX", {})
    ndx = us.get("NDX", {})
    
    mags = global_data.get("mags_val", {})
    mags_pe = mags.get("pe")
    mags_pe_pct = mags.get("pe_pct")
    
    commod = global_data.get("commodities", {})
    gold = commod.get("GOLD", {})
    wti = commod.get("WTI", {})
    brent = commod.get("BRENT", {})
    
    forex = global_data.get("forex", {})
    dxy = forex.get("DXY", {})
    usdcny = forex.get("USDCNY", {})
    
    asia = global_data.get("asia", {})
    hsi = asia.get("HSI", {})
    n225 = asia.get("N225", {})
    kospi = asia.get("KOSPI", {})
    
    techk = global_data.get("techk_val", {})
    techk_pe = techk.get("pe")
    techk_pe_pct = techk.get("pe_pct")
    
    # ─────────────────────────────────────────────────────────────────────────
    # 构建 HTML
    # ─────────────────────────────────────────────────────────────────────────
    
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>宏观交易分析报告 - {report_date}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: #f5f7fa;
            color: #333;
            line-height: 1.6;
        }}
        .container {{ max-width: 1400px; margin: 0 auto; padding: 20px; }}
        
        /* 头部 */
        .header {{
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white;
            padding: 40px;
            border-radius: 16px;
            margin-bottom: 30px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        }}
        .header h1 {{ font-size: 32px; margin-bottom: 10px; }}
        .header .subtitle {{ font-size: 16px; opacity: 0.9; }}
        .header .report-date {{ font-size: 14px; opacity: 0.7; margin-top: 10px; }}
        
        /* 概览卡片 */
        .overview-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .overview-card {{
            background: white;
            padding: 24px;
            border-radius: 12px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.06);
            border-left: 4px solid #2a5298;
        }}
        .overview-card h3 {{ font-size: 14px; color: #666; margin-bottom: 8px; text-transform: uppercase; }}
        .overview-card .value {{ font-size: 28px; font-weight: 700; color: #1e3c72; }}
        .overview-card .change {{ font-size: 14px; margin-top: 4px; }}
        .overview-card .change.positive {{ color: #e74c3c; }} /* A股红色表示涨 */
        .overview-card .change.negative {{ color: #27ae60; }} /* A股绿色表示跌 */
        
        /* 章节 */
        .section {{
            background: white;
            border-radius: 16px;
            padding: 30px;
            margin-bottom: 24px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.06);
        }}
        .section-header {{
            display: flex;
            align-items: center;
            margin-bottom: 24px;
            padding-bottom: 16px;
            border-bottom: 2px solid #f0f0f0;
        }}
        .section-icon {{
            width: 48px;
            height: 48px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            margin-right: 16px;
        }}
        .section-title {{ font-size: 22px; font-weight: 600; color: #1e3c72; }}
        
        /* 指标表格 */
        .indicator-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }}
        .indicator-table th {{
            background: #f8f9fa;
            padding: 14px 12px;
            text-align: left;
            font-weight: 600;
            color: #555;
            border-bottom: 2px solid #e0e0e0;
        }}
        .indicator-table td {{
            padding: 14px 12px;
            border-bottom: 1px solid #f0f0f0;
        }}
        .indicator-table tr:hover {{ background: #fafbfc; }}
        
        /* 信号标签 */
        .signal-tag {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
        }}
        .signal-bullish {{ background: #ffebee; color: #c62828; }}  /* 乐观 - 红色 */
        .signal-neutral {{ background: #fff3e0; color: #ef6c00; }}  /* 中性 - 橙色 */
        .signal-bearish {{ background: #e8f5e9; color: #2e7d32; }}  /* 偏冷 - 绿色 */
        .signal-danger {{ background: #fce4ec; color: #c2185b; }}   /* 过冷/危险 - 紫色 */
        
        /* 状态标签 */
        .status-tag {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
        }}
        .status-pending {{ background: #fff3e0; color: #ef6c00; }}
        .status-na {{ background: #f5f5f5; color: #757575; }}
        
        /* 数据源链接 */
        .source-link {{
            color: #2a5298;
            text-decoration: none;
            font-size: 12px;
        }}
        .source-link:hover {{ text-decoration: underline; }}
        
        /* 估值仪表盘 */
        .gauge-container {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }}
        .gauge-item {{
            text-align: center;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 12px;
        }}
        .gauge-value {{
            font-size: 32px;
            font-weight: 700;
            color: #1e3c72;
        }}
        .gauge-label {{ font-size: 13px; color: #666; margin-top: 8px; }}
        .gauge-percentile {{
            font-size: 14px;
            margin-top: 4px;
            font-weight: 600;
        }}
        
        /* 全球市场网格 */
        .market-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 16px;
        }}
        .market-item {{
            padding: 16px;
            background: #f8f9fa;
            border-radius: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .market-name {{ font-weight: 600; color: #333; }}
        .market-value {{ font-size: 18px; font-weight: 700; }}
        .market-change {{ font-size: 13px; margin-left: 8px; }}
        
        /* 页脚 */
        .footer {{
            text-align: center;
            padding: 30px;
            color: #999;
            font-size: 13px;
        }}
        
        /* 颜色 */
        .bg-capital {{ background: #e3f2fd; }}
        .bg-fundamental {{ background: #e8f5e9; }}
        .bg-policy {{ background: #fff3e0; }}
        .bg-global {{ background: #fce4ec; }}
        
        /* 模态框 */
        .modal {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.5);
            z-index: 1000;
            align-items: center;
            justify-content: center;
        }}
        .modal-content {{
            background: white;
            padding: 30px;
            border-radius: 12px;
            width: 450px;
            max-width: 90%;
            box-shadow: 0 8px 32px rgba(0,0,0,0.2);
        }}
        .modal-title {{
            margin-bottom: 20px;
            color: #1e3c72;
            font-size: 18px;
            font-weight: 600;
        }}
        .form-group {{
            margin-bottom: 16px;
        }}
        .form-group label {{
            display: block;
            margin-bottom: 6px;
            font-weight: 600;
            color: #555;
            font-size: 14px;
        }}
        .form-group input {{
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 6px;
            font-size: 14px;
        }}
        .form-hint {{
            font-size: 12px;
            color: #999;
            margin-top: 4px;
        }}
        .btn-group {{
            display: flex;
            gap: 12px;
            margin-top: 24px;
        }}
        .btn {{
            flex: 1;
            padding: 12px;
            border: none;
            border-radius: 6px;
            font-weight: 600;
            cursor: pointer;
            font-size: 14px;
        }}
        .btn-primary {{
            background: #2a5298;
            color: white;
        }}
        .btn-secondary {{
            background: #f0f0f0;
            color: #666;
            border: 1px solid #ddd;
        }}
        .date-shortcuts {{
            display: flex;
            gap: 8px;
            margin-top: 8px;
        }}
        .date-shortcuts button {{
            flex: 1;
            background: #f0f0f0;
            border: 1px solid #ddd;
            padding: 6px;
            border-radius: 4px;
            font-size: 12px;
            cursor: pointer;
        }}
        
        /* 折叠面板 */
        .collapsible {{
            background: #f8f9fa;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            margin-bottom: 16px;
            overflow: hidden;
        }}
        .collapsible-header {{
            padding: 12px 16px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: #f0f0f0;
        }}
        .collapsible-header:hover {{
            background: #e8e8e8;
        }}
        .collapsible-title {{
            font-weight: 600;
            color: #555;
        }}
        .collapsible-icon {{
            font-weight: bold;
            color: #666;
        }}
        .collapsible-content {{
            display: none;
            padding: 16px;
        }}
        .collapsible-content.active {{
            display: block;
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- 头部 -->
        <div class="header">
            <h1>宏观交易分析报告</h1>
            <div class="subtitle">基于资金面、基本面、政策面、全球市场四维框架</div>
            <div class="report-date">报告生成时间：{report_date}</div>
        </div>
        
        <!-- 市场概览 -->
        <div class="overview-grid">
            <div class="overview-card">
                <h3>万得全A PE</h3>
                <div class="value">{_format_number(pe)}</div>
                <div class="change {_format_change_class(pe_pct - 50) if pe_pct else ''}">历史分位 {pe_pct if pe_pct else '--'}%</div>
            </div>
            <div class="overview-card">
                <h3>指南针活跃市值</h3>
                <div class="value">{_format_number(znz_cap/10000) if znz_cap else '--'}万亿</div>
                <div class="change {_format_change_class(znz_chg) if znz_chg else ''}">日涨跌幅 {_format_pct(znz_chg, False) if znz_chg else '--'}</div>
            </div>
            <div class="overview-card">
                <h3>两融余额</h3>
                <div class="value">{_format_number(mg_bal/10000) if mg_bal else '--'}万亿</div>
                <div class="change {_format_change_class(-mg_chg) if mg_chg else ''}">日变动 {_format_pct(mg_chg, False) if mg_chg else '--'}</div>
            </div>
            <div class="overview-card">
                <h3>七巨头 PE</h3>
                <div class="value">{_format_number(mags_pe) if mags_pe else '--'}</div>
                <div class="change">历史分位 {mags_pe_pct if mags_pe_pct else '--'}%</div>
            </div>
        </div>
        
        <!-- 资金面 -->
        <div class="section">
            <div class="section-header">
                <div class="section-icon bg-capital">💰</div>
                <div class="section-title">一、资金面指标</div>
            </div>
            
            <!-- 核心资金观察指标 -->
            <h4 style="margin: 20px 0 12px; color: #555;">1.1 核心资金观察指标</h4>
            <table class="indicator-table">
                <thead>
                    <tr>
                        <th>指标</th>
                        <th>当前值</th>
                        <th>数据日期</th>
                        <th>当前信号</th>
                        <th>数据源</th>
                    </tr>
                </thead>
                <tbody>
                    <tr id="znz-row">
                        <td>
                            指南针活跃市值
                            <div style="margin-top: 8px;">
                                <button onclick="showManualUpload()" style="background: #2a5298; color: white; border: none; padding: 4px 12px; border-radius: 4px; font-size: 12px; cursor: pointer;">
                                    手动上传
                                </button>
                                <span style="font-size: 11px; color: #666; margin-left: 8px;">📅 支持历史日期</span>
                            </div>
                        </td>
                        <td>
                            <strong id="znz-value">{_format_number(znz_cap/10000, '.2f') if znz_cap else '--'}万亿</strong><br>
                            <span id="znz-change" style="color: #e74c3c; font-size: 12px;">日涨跌幅 {_format_pct(znz_chg, False)}</span>
                        </td>
                        <td id="znz-date">{znz_date}</td>
                        <td><span id="znz-signal" class="signal-tag signal-bearish">{znz_signal}</span></td>
                        <td><a href="#" onclick="showManualUpload(); return false;" class="source-link">手动上传</a></td>
                    </tr>
                </tbody>
            </table>
            
            <!-- 资金流入渠道 -->
            <h4 style="margin: 24px 0 12px; color: #555;">1.2 资金流入渠道</h4>
            
            <!-- 散户资金（折叠） -->
            <div class="collapsible">
                <div class="collapsible-header" onclick="toggleCollapsible(this)">
                    <span class="collapsible-title">📈 散户资金</span>
                    <span class="collapsible-icon">▼</span>
                </div>
                <div class="collapsible-content">
                    <table class="indicator-table">
                        <thead>
                            <tr>
                                <th>指标</th>
                                <th>当前值</th>
                                <th>数据日期</th>
                                <th>当前信号</th>
                                <th>数据源</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>A股月度新开户数</td>
                                <td><strong>{_format_number(na_val, '.1f') if na_val else '--'}万</strong><br><span style="color: #27ae60; font-size: 12px;">环比 {_format_pct(na_mom, False)}</span></td>
                                <td>{na_period}</td>
                                <td><span class="signal-tag signal-neutral">情绪未过热</span></td>
                                <td><a href="http://www.sse.com.cn/services/tradestats/monthly/" class="source-link" target="_blank">上交所</a></td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
            
            <!-- 杠杆资金（折叠） -->
            <div class="collapsible">
                <div class="collapsible-header" onclick="toggleCollapsible(this)">
                    <span class="collapsible-title">⚖️ 杠杆资金</span>
                    <span class="collapsible-icon">▼</span>
                </div>
                <div class="collapsible-content">
                    <table class="indicator-table">
                        <thead>
                            <tr>
                                <th>指标</th>
                                <th>当前值</th>
                                <th>数据日期</th>
                                <th>当前信号</th>
                                <th>数据源</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>两融余额</td>
                                <td><strong>{_format_number(mg_bal, '.2f') if mg_bal else '--'}亿元</strong><br><span style="color: #27ae60; font-size: 12px;">日变动 {_format_number(mg_chg, '+') if mg_chg is not None else '--'}亿</span></td>
                                <td>{mg_date}</td>
                                <td><span class="signal-tag signal-bullish">偏热</span></td>
                                <td><a href="https://data.eastmoney.com/rzrq/" class="source-link" target="_blank">东方财富</a></td>
                            </tr>
                            <tr>
                                <td>两融余额占流通市值</td>
                                <td><strong>{_format_number(mg_bal_mktcap, '.2f') if mg_bal_mktcap else '--'}%</strong></td>
                                <td>{mg_date}</td>
                                <td><span class="signal-tag signal-bullish">过热 (>2.5%)</span></td>
                                <td><a href="https://data.eastmoney.com/rzrq/" class="source-link" target="_blank">东方财富</a></td>
                            </tr>
                            <tr>
                                <td>两融交易额占比</td>
                                <td><strong>{_format_number(mg_tratio, '.2f') if mg_tratio else '--'}%</strong></td>
                                <td>{mg_date}</td>
                                <td><span class="signal-tag signal-neutral">中性</span></td>
                                <td><a href="https://data.eastmoney.com/rzrq/" class="source-link" target="_blank">东方财富</a></td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
            
            <!-- 机构资金（折叠） -->
            <div class="collapsible">
                <div class="collapsible-header" onclick="toggleCollapsible(this)">
                    <span class="collapsible-title">🏦 机构资金</span>
                    <span class="collapsible-icon">▼</span>
                </div>
                <div class="collapsible-content">
                    <table class="indicator-table">
                        <thead>
                            <tr>
                                <th>指标</th>
                                <th>当前值</th>
                                <th>数据日期</th>
                                <th>当前信号</th>
                                <th>状态</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>公募基金新发规模</td>
                                <td>--</td>
                                <td>--</td>
                                <td><span class="signal-tag signal-neutral">待接入</span></td>
                                <td><span class="status-tag status-pending">待实现</span></td>
                            </tr>
                            <tr>
                                <td>保险资金新增权益投资</td>
                                <td>--</td>
                                <td>--</td>
                                <td><span class="signal-tag signal-neutral">待接入</span></td>
                                <td><span class="status-tag status-pending">待实现</span></td>
                            </tr>
                            <tr>
                                <td>社保基金加仓规模</td>
                                <td>--</td>
                                <td>--</td>
                                <td><span class="signal-tag signal-neutral">待接入</span></td>
                                <td><span class="status-tag status-pending">待实现</span></td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
            
            <!-- 外资（折叠） -->
            <div class="collapsible">
                <div class="collapsible-header" onclick="toggleCollapsible(this)">
                    <span class="collapsible-title">🌏 外资（北向资金）</span>
                    <span class="collapsible-icon">▼</span>
                </div>
                <div class="collapsible-content">
                    <table class="indicator-table">
                        <thead>
                            <tr>
                                <th>指标</th>
                                <th>当前值</th>
                                <th>数据日期</th>
                                <th>当前信号</th>
                                <th>状态</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>北向资金净流入</td>
                                <td>--</td>
                                <td>--</td>
                                <td><span class="signal-tag signal-neutral">待接入</span></td>
                                <td><span class="status-tag status-pending">待实现</span></td>
                            </tr>
                            <tr>
                                <td>北向资金累计净买入</td>
                                <td>--</td>
                                <td>--</td>
                                <td><span class="signal-tag signal-neutral">待接入</span></td>
                                <td><span class="status-tag status-pending">待实现</span></td>
                            </tr>
                            <tr>
                                <td>北向资金每日成交额</td>
                                <td>--</td>
                                <td>--</td>
                                <td><span class="signal-tag signal-neutral">待接入</span></td>
                                <td><span class="status-tag status-pending">待实现</span></td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
            
            <!-- 分红再投资（折叠） -->
            <div class="collapsible">
                <div class="collapsible-header" onclick="toggleCollapsible(this)">
                    <span class="collapsible-title">💰 分红再投资</span>
                    <span class="collapsible-icon">▼</span>
                </div>
                <div class="collapsible-content">
                    <table class="indicator-table">
                        <thead>
                            <tr>
                                <th>指标</th>
                                <th>当前值</th>
                                <th>数据日期</th>
                                <th>当前信号</th>
                                <th>状态</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>年度分红总额</td>
                                <td>--</td>
                                <td>--</td>
                                <td><span class="signal-tag signal-neutral">待接入</span></td>
                                <td><span class="status-tag status-pending">待实现</span></td>
                            </tr>
                            <tr>
                                <td>股息再投资流入</td>
                                <td>--</td>
                                <td>--</td>
                                <td><span class="signal-tag signal-neutral">待接入</span></td>
                                <td><span class="status-tag status-pending">待实现</span></td>
                            </tr>
                            <tr>
                                <td>上市公司回购规模</td>
                                <td>--</td>
                                <td>--</td>
                                <td><span class="signal-tag signal-neutral">待接入</span></td>
                                <td><span class="status-tag status-pending">待实现</span></td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
            
            <!-- 资金流出渠道 -->
            <h4 style="margin: 20px 0 12px; color: #555;">1.3 资金流出渠道</h4>
            <div style="padding: 16px; background: #e3f2fd; border-radius: 8px;">
                <p style="color: #1565c0; font-size: 14px;">
                    ⚠️ 资金流出指标（IPO融资、再融资、股东减持等）暂无实时数据源接入
                </p>
            </div>
        </div>
        
        <!-- 基本面 -->
        <div class="section">
            <div class="section-header">
                <div class="section-icon bg-fundamental">📊</div>
                <div class="section-title">二、基本面指标</div>
            </div>
            
            <h4 style="margin: 20px 0 12px; color: #555;">2.1 宏观经济层</h4>
            <table class="indicator-table">
                <thead>
                    <tr>
                        <th>指标</th>
                        <th>当前值</th>
                        <th>数据日期</th>
                        <th>当前信号</th>
                        <th>数据源</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>GDP增速</td>
                        <td><strong>{_format_pct(gdp_yoy, False)}</strong></td>
                        <td>{gdp_period}</td>
                        <td><span class="signal-tag signal-neutral">中性(5%)</span></td>
                        <td><a href="https://data.stats.gov.cn/" class="source-link" target="_blank">国家统计局</a></td>
                    </tr>
                    <tr>
                        <td colspan="5" style="background: #f8f9fa; padding: 8px 12px; font-size: 12px; color: #666;">
                            📝 GDP 官方解读：{gdp_interp_summary[:80] if gdp_interp_summary else '暂无解读'}
                        </td>
                    </tr>
                    <tr>
                        <td>城镇居民人均可支配收入增速</td>
                        <td><strong>{_format_pct(di_yoy, False)}</strong></td>
                        <td>{di_period}</td>
                        <td><span class="signal-tag signal-neutral">中性</span></td>
                        <td><a href="https://data.stats.gov.cn/" class="source-link" target="_blank">国家统计局</a></td>
                    </tr>
                    <tr>
                        <td colspan="5" style="background: #f8f9fa; padding: 8px 12px; font-size: 12px; color: #666;">
                            📝 收入 官方解读：{income_interp_summary[:80] if income_interp_summary else '暂无解读'}
                        </td>
                    </tr>
                    <tr>
                        <td>CPI同比</td>
                        <td><strong>{_format_pct(cpi, False)}</strong></td>
                        <td>{sd_period}</td>
                        <td><span class="signal-tag signal-bearish">偏低(<2%)</span></td>
                        <td><a href="https://data.eastmoney.com/cjsj/cpi.html" class="source-link" target="_blank">东方财富</a></td>
                    </tr>
                    <tr>
                        <td>PPI同比</td>
                        <td><strong>{_format_pct(ppi, False)}</strong></td>
                        <td>{sd_period}</td>
                        <td><span class="signal-tag signal-bearish">通缩压力</span></td>
                        <td><a href="https://data.eastmoney.com/cjsj/ppi.html" class="source-link" target="_blank">东方财富</a></td>
                    </tr>
                    <tr>
                        <td colspan="5" style="background: #f8f9fa; padding: 8px 12px; font-size: 12px; color: #666;">
                            📝 CPI/PPI 官方解读：{cpi_ppi_interp_summary[:80] if cpi_ppi_interp_summary else '暂无解读'}
                        </td>
                    </tr>
                    <tr>
                        <td>制造业PMI</td>
                        <td><strong>{_format_number(pmi_mfg)}</strong></td>
                        <td>{sd_period}</td>
                        <td><span class="signal-tag signal-bearish">{"收缩区间(<50)" if pmi_mfg and pmi_mfg < 50 else "扩张区间(≥50)"}</span></td>
                        <td><a href="https://data.eastmoney.com/cjsj/pmi.html" class="source-link" target="_blank">东方财富</a></td>
                    </tr>
                    <tr>
                        <td>非制造业PMI</td>
                        <td><strong>{_format_number(pmi_svc)}</strong></td>
                        <td>{sd_period}</td>
                        <td><span class="signal-tag signal-bearish">{"收缩区间(<50)" if pmi_svc and pmi_svc < 50 else "扩张区间(≥50)"}</span></td>
                        <td><a href="https://data.eastmoney.com/cjsj/pmi.html" class="source-link" target="_blank">东方财富</a></td>
                    </tr>
                    <tr>
                        <td colspan="5" style="background: #f8f9fa; padding: 8px 12px; font-size: 12px; color: #666;">
                            📝 PMI 官方解读：{pmi_interp_summary[:80] if pmi_interp_summary else '暂无解读'}
                        </td>
                    </tr>
                    <tr>
                        <td>M2同比增速</td>
                        <td><strong>{_format_pct(m2_yoy, False)}</strong></td>
                        <td>{liq_period}</td>
                        <td><span class="signal-tag signal-neutral">中性(9%)</span></td>
                        <td><a href="https://data.eastmoney.com/cjsj/hbgyl.html" class="source-link" target="_blank">东方财富</a></td>
                    </tr>
                    <tr>
                        <td>10年期国债收益率</td>
                        <td><strong>{_format_number(bond_10y, '.2f') if bond_10y else '--'}%</strong></td>
                        <td>{liq_period}</td>
                        <td><span class="signal-tag signal-bullish">宽松(<2.5%)</span></td>
                        <td><a href="http://www.chinamoney.com.cn/" class="source-link" target="_blank">中国货币网</a></td>
                    </tr>
                </tbody>
            </table>
            
            <h4 style="margin: 24px 0 12px; color: #555;">2.2 估值层 - A股整体</h4>
            <div class="gauge-container">
                <div class="gauge-item">
                    <div class="gauge-value">{_format_number(pe)}</div>
                    <div class="gauge-label">万得全A PE</div>
                    <div class="gauge-percentile" style="color: #e74c3c">历史分位 {pe_pct if pe_pct else '--'}%</div>
                </div>
                <div class="gauge-item">
                    <div class="gauge-value">{_format_number(pb)}</div>
                    <div class="gauge-label">万得全A PB</div>
                    <div class="gauge-percentile" style="color: #27ae60">历史分位 {pb_pct if pb_pct else '--'}%</div>
                </div>
                <div class="gauge-item">
                    <div class="gauge-value">{_format_number(div, '.2f') if div else '--'}%</div>
                    <div class="gauge-label">股息率</div>
                    <div class="gauge-percentile">分位 {div_pct if div_pct else '--'}%</div>
                </div>
            </div>
            <p style="margin-top: 16px; padding: 12px; background: #ffebee; border-radius: 8px; color: #c62828; font-size: 14px;">
                <strong>估值判断：</strong>万得全A PE历史分位{pe_pct if pe_pct else '--'}%，处于<strong>{"高估区间" if pe_pct and pe_pct > 80 else "中性区间"}</strong>（{" >80%" if pe_pct and pe_pct > 80 else ""}），需警惕估值回归风险。
            </p>
        </div>
        
        <!-- 政策面 -->
        <div class="section">
            <div class="section-header">
                <div class="section-icon bg-policy">🏛️</div>
                <div class="section-title">三、政策面指标</div>
            </div>
            
            <table class="indicator-table">
                <thead>
                    <tr>
                        <th>指标</th>
                        <th>当前值</th>
                        <th>数据日期</th>
                        <th>当前信号</th>
                        <th>状态</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>存款准备金率</td>
                        <td>--</td>
                        <td>--</td>
                        <td><span class="signal-tag signal-neutral">待接入</span></td>
                        <td><span class="status-tag status-pending">待实现</span></td>
                    </tr>
                    <tr>
                        <td>1年期LPR</td>
                        <td>--</td>
                        <td>--</td>
                        <td><span class="signal-tag signal-neutral">待接入</span></td>
                        <td><span class="status-tag status-pending">待实现</span></td>
                    </tr>
                    <tr>
                        <td>5年期LPR</td>
                        <td>--</td>
                        <td>--</td>
                        <td><span class="signal-tag signal-neutral">待接入</span></td>
                        <td><span class="status-tag status-pending">待实现</span></td>
                    </tr>
                </tbody>
            </table>
            <p style="margin-top: 16px; padding: 12px; background: #fff3e0; border-radius: 8px; color: #ef6c00; font-size: 14px;">
                <strong>说明：</strong>货币政策指标暂未接入实时数据源，建议关注<a href="http://www.chinamoney.com.cn/" target="_blank" style="color: #2a5298;">中国货币网</a>获取最新LPR、MLF等政策利率数据。
            </p>
        </div>
        
        <!-- 全球市场 -->
        <div class="section">
            <div class="section-header">
                <div class="section-icon bg-global">🌍</div>
                <div class="section-title">四、全球市场对比</div>
            </div>
            
            <h4 style="margin: 20px 0 12px; color: #555;">4.1 美股市场估值</h4>
            <div class="gauge-container">
                <div class="gauge-item">
                    <div class="gauge-value">{_format_number(mags_pe)}</div>
                    <div class="gauge-label">七巨头 PE</div>
                    <div class="gauge-percentile" style="color: #c2185b;">历史分位 {mags_pe_pct if mags_pe_pct else '--'}%</div>
                </div>
            </div>
            
            <h4 style="margin: 24px 0 12px; color: #555;">4.2 美股走势</h4>
            <div class="market-grid">
                <div class="market-item">
                    <span class="market-name">标普500</span>
                    <span>
                        <span class="market-value">{_format_number(spx.get('price')) if spx.get('price') else '--'}</span>
                        <span class="market-change" style="color: {'#27ae60' if spx.get('chg5d_pct', 0) < 0 else '#e74c3c'}">{_format_pct(spx.get('chg5d_pct'), False) if spx.get('chg5d_pct') else '--'}</span>
                    </span>
                </div>
                <div class="market-item">
                    <span class="market-name">纳斯达克100</span>
                    <span>
                        <span class="market-value">{_format_number(ndx.get('price')) if ndx.get('price') else '--'}</span>
                        <span class="market-change" style="color: {'#27ae60' if ndx.get('chg5d_pct', 0) < 0 else '#e74c3c'}">{_format_pct(ndx.get('chg5d_pct'), False) if ndx.get('chg5d_pct') else '--'}</span>
                    </span>
                </div>
                <div class="market-item">
                    <span class="market-name">道琼斯</span>
                    <span>
                        <span class="market-value">{_format_number(djia.get('price')) if djia.get('price') else '--'}</span>
                        <span class="market-change" style="color: {'#27ae60' if djia.get('chg5d_pct', 0) < 0 else '#e74c3c'}">{_format_pct(djia.get('chg5d_pct'), False) if djia.get('chg5d_pct') else '--'}</span>
                    </span>
                </div>
            </div>
            
            <h4 style="margin: 24px 0 12px; color: #555;">4.3 港股市场</h4>
            <div class="market-grid">
                <div class="market-item">
                    <span class="market-name">恒生指数</span>
                    <span>
                        <span class="market-value">{_format_number(hsi.get('price')) if hsi.get('price') else '--'}</span>
                        <span class="market-change" style="color: {'#27ae60' if hsi.get('chg5d_pct', 0) < 0 else '#e74c3c'}">{_format_pct(hsi.get('chg5d_pct'), False) if hsi.get('chg5d_pct') else '--'}</span>
                    </span>
                </div>
                <div class="market-item">
                    <span class="market-name">日经225</span>
                    <span>
                        <span class="market-value">{_format_number(n225.get('price')) if n225.get('price') else '--'}</span>
                        <span class="market-change" style="color: {'#27ae60' if n225.get('chg5d_pct', 0) < 0 else '#e74c3c'}">{_format_pct(n225.get('chg5d_pct'), False) if n225.get('chg5d_pct') else '--'}</span>
                    </span>
                </div>
                <div class="market-item">
                    <span class="market-name">韩国综合</span>
                    <span>
                        <span class="market-value">{_format_number(kospi.get('price')) if kospi.get('price') else '--'}</span>
                        <span class="market-change" style="color: {'#27ae60' if kospi.get('chg5d_pct', 0) < 0 else '#e74c3c'}">{_format_pct(kospi.get('chg5d_pct'), False) if kospi.get('chg5d_pct') else '--'}</span>
                    </span>
                </div>
                <div class="market-item">
                    <span class="market-name">港科技 PE</span>
                    <span class="market-value">{_format_number(techk_pe)} ({techk_pe_pct}%)</span>
                </div>
            </div>
            
            <h4 style="margin: 24px 0 12px; color: #555;">4.4 大宗商品与外汇</h4>
            <div class="market-grid">
                <div class="market-item">
                    <span class="market-name">黄金 (COMEX)</span>
                    <span>
                        <span class="market-value">{_format_number(gold.get('price')) if gold.get('price') else '--'}</span>
                        <span class="market-change" style="color: {'#27ae60' if gold.get('chg5d_pct', 0) < 0 else '#e74c3c'}">{_format_pct(gold.get('chg5d_pct'), False) if gold.get('chg5d_pct') else '--'}</span>
                    </span>
                </div>
                <div class="market-item">
                    <span class="market-name">WTI原油</span>
                    <span>
                        <span class="market-value">{_format_number(wti.get('price')) if wti.get('price') else '--'}</span>
                        <span class="market-change" style="color: {'#27ae60' if wti.get('chg5d_pct', 0) < 0 else '#e74c3c'}">{_format_pct(wti.get('chg5d_pct'), False) if wti.get('chg5d_pct') else '--'}</span>
                    </span>
                </div>
                <div class="market-item">
                    <span class="market-name">美元指数 DXY</span>
                    <span>
                        <span class="market-value">{_format_number(dxy.get('price'), '.2f') if dxy.get('price') else '--'}</span>
                        <span class="market-change" style="color: {'#27ae60' if dxy.get('chg5d_pct', 0) < 0 else '#e74c3c'}">{_format_pct(dxy.get('chg5d_pct'), False) if dxy.get('chg5d_pct') else '--'}</span>
                    </span>
                </div>
                <div class="market-item">
                    <span class="market-name">USD/CNY</span>
                    <span>
                        <span class="market-value">{_format_number(usdcny.get('price'), '.4f') if usdcny.get('price') else '--'}</span>
                        <span class="market-change" style="color: {'#27ae60' if usdcny.get('chg5d_pct', 0) < 0 else '#e74c3c'}">{_format_pct(usdcny.get('chg5d_pct'), False) if usdcny.get('chg5d_pct') else '--'}</span>
                    </span>
                </div>
            </div>
        </div>
        
        <!-- 综合判断 -->
        <div class="section">
            <div class="section-header">
                <div class="section-icon" style="background: #f3e5f5;">📋</div>
                <div class="section-title">五、综合判断与交易提示</div>
            </div>
            
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px;">
                <div style="padding: 20px; background: #e3f2fd; border-radius: 12px;">
                    <h4 style="color: #1565c0; margin-bottom: 12px;">💰 资金面</h4>
                    <p style="font-size: 14px; color: #555;">
                        指南针活跃市值 {_format_number(znz_cap/10000, '.2f') if znz_cap else '--'}万亿（{_format_pct(znz_chg, False)}）发出{znz_signal}；
                        杠杆资金偏热，两融余额占流通市值{_format_number(mg_bal_mktcap, '.2f') if mg_bal_mktcap else '--'}%；
                        散户资金：新开户数{_format_number(na_val, '.1f') if na_val else '--'}万，情绪未过热；
                    </p>
                </div>
                <div style="padding: 20px; background: #e8f5e9; border-radius: 12px;">
                    <h4 style="color: #2e7d32; margin-bottom: 12px;">📊 基本面</h4>
                    <p style="font-size: 14px; color: #555;">
                        GDP增速{gdp_yoy if gdp_yoy else '--'}%符合预期；CPI/PPI双低显示通缩压力；
                        PMI处于{"收缩" if (pmi_mfg and pmi_mfg < 50) else "扩张"}区间；
                        10年国债收益率{bond_10y if bond_10y else '--'}%显示流动性宽松。经济基本面偏弱，但政策空间充足。
                    </p>
                </div>
                <div style="padding: 20px; background: #ffebee; border-radius: 12px;">
                    <h4 style="color: #c62828; margin-bottom: 12px;">💹 估值面</h4>
                    <p style="font-size: 14px; color: #555;">
                        <strong>万得全A PE {_format_number(pe) if pe else '--'}倍，历史分位{pe_pct if pe_pct else '--'}%</strong>，
                        处于{"高估" if pe_pct and pe_pct > 80 else "中性"}区间；
                        七巨头PE{mags_pe if mags_pe else '--'}，全球估值承压。
                    </p>
                </div>
                <div style="padding: 20px; background: #fff3e0; border-radius: 12px;">
                    <h4 style="color: #ef6c00; margin-bottom: 12px;">🌍 全球市场</h4>
                    <p style="font-size: 14px; color: #555;">
                        美股近5日回调；港股同步下跌；
                        黄金 {_format_pct(gold.get('chg5d_pct'), False) if gold.get('chg5d_pct') else '--'}；
                        美元指数 {_format_pct(dxy.get('chg5d_pct'), False) if dxy.get('chg5d_pct') else '--'}。全球市场风险偏好下降。
                    </p>
                </div>
            </div>
            
            <div style="margin-top: 24px; padding: 20px; background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); color: white; border-radius: 12px;">
                <h4 style="margin-bottom: 12px;">⚠️ 交易提示</h4>
                <ul style="margin-left: 20px; font-size: 14px; line-height: 2;">
                    <li><strong>估值风险：</strong>A股与美股均处于历史估值高位，警惕均值回归风险</li>
                    <li><strong>杠杆风险：</strong>两融余额占比过高，需关注去杠杆风险</li>
                    <li><strong>基本面风险：</strong>PMI、CPI、PPI均偏弱，经济复苏动能不足</li>
                    <li><strong>配置建议：</strong>控制仓位，关注低估值防御板块，等待更好的入场时机</li>
                </ul>
            </div>
        </div>
        
        <!-- 页脚 -->
        <div class="footer">
            <p>数据来源：东方财富、Wind、国家统计局、上交所、中国货币网等</p>
            <p style="margin-top: 8px;">本报告仅供参考，不构成投资建议</p>
        </div>
    </div>
    
    <!-- 手动上传模态框 -->
    <div id="uploadModal" class="modal">
        <div class="modal-content">
            <h3 class="modal-title">📊 指南针活跃市值 - 手动上传</h3>
            
            <div class="form-group">
                <label>活跃市值点数（亿元）</label>
                <input type="number" step="0.01" id="compassValue" placeholder="例如：186349.4">
                <p class="form-hint">注：输入活跃市值的亿元数</p>
            </div>
            
            <div class="form-group">
                <label>涨跌幅（%）</label>
                <input type="number" step="0.01" id="compassChange" placeholder="例如：-2.94">
                <p class="form-hint">注：正数表示上涨，负数表示下跌</p>
            </div>
            
            <div class="form-group">
                <label>数据日期</label>
                <input type="date" id="compassDate">
                <div class="date-shortcuts">
                    <button onclick="setDate(-1)">昨天</button>
                    <button onclick="setDate(0)">今天</button>
                    <button onclick="setDate(-7)">一周前</button>
                </div>
                <p class="form-hint">选择数据对应的日期，支持历史数据录入</p>
            </div>
            
            <div class="btn-group">
                <button class="btn btn-primary" onclick="saveManualData()">确认更新</button>
                <button class="btn btn-secondary" onclick="hideModal()">取消</button>
            </div>
            
            <p style="font-size: 12px; color: #777; margin-top: 16px;">
                <strong>数据存储：</strong>更新后数据将保存至本地CSV文件，支持历史日期记录
            </p>
        </div>
    </div>
    
    <script>
        // 折叠展开功能
        function toggleCollapsible(header) {{
            const content = header.nextElementSibling;
            const icon = header.querySelector('.collapsible-icon');
            if (content.style.display === 'block') {{
                content.style.display = 'none';
                icon.textContent = '▼';
            }} else {{
                content.style.display = 'block';
                icon.textContent = '▲';
            }}
        }}
        
        // 手动上传模态框
        function showManualUpload() {{
            // 设置默认日期为今天
            const today = new Date().toISOString().split('T')[0];
            document.getElementById('compassDate').value = today;
            
            // 清空输入框
            document.getElementById('compassValue').value = '';
            document.getElementById('compassChange').value = '';
            
            document.getElementById('uploadModal').style.display = 'flex';
        }}
        
        function hideModal() {{
            document.getElementById('uploadModal').style.display = 'none';
        }}
        
        // 快捷日期设置
        function setDate(daysOffset) {{
            const dateField = document.getElementById('compassDate');
            let targetDate = new Date();
            
            if (daysOffset !== 0) {{
                targetDate.setDate(targetDate.getDate() + daysOffset);
            }}
            
            dateField.value = targetDate.toISOString().split('T')[0];
        }}
        
        // 计算指南针信号
        function calcZnzSignal(chgPct) {{
            if (chgPct >= 4.0) {{
                return {{ text: '🟢 增量资金入场（单日涨幅≥4%）', class: 'signal-bullish', signal: 'incremental' }};
            }} else if (chgPct <= -2.3) {{
                return {{ text: '🔴 资金离场警示（单日跌幅≤-2.3%）', class: 'signal-bearish', signal: 'exit' }};
            }} else {{
                return {{ text: '🟡 观望（无明显信号）', class: 'signal-neutral', signal: 'neutral' }};
            }}
        }}
        
        // 保存手动数据
        function saveManualData() {{
            const value = document.getElementById('compassValue').value;
            const change = document.getElementById('compassChange').value;
            const date = document.getElementById('compassDate').value;
            
            if (!value || !change || !date) {{
                alert('请填写完整信息');
                return;
            }}
            
            const currentValue = parseFloat(value);
            const currentChange = parseFloat(change);
            
            // 更新表格中的显示
            const valueCell = document.getElementById('znz-value');
            const changeCell = document.getElementById('znz-change');
            const dateCell = document.getElementById('znz-date');
            const signalCell = document.getElementById('znz-signal');
            
            // 格式化显示值
            const displayValue = (currentValue / 10000).toFixed(2) + '万亿';
            
            if (valueCell) valueCell.textContent = displayValue;
            if (changeCell) {{
                const color = currentChange < 0 ? '#e74c3c' : '#27ae60';
                changeCell.style.color = color;
                changeCell.textContent = `日涨跌幅 ${{currentChange > 0 ? '+' : ''}}${{currentChange.toFixed(2)}}%`;
            }}
            if (dateCell) dateCell.textContent = date;
            
            // 更新信号标签（使用正确的信号规则）
            if (signalCell) {{
                const signal = calcZnzSignal(currentChange);
                signalCell.textContent = signal.text;
                signalCell.className = `signal-tag ${{signal.class}}`;
            }}
            
            // 更新概览卡片
            const overviewValue = document.querySelector('.overview-card:nth-child(2) .value');
            const overviewChange = document.querySelector('.overview-card:nth-child(2) .change');
            
            if (overviewValue) overviewValue.textContent = displayValue;
            if (overviewChange) {{
                const color = currentChange < 0 ? 'negative' : 'positive';
                overviewChange.textContent = `日涨跌幅 ${{currentChange.toFixed(2)}}%`;
                overviewChange.className = `change ${{color}}`;
            }}
            
            // 保存到CSV文件
            saveToCsv({{
                indicator: '指南针活跃市值',
                value: currentValue,
                change_percent: currentChange,
                date: date
            }});
            
            hideModal();
            alert(`数据已更新并保存至CSV！\\n日期：${{date}}\\n活跃市值：${{displayValue}}\\n涨跌幅：${{currentChange.toFixed(2)}}%`);
        }}
        
        // 保存数据到CSV文件
        function saveToCsv(data) {{
            // 计算信号
            const signalInfo = calcZnzSignal(data.change_percent);
            
            // 构建CSV行数据
            const csvRow = `${{data.date}},${{data.value}},${{data.change_percent}},${{signalInfo.signal}},manual\\n`;
            
            // 尝试使用File System Access API保存文件
            if ('showSaveFilePicker' in window) {{
                saveWithFilePicker(csvRow, data);
            }} else {{
                // 降级方案：下载CSV文件
                downloadCsv(csvRow, data);
            }}
        }}
        
        // 使用File System Access API保存
        async function saveWithFilePicker(csvRow, data) {{
            try {{
                // 尝试打开或创建CSV文件
                const fileHandle = await window.showSaveFilePicker({{
                    suggestedName: 'znz_active_cap.csv',
                    types: [{{
                        description: 'CSV文件',
                        accept: {{ 'text/csv': ['.csv'] }}
                    }}]
                }});
                
                const writable = await fileHandle.createWritable();
                
                // 读取现有内容
                let existingContent = '';
                try {{
                    const file = await fileHandle.getFile();
                    existingContent = await file.text();
                }} catch (e) {{
                    // 文件不存在，写入表头
                    existingContent = 'date,active_cap,chg_pct,signal,source\\n';
                }}
                
                // 检查是否已存在该日期的记录
                const lines = existingContent.split('\\n');
                let newContent = lines[0] + '\\n'; // 保留表头
                let dateExists = false;
                
                for (let i = 1; i < lines.length; i++) {{
                    if (lines[i].startsWith(data.date + ',')) {{
                        // 更新已有记录
                        newContent += csvRow;
                        dateExists = true;
                    }} else if (lines[i].trim()) {{
                        newContent += lines[i] + '\\n';
                    }}
                }}
                
                if (!dateExists) {{
                    newContent += csvRow;
                }}
                
                await writable.write(newContent);
                await writable.close();
                
                console.log('CSV文件已保存:', fileHandle.name);
            }} catch (err) {{
                console.error('保存失败:', err);
                // 降级到下载方案
                downloadCsv(csvRow, data);
            }}
        }}
        
        // 下载CSV文件（降级方案）
        function downloadCsv(csvRow, data) {{
            // 构建完整CSV内容
            let csvContent = 'date,active_cap,chg_pct,signal,source\\n';
            csvContent += csvRow;
            
            const blob = new Blob([csvContent], {{ type: 'text/csv;charset=utf-8;' }});
            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = `znz_active_cap_${{data.date}}.csv`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            
            console.log('CSV文件已下载');
        }}
        
        // 点击模态框外部关闭
        document.getElementById('uploadModal').addEventListener('click', function(e) {{
            if (e.target === this) hideModal();
        }});
        
        // 初始化折叠状态
        window.addEventListener('DOMContentLoaded', function() {{
            // 所有折叠面板默认收起
            document.querySelectorAll('.collapsible-content').forEach(function(content) {{
                content.style.display = 'none';
            }});
        }});
    </script>
</body>
</html>"""
    
    return html


def save_html_report(html: str, output_dir: str = None) -> str:
    """
    保存 HTML 报告到文件
    """
    if output_dir is None:
        output_dir = os.path.expanduser("~/WorkBuddy/20260314145315/market_monitor/data")
    
    os.makedirs(output_dir, exist_ok=True)
    
    # 生成文件名：macro_report_YYYY-MM-DD.html
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"macro_report_{today}.html"
    filepath = os.path.join(output_dir, filename)
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)
    
    return filepath


def generate_and_save(
    capital_data: dict,
    fundamental_data: dict,
    valuation_data: dict,
    policy_data: dict,
    global_data: dict,
    output_dir: str = None,
) -> str:
    """
    生成并保存报告，返回文件路径
    """
    html = build_html_report(
        capital_data=capital_data,
        fundamental_data=fundamental_data,
        valuation_data=valuation_data,
        policy_data=policy_data,
        global_data=global_data,
    )
    
    filepath = save_html_report(html, output_dir)
    return filepath
