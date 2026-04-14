"""
选股器模块。

ETF初筛 + 知行趋势线二次筛选的完整选股流程。

使用示例：
    from market_monitor.analysis.stock_selector import StockSelector
    
    selector = StockSelector()
    selector.set_etf_filter(types=["行业主题", "宽基指数"])
    selector.set_trend_filter(min_diff_pct=2)  # 短期高于长期2%以上
    results = selector.execute()
    
    # 或者使用预设
    from market_monitor.analysis.stock_selector import quick_screen
    results = quick_screen("kdj_oversold")
"""

from datetime import datetime
from typing import Optional, List, Dict, Callable

from ..data_sources.etf_selector import ETFFilter, get_kdj_oversold_etfs, fetch_etf_screening
from .zhixing import analyze_stock, analyze_stocks, calculate_zhixing


# ── 筛选器配置 ────────────────────────────────────────────────────────────────

class ETFPreFilter:
    """ETF预筛选器配置"""
    
    def __init__(self):
        self._etf_types: List[str] = []
        self._scale_min: Optional[float] = 5000  # 万元
        self._kdj_op: Optional[str] = "<"
        self._kdj_value: Optional[float] = 0
        self._sort_by: str = "kdj"
        self._sort_order: str = "asc"
        self._page_size: int = 50
        self._max_results: int = 50  # 最多筛选数量
    
    def set_types(self, types: List[str]) -> "ETFPreFilter":
        """设置ETF类型"""
        self._etf_types = types
        return self
    
    def set_scale_min(self, scale: float) -> "ETFPreFilter":
        """设置最小规模"""
        self._scale_min = scale
        return self
    
    def set_kdj_condition(self, op: str, value: float) -> "ETFPreFilter":
        """设置KDJ条件"""
        self._kdj_op = op
        self._kdj_value = value
        return self
    
    def set_sort(self, field: str, order: str = "asc") -> "ETFPreFilter":
        """设置排序"""
        self._sort_by = field
        self._sort_order = order
        return self
    
    def set_max_results(self, max_results: int) -> "ETFPreFilter":
        """设置最大结果数"""
        self._max_results = max_results
        return self
    
    def execute(self) -> Dict:
        """执行预筛选"""
        f = ETFFilter()
        
        if self._etf_types:
            f.add_types(self._etf_types)
        
        if self._scale_min:
            f.add_scale_min(self._scale_min)
        
        if self._kdj_op and self._kdj_value is not None:
            f.add_kdj_condition(self._kdj_op, self._kdj_value)
        
        f.set_page(1, self._page_size)
        f.sort_by(self._sort_by, self._sort_order)
        
        return f.execute()


class TrendFilter:
    """趋势线二次筛选器"""
    
    def __init__(self):
        self._min_diff_pct: Optional[float] = None  # 最小差值百分比
        self._signal_filter: Optional[List[str]] = None  # 信号过滤
        self._position_filter: Optional[List[str]] = None  # 排列过滤
        self._trend_direction: Optional[str] = None  # 趋势方向
        self._kdj_filter: Optional[Dict] = None  # KDJ条件
    
    def set_diff_pct(self, min_pct: float) -> "TrendFilter":
        """设置最小差值百分比"""
        self._min_diff_pct = min_pct
        return self
    
    def set_signal_filter(self, signals: List[str]) -> "TrendFilter":
        """设置信号过滤"""
        self._signal_filter = signals
        return self
    
    def set_position_filter(self, positions: List[str]) -> "TrendFilter":
        """设置排列过滤"""
        self._position_filter = positions
        return self
    
    def set_trend_direction(self, direction: str) -> "TrendFilter":
        """设置趋势方向"""
        self._trend_direction = direction
        return self
    
    def set_kdj_filter(self, op: str, value: float) -> "TrendFilter":
        """设置KDJ过滤条件"""
        self._kdj_filter = {"op": op, "value": value}
        return self
    
    def apply(self, analysis_results: List[Dict]) -> List[Dict]:
        """应用筛选条件"""
        filtered = analysis_results
        
        # 差值过滤
        if self._min_diff_pct is not None:
            filtered = [r for r in filtered 
                       if r.get("trend_diff_pct", 0) >= self._min_diff_pct]
        
        # 信号过滤
        if self._signal_filter:
            filtered = [r for r in filtered 
                       if r.get("signal") in self._signal_filter]
        
        # 排列过滤
        if self._position_filter:
            filtered = [r for r in filtered 
                       if any(p in r.get("position", "") for p in self._position_filter)]
        
        # 趋势方向过滤
        if self._trend_direction:
            filtered = [r for r in filtered 
                       if r.get("trend_direction") == self._trend_direction]
        
        # KDJ过滤
        if self._kdj_filter:
            op = self._kdj_filter["op"]
            val = self._kdj_filter["value"]
            if op == "<":
                filtered = [r for r in filtered if r.get("kdj_j", 100) < val]
            elif op == ">":
                filtered = [r for r in filtered if r.get("kdj_j", 0) > val]
        
        return filtered


