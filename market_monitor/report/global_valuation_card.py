"""
全球估值飞书卡片生成模块。

提供多种展示方案：
  1. 紧凑表格版 - 简洁的横向对比表格
  2. 国家分组版 - 按国家分组展示多个指数
  3. 热力图版 - 使用颜色热力图展示估值水平
"""

import os
import json
from datetime import datetime
from typing import Dict, Any, List, Optional

from ..data_sources.trendonify import fetch_trendonify_valuation
from ..data_sources.worldperatio import fetch_worldperatio_major_indexes, _parse_evaluation_to_percentile
from ..data_sources.hk_valuation import fetch_eniu_hsi
from ..data_sources.hk_tech_valuation import fetch_hk_tech_for_global
from ..data_sources.shiller_api import fetch_us_cape_valuation
from .feishu_image import upload_image_to_feishu


def _get_valuation_level_icon(pct: Optional[float]) -> str:
    """根据百分位返回估值等级图标"""
    if pct is None:
        return "⚪"
    if pct >= 81:
        return "🔴"  # 昂贵
    elif pct >= 61:
        return "🟠"  # 高估
    elif pct >= 41:
        return "🟡"  # 合理
    elif pct >= 21:
        return "🟢"  # 低估
    else:
        return "🟢🟢"  # 有吸引力


def _get_valuation_level_text(pct: Optional[float]) -> str:
    """根据百分位返回估值等级文字"""
    if pct is None:
        return "未知"
    if pct >= 81:
        return "昂贵"
    elif pct >= 61:
        return "高估"
    elif pct >= 41:
        return "合理"
    elif pct >= 21:
        return "低估"
    else:
        return "有吸引力"


def _format_deviation(dev: Optional[str]) -> str:
    """格式化偏离度显示"""
    if not dev:
        return "--"
    # 提取数值
    import re
    match = re.search(r'([+-]?[0-9.]+)', dev)
    if match:
        val = float(match.group(1))
        sign = "+" if val >= 0 else ""
        return f"{sign}{val:.2f}σ"
    return dev


