"""
估值数据本地缓存的读写封装。
"""

import csv
import json
from datetime import datetime
from pathlib import Path

# 处理导入：支持直接执行和模块执行
if __package__:
    from .config import VAL_CACHE_FILE
else:
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from dividend_monitor.config import VAL_CACHE_FILE

# CSV文件路径（与配置目录同级）
CSV_FILE = Path(__file__).parent / "dividend_index_valuation.csv"


def load() -> dict:
    """
    读取本地估值缓存（优先从CSV读取最新数据，降级到JSON缓存）。
    返回 {code: result_dict}；文件不存在或解析失败时返回空字典。
    """
    # 优先从CSV读取最新数据
    csv_data = _load_from_csv()
    if csv_data:
        return csv_data
    
    # 降级到JSON缓存
    try:
        with open(VAL_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _load_from_csv() -> dict:
    """
    从CSV文件读取最新日期的估值数据。
    Returns: {code: result_dict} 或 空字典（CSV不存在或解析失败）
    """
    if not CSV_FILE.exists():
        return {}
    
    try:
        result = {}
        latest_date = None
        
        with open(CSV_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        if not rows:
            return {}
        
        # 找出最新日期
        for row in rows:
            if row.get("date"):
                try:
                    row_date = datetime.strptime(row["date"], "%Y-%m-%d")
                    if latest_date is None or row_date > latest_date:
                        latest_date = row_date
                except ValueError:
                    continue
        
        if latest_date is None:
            return {}
        
        # 筛选最新日期的数据
        latest_date_str = latest_date.strftime("%Y-%m-%d")
        for row in rows:
            if row.get("date") == latest_date_str:
                code = row["index_code"].upper()  # 统一大写
                
                # 计算历史年数（发布日到数据日期）
                launch_date_str = row.get("launch_date", "")
                hist_years = 0.0
                if launch_date_str and row.get("date"):
                    try:
                        launch_dt = datetime.strptime(launch_date_str, "%Y-%m-%d")
                        days = (latest_date - launch_dt).days
                        hist_years = round(days / 365.25, 1)
                    except ValueError:
                        pass
                
                result[code] = {
                    "date": row["date"],
                    "pe": float(row["pe_ttm"]) if row.get("pe_ttm") else None,
                    "pe_pct": float(row["pe_pct"]) if row.get("pe_pct") else None,
                    "div": float(row["div_yield"]) if row.get("div_yield") else None,
                    "div_pct": float(row["div_pct"]) if row.get("div_pct") else None,
                    "risk_premium": float(row["risk_premium"]) if row.get("risk_premium") else None,
                    "risk_premium_pct": float(row["risk_premium_pct"]) if row.get("risk_premium_pct") else None,
                    "launch_date": launch_date_str,
                    "hist_years": hist_years,
                    "launch_short_history": hist_years < 10 if hist_years > 0 else False,
                    "source": row.get("source", "csv"),
                }
        
        if result:
            print(f"  → CSV数据: 读取 {len(result)} 个指数最新数据 ({latest_date_str})")
        
        return result
        
    except Exception as e:
        print(f"  ⚠ CSV读取失败: {e}")
        return {}


def save(cache: dict) -> None:
    """将估值结果追加写入CSV文件，同时保留历史数据。"""
    try:
        # 确保CSV文件存在且有表头
        file_exists = CSV_FILE.exists()
        
        # 获取指数名称映射
        index_names = {
            "931468": "红利质量",
            "931446": "东证红利低波",
            "H30269": "红利低波",
        }
        
        # 获取指数发布日期映射
        launch_dates = {
            "931468": "2020-05-21",
            "931446": "2020-04-21",
            "H30269": "2013-12-19",
        }
        
        today = datetime.now().strftime("%Y-%m-%d")
        
        with open(CSV_FILE, "a", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            
            # 如果文件不存在，写入表头
            if not file_exists:
                writer.writerow([
                    "date", "index_code", "index_name", "launch_date",
                    "pe_ttm", "pe_pct", "div_yield", "div_pct",
                    "risk_premium", "risk_premium_pct", "source"
                ])
            
            # 追加数据
            for code, data in cache.items():
                writer.writerow([
                    today,
                    code,
                    index_names.get(code.upper(), ""),
                    launch_dates.get(code.upper(), ""),
                    data.get("pe", ""),
                    data.get("pe_pct", ""),
                    data.get("div", ""),
                    data.get("div_pct", ""),
                    data.get("risk_premium", ""),
                    data.get("risk_premium_pct", ""),
                    data.get("source", "manual"),
                ])
        
        print(f"  → CSV已追加: {len(cache)} 条记录 ({today})")
        
    except Exception as e:
        print(f"  ⚠ CSV写入失败: {e}")
