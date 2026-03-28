"""
全球市场估值图片生成器。

使用 Pillow 生成 Trendonify 风格的估值图片，方便在飞书中展示。
"""

import os
from datetime import datetime
from typing import Optional

# 尝试导入 Pillow
try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# 数据目录
_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_OUTPUT_DIR = _DATA_DIR


def _valuation_color(pct: float) -> tuple:
    """根据百分位返回颜色 (R, G, B)"""
    if pct >= 81:  # 昂贵 - 红色
        return (220, 53, 69)
    if pct >= 61:  # 高估 - 橙色
        return (255, 153, 0)
    if pct >= 41:  # 合理 - 黄色
        return (255, 193, 7)
    if pct >= 21:  # 低估 - 浅绿
        return (40, 167, 69)
    # 有吸引力 - 深绿
    return (25, 135, 84)


def _valuation_label(pct: float) -> str:
    """根据百分位返回估值标签"""
    if pct >= 81: return "昂贵"
    if pct >= 61: return "高估"
    if pct >= 41: return "合理"
    if pct >= 21: return "低估"
    return "有吸引力"


def generate_valuation_image(data: dict, output_path: Optional[str] = None) -> Optional[str]:
    """
    生成全球市场估值图片。
    """
    if not PIL_AVAILABLE:
        print("[估值图片] Pillow 未安装，无法生成图片")
        return None
    
    # 目标市场数据
    markets = [
        ("US", "🇺🇸 美股", "SPX"),
        ("HK", "🇭🇰 港股", "HSI"),
        ("JP", "🇯🇵 日股", "EWJ"),
        ("KR", "🇰🇷 韩股", "EWY"),
    ]
    
    # Emoji 符号到纯文本的映射（用于不支持 emoji 的情况）
    emoji_map = {
        "🌏": "[全球]",
        "🇺🇸": "[US]",
        "🇭🇰": "[HK]",
        "🇯🇵": "[JP]",
        "🇰🇷": "[KR]",
    }
    
    # 图片参数
    width = 700
    row_height = 70
    header_height = 50
    padding = 20
    height = header_height + len(markets) * row_height + padding * 2
    
    # 创建图片
    img = Image.new('RGB', (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    # 尝试加载字体（使用支持中文的字体）
    font_path = "/System/Library/Fonts/Hiragino Sans GB.ttc"
    try:
        title_font = ImageFont.truetype(font_path, 18)
        header_font = ImageFont.truetype(font_path, 12)
        value_font = ImageFont.truetype(font_path, 14)
        label_font = ImageFont.truetype(font_path, 11)
    except Exception:
        # 备用方案：尝试苹方字体
        try:
            font_path = "/System/Library/Fonts/PingFang.ttc"
            title_font = ImageFont.truetype(font_path, 18)
            header_font = ImageFont.truetype(font_path, 12)
            value_font = ImageFont.truetype(font_path, 14)
            label_font = ImageFont.truetype(font_path, 11)
        except Exception:
            title_font = ImageFont.load_default()
            header_font = ImageFont.load_default()
            value_font = ImageFont.load_default()
            label_font = ImageFont.load_default()
    
    # 绘制标题（将 emoji 替换为纯文本）
    title = "🌏 全球市场估值"
    for emoji, text in emoji_map.items():
        title = title.replace(emoji, text)
    date_str = data.get("date", datetime.now().strftime("%Y-%m-%d"))
    draw.text((padding, padding), title, fill=(0, 0, 0), font=title_font)
    draw.text((padding + 280, padding + 3), f"[{date_str}]", fill=(128, 128, 128), font=header_font)
    
    # 绘制表头
    header_y = padding + 35
    headers = ["市场", "Ticker", "PE", "10年%位", "估值", "20年%位", "20年估值"]
    x_positions = [padding, padding + 80, padding + 160, padding + 240, padding + 340, padding + 440, padding + 540]
    
    for i, header in enumerate(headers):
        draw.text((x_positions[i], header_y), header, fill=(128, 128, 128), font=header_font)
    
    # 绘制分隔线
    draw.line([padding, header_y + 18, width - padding, header_y + 18], fill=(230, 230, 230), width=1)
    
    # 绘制数据行
    for idx, (key, name, default_ticker) in enumerate(markets):
        y_base = header_y + 25 + idx * row_height
        y = int(y_base)
        
        # 背景交替色
        if idx % 2 == 0:
            draw.rectangle([int(padding), y, int(width - padding), y + int(row_height)], fill=(250, 250, 250))
        
        market_data = data.get(key, {})
        pe = market_data.get("pe", "--")
        pct_10y = market_data.get("pct_10y")
        pct_20y = market_data.get("pct_20y")
        label_10y = _valuation_label(pct_10y) if pct_10y is not None else "--"
        label_20y = _valuation_label(pct_20y) if pct_20y is not None else "--"
        
        # 市场名称（将 emoji 替换为纯文本）
        display_name = name
        for emoji, text in emoji_map.items():
            display_name = display_name.replace(emoji, text)
        draw.text((x_positions[0], y + 15), display_name, fill=(0, 0, 0), font=value_font)
        
        # Ticker
        ticker = market_data.get("ticker", default_ticker)
        draw.text((x_positions[1], y + 15), ticker, fill=(80, 80, 80), font=value_font)
        
        # PE 值
        pe_str = f"{pe:.2f}" if isinstance(pe, (int, float)) else str(pe)
        draw.text((x_positions[2], y + 15), pe_str, fill=(0, 0, 0), font=value_font)
        
        # 10年百分位
        pct_10y_str = f"{pct_10y:.1f}%" if pct_10y is not None else "--"
        draw.text((x_positions[3], y + 15), pct_10y_str, fill=(80, 80, 80), font=value_font)
        
        # 10年估值标签（带颜色背景）
        if pct_10y is not None:
            color = _valuation_color(pct_10y)
            label_x = x_positions[4]
            draw.rectangle([label_x, y + 12, label_x + 60, y + 32], fill=color, outline=color)
            draw.text((label_x + 10, y + 15), label_10y, fill=(255, 255, 255), font=label_font)
        
        # 20年百分位
        pct_20y_str = f"{pct_20y:.1f}%" if pct_20y is not None else "--"
        draw.text((x_positions[5], y + 15), pct_20y_str, fill=(80, 80, 80), font=value_font)
        
        # 20年估值标签
        if pct_20y is not None:
            color = _valuation_color(pct_20y)
            label_x = x_positions[6]
            draw.rectangle([label_x, y + 12, label_x + 60, y + 32], fill=color, outline=color)
            draw.text((label_x + 10, y + 15), label_20y, fill=(255, 255, 255), font=label_font)
    
    # 绘制底部边框
    draw.line([padding, height - padding, width - padding, height - padding], fill=(230, 230, 230), width=1)
    
    # 保存图片
    if output_path is None:
        date_str = data.get("date", datetime.now().strftime("%Y-%m-%d"))
        output_path = os.path.join(_OUTPUT_DIR, f"global_valuation_{date_str}.png")
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path, "PNG", quality=90)
    print(f"[估值图片] 已生成: {output_path}")
    
    return output_path


if __name__ == "__main__":
    # 测试
    test_data = {
        "date": "2026-03-27",
        "US": {"pe": 24.43, "pct_10y": 75.8, "pct_20y": 82.9},
        "HK": {"pe": 12.65, "pct_10y": 68.1, "pct_20y": 63.2},
        "JP": {"pe": 18.81, "pct_10y": 100.0, "pct_20y": 94.6},
        "KR": {"pe": 18.95, "pct_10y": 99.2, "pct_20y": 99.6},
    }
    path = generate_valuation_image(test_data)
    print(f"图片路径: {path}")