def fetch_enhanced_global_valuation() -> Dict[str, Any]:
    """
    获取增强版全球估值数据，包含更多指数细节。
    
    Returns:
        {
            "date": str,
            "markets": {
                "US": {
                    "indices": [
                        {"name": "标普500", "symbol": "SPY", "pe": float, "pct_10y": float, ...},
                        {"name": "纳斯达克100", "symbol": "QQQ", ...},
                        {"name": "道琼斯", "symbol": "DIA", ...},
                    ]
                },
                "HK": {
                    "indices": [
                        {"name": "恒生指数", "symbol": "HSI", "pe": float, "dividend_yield": float, ...},
                        {"name": "恒生科技", "symbol": "HSTECH", ...},
                    ]
                },
                "JP": {...},
                "KR": {...},
            },
            "sources": [str],
        }
    """
    result = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "markets": {
            "US": {"indices": []},
            "HK": {"indices": []},
            "JP": {"indices": []},
            "KR": {"indices": []},
        },
        "sources": [],
    }
    
    # 1. 获取 Shiller CAPE 数据（美股权威估值指标）
    print("[全球估值卡片] 获取 Shiller CAPE 数据...")
    cape_data = fetch_us_cape_valuation()
    
    if not cape_data.get("error") and cape_data.get("cape"):
        result["sources"].append("Shiller/Yale")
        
        # 添加标普500 CAPE 数据
        sp500_cape = {
            "name": "标普500 (CAPE)",
            "symbol": "SPY",
            "pe": cape_data.get("cape"),  # CAPE作为PE展示
            "pct_10y": cape_data.get("cape_10y_pct"),
            "pct_max": cape_data.get("cape_max_pct"),
            "avg_10y": cape_data.get("mean_10y"),
            "date": cape_data.get("date", ""),
            "source": "shiller",
            "note": "周期调整市盈率",
            # Shiller 数据准确
            "pct_10y_accurate": True,
            "pct_max_accurate": True,
        }
        result["markets"]["US"]["indices"].append(sp500_cape)
    
    # 2. 获取 WorldPERatio 数据（包含美股、日股等）
    print("[全球估值卡片] 获取 WorldPERatio 数据...")
    wp_data = fetch_worldperatio_major_indexes()
    
    if not wp_data.get("error") and wp_data.get("data"):
        result["sources"].append(f"WorldPERatio ({wp_data.get('last_update', '')})")
        
        for item in wp_data["data"]:
            symbol = item.get("symbol", "")
            country = item.get("country", "")
            
            # 计算10年分位和max分位（20年作为max）
            # 注意：这些是估算值，不是准确的历史百分位
            eval_10y = item.get("evaluation_10y", "")
            eval_20y = item.get("evaluation_20y", "")
            pct_10y = _parse_evaluation_to_percentile(eval_10y)
            pct_max = _parse_evaluation_to_percentile(eval_20y) if eval_20y else pct_10y
            
            index_data = {
                "name": item.get("name", ""),
                "symbol": symbol,
                "pe": item.get("pe"),
                "evaluation_5y": item.get("evaluation_5y", ""),
                "evaluation_10y": eval_10y,
                "evaluation_20y": eval_20y,
                "dev_5y": item.get("dev_5y", ""),
                "dev_10y": item.get("dev_10y", ""),
                "dev_20y": item.get("dev_20y", ""),
                "avg_5y": item.get("avg_5y"),
                "avg_10y": item.get("avg_10y"),
                "avg_20y": item.get("avg_20y"),
                "trend_margin": item.get("trend_margin", ""),
                "date": item.get("date", ""),
                "source": "worldperatio",
                "pct_10y": pct_10y,
                "pct_max": pct_max,
                # 标记数据准确性：WorldPERatio 的百分位是估算值，不准确
                "pct_10y_accurate": False,
                "pct_max_accurate": False,
            }
            
            # 美股指数（跳过SPY，因为已经有CAPE数据）
            if country == "US":
                if symbol in ["QQQ", "DIA", "IWM"]:  # 不包括 SPY
                    result["markets"]["US"]["indices"].append(index_data)
            
            # 日股
            elif country == "JP":
                if symbol == "EWJ":
                    index_data["name"] = "MSCI Japan (日经相关)"
                    result["markets"]["JP"]["indices"].append(index_data)
    
    # 2. 获取港股详细数据
    print("[全球估值卡片] 获取港股估值数据...")
    hk_data = fetch_eniu_hsi()
    
    if not hk_data.get("error") and hk_data.get("pe"):
        result["sources"].append("亿牛网")
        
        # 恒生指数
        hsi_data = {
            "name": "恒生指数",
            "symbol": "HSI",
            "pe": hk_data.get("pe"),
            "dividend_yield": hk_data.get("dividend_yield"),
            "pe_avg": hk_data.get("pe_avg"),
            "pe_max": hk_data.get("pe_max"),
            "pe_min": hk_data.get("pe_min"),
            "pct_3y": hk_data.get("percentile_3y"),
            "pct_5y": hk_data.get("percentile_5y"),
            "pct_10y": hk_data.get("percentile_10y"),
            "pct_max": hk_data.get("percentile_all"),  # 所有时间百分位作为max分位
            "date": hk_data.get("date", ""),
            "source": "eniu",
            # 亿牛网数据准确
            "pct_10y_accurate": True,
            "pct_max_accurate": True,
        }
        result["markets"]["HK"]["indices"].append(hsi_data)
        
        # 恒生科技指数
        hk_tech_data = fetch_hk_tech_for_global()
        if not hk_tech_data.get("error") and hk_tech_data.get("pe"):
            result["sources"].append("雪球基金")
            
            hstech_data = {
                "name": "恒生科技",
                "symbol": "HSTECH",
                "pe": hk_tech_data.get("pe"),
                "pb": hk_tech_data.get("pb"),
                "pct_10y": hk_tech_data.get("pct_10y"),
                "pb_percentile": hk_tech_data.get("pb_percentile"),
                "roe": hk_tech_data.get("roe"),
                "yield": hk_tech_data.get("yield"),
                "eva_type": hk_tech_data.get("eva_type"),
                "date": hk_tech_data.get("date", ""),
                "source": "danjuan",
                # 雪球基金数据准确
                "pct_10y_accurate": True,
                "pct_max_accurate": False,  # 雪球基金没有max分位数据
            }
            result["markets"]["HK"]["indices"].append(hstech_data)
    
    # 3. 获取基础估值数据（用于补充缺失的市场）
    base_data = fetch_trendonify_valuation()
    
    # 补充日股数据（如果没有从WorldPERatio获取到）
    if not result["markets"]["JP"]["indices"] and base_data.get("JP", {}).get("pe"):
        jp_base = base_data["JP"]
        result["markets"]["JP"]["indices"].append({
            "name": "日经225",
            "symbol": "N225",
            "pe": jp_base.get("pe"),
            "pct_10y": jp_base.get("pct_10y"),
            "dev_10y": jp_base.get("dev_10y", ""),
            "date": jp_base.get("date", ""),
            "source": jp_base.get("source", ""),
            "pct_10y_accurate": False,  # trendonify 数据不准确
            "pct_max_accurate": False,
        })
    
    # 补充韩股数据
    if base_data.get("KR", {}).get("pe"):
        kr_base = base_data["KR"]
        result["markets"]["KR"]["indices"].append({
            "name": "KOSPI",
            "symbol": "KS11",
            "pe": kr_base.get("pe"),
            "pct_10y": kr_base.get("pct_10y"),
            "dev_10y": kr_base.get("dev_10y", ""),
            "date": kr_base.get("date", ""),
            "source": kr_base.get("source", ""),
            "note": kr_base.get("note", ""),
            "pct_10y_accurate": False,  # trendonify 数据不准确
            "pct_max_accurate": False,
        })
    
    return result