# ── 选股器主类 ────────────────────────────────────────────────────────────────

class StockSelector:
    """
    选股器主类。
    
    两阶段筛选：
    1. 预筛选：使用东方财富ETF筛选API
    2. 二次筛选：知行趋势线验证
    
    使用示例：
        selector = StockSelector()
        selector.set_etf_filter(types=["行业主题", "宽基指数"])
        selector.set_trend_filter(signal=["BUY", "HOLD_BULL"])
        results = selector.execute()
    """
    
    def __init__(self):
        self._etf_filter = ETFPreFilter()
        self._trend_filter = TrendFilter()
        self._max_batch: int = 30  # 最多分析数量
    
    def set_etf_filter(self, **kwargs) -> "StockSelector":
        """设置ETF预筛选条件"""
        for key, value in kwargs.items():
            if key == "types":
                self._etf_filter.set_types(value)
            elif key == "scale_min":
                self._etf_filter.set_scale_min(value)
            elif key == "kdj":
                self._etf_filter.set_kdj_condition("<", value)
            elif key == "sort":
                self._etf_filter.set_sort(value.get("field", "kdj"), value.get("order", "asc"))
        return self
    
    def set_trend_filter(self, **kwargs) -> "StockSelector":
        """设置趋势线筛选条件"""
        for key, value in kwargs.items():
            if key == "min_diff_pct":
                self._trend_filter.set_diff_pct(value)
            elif key == "signal":
                self._trend_filter.set_signal_filter(value)
            elif key == "position":
                self._trend_filter.set_position_filter(value)
            elif key == "trend":
                self._trend_filter.set_trend_direction(value)
            elif key == "kdj":
                self._trend_filter.set_kdj_filter(value.get("op", "<"), value.get("value", 0))
        return self
    
    def set_max_batch(self, max_batch: int) -> "StockSelector":
        """设置最大批量分析数量"""
        self._max_batch = max_batch
        return self
    
    def execute(self) -> Dict:
        """
        执行选股流程。
        
        Returns:
            {
                "success": bool,
                "generated_at": str,
                "pre_filter_result": {...},    # ETF预筛选结果
                "trend_analysis": [...],        # 知行趋势线分析
                "final_recommendations": [...], # 最终推荐
                "summary": {...},               # 汇总统计
            }
        """
        print("[选股器] 阶段1: ETF预筛选...")
        
        # 阶段1：ETF预筛选
        pre_result = self._etf_filter.execute()
        if not pre_result.get("success"):
            return {
                "success": False,
                "error": f"ETF预筛选失败: {pre_result.get('error')}",
                "pre_filter_result": pre_result,
                "trend_analysis": [],
                "final_recommendations": [],
            }
        
        etfs = pre_result.get("etfs", [])[:self._max_batch]
        print(f"[选股器] ETF预筛选得到 {len(etfs)} 只")
        
        # 阶段2：知行趋势线分析
        print("[选股器] 阶段2: 知行趋势线二次筛选...")
        codes = [etf["code"] for etf in etfs]
        names = [etf["name"] for etf in etfs]
        
        analyses = analyze_stocks(codes, names)
        
        # 合并ETF信息
        for analysis, etf in zip(analyses, etfs):
            analysis["etf_type"] = etf.get("type", "")
            analysis["scale"] = etf.get("scale", 0)
            analysis["premium"] = etf.get("premium", 0)
            analysis["pre_kdj"] = etf.get("kdj_value", 0)  # 预筛选时的KDJ
        
        # 过滤错误和无效结果
        valid_analyses = [a for a in analyses if "error" not in a]
        print(f"[选股器] 趋势线分析完成，有效结果 {len(valid_analyses)}/{len(analyses)}")
        
        # 阶段3：趋势线筛选
        print("[选股器] 阶段3: 应用趋势筛选条件...")
        final_recs = self._trend_filter.apply(valid_analyses)
        
        # 排序（按差值百分比降序）
        final_recs.sort(key=lambda x: x.get("trend_diff_pct", 0), reverse=True)
        
        # 汇总统计
        summary = self._generate_summary(pre_result, analyses, final_recs)
        
        return {
            "success": True,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "pre_filter_result": pre_result,
            "trend_analysis": valid_analyses,
            "final_recommendations": final_recs,
            "summary": summary,
        }
    
    def _generate_summary(self, pre_result: Dict, analyses: List, final: List) -> Dict:
        """生成汇总统计"""
        total_analyzed = len([a for a in analyses if "error" not in a])
        
        # 信号分布
        signal_dist = {}
        for a in analyses:
            if "error" not in a:
                sig = a.get("signal", "UNKNOWN")
                signal_dist[sig] = signal_dist.get(sig, 0) + 1
        
        # 排列分布
        bullish = sum(1 for a in analyses if "多头排列" in a.get("position", ""))
        bearish = sum(1 for a in analyses if "空头排列" in a.get("position", ""))
        
        return {
            "pre_filter_total": pre_result.get("total", 0),
            "analyzed_count": total_analyzed,
            "final_count": len(final),
            "signal_distribution": signal_dist,
            "bullish_count": bullish,
            "bearish_count": bearish,
            "neutral_count": total_analyzed - bullish - bearish,
        }


