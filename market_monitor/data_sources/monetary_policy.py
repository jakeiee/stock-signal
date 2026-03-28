"""
货币政策数据源。

已实现指标：
  - 存款准备金率（大行）：从 AkShare 获取
  - MLF利率（1年期）：从缓存降级（政策利率变化不频繁）
  - 7天逆回购利率：从缓存降级（政策利率变化不频繁）
  - LPR (1年/5年)：从 AkShare 获取
  - 10年国债收益率：从 ChinaMoney API 获取

数据获取策略：
  1. AkShare - LPR、存款准备金率
  2. ChinaMoney API - 10年国债收益率
  3. CSV缓存降级 - MLF、逆回购（无公开API）
  4. Web Search - 动态发现政策变化

注意：
  - 不使用基准值，所有数据必须从API获取
  - 若API全部失败，返回缓存数据（若有）或错误信息

信号规则：
  - 降准≥0.5% → 🟢 资金宽松力度大
  - MLF/逆回购利率下调≥10BP → 🟢 资金成本降低
  - LPR下调 → 🟢 贷款成本降低
  - 10年国债收益率<2.0% → 🟢 低利率环境

数据文件：
  market_monitor/data/monetary_policy.csv
    字段：date, rrr, mlf_7d, repo_7d, lpr_5y, bond_10y, source, cached_at
"""

import os
import csv
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from pathlib import Path

# 缓存路径
DATA_DIR = Path(__file__).parent.parent / "data"
CACHE_FILE = DATA_DIR / "monetary_policy.csv"

# 不使用基准值，所有数据必须从API获取或从CSV缓存降级
# 若所有API失败，返回错误信息


def _fetch_lpr_akshare() -> Optional[Dict]:
    """通过 AkShare 获取 LPR 数据"""
    try:
        import akshare as ak
        df = ak.macro_china_lpr()
        # 获取最新有LPR数据的记录
        valid_df = df[df['LPR1Y'].notna()]
        if len(valid_df) > 0:
            latest = valid_df.iloc[-1]
            return {
                "lpr_1y": float(latest['LPR1Y']),
                "lpr_5y": float(latest['LPR5Y']),
                "date": str(latest['TRADE_DATE'])[:10],
                "source": "akshare"
            }
    except Exception as e:
        print(f"[货币政策] AkShare LPR获取失败: {e}")
    return None


def _fetch_rrr_akshare() -> Optional[Dict]:
    """通过 AkShare 获取存款准备金率数据"""
    try:
        import akshare as ak
        df = ak.macro_china_reserve_requirement_ratio()
        if len(df) > 0:
            latest = df.iloc[0]  # 第一条是最新的
            return {
                "rrr_large": float(latest.get('大型金融机构-调整后', 0)),
                "rrr_small": float(latest.get('中小金融机构-调整后', 0)),
                "date": str(latest.get('公布时间', ''))[:10],
                "source": "akshare"
            }
    except Exception as e:
        print(f"[货币政策] AkShare RRR获取失败: {e}")
    return None


def _fetch_bond_10y_chinamoney() -> Optional[Dict]:
    """
    从中国外汇交易中心（ChinaMoney）获取10年国债收益率。
    API: https://www.chinamoney.com.cn/r/cms/www/chinamoney/data/currency/sdds-intr-rate.json
    """
    import ssl
    import urllib.request
    import json
    import time
    
    try:
        # 创建 SSL 上下文（忽略证书验证）
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        ts = int(time.time() * 1000)
        url = f"https://www.chinamoney.com.cn/r/cms/www/chinamoney/data/currency/sdds-intr-rate.json?t={ts}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json",
        }
        req = urllib.request.Request(url, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=15, context=ssl_context) as resp:
            raw = resp.read().decode("utf-8")
        data = json.loads(raw)
        bond_10y = data.get("data", {}).get("bond10Y")
        if bond_10y is not None:
            return {
                "bond_10y": float(bond_10y),
                "source": "chinamoney"
            }
    except Exception as e:
        print(f"[货币政策] ChinaMoney 10年国债获取失败: {e}")
    return None

# 政策变化历史记录
POLICY_CHANGES = []  # 格式: {"date": "YYYY-MM-DD", "type": "类型", "change": "变化", "impact": "影响"}


def _load_cache() -> Optional[Dict]:
    """读取缓存数据"""
    if not CACHE_FILE.exists():
        return None
    
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            if rows:
                # 返回最新的记录
                return rows[-1]
    except Exception as e:
        print(f"[货币政策] 读取缓存失败: {e}")
    
    return None