def _get_valuation_badge(pct: Optional[float]) -> str:
    """根据百分位返回估值标签（带颜色背景效果）"""
    if pct is None:
        return "--"
    if pct >= 81:
        return "🔴 昂贵"
    elif pct >= 61:
        return "🟠 高估"
    elif pct >= 41:
        return "🟡 合理"
    elif pct >= 21:
        return "🟢 低估"
    else:
        return "🟢🟢 有吸引力"


def generate_compact_table_card(valuation_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    方案1：紧凑表格版卡片（参考图片格式）
    
    特点：
    - 包含10年分位、10年估值、20年分位、20年估值
    - 相同市场不同指数都展示
    - 使用彩色标签展示估值等级
    """
    markets = valuation_data.get("markets", {})
    date_str = valuation_data.get("date", datetime.now().strftime("%Y-%m-%d"))
    sources = valuation_data.get("sources", [])
    
    # 构建表格内容
    table_rows = []
    
    # 表头 - 参考图片格式
    table_rows.append("| 市场 | 指数 | PE | 10年分位 | 10年估值 | 20年分位 | 20年估值 |")
    table_rows.append("|------|------|-----|----------|----------|----------|----------|")
    
    # 市场配置
    market_config = {
        "US": {"flag": "🇺🇸", "code": "US", "name": "美股"},
        "HK": {"flag": "🇭🇰", "code": "HK", "name": "港股"},
        "JP": {"flag": "🇯🇵", "code": "JP", "name": "日股"},
        "KR": {"flag": "🇰🇷", "code": "KR", "name": "韩股"},
    }
    
    for market_code, config in market_config.items():
        market_data = markets.get(market_code, {})
        indices = market_data.get("indices", [])
        
        if not indices:
            continue
        
        # 展示该市场的所有指数（最多3个）
        for idx in indices[:3]:
            name = idx.get("name", "--")
            # 简化指数名称
            name_short = name.replace("Nasdaq 100", "纳指100").replace("S&P 500", "标普500").replace("Dow Jones", "道琼斯").replace("Russell 2000", "罗素2000").replace("恒生指数", "恒指").replace("MSCI Japan", "日经").replace("(日经相关)", "").replace("KOSPI", "KOSPI")
            
            pe = idx.get("pe")
            
            # 10年数据
            pct_10y = idx.get("pct_10y")
            eval_10y = idx.get("evaluation_10y", "")
            
            # 20年数据
            pct_20y = idx.get("pct_20y")
            eval_20y = idx.get("evaluation_20y", "")
            
            # 如果没有直接的百分位，从评估文字转换
            if pct_10y is None and eval_10y:
                pct_10y = _parse_evaluation_to_percentile(eval_10y)
            if pct_20y is None and eval_20y:
                pct_20y = _parse_evaluation_to_percentile(eval_20y)
            
            pe_str = f"{pe:.2f}" if pe else "--"
            pct_10y_str = f"{pct_10y:.1f}%" if pct_10y is not None else "--"
            pct_20y_str = f"{pct_20y:.1f}%" if pct_20y is not None else "--"
            
            badge_10y = _get_valuation_badge(pct_10y)
            badge_20y = _get_valuation_badge(pct_20y)
            
            market_cell = f"[{config['code']}] {config['flag']} {config['name']}"
            
            table_rows.append(
                f"| {market_cell} | {name_short} | {pe_str} | {pct_10y_str} | {badge_10y} | {pct_20y_str} | {badge_20y} |"
            )
    
    table_content = "\n".join(table_rows)
    
    # 构建卡片
    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {
                "tag": "plain_text",
                "content": f"📊 全球主要市场估值 ({date_str})"
            },
            "template": "blue"
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": table_content
                }
            },
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "**估值等级说明：** 🟢🟢有吸引力 🟢低估 🟡合理 🟠高估 🔴昂贵"
                }
            },
            {
                "tag": "hr"
            },
            {
                "tag": "note",
                "elements": [
                    {
                        "tag": "plain_text",
                        "content": f"数据来源: {', '.join(sources) if sources else 'Wind/东方财富'}"
                    }
                ]
            }
        ]
    }
    
    return card


def generate_country_group_card(valuation_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    方案2：国家分组版卡片
    
    特点：
    - 按国家分组展示
    - 每个国家一个独立区块
    - 展示该国家所有主要指数
    - 包含更多估值指标（PE、分位、偏离度、股息率等）
    """
    markets = valuation_data.get("markets", {})
    date_str = valuation_data.get("date", datetime.now().strftime("%Y-%m-%d"))
    sources = valuation_data.get("sources", [])
    
    elements = []
    
    # 市场配置
    market_config = {
        "US": {"flag": "🇺🇸", "name": "美股", "color": "blue"},
        "HK": {"flag": "🇭🇰", "name": "港股", "color": "red"},
        "JP": {"flag": "🇯🇵", "name": "日股", "color": "white"},
        "KR": {"flag": "🇰🇷", "name": "韩股", "color": "green"},
    }
    
    for market_code, config in market_config.items():
        market_data = markets.get(market_code, {})
        indices = market_data.get("indices", [])
        
        if not indices:
            continue
        
        # 国家标题
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**{config['flag']} {config['name']}**"
            }
        })
        
        # 该国家的所有指数
        for idx in indices:
            name = idx.get("name", "--")
            pe = idx.get("pe")
            pct_10y = idx.get("pct_10y")
            dev_10y = idx.get("dev_10y", "")
            dividend = idx.get("dividend_yield")
            avg_10y = idx.get("avg_10y")
            
            pe_str = f"{pe:.2f}" if pe else "--"
            pct_str = f"{pct_10y:.1f}%" if pct_10y is not None else "--"
            dev_str = _format_deviation(dev_10y)
            level_icon = _get_valuation_level_icon(pct_10y)
            
            # 构建指标行
            metrics = [f"PE: {pe_str}", f"10年分位: {pct_str}", f"偏离: {dev_str}"]
            
            if dividend:
                metrics.append(f"股息率: {dividend:.2f}%")
            if avg_10y:
                metrics.append(f"10年均值: {avg_10y:.2f}")
            
            metrics_str = " | ".join(metrics)
            
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"  {level_icon} **{name}**: {metrics_str}"
                }
            })
        
        # 分隔线
        elements.append({"tag": "hr"})
    
    # 添加说明和来源
    elements.append({
        "tag": "div",
        "text": {
            "tag": "lark_md",
            "content": "**估值等级：** 🟢🟢有吸引力(0-20%) 🟢低估(21-40%) 🟡合理(41-60%) 🟠高估(61-80%) 🔴昂贵(81-100%)"
        }
    })
    
    elements.append({
        "tag": "note",
        "elements": [
            {
                "tag": "plain_text",
                "content": f"数据来源: {', '.join(sources) if sources else 'Wind/东方财富'} | 更新时间: {date_str}"
            }
        ]
    })
    
    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {
                "tag": "plain_text",
                "content": "🌍 全球主要市场估值概览"
            },
            "template": "blue"
        },
        "elements": elements
    }
    
    return card


