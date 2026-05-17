"""
全球市场数据源。

已实现指标：
  一、美股市场（美国东部时间 T 日收盘，亚洲交易时段为昨收）
      数据来源：东方财富 push2his K 线接口
      指数：
        DJIA  - 道琼斯工业平均指数（100.DJIA）
        SPX   - 标普 500 指数（100.SPX）
        NDX   - 纳斯达克 100 指数（100.NDX）
      评分参考：
        近 5 日涨跌幅 > +3%  → 美股强势，全球风险偏好高  +1
        近 5 日涨跌幅 -3% ~ +3% → 震荡             0
        近 5 日涨跌幅 < -3%  → 美股弱势，风险偏好回落  -1
        叠加：标普 500 与 200 日均线关系（上方 +0.5，下方 -0.5）

  二、大宗商品（连续合约最新收盘价）
      数据来源：东方财富 push2his K 线接口
        GOLD  - COMEX 黄金期货当月连续（101.GC00Y）  USD/盎司
        WTI   - NYMEX 原油期货当月连续（102.CL00Y）   USD/桶
        BRENT - 布伦特原油期货当月连续（112.B00Y）    USD/桶
      评分参考（评分不纳入综合分，仅辅助展示）：
        金价上涨 → 避险情绪升温；原油上涨 → 输入性通胀压力

  三、外汇市场
      数据来源：东方财富 push2his K 线接口
        DXY    - 美元指数（100.UDI）
        USDCNY - 美元 / 人民币中间价（120.USDCNYC）
      评分参考：
        美元指数近 5 日上涨（强势）→ 新兴市场资金外流压力  -0.5（附加惩罚）
        美元指数近 5 日下跌（弱势）→ 人民币升值，外资流入  +0.5（附加加分）

  四、亚太市场
      数据来源：东方财富 push2his K 线接口
        HSI   - 恒生指数（100.HSI）
        N225  - 日经 225 指数（100.N225）
      评分参考：
        港股恒生 / 日经近 5 日均上涨 → 亚太市场风险偏好正面  +0.5（附加）
        港股恒生 / 日经近 5 日均下跌 → 外围市场拖累          -0.5（附加）

  注：VIX 恐慌指数东方财富接口无公开数据，暂用美股近 5 日涨跌幅代替
      衡量市场情绪，后续可接入 Yahoo Finance（^VIX）。

接口设计原则：
  - 失败时返回 {"error": str}，不抛异常
  - 单项接口失败不影响其他项，对应字段置 None
  - 全部失败时整体返回 {"error": str}
"""

import json
import os
import ssl
import time
import urllib.request
from datetime import date, datetime
from typing import Optional

# ── SSL / 公共请求配置 ───────────────────────────────────────────────────────
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