# ── 预设选股策略 ──────────────────────────────────────────────────────────────

def quick_screen(strategy: str = "kdj_oversold") -> Dict:
    """
    快速筛选预设策略。
    
    Args:
        strategy: 策略名称
            - "kdj_oversold": KDJ超卖策略
            - "golden_cross": 金叉策略
            - "bullish_breakout": 多头突破策略
    
    Returns:
        筛选结果
    """
    strategies = {
        "kdj_oversold": {
            "etf_types": ["行业主题", "宽基指数", "风格策略"],
            "scale_min": 5000,
            "kdj_value": 0,
            "trend": {
                "signal": ["BUY", "HOLD_BULL"],
                "min_diff_pct": 0,
            },
        },
        "golden_cross": {
            "etf_types": ["行业主题", "宽基指数"],
            "scale_min": 5000,
            "kdj_value": 50,
            "trend": {
                "signal": ["BUY"],
                "min_diff_pct": 0,
            },
        },
        "bullish_breakout": {
            "etf_types": ["行业主题", "宽基指数"],
            "scale_min": 10000,
            "kdj_value": 0,
            "trend": {
                "signal": ["BUY", "HOLD_BULL"],
                "min_diff_pct": 2,
                "position": ["多头排列"],
            },
        },
    }
    
    config = strategies.get(strategy, strategies["kdj_oversold"])
    
    selector = StockSelector()
    selector.set_etf_filter(
        types=config.get("etf_types"),
        scale_min=config.get("scale_min"),
        kdj=config.get("kdj_value"),
    )
    selector.set_trend_filter(**config.get("trend", {}))
    
    return selector.execute()


def screen_custom(
    etf_types: List[str],
    min_scale: float = 5000,
    trend_signal: Optional[List[str]] = None,
    min_diff_pct: float = 0,
    bullish_only: bool = False,
) -> Dict:
    """
    自定义筛选条件。
    
    Args:
        etf_types: ETF类型列表
        min_scale: 最小规模（万元）
        trend_signal: 趋势信号列表
        min_diff_pct: 最小差值百分比
        bullish_only: 仅多头排列
    
    Returns:
        筛选结果
    """
    selector = StockSelector()
    selector.set_etf_filter(
        types=etf_types,
        scale_min=min_scale,
    )
    
    trend_filter = {}
    if trend_signal:
        trend_filter["signal"] = trend_signal
    if min_diff_pct > 0:
        trend_filter["min_diff_pct"] = min_diff_pct
    if bullish_only:
        trend_filter["position"] = ["多头排列"]
    
    if trend_filter:
        selector.set_trend_filter(**trend_filter)
    
    return selector.execute()