def generate_heatmap_card(valuation_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    方案3：热力图版卡片
    
    特点：
    - 使用颜色块直观展示估值水平
    - 每个指数一个色块
    - 色块大小可表示市值或重要性
    - 适合快速扫视整体估值分布
    """
    markets = valuation_data.get("markets", {})
    date_str = valuation_data.get("date", datetime.now().strftime("%Y-%m-%d"))
    sources = valuation_data.get("sources", [])
    
    # 收集所有指数
    all_indices = []
    
    market_names = {
        "US": "🇺🇸 美股",
        "HK": "🇭🇰 港股",
        "JP": "🇯🇵 日股",
        "KR": "🇰🇷 韩股",
    }
    
    for market_code, market_data in markets.items():
        for idx in market_data.get("indices", []):
            pct = idx.get("pct_10y") or idx.get("pct_3y") or 50
            
            # 确定颜色
            if pct >= 81:
                color = "red"  # 昂贵
            elif pct >= 61:
                color = "orange"  # 高估
            elif pct >= 41:
                color = "yellow"  # 合理
            elif pct >= 21:
                color = "green"  # 低估
            else:
                color = "turquoise"  # 有吸引力
            
            all_indices.append({
                "market": market_names.get(market_code, market_code),
                "name": idx.get("name", ""),
                "pe": idx.get("pe"),
                "pct": pct,
                "color": color,
            })
    
    # 构建热力图内容 - 使用emoji色块
    heatmap_lines = []
    
    for idx in all_indices:
        pe_str = f"{idx['pe']:.1f}" if idx['pe'] else "--"
        pct_str = f"{idx['pct']:.0f}%" if idx['pct'] is not None else "--"
        
        # 使用不同emoji表示估值水平
        if idx['color'] == 'red':
            block = "🟥"
        elif idx['color'] == 'orange':
            block = "🟧"
        elif idx['color'] == 'yellow':
            block = "🟨"
        elif idx['color'] == 'green':
            block = "🟩"
        else:
            block = "🟦"
        
        heatmap_lines.append(
            f"{block} **{idx['market']} {idx['name']}**: PE {pe_str} ({pct_str})"
        )
    
    heatmap_content = "\n".join(heatmap_lines)
    
    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {
                "tag": "plain_text",
                "content": f"🌡️ 全球估值热力图 ({date_str})"
            },
            "template": "blue"
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": heatmap_content
                }
            },
            {
                "tag": "hr"
            },
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "**图例：** 🟦有吸引力(0-20%) 🟩低估(21-40%) 🟨合理(41-60%) 🟧高估(61-80%) 🟥昂贵(81-100%)"
                }
            },
            {
                "tag": "note",
                "elements": [
                    {
                        "tag": "plain_text",
                        "content": f"数据来源: {', '.join(sources) if sources else 'Wind/东方财富'}"
                    }
                ]
            }
        ]
    }
    
    return card


def send_global_valuation_card(style: str = "compact", webhook_url: Optional[str] = None) -> bool:
    """
    发送全球估值卡片到飞书。
    
    Args:
        style: 卡片风格，可选 "compact"(紧凑表格)、"group"(国家分组)、"heatmap"(热力图)
        webhook_url: 飞书 webhook URL，None 则使用配置文件中的
    
    Returns:
        发送成功返回 True
    """
    import requests
    
    # 获取数据
    print("[全球估值卡片] 正在获取估值数据...")
    valuation_data = fetch_enhanced_global_valuation()
    
    # 生成卡片
    if style == "compact":
        card = generate_compact_table_card(valuation_data)
    elif style == "group":
        card = generate_country_group_card(valuation_data)
    elif style == "heatmap":
        card = generate_heatmap_card(valuation_data)
    else:
        print(f"[全球估值卡片] 未知风格: {style}，使用默认紧凑表格")
        card = generate_compact_table_card(valuation_data)
    
    # 发送消息
    if webhook_url is None:
        from ..config import FEISHU_WEBHOOK
        webhook_url = FEISHU_WEBHOOK
    
    if not webhook_url:
        print("[全球估值卡片] 错误: 未配置飞书 webhook")
        return False
    
    payload = {
        "msg_type": "interactive",
        "card": card
    }
    
    try:
        resp = requests.post(webhook_url, json=payload, timeout=30)
        result = resp.json()
        
        if result.get("code") == 0:
            print(f"[全球估值卡片] ✓ 发送成功 (风格: {style})")
            return True
        else:
            print(f"[全球估值卡片] ✗ 发送失败: {result.get('msg')}")
            return False
            
    except Exception as e:
        print(f"[全球估值卡片] ✗ 请求异常: {e}")
        return False


def generate_and_send_valuation_image(valuation_data: Optional[Dict[str, Any]] = None, 
                                       webhook_url: Optional[str] = None) -> bool:
    """
    生成估值图片并发送到飞书。
    
    Args:
        valuation_data: 估值数据，None 则自动获取
        webhook_url: 飞书 webhook URL
    
    Returns:
        发送成功返回 True
    """
    import requests
    from .valuation_image import generate_valuation_image
    
    # 获取数据
    if valuation_data is None:
        base_data = fetch_trendonify_valuation()
        valuation_data = {
            "date": base_data.get("date", ""),
            "US": base_data.get("US", {}),
            "HK": base_data.get("HK", {}),
            "JP": base_data.get("JP", {}),
            "KR": base_data.get("KR", {}),
        }
    
    # 生成图片
    print("[全球估值图片] 正在生成图片...")
    img_path = generate_valuation_image(valuation_data)
    
    if not img_path:
        print("[全球估值图片] ✗ 图片生成失败")
        return False
    
    print(f"[全球估值图片] 图片已生成: {img_path}")
    
    # 上传图片到飞书
    print("[全球估值图片] 正在上传图片到飞书...")
    img_url = upload_image_to_feishu(img_path)
    
    if not img_url:
        print("[全球估值图片] ✗ 图片上传失败")
        return False
    
    # 发送图片消息
    if webhook_url is None:
        from ..config import FEISHU_WEBHOOK
        webhook_url = FEISHU_WEBHOOK
    
    if not webhook_url:
        print("[全球估值图片] 错误: 未配置飞书 webhook")
        return False
    
    # 构建带图片的卡片
    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {
                "tag": "plain_text",
                "content": f"📊 全球主要市场估值对比 ({valuation_data.get('date', '')})"
            },
            "template": "blue"
        },
        "elements": [
            {
                "tag": "img",
                "img_key": img_url.replace("fileutil/", ""),
                "alt": {
                    "tag": "plain_text",
                    "content": "全球估值对比图"
                }
            },
            {
                "tag": "note",
                "elements": [
                    {
                        "tag": "plain_text",
                        "content": "数据来源: WorldPERatio/亿牛网"
                    }
                ]
            }
        ]
    }
    
    payload = {
        "msg_type": "interactive",
        "card": card
    }
    
    try:
        resp = requests.post(webhook_url, json=payload, timeout=30)
        result = resp.json()
        
        if result.get("code") == 0:
            print("[全球估值图片] ✓ 图片发送成功")
            return True
        else:
            print(f"[全球估值图片] ✗ 发送失败: {result.get('msg')}")
            return False
            
    except Exception as e:
        print(f"[全球估值图片] ✗ 请求异常: {e}")
        return False


if __name__ == "__main__":
    # 测试三种卡片风格
    print("=" * 70)
    print("全球估值卡片生成测试")
    print("=" * 70)
    
    # 获取数据
    data = fetch_enhanced_global_valuation()
    
    print("\n获取到的数据:")
    print(json.dumps(data, ensure_ascii=False, indent=2))
    
    print("\n" + "=" * 70)
    print("方案1: 紧凑表格版")
    print("=" * 70)
    card1 = generate_compact_table_card(data)
    print(json.dumps(card1, ensure_ascii=False, indent=2))
    
    print("\n" + "=" * 70)
    print("方案2: 国家分组版")
    print("=" * 70)
    card2 = generate_country_group_card(data)
    print(json.dumps(card2, ensure_ascii=False, indent=2))
    
    print("\n" + "=" * 70)
    print("方案3: 热力图版")
    print("=" * 70)
    card3 = generate_heatmap_card(data)
    print(json.dumps(card3, ensure_ascii=False, indent=2))