_EM_HEADERS = {
    "Accept":          "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer":         "https://data.eastmoney.com/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}

# ── 证券 secid 配置表 ─────────────────────────────────────────────────────────
# 格式：代码 -> (secid, 中文名称)
_SECID = {
    # 美股指数
    "DJIA":    ("100.DJIA",    "道琼斯"),
    "SPX":     ("100.SPX",     "标普500"),
    "NDX":     ("100.NDX",     "纳斯达克100"),
    # 大宗商品（连续合约）
    "GOLD":    ("101.GC00Y",   "COMEX黄金"),
    "WTI":     ("102.CL00Y",   "NYMEX原油"),
    "BRENT":   ("112.B00Y",    "布伦特原油"),
    # 外汇
    "DXY":     ("100.UDI",     "美元指数"),
    "USDCNY":  ("120.USDCNYC", "美元/人民币"),
    # 港股指数
    "HSI":     ("100.HSI",     "恒生指数"),
    "HSTECH":  ("100.HSTECH",  "恒生科技"),
    # 日本
    "N225":    ("100.N225",    "日经225"),
    # 韩国
    "KOSPI":   ("100.KS11",    "韩国综合"),
    "KOSDAQ":  ("100.KQ11",    "韩国创业"),
}

# ── Wind 估值接口 URL ──────────────────────────────────────────────────────────
# 万得全A（除金融石油石化）881003.WI
_WIND_VAL_URL = "https://index_api.wind.com.cn/indexofficialwebsite/indexValuation"
_WIND_VAL_HEADERS = {
    "accept": "application/json",
    "accept-language": "zh-CN,zh;q=0.9",
    "cache-control": "max-age=0",
    "content-type": "application/x-www-form-urlencoded",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}

# ── Wind 指数 ID（私有 indexid，非 secid）────────────────────────────────────
_WIND_INDEX_IDS = {
    "MAGS":   "705e7aea0338979a",   # 万得美国科技七巨头 MAGS.WI（发布日期 2024-10-14，仅供参考）
    "TECHK":  "f4e72fbcc5f973d2",   # 万得港股中国科技龙头 TECHK.WI
    # 万得全A（除金融石油石化）
    # 代码：881003.WI，indexid：QNhAnjFWhloETMqHcp1KMQ==
    # API接口：https://index_api.wind.com.cn/indexofficialwebsite/indexValuation
    "WA_EX_FIN_OIL": "QNhAnjFWhloETMqHcp1KMQ==",
}

# ── Wind 估值历史 CSV 路径 ────────────────────────────────────────────────────
_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_WIND_CSV = {
    "MAGS":  os.path.join(_DATA_DIR, "wind_mags_pe_history.csv"),
    "TECHK": os.path.join(_DATA_DIR, "wind_techk_pe_history.csv"),
    # 万得全A（已有）
    "WA":    os.path.join(_DATA_DIR, "wind_a_pe_history.csv"),
}


def _fetch_kline(
    secid: str,
    n: int = 15,
    timeout: int = 8,
) -> list:
    """
    通过 push2his K 线接口获取最近 n 根日 K 线数据。

    实现策略：不依赖 smplmt 采样，而是设 beg=近 60 自然日，
    取全量 K 线后在本地截取最后 n 根，确保连续性与精确性。

    Returns:
        列表，每项为 (date_str, close_price: float)，按日期升序。
        失败返回空列表。

    K 线字段：f51=日期, f52=开, f53=收, f54=高, f55=低, f56=成交量,
              f57=成交额, f58=振幅, f59=涨跌幅, f60=涨跌额, f61=换手率
    """
    from datetime import timedelta
    today_str = date.today().strftime("%Y%m%d")
    # 按需要根数动态计算 beg：n 根交易日 × 2（节假日系数）+ 20 天余量，最少 60 天
    days_back = max(n * 2 + 20, 60)
    beg_str = (date.today() - timedelta(days=days_back)).strftime("%Y%m%d")
    url = (
        "https://push2his.eastmoney.com/api/qt/stock/kline/get"
        f"?secid={secid}"
        "&fields1=f1,f2,f3,f4,f5,f6"
        "&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
        "&klt=101&fqt=1"
        f"&beg={beg_str}&end={today_str}"
        "&smplmt=500&lmt=500"
    )
    req = urllib.request.Request(url, headers=_EM_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        klines = (data.get("data") or {}).get("klines") or []
        result = []
        for kl in klines:
            parts = kl.split(",")
            if len(parts) >= 3:
                try:
                    result.append((parts[0], float(parts[2])))
                except (ValueError, IndexError):
                    pass
        # 本地截取最后 n 根
        return result[-n:] if len(result) >= n else result
    except Exception:
        return []

def _eastmoney_secid_to_westlock(secid: str) -> Optional[str]:
    """
    将 Eastmoney secid 转换为 westock-data 代码。
    例：100.HSI → hkHSI，100.N225 → jpN225
    """
    if not secid or "." not in secid:
        return None
    market_code, symbol = secid.split(".", 1)
    market_map = {
        "100": "hk",    # 港股
        "101": "jp",    # 日本
        "102": "kr",    # 韩国（可能不支持）
        "103": "us",    # 美股
    }
    market = market_map.get(market_code)
    if market:
        return f"{market}{symbol}"
    return None


def _fetch_kline_westlock(code: str, n: int = 15, timeout: int = 15) -> list:
    """
    通过 westock-data-skill-hub CLI 获取最近 n 根日 K 线。
    Fallback 方案，用于 Eastmoney API 无数据的情况。

    Returns:
        列表，每项为 (date_str, close_price: float)，按日期升序。
        失败返回空列表。
    """
    import subprocess, os
    # 尝试定位 npx
    npx_path = os.popen("which npx 2>/dev/null || echo /usr/bin/npx").read().strip()
    if not npx_path or not os.path.exists(npx_path):
        npx_path = "/Users/liuyi/.nvm/versions/node/v24.14.0/bin/npx"
    try:
        cmd = [npx_path, "--yes", "westock-data-skillhub@latest", "kline", code, "day", str(n)]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            return []
        lines = result.stdout.strip().split("\n")
        data = []
        # 跳过表头和分隔线（前2行）
        for line in lines[2:]:
            if not line.strip() or not line.startswith("|"):
                continue
            parts = [p.strip() for p in line.split("|")]
            # 格式：| date | open | last | high | low | volume | amount | exchange |
            if len(parts) >= 4:
                date_str = parts[1].strip()
                try:
                    close = float(parts[3].strip())
                    data.append((date_str, close))
                except (ValueError, IndexError):
                    pass
        # westock-data 返回降序（最新在前），需反转为升序（最老在前）
        # 与 _fetch_kline() 行为保持一致
        data.reverse()
        return data[-n:] if len(data) >= n else data
    except Exception:
        return []


def _fetch_kline_with_fallback(secid: str, n: int = 15, timeout: int = 8) -> list:
    """
    获取 K 线数据，优先使用 Eastmoney API，失败时 fallback 到 westock-data-skill-hub。
    """
    # 优先尝试 Eastmoney API
    klines = _fetch_kline(secid, n=n, timeout=timeout)
    if klines:
        return klines
    # Fallback 到 westock-data
    wd_code = _eastmoney_secid_to_westlock(secid)
    if wd_code:
        return _fetch_kline_westlock(wd_code, n=n, timeout=timeout)
    return []


def _safe_float(v) -> Optional[float]:
    try:
        return float(v) if v is not None else None
    except (ValueError, TypeError):
        return None


def _calc_percentile(values: list, current: float) -> Optional[float]:
    """计算 current 在 values 历史序列中的百分位（%，0-100）。"""
    if not values or current is None:
        return None
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    pct = sum(1 for v in vals if v <= current) / len(vals) * 100
    return round(pct, 1)


def _chg_pct(klines: list, n: int = 5) -> Optional[float]:
    """
    计算最近 n 根 K 线相对于 n+1 根前收盘的涨跌幅（%）。
    klines: [(date_str, close), ...]，升序排列。
    """
    if len(klines) < 2:
        return None
    # 取最后 n+1 根，base=第1根收盘，now=最后1根收盘
    tail = klines[-(n + 1):]
    base = tail[0][1]
    now  = tail[-1][1]
    if base <= 0:
        return None
    return round((now / base - 1) * 100, 2)


def _latest_close(klines: list) -> Optional[float]:
    """返回最新收盘价。"""
    if not klines:
        return None
    return klines[-1][1]


def _latest_date(klines: list) -> Optional[str]:
    if not klines:
        return None
    return klines[-1][0]



# ─────────────────────────────────────────────────────────────────────────────
# Wind 估值通用工具
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_wind_valuation_raw(indexid: str, timeout: int = 15) -> list:
    """
    通用：调用 Wind indexValuation 接口，返回原始 Result 列表。
    每项含 tradeDate(ms), peValue, pbValue, close 等字段。
    失败抛出异常。
    """
    url = f"{_WIND_VAL_URL}?indexid={indexid}&limit=false&lan=cn"
    req = urllib.request.Request(url, headers=_WIND_VAL_HEADERS, method="GET")
    with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:
        raw = resp.read().decode("utf-8")
    data = json.loads(raw)
    result_list = data.get("Result", [])
    if not result_list:
        raise RuntimeError(f"Wind API 返回空数据 (indexid={indexid})")
    return result_list


def _wind_parse_valuation(result_list: list) -> dict:
    """
    解析 Wind Result 列表，计算 PE/PB 最新值及历史百分位。
    返回 {"date": str, "pe": float, "pe_pct": float, "pb": float, "pb_pct": float}
    """
    pe_vals = [item.get("peValue") for item in result_list]
    pb_vals = [item.get("pbValue") for item in result_list]
    latest  = result_list[-1]
    dt      = datetime.fromtimestamp(latest["tradeDate"] / 1000).strftime("%Y-%m-%d")
    pe      = latest.get("peValue")
    pb      = latest.get("pbValue")
    pe_pct  = _calc_percentile(pe_vals, pe)
    pb_pct  = _calc_percentile(pb_vals, pb)
    return {
        "date":    dt,
        "pe":      round(pe, 2) if pe else None,
        "pe_pct":  pe_pct,
        "pb":      round(pb, 2) if pb else None,
        "pb_pct":  pb_pct,
    }


def _wind_save_csv(result_list: list, csv_path: str) -> None:
    """
    将 Wind Result 完整历史 PE/PB 数据保存/覆写到 CSV 文件。
    格式：date,pe,pb,close
    """
    import csv
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "pe", "pb", "close"])
        for item in result_list:
            if "tradeDate" not in item:
                continue
            dt  = datetime.fromtimestamp(item["tradeDate"] / 1000).strftime("%Y-%m-%d")
            pe  = item.get("peValue", "")
            pb  = item.get("pbValue", "")
            cls = item.get("close", "")
            writer.writerow([dt, pe, pb, cls])


