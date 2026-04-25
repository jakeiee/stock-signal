"""
全球估值表格图片生成模块。

生成类似参考图片格式的表格图片，包含：
- 市场、指数、PE、10年分位、10年估值、20年分位、20年估值
"""

import os
from datetime import datetime
from typing import Dict, Any, List, Optional


def _get_valuation_level_color(pct: Optional[float]) -> str:
    """根据百分位返回估值等级颜色"""
    if pct is None:
        return '#95a5a6'  # 灰色 - 未知
    if pct >= 81:
        return '#e74c3c'  # 红色 - 昂贵
    elif pct >= 61:
        return '#e67e22'  # 橙色 - 高估
    elif pct >= 41:
        return '#f1c40f'  # 黄色 - 合理
    elif pct >= 21:
        return '#2ecc71'  # 绿色 - 低估
    else:
        return '#27ae60'  # 深绿 - 有吸引力


def _get_valuation_level_text(pct: Optional[float]) -> str:
    """根据百分位返回估值等级文字"""
    if pct is None:
        return "--"
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


def _parse_evaluation_to_percentile(evaluation: str) -> Optional[float]:
    """将估值评估转换为估算百分位"""
    mapping = {
        "Cheap": 10.0,
        "Fair": 35.0,
        "Overvalued": 65.0,
        "Expensive": 85.0,
    }
    return mapping.get(evaluation, None)


def _get_valuation_level_from_evaluation(evaluation: str) -> str:
    """根据评估数据返回估值等级文字"""
    mapping = {
        "Cheap": "有吸引力",
        "Fair": "合理",
        "Overvalued": "高估",
        "Expensive": "昂贵",
    }
    return mapping.get(evaluation, "--")


def _get_valuation_color_from_evaluation(evaluation: str) -> str:
    """根据评估数据返回估值等级颜色"""
    mapping = {
        "Cheap": '#27ae60',      # 深绿 - 有吸引力
        "Fair": '#f1c40f',       # 黄色 - 合理
        "Overvalued": '#e67e22',  # 橙色 - 高估
        "Expensive": '#e74c3c',   # 红色 - 昂贵
    }
    return mapping.get(evaluation, '#95a5a6')


