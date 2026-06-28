"""
持仓数据管理器 —— 实时市值/盈亏计算。

通过 xalpha FundInfo 获取最新净值，结合 positions.json 中的持仓信息，
自动计算每只ETF的 market_value 和 profit_pct。

使用示例：
    from market_monitor.data.portfolio_manager import PortfolioManager
    
    pm = PortfolioManager("market_monitor/positions.json")
    updated = pm.update_all_positions()
    # positions.json 会被更新，添加 market_value / profit_pct / current_price
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple


class PortfolioManager:
    """持仓数据管理器"""
    
    def __init__(self, positions_path: str = "market_monitor/positions.json"):
        self.positions_path = positions_path
        self.positions = self._load()
    
    def _load(self) -> List[Dict]:
        if not os.path.exists(self.positions_path):
            return []
        with open(self.positions_path, 'r') as f:
            return json.load(f)
    
    def _save(self) -> None:
        with open(self.positions_path, 'w') as f:
            json.dump(self.positions, f, ensure_ascii=False, indent=2)
    
    def get_nav(self, code: str) -> Tuple[float, Optional[str]]:
        """通过 xalpha 获取ETF最新净值和日期。
        
        Returns:
            (nav, date_str) 或 (0.0, None) 表示获取失败
        """
        try:
            import xalpha as xa
            info = xa.FundInfo(code)
            if info and hasattr(info, 'price') and not info.price.empty:
                latest = info.price.iloc[-1]
                nav = float(latest.get('netvalue', latest.get('close', 0)))
                date = str(latest.get('date', ''))
                return nav, date
            return 0.0, None
        except Exception as e:
            print(f"  [净值] {code} 获取失败: {e}")
            return 0.0, None
    
    def update_position(self, code: str, force: bool = False) -> Optional[Dict]:
        """更新单只ETF的市值和盈亏。
        
        Args:
            code: ETF代码
            force: 是否强制更新已有时值
        
        Returns:
            更新后的持仓 dict，失败返回 None
        """
        for pos in self.positions:
            if pos.get('code') == code:
                # 如果已有 market_value 且不强制，跳过
                if pos.get('market_value') and pos.get('profit_pct') is not None and not force:
                    return pos
                
                nav, date = self.get_nav(code)
                if nav <= 0:
                    return pos  # 保留旧数据
                
                shares = pos.get('shares', 0)
                cost_price = pos.get('cost_price', 0)
                market_value = nav * shares
                cost_value = cost_price * shares
                profit_pct = (market_value - cost_value) / cost_value * 100 if cost_value else 0
                
                pos['current_price'] = round(nav, 4)
                pos['market_value'] = round(market_value, 2)
                pos['cost_value'] = round(cost_value, 2)
                pos['profit_pct'] = round(profit_pct, 2)
                pos['nav_date'] = date or ''
                
                return pos
        return None
    
    def update_all_positions(self) -> List[Dict]:
        """批量更新所有持仓。"""
        errors = []
        for pos in self.positions:
            code = pos.get('code', '')
            result = self.update_position(code)
            if result is None:
                errors.append(code)
        
        self._save()
        
        if errors:
            print(f"  ⚠ {len(errors)} 只ETF净值获取失败: {', '.join(errors)}")
        
        return self.positions
    
    def get_total_value(self) -> Tuple[float, float, float]:
        """获取组合总市值、总成本、总盈亏。
        
        Returns:
            (total_market_value, total_cost_value, total_profit_pct)
        """
        total_mv, total_cost = 0.0, 0.0
        for pos in self.positions:
            mv = pos.get('market_value', 0)
            cv = pos.get('cost_value', pos.get('shares', 0) * pos.get('cost_price', 0))
            total_mv += mv
            total_cost += cv
        
        profit_pct = (total_mv - total_cost) / total_cost * 100 if total_cost else 0
        return total_mv, total_cost, profit_pct
    
    def get_weight_distribution(self) -> Dict[str, float]:
        """获取持仓权重分布（按ETF代码）。"""
        total_mv, _, _ = self.get_total_value()
        if total_mv <= 0:
            return {}
        
        return {
            pos['code']: pos.get('market_value', 0) / total_mv
            for pos in self.positions
        }