# ─────────────────────────────────────────────────────────────────────────────
# 美国科技七巨头估值（MAGS.WI）
# ─────────────────────────────────────────────────────────────────────────────

def fetch_mags_valuation(timeout: int = 15) -> dict:
    """
    获取万得美国科技七巨头指数（MAGS.WI）估值。

    注：该指数于 2024-10-14 发布，历史 PE 数据为回算，仅供参考。
    历史数据保存到 CSV：data/wind_mags_pe_history.csv

    Returns:
        {
            "date":    str,
            "pe":      float,
            "pe_pct":  float,   # 历史百分位（%）
            "pb":      float,
            "pb_pct":  float,
            "source":  "wind",
            "note":    str,     # 发布日期说明
        }
        失败时：{"error": str}
    """
    try:
        indexid = _WIND_INDEX_IDS["MAGS"]
        result_list = _fetch_wind_valuation_raw(indexid, timeout=timeout)

        print(f"[接口URL] {_WIND_VAL_URL}?indexid={indexid}&limit=false&lan=cn")
        print(f"[原始数据] 条数={len(result_list)}, 最新={json.dumps(result_list[-1], ensure_ascii=False)}")

        parsed = _wind_parse_valuation(result_list)

        print(f"[计算步骤] MAGS PE={parsed['pe']}, 百分位={parsed['pe_pct']}% (共{len(result_list)}条历史)")
        print(f"[最终结果] date={parsed['date']}, PE={parsed['pe']}, pe_pct={parsed['pe_pct']}%")

        # 保存 CSV
        _wind_save_csv(result_list, _WIND_CSV["MAGS"])
        print(f"[计算步骤] 已保存到 CSV: {_WIND_CSV['MAGS']}")

        return {**parsed, "source": "wind", "note": "发布日期2024-10-14，历史PE为回算，仅供参考"}

    except Exception as e:
        return {"error": f"MAGS七巨头估值获取失败：{e}"}


