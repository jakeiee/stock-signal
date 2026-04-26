"""
全球估值图表生成。

使用 matplotlib 生成全球主要市场估值对比图表。
"""

import os
from datetime import datetime
from typing import Optional


def generate_valuation_image(valuation_data: dict) -> Optional[str]:
    """
    生成全球估值图表图片（支持多指数）。
    
    Args:
        valuation_data: 支持两种格式：
            Format 1 (旧格式，向后兼容):
            {
                "date": str,
                "US": {"pe": float, "pct_10y": float},
                "HK": {"pe": float, "pct_10y": float},
                ...
            }
            
            Format 2 (新格式，支持多指数):
            {
                "date": str,
                "markets": {
                    "US": {
                        "name": "美股",
                        "indices": [
                            {"name": "标普500", "pe": 27.24, "pct_10y": 28.9},
                            {"name": "七巨头", "pe": 34.62, "pct_10y": 28.9}
                        ]
                    },
                    "HK": {...},
                    ...
                }
            }
    
    Returns:
        生成的图片文件路径，失败返回 None
    """
    try:
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        from matplotlib import rcParams
        
        # 设置中文字体
        rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
        rcParams['axes.unicode_minus'] = False
        
        # 解析数据格式
        indices_data = []  # [(market_name, index_name, pe, pct_10y), ...]
        
        if "markets" in valuation_data:
            # 新格式：支持多指数
            markets = valuation_data.get("markets", {})
            for market_code, market_info in markets.items():
                market_name = market_info.get("name", market_code)
                indices = market_info.get("indices", [])
                
                for idx in indices:
                    pe = idx.get("pe")
                    if pe is not None:
                        index_name = idx.get("name", "未知")
                        pct_10y = idx.get("pct_10y")
                        indices_data.append((market_name, index_name, pe, pct_10y))
        else:
            # 旧格式：每个市场一个指数（向后兼容）
            market_names = {
                "US": "美股",
                "HK": "港股",
                "JP": "日股",
                "KR": "韩股",
            }
            index_names = {
                "US": "SPX",
                "HK": "HSI",
                "JP": "N225",
                "KR": "KOSPI",
            }
            
            for market_code in ["US", "HK", "JP", "KR"]:
                data = valuation_data.get(market_code, {})
                pe = data.get("pe")
                if pe is not None:
                    market_name = market_names.get(market_code, market_code)
                    index_name = index_names.get(market_code, market_code)
                    pct_10y = data.get("pct_10y")
                    indices_data.append((market_name, index_name, pe, pct_10y))
        
        if not indices_data:
            print("[valuation_image] 没有有效的估值数据")
            return None
        
        # 动态计算图表高度（每个指数约0.5英寸 + 顶部底部边距）
        n_indices = len(indices_data)
        fig_height = max(6, n_indices * 0.6 + 2)
        
        # 创建图表
        fig, ax = plt.subplots(figsize=(12, fig_height))
        
        # 准备数据
        labels = []
        pes = []
        pcts = []
        colors = []
        
        for market_name, index_name, pe, pct in indices_data:
            # 标签格式：市场名 + 指数名
            label = f"{market_name}-{index_name}"
            labels.append(label)
            pes.append(pe)
            pct = pct or 50  # 默认50%
            pcts.append(pct)
            
            # 根据百分位确定颜色
            if pct >= 81:
                colors.append('#e74c3c')  # 红色 - 昂贵
            elif pct >= 61:
                colors.append('#e67e22')  # 橙色 - 高估
            elif pct >= 41:
                colors.append('#f1c40f')  # 黄色 - 合理
            elif pct >= 21:
                colors.append('#2ecc71')  # 绿色 - 低估
            else:
                colors.append('#27ae60')  # 深绿 - 有吸引力
        
        # 绘制横向条形图
        y_pos = range(len(labels))
        bars = ax.barh(y_pos, pes, color=colors, alpha=0.8, edgecolor='white', linewidth=1.5)
        
        # 添加数值标签
        for i, (bar, pe, pct) in enumerate(zip(bars, pes, pcts)):
            width = bar.get_width()
            # PE值
            ax.text(width + 0.5, bar.get_y() + bar.get_height()/2, 
                   f'{pe:.1f}', ha='left', va='center', fontsize=11, fontweight='bold')
            # 百分位
            ax.text(max(pes) * 0.05, bar.get_y() + bar.get_height()/2,
                   f'{pct:.0f}%', ha='left', va='center', fontsize=9, color='white', fontweight='bold')
        
        # 设置Y轴
        ax.set_yticks(y_pos)
        ax.set_yticklabels(labels, fontsize=10)
        ax.invert_yaxis()
        
        # 设置X轴
        ax.set_xlabel('市盈率 (PE)', fontsize=11)
        ax.set_xlim(0, max(pes) * 1.25)
        
        # 添加标题
        date_str = valuation_data.get("date", datetime.now().strftime("%Y-%m-%d"))
        ax.set_title(f'全球市场估值对比\n{date_str}', fontsize=14, fontweight='bold', pad=20)
        
        # 添加图例
        legend_elements = [
            mpatches.Patch(color='#27ae60', label='有吸引力 (0-20%)'),
            mpatches.Patch(color='#2ecc71', label='低估 (21-40%)'),
            mpatches.Patch(color='#f1c40f', label='合理 (41-60%)'),
            mpatches.Patch(color='#e67e22', label='高估 (61-80%)'),
            mpatches.Patch(color='#e74c3c', label='昂贵 (81-100%)'),
        ]
        ax.legend(handles=legend_elements, loc='lower right', fontsize=9)
        
        # 添加网格线
        ax.grid(axis='x', alpha=0.3, linestyle='--')
        ax.set_axisbelow(True)
        
        # 添加数据来源
        sources = valuation_data.get("sources", [])
        source_str = ", ".join(sources) if sources else "多数据源"
        fig.text(0.99, 0.01, f'数据来源: {source_str}', ha='right', va='bottom', 
                fontsize=8, color='gray', style='italic')
        
        # 调整布局
        plt.tight_layout()
        
        # 保存图片
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        os.makedirs(data_dir, exist_ok=True)
        
        date_str = datetime.now().strftime("%Y-%m-%d")
        img_path = os.path.join(data_dir, f"global_valuation_{date_str}.png")
        
        plt.savefig(img_path, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close()
        
        return img_path
        
    except ImportError as e:
        print(f"[valuation_image] 缺少依赖: {e}")
        return None
    except Exception as e:
        print(f"[valuation_image] 生成图片失败: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    # 测试
    test_data = {
        "date": "2026-04-18",
        "US": {"pe": 30.62, "pct_10y": 75.8},
        "HK": {"pe": 13.52, "pct_10y": 35.2},
        "JP": {"pe": 20.03, "pct_10y": 69.8},
        "KR": {"pe": 14.74, "pct_10y": 66.7},
    }
    
    path = generate_valuation_image(test_data)
    if path:
        print(f"图片已生成: {path}")
    else:
        print("图片生成失败")