# ── 报告生成 ─────────────────────────────────────────────────────────────────

def print_selector_report(result: Dict) -> None:
    """打印选股报告"""
    if not result.get("success"):
        print(f"❌ 选股失败: {result.get('error')}")
        return
    
    summary = result.get("summary", {})
    
    print("\n" + "=" * 60)
    print(f"📊 选股报告 - {result.get('generated_at', '')}")
    print("=" * 60)
    
    print(f"\n📈 统计汇总")
    print(f"  ETF预筛选: {summary.get('pre_filter_total', 0)} 只")
    print(f"  趋势分析: {summary.get('analyzed_count', 0)} 只")
    print(f"  最终推荐: {summary.get('final_count', 0)} 只")
    
    print(f"\n📉 信号分布")
    for sig, count in summary.get("signal_distribution", {}).items():
        print(f"  {sig}: {count}")
    
    # 买入推荐
    buy_recs = [r for r in result.get("final_recommendations", []) 
               if r.get("signal") == "BUY"]
    if buy_recs:
        print(f"\n🟢 买入信号 ({len(buy_recs)}只)")
        print("-" * 60)
        print(f"{'代码':<10} {'名称':<12} {'类型':<10} {'差值%':>6} {'KDJ_J':>7}")
        print("-" * 60)
        for r in buy_recs[:10]:
            print(
                f"{r.get('code', ''):<10} "
                f"{r.get('name', ''):<12} "
                f"{r.get('etf_type', ''):<10} "
                f"{r.get('trend_diff_pct', 0):>6.2f} "
                f"{r.get('kdj_j', 0):>7.2f}"
            )
    
    # 持有推荐
    hold_recs = [r for r in result.get("final_recommendations", []) 
                if r.get("signal") != "BUY"]
    if hold_recs:
        print(f"\n🟡 关注推荐 ({len(hold_recs)}只)")
        print("-" * 60)
        print(f"{'代码':<10} {'名称':<12} {'信号':<10} {'排列':<8} {'差值%':>6}")
        print("-" * 60)
        for r in hold_recs[:10]:
            print(
                f"{r.get('code', ''):<10} "
                f"{r.get('name', ''):<12} "
                f"{r.get('signal', ''):<10} "
                f"{r.get('position', ''):<8} "
                f"{r.get('trend_diff_pct', 0):>6.2f}"
            )
    
    print("=" * 60)


def get_selector_report_for_feishu(result: Dict) -> Dict:
    """生成适合飞书推送的选股报告"""
    if not result.get("success"):
        return {"error": result.get("error")}
    
    summary = result.get("summary", {})
    recs = result.get("final_recommendations", [])
    
    buy_recs = [r for r in recs if r.get("signal") == "BUY"]
    
    return {
        "title": f"📊 选股建议 {result.get('generated_at', '')}",
        "summary": {
            "total_analyzed": summary.get("analyzed_count", 0),
            "final_count": summary.get("final_count", 0),
            "buy_signals": len(buy_recs),
            "strategy": "KDJ超卖 + 知行趋势线",
        },
        "buy_recommendations": [
            {
                "code": r.get("code"),
                "name": r.get("name"),
                "type": r.get("etf_type"),
                "trend_diff_pct": r.get("trend_diff_pct"),
                "kdj_j": r.get("kdj_j"),
                "scale": r.get("scale"),
            }
            for r in buy_recs[:5]
        ],
        "attention_recommendations": [
            {
                "code": r.get("code"),
                "name": r.get("name"),
                "signal": r.get("signal"),
                "position": r.get("position"),
            }
            for r in recs if r.get("signal") != "BUY"[:5]
        ],
    }


if __name__ == "__main__":
    # 测试代码
    print("[选股器] 执行快速筛选 (KDJ超卖策略)...")
    result = quick_screen("kdj_oversold")
    print_selector_report(result)