# ─────────────────────────────────────────────────────────────────────────────
# 港股中国科技龙头估值（TECHK.WI）
# ─────────────────────────────────────────────────────────────────────────────

def fetch_techk_valuation(timeout: int = 15) -> dict:
    """
    获取万得港股中国科技龙头指数（TECHK.WI）估值。

    历史数据保存到 CSV：data/wind_techk_pe_history.csv

    Returns:
        {
            "date":    str,
            "pe":      float,
            "pe_pct":  float,
            "pb":      float,
            "pb_pct":  float,
            "source":  "wind",
        }
        失败时：{"error": str}
    """
    try:
        indexid = _WIND_INDEX_IDS["TECHK"]
        result_list = _fetch_wind_valuation_raw(indexid, timeout=timeout)

        print(f"[接口URL] {_WIND_VAL_URL}?indexid={indexid}&limit=false&lan=cn")
        print(f"[原始数据] 条数={len(result_list)}, 最新={json.dumps(result_list[-1], ensure_ascii=False)}")

        parsed = _wind_parse_valuation(result_list)

        print(f"[计算步骤] TECHK PE={parsed['pe']}, 百分位={parsed['pe_pct']}% (共{len(result_list)}条历史)")
        print(f"[最终结果] date={parsed['date']}, PE={parsed['pe']}, pe_pct={parsed['pe_pct']}%")

        # 保存 CSV
        _wind_save_csv(result_list, _WIND_CSV["TECHK"])
        print(f"[计算步骤] 已保存到 CSV: {_WIND_CSV['TECHK']}")

        return {**parsed, "source": "wind"}

    except Exception as e:
        return {"error": f"TECHK港股科技龙头估值获取失败：{e}"}


