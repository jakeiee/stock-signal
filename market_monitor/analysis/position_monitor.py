"""
持仓监控模块。

通过妙想API获取持仓列表，计算知行趋势线状态，生成持仓分析报告。

使用示例：
    from market_monitor.analysis.position_monitor import get_positions, analyze_portfolio
    
    # 获取持仓
    positions = get_positions()
    
    # 分析持仓
    report = analyze_portfolio(positions)
    
    # 输出报告
    print_report(report)
"""

import json
import os
import ssl
import time
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Optional, List, Dict

from .zhixing import (
    analyze_stock, calculate_zhixing, generate_signal,
    comprehensive_score, analyze_position_with_score
)

# ── SSL 配置 ─────────────────────────────────────────────────────────────────
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

# ── 妙想API配置 ─────────────────────────────────────────────────────────────
_MX_API_URL = "https://miaoxiang.mxapi.com/api/selfselect/list"
_MX_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
}

# ── 持仓数据结构 ─────────────────────────────────────────────────────────────

POSITION_STRUCT = {
    "code": str,       # 股票代码
    "name": str,       # 股票名称
    "amount": float,   # 持股数量
    "cost": float,     # 成本价
}


# ── 妙想API调用 ─────────────────────────────────────────────────────────────

def _call_miaoxiang_api(api_key: str) -> Optional[dict]:
    """调用妙想自选股API"""
    # 尝试妙想标准接口
    urls_to_try = [
        ("https://miaoxiang.mxapi.com/api/selfselect/list", "POST"),
        ("https://miaoxiang.mxapi.com/api/position/list", "POST"),
        ("https://api.miaoxiang.cn/selfselect/list", "POST"),
    ]
    
    body = json.dumps({
        "apikey": api_key,
        "timestamp": int(time.time() * 1000),
    }, ensure_ascii=False).encode("utf-8")
    
    for url, method in urls_to_try:
        try:
            headers = {**_MX_HEADERS, "X-API-Key": api_key}
            req = urllib.request.Request(url, data=body, headers=headers, method=method)
            with urllib.request.urlopen(req, context=_SSL_CTX, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                if result.get("code") == 0 or result.get("success"):
                    return result
        except Exception as e:
            continue
    
    return None


def _parse_miaoxiang_response(data: dict) -> List[Dict]:
    """解析妙想API响应"""
    positions = []
    
    # 尝试不同的响应格式
    records = data.get("data", []) or data.get("result", []) or data.get("list", [])
    
    if isinstance(records, dict):
        records = [records]
    
    for item in records:
        position = {
            "code": item.get("code", item.get("stock_code", "")),
            "name": item.get("name", item.get("stock_name", "")),
            "amount": float(item.get("amount", item.get("shares", 0))),
            "cost": float(item.get("cost", item.get("avg_cost", 0))),
        }
        
        if position["code"]:
            positions.append(position)
    
    return positions


# ── 东方财富自选股 ────────────────────────────────────────────────────────────

def _fetch_from_eastmoney() -> List[Dict]:
    """
    从东方财富获取自选股列表（备用方案）。
    
    注：需要登录态，这里仅作为示例结构
    """
    # 东方财富自选股API（需要登录）
    url = "https://np-anotice-stock.eastmoney.com/securitystock/index"
    
    headers = {
        "Accept": "application/json",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://data.eastmoney.com/myestock/",
    }
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            
            positions = []
            for item in data.get("data", []):
                positions.append({
                    "code": item.get("code", ""),
                    "name": item.get("name", ""),
                    "amount": float(item.get("holdAmount", 0)),
                    "cost": float(item.get("cost", 0)),
                })
            
            return positions
    except Exception:
        return []


# ── 配置文件方式 ─────────────────────────────────────────────────────────────

def load_positions_from_file(filepath: str = "data/positions.json") -> List[Dict]:
    """
    从配置文件加载持仓列表。
    
    Args:
        filepath: 配置文件路径
    
    Returns:
        持仓列表
    """
    # 尝试多个可能的位置
    possible_paths = [
        filepath,
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "positions.json"),
        os.path.join(os.path.expanduser("~"), ".stock-signal", "positions.json"),
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
                    elif isinstance(data, dict) and "positions" in data:
                        return data["positions"]
            except Exception as e:
                print(f"[持仓监控] 读取配置文件失败 {path}: {e}")
    
    return []


def save_positions_to_file(positions: List[Dict], filepath: str = "positions.json") -> bool:
    """保存持仓列表到配置文件"""
    try:
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(positions, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[持仓监控] 保存配置文件失败: {e}")
        return False


# ── 主入口函数 ───────────────────────────────────────────────────────────────

def get_positions(
    api_key: Optional[str] = None,
    use_miaoxiang: bool = True,
    use_config: bool = True,
) -> List[Dict]:
    """
    获取持仓列表。
    
    Args:
        api_key: 妙想API密钥
        use_miaoxiang: 是否尝试妙想API
        use_config: 是否使用本地配置文件
    
    Returns:
        持仓列表
    """
    positions = []
    
    # 方式1：妙想API
    if use_miaoxiang and api_key:
        print("[持仓监控] 尝试从妙想API获取持仓...")
        data = _call_miaoxiang_api(api_key)
        if data:
            positions = _parse_miaoxiang_response(data)
            print(f"[持仓监控] 妙想API获取到 {len(positions)} 只持仓")
    
    # 方式2：东方财富（需要登录）
    if not positions:
        print("[持仓监控] 尝试从东方财富获取持仓...")
        positions = _fetch_from_eastmoney()
        print(f"[持仓监控] 东方财富获取到 {len(positions)} 只持仓")
    
    # 方式3：配置文件
    if not positions and use_config:
        print("[持仓监控] 从本地配置文件加载持仓...")
        positions = load_positions_from_file()
        print(f"[持仓监控] 配置文件加载了 {len(positions)} 只持仓")
    
    return positions


def analyze_portfolio(
    positions: List[Dict],
    include_etf: bool = True,
    with_scores: bool = True,
) -> Dict:
    """
    分析持仓组合（支持综合评分）。
    
    Args:
        positions: 持仓列表
        include_etf: 是否包含ETF分析
        with_scores: 是否计算综合评分
    
    Returns:
        分析报告
    """
    if not positions:
        return {
            "error": "无持仓数据",
            "positions": [],
            "summary": {},
        }
    
    print(f"\n[持仓监控] 开始分析 {len(positions)} 只持仓...")
    
    analyzed = []
    
    for i, pos in enumerate(positions):
        code = pos.get("code", "")
        name = pos.get("name", "")
        
        print(f"  [{i+1}/{len(positions)}] 分析 {code} {name}...", end=" ", flush=True)
        
        if with_scores:
            # 使用带评分的分析
            analysis = analyze_position_with_score(pos)
        else:
            # 基础分析
            analysis = analyze_stock(code, name)
            # 合并持仓信息
            analysis["amount"] = pos.get("amount", 0)
            analysis["cost"] = pos.get("cost", 0)
            
            # 计算盈亏
            if analysis.get("price") and analysis.get("cost") and analysis["cost"] > 0:
                analysis["profit_pct"] = (analysis["price"] - analysis["cost"]) / analysis["cost"] * 100
                analysis["profit_amount"] = analysis["amount"] * (analysis["price"] - analysis["cost"])
            else:
                analysis["profit_pct"] = 0
                analysis["profit_amount"] = 0
        
        # 生成操作建议
        analysis["action"] = _generate_action_suggestion(analysis)
        
        analyzed.append(analysis)
        
        if with_scores:
            print(f"评分={analysis.get('total_score', 0)}, 评级={analysis.get('rating', 'N/A')}")
        else:
            print(f"信号={analysis.get('signal')}, 排列={analysis.get('position', 'N/A')}")
    
    # 汇总统计
    summary = _generate_summary(analyzed, with_scores=with_scores)
    
    # 按评分排序
    if with_scores:
        analyzed.sort(key=lambda x: x.get("total_score", 0), reverse=True)
    
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "positions": analyzed,
        "summary": summary,
    }


def _generate_action_suggestion(analysis: Dict) -> str:
    """生成操作建议"""
    signal = analysis.get("signal", "")
    position = analysis.get("position", "")
    profit_pct = analysis.get("profit_pct", 0)
    
    if signal == "BUY":
        return "买入信号，建议关注"
    elif signal == "SELL":
        if profit_pct > 10:
            return "死叉信号，建议减仓止盈"
        elif profit_pct < -5:
            return "死叉信号，建议止损"
        else:
            return "死叉信号，考虑换仓"
    elif "多头排列" in position:
        if profit_pct > 20:
            return "强势持有，注意止盈"
        elif profit_pct > 10:
            return "稳定持有，可适当加仓"
        else:
            return "多头排列，持有待涨"
    elif "空头排列" in position:
        if profit_pct < -10:
            return "亏损较大，建议止损"
        elif profit_pct < -5:
            return "空头排列，考虑减仓"
        else:
            return "空头排列，建议观望"
    else:
        return "震荡整理，保持观察"


def _generate_summary(positions: List[Dict], with_scores: bool = True) -> Dict:
    """生成汇总统计"""
    total = len(positions)
    
    # 信号统计
    signals = {}
    for pos in positions:
        sig = pos.get("signal", "UNKNOWN")
        signals[sig] = signals.get(sig, 0) + 1
    
    # 排列统计
    bullish = sum(1 for p in positions if "多头排列" in p.get("position", ""))
    bearish = sum(1 for p in positions if "空头排列" in p.get("position", ""))
    
    # 盈亏统计
    total_cost = sum(p.get("cost", 0) * p.get("amount", 0) for p in positions)
    total_value = sum(p.get("price", 0) * p.get("amount", 0) for p in positions)
    total_profit = total_value - total_cost
    total_profit_pct = total_profit / total_cost * 100 if total_cost > 0 else 0
    
    # 买入信号
    buy_signals = [p for p in positions if p.get("signal") == "BUY"]
    sell_signals = [p for p in positions if p.get("signal") == "SELL"]
    
    result = {
        "total_positions": total,
        "signals": signals,
        "bullish_count": bullish,
        "bearish_count": bearish,
        "neutral_count": total - bullish - bearish,
        "total_cost": round(total_cost, 2),
        "total_value": round(total_value, 2),
        "total_profit": round(total_profit, 2),
        "total_profit_pct": round(total_profit_pct, 2),
        "buy_signals": [{"code": p["code"], "name": p["name"]} for p in buy_signals],
        "sell_signals": [{"code": p["code"], "name": p["name"]} for p in sell_signals],
    }
    
    # 综合评分统计
    if with_scores:
        result["avg_score"] = sum(p.get("total_score", 0) for p in positions) / total if total > 0 else 0
        result["buy_strong"] = sum(1 for p in positions if p.get("rating_code") == "BUY_STRONG")
        result["buy"] = sum(1 for p in positions if p.get("rating_code") == "BUY")
        result["hold"] = sum(1 for p in positions if p.get("rating_code") == "HOLD")
        result["sell"] = sum(1 for p in positions if p.get("rating_code") == "SELL")
    
    return result


# ── 报告输出 ─────────────────────────────────────────────────────────────────

def print_report(report: Dict) -> None:
    """打印持仓分析报告（带综合评分）"""
    if report.get("error"):
        print(f"错误: {report['error']}")
        return
    
    print("\n" + "=" * 80)
    print(f"📊 持仓分析报告 - {report.get('generated_at', '')}")
    print("=" * 80)
    
    summary = report.get("summary", {})
    
    # 汇总统计
    print(f"\n📈 汇总统计")
    print(f"  持仓数量: {summary.get('total_positions', 0)}")
    print(f"  多头排列: {summary.get('bullish_count', 0)}")
    print(f"  空头排列: {summary.get('neutral_count', 0)}")
    print(f"  总成本: {summary.get('total_cost', 0):,.2f}")
    print(f"  总市值: {summary.get('total_value', 0):,.2f}")
    print(f"  总盈亏: {summary.get('total_profit', 0):,.2f} ({summary.get('total_profit_pct', 0):.2f}%)")
    
    # 综合评分汇总
    avg_score = summary.get("avg_score", 0)
    buy_strong = summary.get("buy_strong", 0)
    buy = summary.get("buy", 0)
    hold = summary.get("hold", 0)
    sell = summary.get("sell", 0)
    
    print(f"\n🎯 综合评分汇总")
    print(f"  平均评分: {avg_score:.1f}")
    print(f"  🟢 强烈买入: {buy_strong}只")
    print(f"  🟡 买入: {buy}只")
    print(f"  ⚪ 持有: {hold}只")
    print(f"  🔴 减仓: {sell}只")
    
    # 详细持仓（按评分排序）
    print(f"\n📋 持仓明细（按评分排序）")
    print("-" * 80)
    print(f"{'代码':<8} {'名称':<10} {'评分':>5} {'评级':<12} {'趋势':<6} {'KDJ':<6} {'回踩':<6} {'强度':<6} {'成本':>7} {'现价':>7} {'盈亏%':>7}")
    print("-" * 80)
    
    for pos in report.get("positions", []):
        total_score = pos.get("total_score", 0)
        rating = pos.get("rating", "⚪ 持有")
        trend_s = pos.get("trend_score", 0)
        kdj_s = pos.get("kdj_score", 0)
        pullback_s = pos.get("pullback_score", 0)
        strength_s = pos.get("strength_score", 0)
        
        # 简化显示
        trend_str = f"+{trend_s}" if trend_s >= 0 else str(trend_s)
        kdj_str = f"+{kdj_s}" if kdj_s >= 0 else str(kdj_s)
        pullback_str = f"+{pullback_s}" if pullback_s >= 0 else str(pullback_s)
        strength_str = f"+{strength_s}" if strength_s >= 0 else str(strength_s)
        
        print(
            f"{pos.get('code', ''):<8} "
            f"{pos.get('name', ''):<10} "
            f"{total_score:>5} "
            f"{rating:<12} "
            f"{trend_str:>6} "
            f"{kdj_str:>6} "
            f"{pullback_str:>6} "
            f"{strength_str:>6} "
            f"{pos.get('cost', 0):>7.2f} "
            f"{pos.get('price', 0):>7.2f} "
            f"{pos.get('profit_pct', 0):>7.2f}%"
        )
    
    print("=" * 80)


def get_report_for_feishu(report: Dict) -> Dict:
    """
    生成适合飞书推送的报告格式。
    
    Returns:
        飞书卡片内容
    """
    if report.get("error"):
        return {"error": report["error"]}
    
    summary = report.get("summary", {})
    positions = report.get("positions", [])
    
    # 信号分类
    buy_positions = [p for p in positions if p.get("signal") == "BUY"]
    sell_positions = [p for p in positions if p.get("signal") == "SELL"]
    hold_positions = [p for p in positions if "多头排列" in p.get("position", "")]
    
    return {
        "title": f"📊 持仓监控 {report.get('generated_at', '')}",
        "summary": {
            "total": summary.get("total_positions", 0),
            "profit": f"{summary.get('total_profit', 0):,.2f}",
            "profit_pct": f"{summary.get('total_profit_pct', 0):.2f}%",
            "bullish": summary.get("bullish_count", 0),
            "bearish": summary.get("bearish_count", 0),
        },
        "buy_alerts": [
            {"code": p["code"], "name": p["name"], "action": p.get("action", "")}
            for p in buy_positions
        ],
        "sell_alerts": [
            {"code": p["code"], "name": p["name"], "action": p.get("action", ""), "profit_pct": p.get("profit_pct", 0)}
            for p in sell_positions
        ],
        "positions": [
            {
                "code": p["code"],
                "name": p["name"],
                "signal": p.get("signal", ""),
                "position": p.get("position", ""),
                "profit_pct": p.get("profit_pct", 0),
                "action": p.get("action", ""),
            }
            for p in positions[:10]  # 最多10只
        ],
    }


if __name__ == "__main__":
    # 测试代码
    # 方式1：从配置文件加载
    # positions = load_positions_from_file()
    
    # 方式2：直接指定（测试用）
    positions = [
        {"code": "600519", "name": "贵州茅台", "amount": 100, "cost": 1800},
        {"code": "000858", "name": "五粮液", "amount": 500, "cost": 180},
        {"code": "510300", "name": "沪深300ETF", "amount": 1000, "cost": 3.8},
    ]
    
    report = analyze_portfolio(positions)
    print_report(report)
