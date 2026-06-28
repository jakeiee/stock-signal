"""
组合维度分析 —— 板块集中度、ETF相关性、最大回撤、权重分布。

使用示例：
    from market_monitor.analysis.portfolio_analyzer import PortfolioAnalyzer
    
    analyzer = PortfolioAnalyzer(positions_data)
    conc = analyzer.sector_concentration()
    corr = analyzer.correlation_matrix()
    dd = analyzer.max_drawdown()
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional


# 板块分类规则（基于指数名称关键词）
_SECTOR_KEYWORDS = {
    "港股科技": ["恒生科技", "港股通科技", "港股通互联网"],
    "港股其他": ["恒生互联网", "恒生医疗", "港股通创新药", "香港证券", "恒生中国", "港股通消费"],
    "A股科技": ["科创", "软件", "机器人", "人工智能", "物联网"],
    "A股消费/游戏": ["游戏", "消费电子", "家电"],
    "A股价值/红利": ["红利", "价值", "银行", "煤炭", "能源", "公用", "电力"],
}


def _classify(index_name: str) -> str:
    """根据指数名称归类板块。"""
    for sector, keywords in _SECTOR_KEYWORDS.items():
        for kw in keywords:
            if kw in index_name:
                return sector
    return "其他"


class PortfolioAnalyzer:
    """组合维度分析器"""
    
    def __init__(self, results: List[Dict]):
        self.results = results
    
    def sector_concentration(self) -> Dict:
        """计算板块集中度。
        
        Returns:
            {sector_name: {count, weight, etfs: [...]}}
        """
        distribution = {}
        total_mv = sum(r.get('market_value', 0) for r in self.results)
        
        for r in self.results:
            index_name = r.get('index_name', '')
            sector = _classify(index_name)
            
            if sector not in distribution:
                distribution[sector] = {"count": 0, "weight": 0.0, "etfs": []}
            
            mv = r.get('market_value', 0)
            distribution[sector]["count"] += 1
            distribution[sector]["weight"] += mv / total_mv * 100 if total_mv else 0
            distribution[sector]["etfs"].append(r.get('etf_name', index_name))
        
        # 按权重降序
        return dict(sorted(distribution.items(), key=lambda x: x[1]["weight"], reverse=True))
    
    def correlation_matrix(self) -> Optional[Dict]:
        """计算ETF间相关系数矩阵（需要各ETF的历史价格序列）。
        
        注意：需要 results 中包含 _prices 字段（pd.Series），
        否则需要先通过 get_index_data 获取历史数据。
        
        Returns:
            {matrix: [[...]], labels: [...]} 或 None
        """
        prices = {}
        for r in self.results:
            code = r.get('etf_code', '')
            price_series = r.get('_price_series')
            if price_series is not None:
                prices[code] = price_series
        
        if len(prices) < 2:
            return None
        
        df = pd.DataFrame(prices)
        corr = df.corr().round(3)
        
        return {
            "matrix": corr.values.tolist(),
            "labels": corr.columns.tolist(),
            "avg_correlation": round((corr.values.sum() - len(corr)) / (len(corr) * (len(corr) - 1)), 3),
        }
    
    def max_drawdown(self) -> Dict:
        """计算组合最大回撤（基于各ETF的回撤加权平均）。"""
        drawdowns = []
        weights = []
        
        for r in self.results:
            dd = r.get('max_drawdown_60d')
            if dd is not None:
                w = r.get('weight', 1.0 / len(self.results))
                drawdowns.append(dd)
                weights.append(w)
        
        if not drawdowns:
            return {"portfolio_max_dd": 0, "details": "无回撤数据"}
        
        weighted_dd = sum(d * w for d, w in zip(drawdowns, weights)) / sum(weights)
        max_single = min(drawdowns)  # 负值越大 = 回撤越大
        
        return {
            "portfolio_weighted_max_dd": round(weighted_dd, 2),
            "worst_single_etf_dd": round(max_single, 2),
            "individual_drawdowns": drawdowns,
        }
    
    def weight_distribution(self) -> Dict:
        """各市场/板块的权重分布。
        
        Returns:
            {market: weight_pct, ...}
        """
        dist = {}
        total_mv = sum(r.get('market_value', 0) for r in self.results)
        
        for r in self.results:
            # 判断市场
            code = r.get('etf_code', '')
            if code.startswith('5'):
                market = "港股"
            elif code.startswith(('1', '0', '5')):
                market = "A股"
            else:
                market = "其他"
            
            mv = r.get('market_value', 0)
            dist[market] = dist.get(market, 0) + mv
        
        return {k: round(v / total_mv * 100, 1) if total_mv else 0 for k, v in dist.items()}
    
    def summary(self) -> Dict:
        """生成组合分析摘要。"""
        return {
            "sector_concentration": self.sector_concentration(),
            "weight_distribution": self.weight_distribution(),
            "max_drawdown": self.max_drawdown(),
        }