# ─────────────────────────────────────────────────────────────────────────────
# 一、美股市场（道指 / 标普500 / 纳斯达克100）
# ─────────────────────────────────────────────────────────────────────────────


def fetch_us_market(timeout: int = 15) -> dict:
    """
    获取美股三大指数最新行情及近 5 日涨跌幅。

    Returns:
        {
            "date":   str,    # 最新数据日期（YYYY-MM-DD）
            "DJIA":   {"price": float, "chg5d_pct": float},
            "SPX":    {"price": float, "chg5d_pct": float},
            "NDX":    {"price": float, "chg5d_pct": float},
            "spx_above_ma200": bool | None,   # 标普500 是否在200日均线上方（简化：近200根K线均值）
            "source": str,
        }
        失败时：{"error": str}
    """
    result: dict = {
        "date":   None,
        "DJIA":   {},
        "SPX":    {},
        "NDX":    {},
        "spx_above_ma200": None,
        "source": "eastmoney",
    }
    any_ok = False

    for sym in ("DJIA", "SPX", "NDX"):
        secid, _ = _SECID[sym]
        # 取 220 根：SPX 需要200根做 MA200 均线，其余15根足够做5日涨跌
        n_fetch = 220 if sym == "SPX" else 15
        klines = _fetch_kline(secid, n=n_fetch, timeout=timeout)
        if klines:
            any_ok = True
            price   = _latest_close(klines)
            chg5d   = _chg_pct(klines, n=5)
            dt      = _latest_date(klines)
            result[sym] = {"price": price, "chg5d_pct": chg5d}
            if result["date"] is None:
                result["date"] = dt
            # 计算标普 200 日均线
            if sym == "SPX" and len(klines) >= 200:
                closes = [c for _, c in klines[-200:]]
                ma200  = sum(closes) / len(closes)
                result["spx_above_ma200"] = price > ma200 if price else None
        else:
            result[sym] = {"price": None, "chg5d_pct": None}

    if not any_ok:
        return {"error": "美股行情接口全部失败（DJIA/SPX/NDX）"}
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 二、大宗商品（黄金 / WTI / 布伦特）
# ─────────────────────────────────────────────────────────────────────────────

def fetch_commodities(timeout: int = 15) -> dict:
    """
    获取黄金、原油（WTI / 布伦特）最新价格及近 5 日涨跌幅。

    Returns:
        {
            "date":   str,
            "GOLD":   {"price": float, "unit": "USD/oz",  "chg5d_pct": float},
            "WTI":    {"price": float, "unit": "USD/bbl", "chg5d_pct": float},
            "BRENT":  {"price": float, "unit": "USD/bbl", "chg5d_pct": float},
            "source": str,
        }
        失败时：{"error": str}
    """
    UNITS = {"GOLD": "USD/oz", "WTI": "USD/bbl", "BRENT": "USD/bbl"}
    result: dict = {"date": None, "source": "eastmoney"}
    any_ok = False

    for sym in ("GOLD", "WTI", "BRENT"):
        secid, _ = _SECID[sym]
        klines = _fetch_kline(secid, n=15, timeout=timeout)
        if klines:
            any_ok = True
            price  = _latest_close(klines)
            chg5d  = _chg_pct(klines, n=5)
            dt     = _latest_date(klines)
            result[sym] = {"price": price, "unit": UNITS[sym], "chg5d_pct": chg5d}
            if result["date"] is None:
                result["date"] = dt
        else:
            result[sym] = {"price": None, "unit": UNITS[sym], "chg5d_pct": None}

    if not any_ok:
        return {"error": "大宗商品行情接口全部失败（GOLD/WTI/BRENT）"}
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 三、外汇市场（美元指数 / 美元兑人民币）
# ─────────────────────────────────────────────────────────────────────────────