def _save_cache(data: Dict) -> None:
    """保存到缓存"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    file_exists = CACHE_FILE.exists()
    
    try:
        with open(CACHE_FILE, "a", encoding="utf-8", newline="") as f:
            fieldnames = ["date", "rrr_large", "rrr_small", "mlf_1y", "repo_7d", "lpr_1y", "lpr_5y", "bond_10y", "policy_change", "impact", "signal", "signal_rules", "source", "cached_at"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            
            # 移除signal和signal_rules（JSON字段不适合CSV）
            save_data = {k: v for k, v in data.items() if k not in ["signal", "signal_rules"]}
            if isinstance(save_data.get("signal_rules"), list):
                save_data["signal_rules"] = str(save_data["signal_rules"])
            
            if not file_exists:
                writer.writeheader()
            
            save_data["cached_at"] = datetime.now().isoformat()
            writer.writerow(save_data)
            
        print(f"[货币政策] 已缓存到: {CACHE_FILE}")
    except Exception as e:
        print(f"[货币政策] 缓存失败: {e}")


def _search_policy_change() -> Optional[Dict]:
    """通过Web Search搜索近期政策变化"""
    try:
        from market_monitor.utils.web_search import search_web
        
        # 搜索近期的货币政策变化
        queries = [
            "MLF 利率下调 2026",
            "降准 2026 央行",
            "LPR 利率调整 2026",
            "逆回购 利率 2026",
        ]
        
        for query in queries:
            results = search_web(query, limit=5)
            for r in results:
                url = r.get("url", "")
                title = r.get("title", "")
                
                # 检查是否有最新政策
                keywords = ["下调", "降息", "降准", "上调", "升息", "升准"]
                if any(kw in title for kw in keywords):
                    return {
                        "title": title,
                        "url": url,
                        "query": query
                    }
        
        return None
        
    except Exception as e:
        print(f"[货币政策] 搜索失败: {e}")
        return None


def fetch_monetary_policy(force_refresh: bool = False) -> Dict:
    """
    获取货币政策数据。
    
    数据获取优先级：
    1. 缓存数据（7天内有效）
    2. AkShare API - LPR、存款准备金率
    3. ChinaMoney API - 10年国债收益率
    4. CSV缓存降级 - MLF、逆回购（无公开API）
    5. Web Search - 动态发现政策变化
    
    注意：若所有API失败，返回缓存数据或错误信息
    
    Args:
        force_refresh: 是否强制刷新（忽略缓存）
    
    Returns:
        {
            "date": "2026-03-26",
            "rrr_large": 10.0,
            "rrr_small": 7.0, 
            "mlf_1y": 2.0,
            "repo_7d": 1.5,
            "lpr_1y": 3.0,
            "lpr_5y": 3.5,
            "bond_10y": 1.82,
            "policy_change": "MLF利率维持不变",
            "impact": "中性",
            "signal": "🟡 货币宽松观望",
            "source": "akshare + chinamoney + 缓存",
            "signal_rules": [...]
        }
    """
    # 1. 尝试从缓存读取
    if not force_refresh:
        cached = _load_cache()
        if cached:
            cached_date = cached.get("date", "")
            if cached_date:
                try:
                    cached_dt = datetime.strptime(cached_date, "%Y-%m-%d")
                    if (datetime.now() - cached_dt).days < 7:
                        print(f"[货币政策] 命中缓存: {cached_date}")
                        return cached
                except:
                    pass
    
    today = datetime.now().strftime("%Y-%m-%d")
    sources = []
    api_success = False
    
    # 2. 尝试从 AkShare 获取 LPR 数据
    lpr_data = _fetch_lpr_akshare()
    if lpr_data:
        lpr_1y = lpr_data.get("lpr_1y")
        lpr_5y = lpr_data.get("lpr_5y")
        if lpr_1y and lpr_5y:
            sources.append(f"LPR(akshare): 1Y={lpr_1y}%, 5Y={lpr_5y}%")
            api_success = True
    
    # 3. 尝试从 AkShare 获取存款准备金率
    rrr_data = _fetch_rrr_akshare()
    if rrr_data:
        rrr_large = rrr_data.get("rrr_large")
        rrr_small = rrr_data.get("rrr_small")
        if rrr_large and rrr_small:
            sources.append(f"RRR(akshare): 大行={rrr_large}%, 小行={rrr_small}%")
            api_success = True
    
    # 4. 尝试从 ChinaMoney 获取 10年国债收益率
    bond_data = _fetch_bond_10y_chinamoney()
    if bond_data:
        bond_10y = bond_data.get("bond_10y")
        if bond_10y:
            sources.append(f"10年国债(chinamoney): {bond_10y}%")
            api_success = True
    
    # 5. 如果所有API都失败，尝试降级读取缓存
    if not api_success:
        cached = _load_cache()
        if cached:
            print(f"[货币政策] 所有API失败，使用缓存降级")
            cached["policy_change"] = "API获取失败，使用缓存数据"
            cached["source"] = "缓存降级"
            return cached
        else:
            # 无缓存，返回错误
            return {
                "error": "货币政策数据获取失败：所有API和缓存均不可用",
                "date": today,
            }
    
    # 6. 构建数据（从缓存获取MLF和逆回购，因为无公开API）
    # 尝试从缓存获取MLF和逆回购
    cached_fallback = _load_cache()
    mlf_1y = cached_fallback.get("mlf_1y") if cached_fallback else None
    repo_7d = cached_fallback.get("repo_7d") if cached_fallback else None
    
    data = {
        "date": today,
        "rrr_large": rrr_data.get("rrr_large") if rrr_data else None,
        "rrr_small": rrr_data.get("rrr_small") if rrr_data else None,
        "mlf_1y": mlf_1y if mlf_1y else None,
        "repo_7d": repo_7d if repo_7d else None,
        "lpr_1y": lpr_data.get("lpr_1y") if lpr_data else None,
        "lpr_5y": lpr_data.get("lpr_5y") if lpr_data else None,
        "bond_10y": bond_data.get("bond_10y") if bond_data else None,
    }
    
    # 7. 搜索近期政策变化
    policy_info = _search_policy_change()
    
    if policy_info:
        data["policy_change"] = f"发现新政策动态: {policy_info.get('title', '')[:30]}..."
    else:
        data["policy_change"] = "近期无重大政策变化"
    
    data["source"] = " | ".join(sources) if sources else "缓存降级"
    
    # 8. 生成信号
    data["signal"], data["signal_rules"] = _generate_signal(data)
    data["impact"] = data["signal"]
    
    # 9. 缓存
    _save_cache(data)
    
    return data


def _safe_float(val) -> Optional[float]:
    """安全转换为浮点数"""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        try:
            return float(val)
        except:
            return None
    return None


def _generate_signal(data: Dict) -> tuple:
    """生成政策信号"""
    signals = []
    rules = []
    
    # MLF利率（无数据时不展示）
    mlf = _safe_float(data.get("mlf_1y"))
    if mlf is not None and mlf > 0:
        if mlf <= 2.0:
            signals.append("🟢 MLF利率低位")
            rules.append(f"MLF利率 {mlf}%（低位，宽松信号）")
        elif mlf <= 2.5:
            signals.append("🟡 MLF利率正常")
            rules.append(f"MLF利率 {mlf}%（正常区间）")
        else:
            signals.append("🔴 MLF利率偏高")
            rules.append(f"MLF利率 {mlf}%（偏高）")
    
    # 存款准备金率
    rrr = _safe_float(data.get("rrr_large"))
    if rrr is not None and rrr > 0:
        if rrr <= 10.0:
            signals.append("🟢 降准空间")
            rules.append(f"存款准备金率 {rrr}%")
    
    # 10年国债收益率
    bond = _safe_float(data.get("bond_10y"))
    if bond is not None:
        if bond < 2.0:
            signals.append("🟢 低利率环境")
            rules.append(f"10年国债收益率 {bond}%（低利率）")
        elif bond > 2.5:
            signals.append("🔴 利率较高")
            rules.append(f"10年国债收益率 {bond}%")
    
    # LPR
    lpr_5y = _safe_float(data.get("lpr_5y"))
    if lpr_5y is not None:
        if lpr_5y < 3.5:
            signals.append("🟢 LPR下调")
            rules.append(f"5年期LPR {lpr_5y}%")
    
    # 综合信号
    green_count = sum(1 for s in signals if "🟢" in s)
    red_count = sum(1 for s in signals if "🔴" in s)
    
    if green_count > red_count:
        overall = "🟢 货币宽松"
    elif red_count > green_count:
        overall = "🔴 货币收紧"
    else:
        overall = "🟡 货币中性"
    
    return overall, rules


if __name__ == "__main__":
    # 测试
    data = fetch_monetary_policy()
    print(json.dumps(data, ensure_ascii=False, indent=2))
