"""
Wind APP手动记录数据源封装。
"""

import os
import json
import re
from datetime import datetime
from typing import Optional, Dict, Any

# Wind APP数据目录 - 基于项目根目录
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WIND_APP_DATA_DIR = os.path.join(_project_root, "wind_app_recorded_data")

def load_wind_app_data() -> Dict[str, Dict[str, Any]]:
    """加载所有Wind APP记录的估值数据
    
    Returns:
        字典：{index_code: 数据字典}
    """
    result = {}
    
    if not os.path.exists(WIND_APP_DATA_DIR):
        return {}
    
    try:
        for filename in os.listdir(WIND_APP_DATA_DIR):
            if filename.endswith(".json"):
                filepath = os.path.join(WIND_APP_DATA_DIR, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                index_code = data.get("index_code")
                if index_code:
                    result[index_code] = data
        
        print(f"  → Wind APP数据: 加载了 {len(result)} 个指数的专业估值数据")
        return result
    except Exception as e:
        print(f"  → Wind APP数据加载失败: {e}")
        return {}


def get_valuation_from_wind_app(index_code: str, risk_free_rate: float) -> Optional[Dict[str, Any]]:
    """从Wind APP数据获取指定指数的估值
    
    Args:
        index_code: 指数代码，如 "H30269", "931468", "931446"
        risk_free_rate: 无风险利率（%）
    
    Returns:
        估值数据字典，格式适配系统使用规范
        或 None（如果数据不可用）
    """
    wind_data = load_wind_app_data()
    
    # 尝试大小写敏感匹配
    if index_code in wind_data:
        data = wind_data[index_code]
    else:
        # 尝试大小写不敏感匹配
        index_lower = index_code.lower()
        for key, value in wind_data.items():
            if key.lower() == index_lower:
                data = value
                break
        else:
            # 没有匹配的
            return None
    
    data = wind_data[index_code]
    valuation_data = data.get("valuation_data", {})
    
    # 提取估值数据
    pe_data = valuation_data.get("PE_TTM", {})
    div_data = valuation_data.get("dividend_yield", {})
    risk_data = valuation_data.get("risk_premium", {})
    
    # 质量检查信息
    quality = data.get("data_quality_check", {})
    
    # 从historical_period字段提取发布日
    # 格式示例: "发布以来（2012-10-26至今13.4年）"
    historical_period = data.get("historical_period", "")
    launch_date = ""
    
    # 匹配日期模式 YYYY-MM-DD
    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', historical_period)
    if date_match:
        launch_date = date_match.group(1)
    
    # 计算历史年限
    hist_years = float(quality.get("historical_period_years", 0))
    
    # 对于Wind APP数据，历史起始日就是发布日
    # 因为我们有完整发布历史
    hist_start_date = launch_date if launch_date else ""
    
    # 交易日数估算（基于历史年限）
    hist_days = int(hist_years * 240) if hist_years > 0 else 0
    
    # 按系统规范格式化
    result = {
        "date": data.get("record_date", ""),
        "div": div_data.get("value"),
        "div_pct": div_data.get("percentile"),
        "pe": pe_data.get("value"),
        "pe_pct": pe_data.get("percentile"),
        "risk_premium": risk_data.get("value"),
        "hist_start": hist_start_date,          # 对于Wind APP，就是发布日
        "hist_years": hist_years,
        "hist_days": hist_days,
        "launch_date": launch_date,             # 提取的发布日
        "launch_years": hist_years,             # 发布年限
        "launch_short_history": hist_years < 5,  # 如果低于5年，标记为短期历史
        "source": "wind_app",
        "wind_app_data_quality": quality.get("quality_grade", "未知")
    }
    
    return result


def update_valuation_cache() -> None:
    """使用Wind APP数据更新系统的估值缓存"""
    # 获取Wind APP数据
    wind_data = load_wind_app_data()
    
    if not wind_data:
        print("  找不到Wind APP数据，保持妙想API缓存")
        return
    
    # 缓存文件路径 - 基于项目根目录
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    cache_file = os.path.join(project_root, "dividend_monitor", "valuation_cache.json")
    
    try:
        # 加载现有缓存或创建新缓存
        if os.path.exists(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache = json.load(f)
        else:
            cache = {}
        
        # 更新每个指数的缓存
        updated_count = 0
        for index_code, data in wind_data.items():
            cache_key = index_code.lower()
            
            # 获取无风险利率（简化处理，使用默认值1.8%）
            risk_free_rate = 1.8
            
            # 获取估值数据
            valuation = get_valuation_from_wind_app(index_code, risk_free_rate)
            if valuation:
                # 更新缓存 - 包含所有必要的字段
                cache[cache_key] = {
                    "date": valuation["date"],
                    "div": valuation["div"],
                    "div_pct": valuation["div_pct"],
                    "pe": valuation["pe"],
                    "pe_pct": valuation["pe_pct"],
                    "risk_free_rate": risk_free_rate,
                    "risk_premium": valuation["risk_premium"],
                    "hist_start": valuation.get("hist_start", ""),
                    "hist_years": valuation["hist_years"],
                    "hist_days": valuation.get("hist_days", 0),
                    "launch_date": valuation.get("launch_date", ""),
                    "launch_years": valuation.get("launch_years", 0),
                    "launch_short_history": valuation.get("launch_short_history", False),
                    "source": "wind_app",
                    "wind_app_data_quality": valuation["wind_app_data_quality"],
                    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                updated_count += 1
        
        # 保存缓存
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
        
        if updated_count > 0:
            print(f"  ✓ Wind APP数据已更新估值缓存 ({updated_count}个指数)")
        else:
            print("  ⚠ Wind APP数据更新缓存失败")
    except Exception as e:
        print(f"  ⚠ Wind APP缓存更新失败: {e}")