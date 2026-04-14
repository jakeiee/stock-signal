"""
板块数据获取模块。

数据来源：
  - AkShare 同花顺概念板块汇总（热点分析）
  - AkShare 概念板块历史行情

使用示例：
    from market_monitor.data_sources.sector import fetch_all_sector_data

    data = fetch_all_sector_data()
    print(f"概念板块: {len(data['concept_boards'])} 个")
"""

import os
import time
from datetime import datetime, timedelta
from typing import List, Dict

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


def _retry_akshare(func, max_retries: int = 2, delay: float = 1.0, *args, **kwargs):
    """带重试机制的 AkShare 调用封装"""
    last_error = None
    for attempt in range(max_retries):
        try:
            result = func(*args, **kwargs)
            if result is not None and not (hasattr(result, 'empty') and result.empty):
                return result
        except Exception as e:
            last_error = e
        
        if attempt < max_retries - 1:
            time.sleep(delay)
    
    return None


def fetch_industry_boards() -> List[Dict]:
    """
    获取行业板块数据。
    
    注意：同花顺行业板块列表只有名称和代码，无涨跌幅数据。
    如需涨跌幅，请使用东方财富行业板块（需要稳定网络）。
    
    Returns:
        行业板块列表（基本信息）
    """
    try:
        import akshare as ak
        df = ak.stock_board_industry_name_ths()
        
        if df is None or df.empty:
            return []
        
        boards = []
        for i, row in df.iterrows():
            boards.append({
                "name": str(row.get("name", "")),
                "code": str(row.get("code", "")),
                "rank": i + 1,
            })
        
        return boards
    except Exception as e:
        print(f"[板块数据] 获取行业板块失败: {e}")
        return []


def fetch_concept_boards() -> List[Dict]:
    """
    获取概念板块数据（带热点事件）。
    
    Returns:
        概念板块列表，包含近期热点事件
    """
    try:
        import akshare as ak
        df = _retry_akshare(ak.stock_board_concept_summary_ths, max_retries=2)
        
        if df is None or df.empty:
            return []
        
        boards = []
        for _, row in df.iterrows():
            boards.append({
                "name": str(row.get("概念名称", "")),
                "date": str(row.get("日期", "")),
                "event": str(row.get("驱动事件", "")),
                "leader": str(row.get("龙头股", "")),
                "stock_count": int(row.get("成分股数量", 0) or 0),
            })
        
        return boards
    except Exception as e:
        print(f"[板块数据] 获取概念板块失败: {e}")
        return []


def fetch_concept_hist(concept_name: str, period: str = "日线", adjust: str = "qfq") -> List[Dict]:
    """
    获取指定概念板块的历史行情。
    
    Args:
        concept_name: 概念名称
        period: K线周期
        adjust: 复权方式
    
    Returns:
        历史行情列表
    """
    try:
        import akshare as ak
        df = _retry_akshare(
            ak.stock_board_concept_hist_em,
            symbol=concept_name,
            period=period,
            adjust=adjust,
            max_retries=2
        )
        
        if df is None or df.empty:
            return []
        
        boards = []
        for _, row in df.iterrows():
            date_val = row.get("日期", "")
            if isinstance(date_val, str) and len(date_val) == 10:
                date_val = date_val.replace("-", "")
            
            boards.append({
                "date": date_val,
                "open": float(row.get("开盘", 0) or 0),
                "close": float(row.get("收盘", 0) or 0),
                "high": float(row.get("最高", 0) or 0),
                "low": float(row.get("最低", 0) or 0),
                "volume": float(row.get("成交量", 0) or 0),
                "turnover": float(row.get("成交额", 0) or 0),
                "change_pct": float(row.get("涨跌幅", 0) or 0),
            })
        
        return boards
    except Exception as e:
        print(f"[板块数据] 获取 {concept_name} 历史行情失败: {e}")
        return []


def fetch_hot_sectors(top_n: int = 10) -> Dict:
    """
    获取热点概念板块。
    
    通过获取近期热点概念来识别市场热点。
    """
    concept = fetch_concept_boards()
    
    if not concept:
        return {"hot_sectors": [], "change_pct": [], "hot_leading": None}
    
    # 取最新事件的概念（前N）
    hot_boards = concept[:top_n]
    
    # 尝试获取涨跌幅
    hot_sectors = []
    change_pcts = []
    for board in hot_boards:
        name = board.get("name", "")
        hist = fetch_concept_hist(name, period="日线")
        
        if hist and len(hist) >= 2:
            latest_change = hist[-1].get("change_pct", 0)
        else:
            latest_change = 0
        
        hot_sectors.append(name)
        change_pcts.append(latest_change)
    
    return {
        "hot_leading": hot_boards[0] if hot_boards else None,
        "hot_sectors": hot_sectors,
        "change_pct": change_pcts,
        "concepts": hot_boards,
    }


# ── 主入口：获取完整板块数据 ─────────────────────────────────────────────────────

def fetch_all_sector_data() -> Dict:
    """
    获取完整的板块分析数据。
    """
    print("[板块数据] 开始获取板块数据...", end=" ", flush=True)
    
    # 获取概念板块（主要）
    concept = fetch_concept_boards()
    
    # 热点概念
    hot = fetch_hot_sectors(10)
    
    # 行业板块
    industry = fetch_industry_boards()
    
    # 生成摘要
    summary = _generate_sector_summary(industry, concept, hot)
    
    result = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "industry_boards": industry,
        "concept_boards": concept,
        "hot_sectors": hot,
        "summary": summary,
    }
    
    print(f"完成（行业{len(industry)}个，概念{len(concept)}个）")
    return result


def _generate_sector_summary(industry: List, concept: List, hot: Dict) -> Dict:
    """生成板块分析摘要"""
    # 基于热点概念判断市场情绪
    hot_concepts = hot.get("concepts", [])
    change_pcts = hot.get("change_pct", [])
    
    if not change_pcts:
        avg_change = 0
    else:
        avg_change = sum(change_pcts) / len(change_pcts)
    
    # 市场情绪判断
    if avg_change > 2:
        market_bias = "强势"
    elif avg_change > 0:
        market_bias = "偏多"
    elif avg_change > -1:
        market_bias = "中性"
    elif avg_change > -3:
        market_bias = "偏空"
    else:
        market_bias = "弱势"
    
    return {
        "total_industry": len(industry),
        "total_concept": len(concept),
        "market_bias": market_bias,
        "avg_change_pct": round(avg_change, 2),
        "hot_concepts_count": len(hot_concepts),
    }


if __name__ == "__main__":
    # 测试代码
    data = fetch_all_sector_data()
    print(f"\n=== 板块数据概览 ===")
    print(f"时间: {data['generated_at']}")
    print(f"行业板块: {len(data['industry_boards'])} 个")
    print(f"概念板块: {len(data['concept_boards'])} 个")
    print(f"市场情绪: {data['summary'].get('market_bias', 'N/A')}")
    print(f"\n近期热点概念（前5）:")
    for i, board in enumerate(data["concept_boards"][:5]):
        print(f"  {i+1}. {board['name']} ({board.get('date', '')})")
        event = board.get('event', '')[:50]
        if event:
            print(f"     事件: {event}...")