def fetch_forex(timeout: int = 15) -> dict:
    """
    获取美元指数（DXY）及美元兑人民币中间价最新数据及近 5 日涨跌幅。

    Returns:
        {
            "date":    str,
            "DXY":     {"price": float, "chg5d_pct": float},
            "USDCNY":  {"price": float, "chg5d_pct": float},
            "source":  str,
        }
        失败时：{"error": str}
    """
    result: dict = {"date": None, "source": "eastmoney"}
    any_ok = False

    for sym in ("DXY", "USDCNY"):
        secid, _ = _SECID[sym]
        klines = _fetch_kline(secid, n=15, timeout=timeout)
        if klines:
            any_ok = True
            price  = _latest_close(klines)
            chg5d  = _chg_pct(klines, n=5)
            dt     = _latest_date(klines)
            result[sym] = {"price": price, "chg5d_pct": chg5d}
            if result["date"] is None:
                result["date"] = dt
        else:
            result[sym] = {"price": None, "chg5d_pct": None}

    if not any_ok:
        return {"error": "外汇行情接口全部失败（DXY/USDCNY）"}
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 四、亚太市场（港股 / 日本 / 韩国）
# ─────────────────────────────────────────────────────────────────────────────

def fetch_asia_market(timeout: int = 15) -> dict:
    """
    获取亚太主要股市最新行情及近 5 日涨跌幅。

    Returns:
        {
            "date":    str,
            "HSI":     {"price": float, "chg5d_pct": float},   # 恒生指数
            "HSTECH":  {"price": float, "chg5d_pct": float},   # 恒生科技
            "N225":    {"price": float, "chg5d_pct": float},   # 日经225
            "KOSPI":   {"price": float, "chg5d_pct": float},   # 韩国综合
            "KOSDAQ":  {"price": float, "chg5d_pct": float},   # 韩国创业
            "source":  str,
        }
        失败时：{"error": str}
    """
    result: dict = {"date": None, "source": "eastmoney+westock"}
    any_ok = False

    for sym in ("HSI", "HSTECH", "N225", "KOSPI", "KOSDAQ"):
        secid, _ = _SECID[sym]
        klines = _fetch_kline_with_fallback(secid, n=15, timeout=timeout)
        if klines:
            any_ok = True
            price  = _latest_close(klines)
            chg5d  = _chg_pct(klines, n=5)
            dt     = _latest_date(klines)
            result[sym] = {"price": price, "chg5d_pct": chg5d}
            if result["date"] is None:
                result["date"] = dt
        else:
            result[sym] = {"price": None, "chg5d_pct": None}

    if not any_ok:
        return {"error": "亚太市场行情接口全部失败（HSI/HSTECH/N225/KOSPI/KOSDAQ）"}
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 万得全A（除金融石油石化）估值（881003.WI）
# ⚠️ 已废弃：万得全A PE百分位数据改用 wind_a_ex_fin_oil_pe.csv（手动维护）
# ⚠️ fetch_wa_valuation() 不再被主流程调用
# ─────────────────────────────────────────────────────────────────────────────