def generate_valuation_table_image(valuation_data: Dict[str, Any]) -> Optional[str]:
    """
    生成全球估值表格图片（参考图片格式）。
    
    Args:
        valuation_data: 包含 markets, date, sources 的估值数据
    
    Returns:
        生成的图片文件路径，失败返回 None
    """
    try:
        import matplotlib.pyplot as plt
        from matplotlib import rcParams
        from matplotlib.patches import Rectangle, FancyBboxPatch
        import matplotlib.patches as mpatches
        
        # 设置中文字体
        rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans', 'WenQuanYi Micro Hei']
        rcParams['axes.unicode_minus'] = False
        
        markets = valuation_data.get("markets", {})
        date_str = valuation_data.get("date", datetime.now().strftime("%Y-%m-%d"))
        sources = valuation_data.get("sources", [])
        
        # 打印各市场数据源信息
        print("\n" + "="*60)
        print("各市场估值数据源详情:")
        print("="*60)
        
        # 收集所有行数据，按市场分组
        market_config = {
            "US": {"flag": "", "code": "US", "name": "美股"},
            "HK": {"flag": "", "code": "HK", "name": "港股"},
            "JP": {"flag": "", "code": "JP", "name": "日股"},
            "KR": {"flag": "", "code": "KR", "name": "韩股"},
        }

        # 按市场分组存储数据
        market_groups = {}  # {market_code: [indices]}
        market_sources = {}  # {market_code: set(sources)}

        for market_code, config in market_config.items():
            market_data = markets.get(market_code, {})
            indices = market_data.get("indices", [])

            if not indices:
                continue

            market_groups[market_code] = []
            market_sources[market_code] = set()

            for idx in indices[:3]:  # 最多3个指数
                name = idx.get("name", "--")
                # 简化名称
                name_short = name.replace("Nasdaq 100", "纳指100")\
                                .replace("S&P 500", "标普500")\
                                .replace("Dow Jones", "道琼斯")\
                                .replace("Russell 2000", "罗素2000")\
                                .replace("恒生指数", "恒指")\
                                .replace("MSCI Japan (日经相关)", "日经")\
                                .replace("MSCI Japan", "日经")\
                                .replace("KOSPI", "KOSPI")

                pe = idx.get("pe")

                # 10年数据 - 优先使用已有的 pct_10y 字段
                pct_10y = idx.get("pct_10y")
                eval_10y = idx.get("evaluation_10y", "")
                if pct_10y is None and eval_10y:
                    pct_10y = _parse_evaluation_to_percentile(eval_10y)

                # max分位数据 - 优先使用已有的 pct_max 字段
                pct_max = idx.get("pct_max")
                eval_20y = idx.get("evaluation_20y", "")

                # 记录数据源
                source = idx.get("source", "unknown")
                market_sources[market_code].add(source)

                # 获取准确性标记（如果不存在则默认为 False，即不显示百分位）
                pct_10y_accurate = idx.get("pct_10y_accurate", False)
                pct_max_accurate = idx.get("pct_max_accurate", False)

                # 即使百分位不准确，但如果有评估数据（evaluation_10y），也显示估值等级
                # 使用评估数据直接判断估值等级，而不是依赖百分位
                if pct_10y is not None:
                    level_10y = _get_valuation_level_text(pct_10y)
                    color_10y = _get_valuation_level_color(pct_10y)
                elif eval_10y:
                    # 没有准确百分位，但有评估数据，根据评估数据判断估值等级
                    level_10y = _get_valuation_level_from_evaluation(eval_10y)
                    color_10y = _get_valuation_color_from_evaluation(eval_10y)
                else:
                    level_10y = "--"
                    color_10y = '#95a5a6'

                if pct_max is not None:
                    level_max = _get_valuation_level_text(pct_max)
                    color_max = _get_valuation_level_color(pct_max)
                elif eval_20y:
                    level_max = _get_valuation_level_from_evaluation(eval_20y)
                    color_max = _get_valuation_color_from_evaluation(eval_20y)
                else:
                    level_max = "--"
                    color_max = '#95a5a6'

                market_groups[market_code].append({
                    "market_code": market_code,
                    "market_name": config['name'],
                    "market_display": f"[{config['code']}] {config['name']}",
                    "index": name_short,
                    "pe": pe,
                    "pct_10y": pct_10y,
                    "pct_10y_accurate": pct_10y_accurate,
                    "eval_10y": eval_10y,
                    "level_10y": level_10y,
                    "color_10y": color_10y,
                    "pct_max": pct_max,
                    "pct_max_accurate": pct_max_accurate,
                    "eval_20y": eval_20y,
                    "level_max": level_max,
                    "color_max": color_max,
                    "source": source,
                })
        
        # 打印各市场数据源
        for market_code, config in market_config.items():
            if market_code in market_groups:
                sources_list = ", ".join(sorted(market_sources[market_code]))
                indices_list = [idx['index'] for idx in market_groups[market_code]]
                print(f"\n【{config['name']}】({market_code})")
                print(f"  指数: {', '.join(indices_list)}")
                print(f"  数据源: {sources_list}")
                for idx in market_groups[market_code]:
                    pe_str = f"{idx['pe']:.2f}" if idx['pe'] else '--'
                    pct_10y_str = f"{idx['pct_10y']:.1f}%" if idx['pct_10y'] is not None else '--'
                    pct_max_str = f"{idx['pct_max']:.1f}%" if idx['pct_max'] is not None else '--'
                    print(f"    - {idx['index']}: PE={pe_str}, "
                          f"10年分位={pct_10y_str}, "
                          f"max分位={pct_max_str}")
        
        print("\n" + "="*60)
        print(f"整体数据来源: {', '.join(sources)}")
        print("="*60 + "\n")
        
        # 展平为行数据，用于绘制
        rows = []
        for market_code in ["US", "HK", "JP", "KR"]:
            if market_code in market_groups:
                rows.extend(market_groups[market_code])
        
        if not rows:
            return None
        
        # 创建图表 - 紧凑布局
        row_height = 0.32
        fig_height = 1.2 + len(rows) * row_height
        fig, ax = plt.subplots(figsize=(12, fig_height))
        ax.set_xlim(0, 12)
        ax.set_ylim(0, len(rows) + 1.5)
        ax.axis('off')
        
        # 标题
        fig.text(0.5, 0.98, '[全球] 全球市场估值', ha='center', va='top', 
                fontsize=16, fontweight='bold', color='#333333')
        fig.text(0.88, 0.98, f'[{date_str}]', ha='right', va='top',
                fontsize=10, color='#999999')
        
        # 表头 - 调整列宽使表头与数据对齐
        headers = ['市场', '指数', 'PE', '10年分位', '10年估值', 'max分位', 'max估值']
        # 调整列宽：市场列更宽以容纳合并单元格，其他列根据内容调整
        col_widths = [1.6, 1.6, 1.0, 1.4, 1.4, 1.4, 1.4]
        col_starts = [0.2]
        for w in col_widths[:-1]:
            col_starts.append(col_starts[-1] + w)
        
        header_y = len(rows) + 0.6
        
        # 绘制表头背景
        total_width = sum(col_widths)
        ax.add_patch(Rectangle((0.2, header_y - 0.25), total_width, 0.4, 
                              facecolor='#f5f5f5', edgecolor='#dddddd', linewidth=0.8))
        
        # 绘制表头文字 - 居中对齐
        for i, (header, x, w) in enumerate(zip(headers, col_starts, col_widths)):
            ax.text(x + w/2, header_y - 0.05, header, 
                   ha='center', va='center', fontsize=10, fontweight='bold', color='#666666')
        
        # 绘制数据行，每行都显示市场名称（不合并）
        for row_idx, row in enumerate(rows):
            y = len(rows) - row_idx - 0.15

            # 行背景（交替色）
            bg_color = '#fafafa' if row_idx % 2 == 0 else '#ffffff'
            ax.add_patch(Rectangle((0.2, y - 0.22), total_width, 0.4,
                                  facecolor=bg_color, edgecolor='#dddddd', linewidth=0.5))

            # 市场名称 - 每行都显示
            ax.text(col_starts[0] + col_widths[0]/2, y, row['market_display'],
                   ha='center', va='center', fontsize=9, color='#333333', fontweight='bold')

            # 指数
            ax.text(col_starts[1] + col_widths[1]/2, y, row['index'],
                   ha='center', va='center', fontsize=9, color='#333333')

            # PE
            pe_str = f"{row['pe']:.2f}" if row['pe'] else "--"
            ax.text(col_starts[2] + col_widths[2]/2, y, pe_str,
                   ha='center', va='center', fontsize=9, color='#333333')

            # 10年分位 - 仅显示准确的百分位，不准确的显示 "--"
            pct_10y = row.get('pct_10y')
            pct_10y_accurate = row.get('pct_10y_accurate', True)
            if pct_10y is not None and pct_10y_accurate:
                pct_10y_str = f"{pct_10y:.1f}%"
            else:
                pct_10y_str = "--"
            ax.text(col_starts[3] + col_widths[3]/2, y, pct_10y_str,
                   ha='center', va='center', fontsize=8, color='#333333')

            # 10年估值标签 - 有估值等级就显示
            level_10y = row.get('level_10y', '--')
            color_10y = row.get('color_10y', '#95a5a6')
            if level_10y != '--':
                bbox = FancyBboxPatch((col_starts[4] + 0.15, y - 0.12), col_widths[4] - 0.3, 0.24,
                                     boxstyle="round,pad=0.02,rounding_size=0.08",
                                     facecolor=color_10y, edgecolor='none',
                                     transform=ax.transData)
                ax.add_patch(bbox)
                ax.text(col_starts[4] + col_widths[4]/2, y, level_10y,
                       ha='center', va='center', fontsize=8, color='white', fontweight='bold')

            # max分位 - 仅显示准确的百分位，不准确的显示 "--"
            pct_max = row.get('pct_max')
            pct_max_accurate = row.get('pct_max_accurate', True)
            if pct_max is not None and pct_max_accurate:
                pct_max_str = f"{pct_max:.1f}%"
            else:
                pct_max_str = "--"
            ax.text(col_starts[5] + col_widths[5]/2, y, pct_max_str,
                   ha='center', va='center', fontsize=8, color='#333333')

            # max估值标签 - 有估值等级就显示
            level_max = row.get('level_max', '--')
            color_max = row.get('color_max', '#95a5a6')
            if level_max != '--':
                bbox = FancyBboxPatch((col_starts[6] + 0.15, y - 0.12), col_widths[6] - 0.3, 0.24,
                                     boxstyle="round,pad=0.02,rounding_size=0.08",
                                     facecolor=color_max, edgecolor='none',
                                     transform=ax.transData)
                ax.add_patch(bbox)
                ax.text(col_starts[6] + col_widths[6]/2, y, level_max,
                       ha='center', va='center', fontsize=8, color='white', fontweight='bold')
        
        # 添加分隔线
        ax.axhline(y=len(rows) + 0.35, color='#dddddd', linewidth=0.8, xmin=0.02, xmax=0.98)
        
        # 数据来源
        fig.text(0.99, 0.01, '数据来源: WorldPERatio / 亿牛网 / Shiller', ha='right', va='bottom',
                fontsize=7, color='#999999', style='italic')
        
        # 调整布局
        plt.tight_layout()
        plt.subplots_adjust(top=0.92, bottom=0.06)
        
        # 保存图片
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        os.makedirs(data_dir, exist_ok=True)
        
        date_str_file = datetime.now().strftime("%Y-%m-%d")
        img_path = os.path.join(data_dir, f"global_valuation_table_{date_str_file}.png")
        
        plt.savefig(img_path, dpi=150, bbox_inches='tight', facecolor='white', edgecolor='none')
        plt.close()
        
        return img_path
        
    except ImportError as e:
        print(f"[valuation_table_image] 缺少依赖: {e}")
        return None
    except Exception as e:
        print(f"[valuation_table_image] 生成图片失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def generate_and_send_table_image(valuation_data: Optional[Dict[str, Any]] = None,
                                   webhook_url: Optional[str] = None) -> bool:
    """
    生成表格图片并发送到飞书。
    
    Args:
        valuation_data: 估值数据，None 则自动获取
        webhook_url: 飞书 webhook URL
    
    Returns:
        发送成功返回 True
    """
    import requests
    
    # 获取数据
    if valuation_data is None:
        from .global_valuation_card import fetch_enhanced_global_valuation
        valuation_data = fetch_enhanced_global_valuation()
    
    # 生成图片
    print("[全球估值表格图片] 正在生成图片...")
    img_path = generate_valuation_table_image(valuation_data)
    
    if not img_path:
        print("[全球估值表格图片] ✗ 图片生成失败")
        return False
    
    print(f"[全球估值表格图片] 图片已生成: {img_path}")
    
    # 上传图片到飞书
    from .feishu_image import upload_image_to_feishu
    print("[全球估值表格图片] 正在上传图片到飞书...")
    img_url = upload_image_to_feishu(img_path)
    
    if not img_url:
        print("[全球估值表格图片] ✗ 图片上传失败")
        return False
    
    # 发送图片消息
    if webhook_url is None:
        from ..config import FEISHU_WEBHOOK
        webhook_url = FEISHU_WEBHOOK
    
    if not webhook_url:
        print("[全球估值表格图片] 错误: 未配置飞书 webhook")
        return False
    
    # 构建带图片的卡片
    date_str = valuation_data.get("date", datetime.now().strftime("%Y-%m-%d"))
    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {
                "tag": "plain_text",
                "content": f"📊 全球市场估值 ({date_str})"
            },
            "template": "blue"
        },
        "elements": [
            {
                "tag": "img",
                "img_key": img_url.replace("fileutil/", ""),
                "alt": {
                    "tag": "plain_text",
                    "content": "全球估值表格"
                }
            },
            {
                "tag": "note",
                "elements": [
                    {
                        "tag": "plain_text",
                        "content": "数据来源: WorldPERatio / 亿牛网"
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
            print("[全球估值表格图片] ✓ 图片发送成功")
            return True
        else:
            print(f"[全球估值表格图片] ✗ 发送失败: {result.get('msg')}")
            return False
            
    except Exception as e:
        print(f"[全球估值表格图片] ✗ 请求异常: {e}")
        return False


if __name__ == "__main__":
    # 测试
    test_data = {
        "date": "2026-04-19",
        "markets": {
            "US": {
                "indices": [
                    {"name": "S&P 500", "pe": 27.09, "pct_10y": 85.0, "evaluation_10y": "Expensive", "evaluation_20y": "Expensive"},
                    {"name": "Nasdaq 100", "pe": 31.06, "evaluation_10y": "Overvalued", "evaluation_20y": "Overvalued"},
                ]
            },
            "HK": {
                "indices": [
                    {"name": "恒生指数", "pe": 13.98, "pct_10y": 78.2, "evaluation_10y": "Overvalued", "evaluation_20y": "Fair"},
                ]
            },
            "JP": {
                "indices": [
                    {"name": "MSCI Japan", "pe": 17.46, "pct_10y": 85.0, "evaluation_10y": "Expensive", "evaluation_20y": "Overvalued"},
                ]
            },
            "KR": {
                "indices": [
                    {"name": "KOSPI", "pe": 16.47, "pct_10y": 85.0, "evaluation_10y": "Expensive", "evaluation_20y": "Expensive"},
                ]
            },
        },
        "sources": ["WorldPERatio", "亿牛网"],
    }
    
    path = generate_valuation_table_image(test_data)
    if path:
        print(f"图片已生成: {path}")
    else:
        print("图片生成失败")
