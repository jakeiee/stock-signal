"""
选股效果追踪模块。

追踪选股推荐的实际表现，统计命中率和胜率。

使用示例：
    from market_monitor.report.selection_tracker import SelectionTracker
    
    tracker = SelectionTracker()
    tracker.track_recommendations("2026-06-28", recommendations)
    perf = tracker.check_performance("2026-07-05")  # 7天后检查
    stats = tracker.get_tracking_stats()
"""

from typing import Dict, List, Optional
from market_monitor.data.portfolio_db import get_db, PortfolioDB


class SelectionTracker:
    """选股效果追踪器"""
    
    def __init__(self, db: PortfolioDB = None):
        self.db = db or get_db()
    
    def track_recommendations(self, date: str, recommendations: List[Dict]) -> int:
        """记录选股推荐到数据库。
        
        Args:
            date: 推荐日期
            recommendations: [{code, name, signal, total_score, kdj_j, etf_type, price}, ...]
        
        Returns:
            写入记录数
        """
        return self.db.track_recommendation(date, recommendations)
    
    def check_performance(self, date: str) -> Dict:
        """检查7天前推荐标的的实际表现，并更新数据库。
        
        实际价格通过 xalpha 获取。
        
        Args:
            date: 检查日期（当天）
        
        Returns:
            {total, hits, misses, hit_rate, avg_return, details}
        """
        from datetime import datetime as dt, timedelta
        target_date = (dt.strptime(date, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")
        
        result = self.db.check_performance(date)
        
        if result["total"] > 0 and any(d.get('actual_return_7d') is None for d in result.get('details', [])):
            # 部分尚未填写实际表现，尝试自动获取
            for detail in result['details']:
                if detail.get('actual_return_7d') is None:
                    try:
                        import xalpha as xa
                        from market_monitor.data.etf_index_mapping import lookup_by_etf_code
                        
                        code = detail['etf_code']
                        mapping = lookup_by_etf_code(code)
                        if mapping:
                            # 用指数价格近似
                            info = xa.indexinfo(code=mapping['xa_code'])
                            df = info.price
                            if not df.empty:
                                current_price = float(df.iloc[-1]['close'])
                                self.db.update_tracking(
                                    code, target_date, current_price, date
                                )
                        else:
                            # 直接用FundInfo
                            fund = xa.FundInfo(code)
                            if fund and fund.price is not None and not fund.price.empty:
                                nav = float(fund.price.iloc[-1].get('netvalue', 0))
                                if nav > 0:
                                    self.db.update_tracking(
                                        code, target_date, nav, date
                                    )
                    except Exception:
                        pass
            
            # 重新查询
            result = self.db.check_performance(date)
        
        return result
    
    def get_tracking_stats(self) -> Dict:
        """获取累计追踪统计（胜率/命中率/平均收益）。"""
        return self.db.get_tracking_stats()
    
    def get_tracking_summary_text(self) -> str:
        """生成追踪摘要文本（用于飞书报告）。"""
        stats = self.get_tracking_stats()
        if stats["total_checked"] == 0:
            return "暂无追踪数据"
        
        lines = [
            f"📊 选股追踪统计",
            f"累计检查 {stats['total_checked']} 条",
            f"命中率 {stats['hit_rate']:.0f}%（{stats['hits']}/{stats['total_checked']}）",
            f"平均7日收益 {stats['avg_return_7d']:+.2f}%",
        ]
        return "\n".join(lines)