def fetch_wa_valuation(timeout: int = 15) -> dict:
    """
    ⚠️ 已废弃，请使用 valuation.py 中的 fetch_market_valuation()
    
    获取万得全A（除金融石油石化）估值数据。

    流程：
    1. 调用 Wind API 获取最新估值数据
    2. 追加到 wind_a_pe_history.csv（仅追加新日期）
    3. 返回最新估值数据（不含百分位，百分位需手动维护）

    Returns:
        {
            "date":        str,      # 交易日期
            "pe":          float,   # 市盈率
            "pb":          float,   # 市净率
            "div_yield":   float,   # 股息率
            "close":       float,   # 收盘点位
            "source":      str,     # 数据来源
            "is_new":      bool,    # 是否为新数据（追加到CSV）
        }
        失败时：{"error": str}
    """
    try:
        indexid = _WIND_INDEX_IDS["WA_EX_FIN_OIL"]
        result_list = _fetch_wind_valuation_raw(indexid, timeout=timeout)

        print(f"[接口URL] {_WIND_VAL_URL}?indexid={indexid}&limit=false&lan=cn")
        print(f"[原始数据] 条数={len(result_list)}, 最新={json.dumps(result_list[-1], ensure_ascii=False)}")

        # 获取最新数据
        latest = result_list[-1]
        dt = datetime.fromtimestamp(latest["tradeDate"] / 1000).strftime("%Y-%m-%d")
        pe = latest.get("peValue")
        pb = latest.get("pbValue")
        div_yield = latest.get("didValue")  # Wind API 的股息率字段（股息率 = didValue）
        close = latest.get("close")

        print(f"[获取数据] 万得全A date={dt}, PE={pe}, PB={pb}, 股息率={div_yield}, close={close}")

        # 检查是否需要追加到 CSV
        is_new = _append_wa_to_csv(result_list)

        return {
            "date":      dt,
            "pe":        round(pe, 2) if pe else None,
            "pb":        round(pb, 2) if pb else None,
            "div_yield": round(div_yield, 4) if div_yield else None,
            "close":     round(close, 4) if close else None,
            "source":    "wind",
            "is_new":    is_new,
        }

    except Exception as e:
        return {"error": f"万得全A估值获取失败：{e}"}


def _append_wa_to_csv(result_list: list) -> bool:
    """
    将 Wind API 返回的数据追加到 wind_a_pe_history.csv。

    仅追加 CSV 中不存在的日期数据，保留现有的 pe_pct 和 last_updated 字段。
    对于旧格式的数据（缺少 pe_pct 和 last_updated 列），自动补空值。

    Returns:
        True  - 有新数据追加
        False - 无新数据或追加失败
    """
    import csv
    csv_path = _WIND_CSV["WA"]
    fieldnames = ["trade_date", "pe", "pb", "div_yield", "close", "pe_pct", "last_updated"]

    # 读取现有数据，构建日期集合
    existing_dates = set()
    existing_rows = []  # 保留现有行（含 pe_pct 和 last_updated）

    if os.path.exists(csv_path):
        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    existing_dates.add(row["trade_date"])
                    # 确保所有字段都存在
                    for field in fieldnames:
                        row.setdefault(field, "")
                    existing_rows.append(row)
        except Exception as e:
            print(f"[警告] 读取 CSV 失败: {e}")
            existing_rows = []

    # 构建 API 数据的日期集合
    api_dates = set()
    api_data_map = {}
    for item in result_list:
        if "tradeDate" not in item:
            continue
        dt = datetime.fromtimestamp(item["tradeDate"] / 1000).strftime("%Y-%m-%d")
        pe = item.get("peValue", "")
        pb = item.get("pbValue", "")
        div = item.get("didValue", "")  # Wind API 的股息率字段
        close = item.get("close", "")
        api_dates.add(dt)
        api_data_map[dt] = {"pe": pe, "pb": pb, "div_yield": div, "close": close}

    # 找出需要新增的日期
    new_dates = api_dates - existing_dates
    if not new_dates:
        print(f"[CSV] 无新数据需追加（最新: {max(api_dates) if api_dates else 'N/A'}）")
        return False

    # 生成新行
    new_rows = []
    for dt in sorted(new_dates):
        data = api_data_map[dt]
        new_rows.append({
            "trade_date":  dt,
            "pe":         data["pe"],
            "pb":         data["pb"],
            "div_yield":  data["div_yield"],
            "close":      data["close"],
            "pe_pct":     "",  # 新数据需手动维护
            "last_updated": "",  # 新数据需手动维护
        })

    # 写入 CSV（保留现有数据 + 新增数据）
    try:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(existing_rows)
            writer.writerows(new_rows)

        print(f"[CSV] 已追加 {len(new_rows)} 条新数据到 {csv_path}（日期: {min(new_dates)} ~ {max(new_dates)}）")
        return True
    except Exception as e:
        print(f"[错误] 写入 CSV 失败: {e}")
        return False
