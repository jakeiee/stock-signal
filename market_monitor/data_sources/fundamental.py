"""
基本面数据源——宏观经济指标。

已实现模块：
  一、经济总量 / 结构（GDP）
      数据来源：东方财富 RPT_ECONOMY_GDP 接口（季度累计口径）
      字段：
        REPORT_DATE            - 报告期截止日（季末日）
        TIME                   - 季度文字描述，如"2025年第1-4季度"
        DOMESTICL_PRODUCT_BASE - GDP 总量（亿元）
        FIRST_PRODUCT_BASE     - 第一产业（亿元）
        SECOND_PRODUCT_BASE    - 第二产业（亿元）
        THIRD_PRODUCT_BASE     - 第三产业（亿元）
        SUM_SAME               - GDP 同比增速（%）
        FIRST_SAME             - 第一产业同比（%）
        SECOND_SAME            - 第二产业同比（%）
        THIRD_SAME             - 第三产业同比（%）

      注意：接口数据为"累计口径"（前N季度之和），非单季度值。
      CSV 缓存：market_monitor/data/gdp.csv，字段见 _GDP_CSV_FIELDS。

  二、人均可支配收入增速
      接口待补充，当前返回占位错误。

  三、宏观供需关系（CPI / PPI / PMI）
      数据来源：东方财富三路接口
        CPI：RPT_ECONOMY_CPI
          REPORT_DATE       - 报告期（月末日）
          TIME              - 月份描述，如"2026年02月份"
          NATIONAL_SAME     - 全国 CPI 同比（%）
          NATIONAL_SEQUENTIAL - 全国 CPI 环比（%）
          NATIONAL_ACCUMULATE - 全国 CPI 累计（%）
        PPI：RPT_ECONOMY_PPI
          REPORT_DATE       - 报告期
          TIME              - 月份描述
          BASE_SAME         - PPI 同比（%）
          BASE_ACCUMULATE   - PPI 累计同比（%）
        PMI：RPT_ECONOMY_PMI
          REPORT_DATE       - 报告期
          TIME              - 月份描述
          MAKE_INDEX        - 制造业 PMI
          MAKE_SAME         - 制造业 PMI 同比变化（pp）
          NMAKE_INDEX       - 非制造业 PMI
          NMAKE_SAME        - 非制造业 PMI 同比变化（pp）

      CSV 缓存：market_monitor/data/supply_demand.csv，字段见 _SD_CSV_FIELDS。

  四、宏观流动性（M2 / 10年国债收益率 / 社融）
      数据来源：
        M2：东方财富 RPT_ECONOMY_CURRENCY_SUPPLY
          REPORT_DATE        - 报告期（月末日）
          TIME               - 月份描述，如"2026年02月份"
          BASIC_CURRENCY     - M2 余额（亿元）
          BASIC_CURRENCY_SAME - M2 同比增速（%）
          CURRENCY           - M1 余额（亿元）
          CURRENCY_SAME      - M1 同比增速（%）
          FREE_CASH          - M0（流通中货币，亿元）
          FREE_CASH_SAME     - M0 同比增速（%）

        10年国债收益率：通过东方财富 push2his K线接口获取最新活跃10年期国债收盘价，
          并结合票面利率、剩余期限计算到期收益率（YTM）。
          默认使用 sh019753（24国债17，票面利率2.1%，到期2034-11-18）。

        社融：东方财富接口未公开（code=9501），暂时从 M2 接口中提取并标注为待补充。
          待后续找到人民银行官网可用接口后接入社融存量同比增速。

      CSV 缓存：market_monitor/data/liquidity.csv，字段见 _LIQ_CSV_FIELDS。

接口设计原则：
  - 失败时返回 {"error": str}，不抛异常
  - 网络失败自动降级读 CSV 缓存
  - 接口成功后回写 CSV 缓存
  - 所有数值单位在字段名或注释中标注
"""

import csv
import json
import os
import re
import ssl
import time
import urllib.request
from typing import Optional

# ── SSL / 公共 HTTP 配置（同 capital.py） ──────────────────────────────────
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

_EM_BASE_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"

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

# ── CSV 缓存路径 ──────────────────────────────────────────────────────────
_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

_GDP_CSV_PATH = os.path.join(_DATA_DIR, "gdp.csv")
_GDP_CSV_FIELDS = [
    "period", "time_str",
    "gdp_yoy", "p1_yoy", "p2_yoy", "p3_yoy",
    "p1_pct", "p2_pct", "p3_pct",
    "p3_pct_yoy_delta",
    "source",
]

_SD_CSV_PATH = os.path.join(_DATA_DIR, "supply_demand.csv")
_SD_CSV_FIELDS = [
    "period",
    "cpi_yoy", "cpi_mom", "cpi_accum",
    "ppi_yoy", "ppi_accum",
    "ppi_cpi_spread",
    "pmi_mfg", "pmi_svc",
    "source",
]

_LIQ_CSV_PATH = os.path.join(_DATA_DIR, "liquidity.csv")
_LIQ_CSV_FIELDS = [
    "period",
    "m2_yoy",           # M2 同比增速（%）
    "m2_bal",           # M2 余额（亿元）
    "m1_yoy",           # M1 同比增速（%）
    "bond_10y",         # 10年国债到期收益率YTM（%）
    "bond_10y_code",    # 使用的国债代码
    "bond_10y_price",   # 国债收盘价（元/百元面值）
    "social_fin_yoy",   # 社融存量同比（%）
    "source",
]

# 居民人均可支配收入 CSV 缓存
_DI_CSV_PATH = os.path.join(_DATA_DIR, "disposable_income.csv")
_DI_CSV_FIELDS = [
    "period",
    "income_yoy",       # 人均可支配收入同比增速（%）
    "real_yoy",         # 扣除价格因素后实际增速（%）
    "source",
]

# 社融 CSV 缓存
_SF_CSV_PATH = os.path.join(_DATA_DIR, "social_finance.csv")
_SF_CSV_FIELDS = [
    "period",
    "sf_yoy",           # 社融存量同比增速（%）
    "sf_bal",           # 社融存量（亿元）
    "source",
]

# 国家统计局接口配置
_STATS_BASE_URL = "https://data.stats.gov.cn/easyquery.htm"

_STATS_HEADERS = {
    "Accept":          "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    "Referer":         "https://data.stats.gov.cn/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "X-Requested-With": "XMLHttpRequest",
}


def _stats_fetch_json(url: str, timeout: int = 15) -> dict:
    """从国家统计局API获取JSON数据。"""
    req = urllib.request.Request(url, headers=_STATS_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _ensure_data_dir() -> None:
    os.makedirs(_DATA_DIR, exist_ok=True)


def _em_fetch_json(url: str, timeout: int = 15) -> dict:
    req = urllib.request.Request(url, headers=_EM_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:
        raw = resp.read().decode("utf-8")
    m = re.search(r"(?:datatable\w+|jQuery\w+)\((.+)\)\s*;?\s*$", raw, re.DOTALL)
    return json.loads(m.group(1) if m else raw)


def _em_extract_rows(data: dict) -> list:
    result = data.get("result") or {}
    if isinstance(result, dict):
        return result.get("data") or []
    return []


def _safe_float(value) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


# ─────────────────────────────────────────────────────────────────────────────
# GDP CSV 缓存读写
# ─────────────────────────────────────────────────────────────────────────────

def _read_gdp_csv() -> dict:
    """读取 GDP CSV 缓存，返回 {period: row_dict}。"""
    if not os.path.isfile(_GDP_CSV_PATH):
        return {}
    result = {}
    with open(_GDP_CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            p = row.get("period", "").strip()
            if not p:
                continue
            result[p] = {
                "period":           p,
                "time_str":         row.get("time_str", ""),
                "gdp_yoy":          _safe_float(row.get("gdp_yoy")),
                "p1_yoy":           _safe_float(row.get("p1_yoy")),
                "p2_yoy":           _safe_float(row.get("p2_yoy")),
                "p3_yoy":           _safe_float(row.get("p3_yoy")),
                "p1_pct":           _safe_float(row.get("p1_pct")),
                "p2_pct":           _safe_float(row.get("p2_pct")),
                "p3_pct":           _safe_float(row.get("p3_pct")),
                "p3_pct_yoy_delta": _safe_float(row.get("p3_pct_yoy_delta")),
                "source":           row.get("source", ""),
            }
    return result


def _write_gdp_csv(records: dict) -> None:
    """将 {period: row_dict} 写入 GDP CSV，按 period 升序。"""
    _ensure_data_dir()
    with open(_GDP_CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_GDP_CSV_FIELDS)
        writer.writeheader()
        for p in sorted(records.keys()):
            row = records[p]
            writer.writerow({
                k: ("" if row.get(k) is None else row[k])
                for k in _GDP_CSV_FIELDS
            })


# ─────────────────────────────────────────────────────────────────────────────
# 供需关系 CSV 缓存读写
# ─────────────────────────────────────────────────────────────────────────────

def _read_sd_csv() -> dict:
    """读取宏观供需关系 CSV 缓存，返回 {period: row_dict}。"""
    if not os.path.isfile(_SD_CSV_PATH):
        return {}
    result = {}
    with open(_SD_CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            p = row.get("period", "").strip()
            if not p:
                continue
            result[p] = {
                "period":         p,
                "cpi_yoy":        _safe_float(row.get("cpi_yoy")),
                "cpi_mom":        _safe_float(row.get("cpi_mom")),
                "cpi_accum":      _safe_float(row.get("cpi_accum")),
                "ppi_yoy":        _safe_float(row.get("ppi_yoy")),
                "ppi_accum":      _safe_float(row.get("ppi_accum")),
                "ppi_cpi_spread": _safe_float(row.get("ppi_cpi_spread")),
                "pmi_mfg":        _safe_float(row.get("pmi_mfg")),
                "pmi_svc":        _safe_float(row.get("pmi_svc")),
                "source":         row.get("source", ""),
            }
    return result


def _write_sd_csv(records: dict) -> None:
    """将 {period: row_dict} 写入供需关系 CSV，按 period 升序。"""
    _ensure_data_dir()
    with open(_SD_CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_SD_CSV_FIELDS)
        writer.writeheader()
        for p in sorted(records.keys()):
            row = records[p]
            writer.writerow({
                k: ("" if row.get(k) is None else row[k])
                for k in _SD_CSV_FIELDS
            })


# ─────────────────────────────────────────────────────────────────────────────
# 一、GDP / 经济结构
# ─────────────────────────────────────────────────────────────────────────────

def _parse_quarter(time_str: str) -> Optional[int]:
    """
    从 TIME 字段文本解析最新季度序号（1–4）。
    "2025年第1季度"      → 1
    "2025年第1-2季度"    → 2
    "2025年第1-3季度"    → 3
    "2025年第1-4季度"    → 4
    """
    m = re.search(r"第1[-–~]?(\d)季度", time_str)
    if m:
        return int(m.group(1))
    m2 = re.search(r"第(\d)季度", time_str)
    if m2:
        return int(m2.group(1))
    return None


def _extract_year(time_str: str) -> Optional[int]:
    m = re.match(r"(\d{4})年", time_str)
    return int(m.group(1)) if m else None


def fetch_gdp(timeout: int = 20) -> dict:
    """
    获取 A 股 GDP 季度增速及三产结构数据。

    数据获取策略：
      1. 东方财富 RPT_ECONOMY_GDP 接口（最新8条，用于单季拆算及同期对比）
      2. 接口失败 → 降级读取 CSV 缓存最新一条
      接口成功后回写 CSV 缓存。

    返回（最新完整季度数据）：
        {
            "period":      str,    # 季度标识，如 "2025Q4"
            "time_str":    str,    # 接口原始文字，如 "2025年第1-4季度"
            "gdp_yoy":     float,  # GDP 同比增速（%），接口直给累计值
            "p1_yoy":      float,  # 第一产业同比（%）
            "p2_yoy":      float,  # 第二产业同比（%）
            "p3_yoy":      float,  # 第三产业同比（%）
            "p1_pct":      float,  # 第一产业占比（%）
            "p2_pct":      float,  # 第二产业占比（%）
            "p3_pct":      float,  # 第三产业占比（%）
            "p3_pct_yoy_delta": float|None,  # 第三产业占比较去年同期变化（pp）
            "source":      str,
        }
        失败时：{"error": str}

    评分参考：
        GDP 同比增速（累计）:
            ≥ 5.5%  → 强劲  +2
            5.0–5.5% → 良好  +1
            4.0–5.0% → 正常   0
            3.0–4.0% → 偏弱  -1
            < 3.0%  → 偏差  -2
        第三产业占比趋势：
            同比提升 ≥ 0.5pp → 消费/服务结构改善 +0.5（附加）
            同比下降 ≥ 0.5pp → 内需偏弱           -0.5（附加）
    """
    try:
        ts  = int(time.time() * 1000)
        url = (
            f"{_EM_BASE_URL}"
            "?columns=REPORT_DATE%2CTIME%2CDOMESTICL_PRODUCT_BASE"
            "%2CFIRST_PRODUCT_BASE%2CSECOND_PRODUCT_BASE%2CTHIRD_PRODUCT_BASE"
            "%2CSUM_SAME%2CFIRST_SAME%2CSECOND_SAME%2CTHIRD_SAME"
            f"&pageNumber=1&pageSize=8"
            "&sortColumns=REPORT_DATE&sortTypes=-1"
            f"&source=WEB&client=WEB&reportName=RPT_ECONOMY_GDP&_={ts}"
        )
        data = _em_fetch_json(url, timeout=timeout)
        rows = _em_extract_rows(data)
        if not rows:
            raise RuntimeError("RPT_ECONOMY_GDP 返回空数据")

        def _f(row, key):
            return _safe_float(row.get(key))

        # 最新一条（降序排列，rows[0] 为最新）
        r0       = rows[0]
        time_str = str(r0.get("TIME", "")).strip()
        quarter  = _parse_quarter(time_str)
        year     = _extract_year(time_str)
        period   = f"{year}Q{quarter}" if year and quarter else time_str

        gdp_yoy = _f(r0, "SUM_SAME")
        p1_yoy  = _f(r0, "FIRST_SAME")
        p2_yoy  = _f(r0, "SECOND_SAME")
        p3_yoy  = _f(r0, "THIRD_SAME")

        gdp_base = _f(r0, "DOMESTICL_PRODUCT_BASE") or 0.0
        p1_base  = _f(r0, "FIRST_PRODUCT_BASE") or 0.0
        p2_base  = _f(r0, "SECOND_PRODUCT_BASE") or 0.0
        p3_base  = _f(r0, "THIRD_PRODUCT_BASE") or 0.0

        p1_pct = round(p1_base / gdp_base * 100, 2) if gdp_base > 0 else None
        p2_pct = round(p2_base / gdp_base * 100, 2) if gdp_base > 0 else None
        p3_pct = round(p3_base / gdp_base * 100, 2) if gdp_base > 0 else None

        # 查找上年同期（相同季度）
        p3_pct_yoy_delta = None
        if quarter and year:
            for r in rows[1:]:
                t2 = str(r.get("TIME", "")).strip()
                y2 = _extract_year(t2)
                q2 = _parse_quarter(t2)
                if y2 == year - 1 and q2 == quarter:
                    gdp_base2 = _f(r, "DOMESTICL_PRODUCT_BASE") or 0.0
                    p3_base2  = _f(r, "THIRD_PRODUCT_BASE") or 0.0
                    if gdp_base2 > 0 and p3_pct is not None:
                        p3_pct2 = round(p3_base2 / gdp_base2 * 100, 2)
                        p3_pct_yoy_delta = round(p3_pct - p3_pct2, 2)
                    break

        result = {
            "period":            period,
            "time_str":          time_str,
            "gdp_yoy":           gdp_yoy,
            "p1_yoy":            p1_yoy,
            "p2_yoy":            p2_yoy,
            "p3_yoy":            p3_yoy,
            "p1_pct":            p1_pct,
            "p2_pct":            p2_pct,
            "p3_pct":            p3_pct,
            "p3_pct_yoy_delta":  p3_pct_yoy_delta,
            "source":            "eastmoney",
        }

        # 回写 CSV 缓存（合并，以 period 为 key）
        try:
            cached = _read_gdp_csv()
            cached[period] = result
            _write_gdp_csv(cached)
        except Exception:
            pass  # 缓存写入失败不影响主流程

        return result

    except Exception as e:
        # 降级：读取 CSV 缓存最新一条
        try:
            cached = _read_gdp_csv()
            if cached:
                latest_period = sorted(cached.keys())[-1]
                rec = cached[latest_period].copy()
                rec["source"] = "csv_cache"
                return rec
        except Exception:
            pass
        return {"error": f"GDP 接口获取失败：{e}"}


# ─────────────────────────────────────────────────────────────────────────────
# 二、人均可支配收入增速
# ─────────────────────────────────────────────────────────────────────────────

def fetch_disposable_income(timeout: int = 20) -> dict:
    """
    获取全国居民人均可支配收入增速（季度）。

    接口：国家统计局 api (dbcode=hgjd, rowcode=zb)
    返回数据包含：居民人均可支配收入同比增速

    Returns:
        {
            "period":     str,    # 如 "2025Q4"
            "income_yoy": float,  # 人均可支配收入同比增速（%）
            "real_yoy":   float|None,  # 扣除价格因素后实际增速（%）
            "source":     str,
        }
        失败时：{"error": str}

    评分参考：
        实际增速 ≥ 6%  → 收入强劲增长，消费/可选板块预期改善  +1
        4–6%          → 正常                                    0
        2–4%          → 偏弱，可选消费谨慎                     -1
        < 2%          → 居民收入压力大，消费板块下行风险         -2
    """
    try:
        # 国家统计局接口 - 居民人均可支配收入
        # 正确参数：dbcode=hgjd, rowcode=sj, colcode=zb
        #           dfwds 同时限定 zb=A0501（全国居民人均收入情况）+ sj=LAST10
        # 指标 A050102 = 居民人均可支配收入_累计增长(%)，直接就是图中的同比增速
        ts = int(time.time() * 1000)
        import urllib.parse as _up
        dfwds_val = _up.quote(
            json.dumps([
                {"wdcode": "zb", "valuecode": "A0501"},
                {"wdcode": "sj", "valuecode": "LAST10"},
            ])
        )
        url = (
            f"{_STATS_BASE_URL}"
            f"?m=QueryData&dbcode=hgjd&rowcode=sj&colcode=zb"
            f"&wds=%5B%5D"
            f"&dfwds={dfwds_val}"
            f"&k1={ts}"
        )
        print(f"[接口URL] {url}")
        data = _stats_fetch_json(url, timeout=timeout)

        # 解析返回数据
        returndata = data.get("returndata", {})
        datanodes = returndata.get("datanodes", [])
        print(f"[原始数据] {json.dumps(data, ensure_ascii=False)[:500]}")

        if not datanodes:
            raise RuntimeError("国家统计局接口返回空数据")

        # 查找 A050102（居民人均可支配收入_累计增长%）的最新数据
        # 数据结构：{"code": "zb.A050102_sj.2025D", "data": {"data": 4.9939...}}
        yoy_data = {}  # {"2025D": 4.9939, "2025C": 5.2, ...}
        for node in datanodes:
            code = node.get("code", "")
            if "A050102" in code:
                period_key = code.split(".")[-1]  # 如 "2025D"
                val = node.get("data", {}).get("data")
                hasdata = node.get("data", {}).get("hasdata", False)
                if val and hasdata:
                    yoy_data[period_key] = val

        print(f"[计算步骤] A050102 各期数据: {yoy_data}")

        if not yoy_data:
            raise RuntimeError("未找到居民人均收入同比增速数据(A050102)")

        # 取最新期
        sorted_periods = sorted(yoy_data.keys(), reverse=True)
        latest_period = sorted_periods[0]  # 如 "2025D"
        income_yoy = yoy_data[latest_period]

        # 转换period格式: 2025D -> 2025Q4, 2025C -> 2025Q3, 2025B -> 2025Q2, 2025A -> 2025Q1
        period_map = {"D": "Q4", "C": "Q3", "B": "Q2", "A": "Q1"}
        period_type = latest_period[-1]
        period_year = latest_period[:-1]
        period_label = period_map.get(period_type, "")
        display_period = f"{period_year}{period_label}"

        print(f"[计算步骤] 最新期={latest_period} → period={display_period}, income_yoy={income_yoy}%")
        print(f"[最终结果] period={display_period}, income_yoy={round(income_yoy, 1)}%")

        result = {
            "period":       display_period,
            "income_yoy":   round(income_yoy, 1),
            "real_yoy":     None,
            "source":       "stats.gov.cn",
        }

        # 回写 CSV 缓存
        try:
            cached = _read_di_csv()
            cached[display_period] = result
            _write_di_csv(cached)
        except Exception:
            pass

        return result

    except Exception as e:
        # 降级：读取 CSV 缓存最新一条
        try:
            cached = _read_di_csv()
            if cached:
                latest_period = sorted(cached.keys())[-1]
                rec = cached[latest_period].copy()
                rec["source"] = "csv_cache"
                return rec
        except Exception:
            pass
        return {"error": f"居民人均收入接口获取失败：{e}"}


# ─────────────────────────────────────────────────────────────────────────────
# 二、社融增速（社会融资规模存量同比）
# ─────────────────────────────────────────────────────────────────────────────

def fetch_social_finance(timeout: int = 20) -> dict:
    """
    获取社会融资规模存量同比增速（年度）。

    数据来源：国家统计局 API
      - dbcode: hgnd (年度数据)
      - 指标: A0L0801 = 社会融资规模 (亿元)
    
    Returns:
        {
            "period":   str,    # 如 "2025"
            "sf_yoy":   float,  # 社融存量同比增速（%）
            "sf_bal":   float|None,  # 社融存量（亿元）
            "source":   str,
        }
        失败时：{"error": str}

    评分参考：
        社融同比增速：
            ≥ 12%  → 融资旺盛，经济增长动力强  +1
            8–12%  → 正常偏松                    0
            5–8%   → 偏弱，稳增长压力            -1
            < 5%   → 融资低迷，经济下行风险大    -2
    """
    try:
        # 国家统计局 API - 社会融资规模
        # 指标 A0L0801 = 社会融资规模 (亿元)
        ts = int(time.time() * 1000)
        import urllib.parse as _up
        dfwds_val = _up.quote(json.dumps([
            {"wdcode": "zb", "valuecode": "A0L0801"},
            {"wdcode": "sj", "valuecode": "LAST20"},
        ]))
        url = (
            f"{_STATS_BASE_URL}"
            f"?m=QueryData&dbcode=hgnd&rowcode=zb&colcode=sj"
            f"&wds=%5B%5D"
            f"&dfwds={dfwds_val}"
            f"&k1={ts}"
        )
        print(f"[接口URL] {url}")
        
        req = urllib.request.Request(url, headers=_STATS_HEADERS)
        with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:
            raw = resp.read().decode("utf-8")
        
        data = json.loads(raw)
        print(f"[原始数据] {json.dumps(data, ensure_ascii=False)[:500]}")
        
        returndata = data.get("returndata", {})
        datanodes = returndata.get("datanodes", [])
        
        if not datanodes:
            raise RuntimeError("国家统计局社融接口返回空数据")
        
        # 提取 A0L0801 数据
        sf_data = {}  # {年份: 社融存量(亿元)}
        for node in datanodes:
            code = node.get("code", "")
            val = node.get("data", {}).get("data")
            hasdata = node.get("data", {}).get("hasdata", False)
            
            if "A0L0801" in code and hasdata and val is not None and val > 100000:
                year = code.split(".")[-1]
                sf_data[year] = val
                print(f"[数据节点] {year}年: {val}亿元")
        
        print(f"[计算步骤] 获取到 {len(sf_data)} 年数据: {sorted(sf_data.keys(), reverse=True)[:5]}")
        
        if not sf_data:
            raise RuntimeError("未找到社融数据(A0L0801)")
        
        # 计算同比
        sorted_years = sorted(sf_data.keys(), reverse=True)
        latest_year = sorted_years[0]
        prev_year = str(int(latest_year) - 1)
        
        sf_bal = sf_data[latest_year]
        
        if prev_year in sf_data:
            prev_val = sf_data[prev_year]
            sf_yoy = (sf_bal / prev_val - 1) * 100
            print(f"[计算步骤] {latest_year}年: {sf_bal}亿 vs {prev_year}年: {prev_val}亿 → 同比={sf_yoy:.2f}%")
        else:
            sf_yoy = None
            print(f"[计算步骤] {latest_year}年: {sf_bal}亿 (无去年数据，无法计算同比)")
        
        print(f"[最终结果] period={latest_year}, sf_bal={sf_bal:.0f}亿, sf_yoy={round(sf_yoy, 1) if sf_yoy else 'N/A'}%")
        
        result = {
            "period":   latest_year,
            "sf_yoy":   round(sf_yoy, 1) if sf_yoy else None,
            "sf_bal":   sf_bal,
            "source":   "stats.gov.cn",
        }
        
        # 回写 CSV 缓存
        try:
            cached = _read_sf_csv()
            cached[latest_year] = result
            _write_sf_csv(cached)
        except Exception:
            pass
        
        return result
        
    except Exception as e:
        # 降级：读取 CSV 缓存
        try:
            cached = _read_sf_csv()
            if cached:
                latest_period = sorted(cached.keys())[-1]
                rec = cached[latest_period].copy()
                rec["source"] = "csv_cache"
                print(f"[降级] 使用CSV缓存: {rec}")
                return rec
        except Exception:
            pass
        return {"error": f"社融数据获取失败：{e}"}


# ─────────────────────────────────────────────────────────────────────────────
# 三、宏观供需关系（CPI / PPI / PMI）
# ─────────────────────────────────────────────────────────────────────────────

def _parse_month_period(time_str: str) -> Optional[str]:
    """
    将 TIME 字段文字转换为 "YYYY-MM" 格式 period key。
    "2026年02月份" → "2026-02"
    """
    m = re.match(r"(\d{4})年(\d{1,2})月", time_str)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}"
    return time_str


def fetch_macro_supply_demand(timeout: int = 20) -> dict:
    """
    获取宏观供需关系指标：CPI / PPI / PMI（最新月度数据）。

    数据获取策略：
      1. 同时请求 CPI / PPI / PMI 三个接口，以最新可用月份为准。
      2. 任一接口失败，对应字段置 None，不影响其他字段。
      3. 全部接口失败 → 降级读取 CSV 缓存最新一条。
      接口成功后回写 CSV 缓存。

    返回（最新月度数据）：
        {
            "period":         str,    # 如 "2026-02"
            "cpi_yoy":        float,  # CPI 同比（%），NATIONAL_SAME
            "cpi_mom":        float,  # CPI 环比（%），NATIONAL_SEQUENTIAL
            "cpi_accum":      float,  # CPI 累计同比（%），NATIONAL_ACCUMULATE（基期100换算）
            "ppi_yoy":        float,  # PPI 同比（%），BASE_SAME
            "ppi_accum":      float,  # PPI 累计同比（%），BASE_ACCUMULATE（基期100换算）
            "ppi_cpi_spread": float,  # PPI - CPI 剪刀差（pp）
            "pmi_mfg":        float,  # 制造业 PMI
            "pmi_svc":        float,  # 非制造业 PMI
            "source":         str,
        }
        失败时：{"error": str}

    评分参考（scorer.py 使用）：
        PPI 同比:
            > 0%  → 上游企业盈利改善    +1
            -2~0% → 轻微通缩，偏弱      0
            < -2% → 明显通缩，上游压力  -1
        CPI 同比:
            0–3%  → 温和，消费端健康    +0.5
            > 3%  → 通胀压力            -0.5
            < 0%  → 通缩，需求偏弱      -1
        PPI-CPI 剪刀差:
            > +2pp → 上游盈利优于下游   附加 +0.5
            < -2pp → 下游企业利润承压   附加 -0.5
        制造业 PMI:
            > 50  → 景气扩张            +1
            49–50 → 临界偏弱            0
            < 49  → 明显收缩            -1
    """
    cpi_data: dict = {}
    ppi_data: dict = {}
    pmi_data: dict = {}

    ts = int(time.time() * 1000)

    # ── CPI ──────────────────────────────────────────────────────────────
    try:
        url_cpi = (
            f"{_EM_BASE_URL}"
            "?columns=REPORT_DATE%2CTIME%2CNATIONAL_SAME%2CNATIONAL_BASE"
            "%2CNATIONAL_SEQUENTIAL%2CNATIONAL_ACCUMULATE"
            "&pageNumber=1&pageSize=2"
            "&sortColumns=REPORT_DATE&sortTypes=-1"
            f"&source=WEB&client=WEB&reportName=RPT_ECONOMY_CPI&_={ts}"
        )
        d_cpi  = _em_fetch_json(url_cpi, timeout=timeout)
        rows_c = _em_extract_rows(d_cpi)
        if rows_c:
            r = rows_c[0]
            period_c = _parse_month_period(str(r.get("TIME", "")))
            cpi_yoy  = _safe_float(r.get("NATIONAL_SAME"))
            cpi_mom  = _safe_float(r.get("NATIONAL_SEQUENTIAL"))
            # NATIONAL_ACCUMULATE 字段是以100为基期的指数（如100.8），换算为同比%
            accum_idx = _safe_float(r.get("NATIONAL_ACCUMULATE"))
            cpi_accum = round(accum_idx - 100.0, 2) if accum_idx is not None else None
            cpi_data  = {
                "period":    period_c,
                "cpi_yoy":   cpi_yoy,
                "cpi_mom":   cpi_mom,
                "cpi_accum": cpi_accum,
            }
    except Exception as e:
        cpi_data = {"_err": f"CPI接口失败：{e}"}

    # ── PPI ──────────────────────────────────────────────────────────────
    try:
        url_ppi = (
            f"{_EM_BASE_URL}"
            "?columns=REPORT_DATE%2CTIME%2CBASE%2CBASE_SAME%2CBASE_ACCUMULATE"
            "&pageNumber=1&pageSize=2"
            "&sortColumns=REPORT_DATE&sortTypes=-1"
            f"&source=WEB&client=WEB&reportName=RPT_ECONOMY_PPI&_={ts}"
        )
        d_ppi  = _em_fetch_json(url_ppi, timeout=timeout)
        rows_p = _em_extract_rows(d_ppi)
        if rows_p:
            r = rows_p[0]
            period_p = _parse_month_period(str(r.get("TIME", "")))
            ppi_yoy  = _safe_float(r.get("BASE_SAME"))
            accum_idx2 = _safe_float(r.get("BASE_ACCUMULATE"))
            ppi_accum  = round(accum_idx2 - 100.0, 2) if accum_idx2 is not None else None
            ppi_data   = {
                "period":    period_p,
                "ppi_yoy":   ppi_yoy,
                "ppi_accum": ppi_accum,
            }
    except Exception as e:
        ppi_data = {"_err": f"PPI接口失败：{e}"}

    # ── PMI ──────────────────────────────────────────────────────────────
    try:
        url_pmi = (
            f"{_EM_BASE_URL}"
            "?columns=REPORT_DATE%2CTIME%2CMAKE_INDEX%2CMAKE_SAME%2CNMAKE_INDEX%2CNMAKE_SAME"
            "&pageNumber=1&pageSize=2"
            "&sortColumns=REPORT_DATE&sortTypes=-1"
            f"&source=WEB&client=WEB&reportName=RPT_ECONOMY_PMI&_={ts}"
        )
        d_pmi  = _em_fetch_json(url_pmi, timeout=timeout)
        rows_m = _em_extract_rows(d_pmi)
        if rows_m:
            r = rows_m[0]
            period_m = _parse_month_period(str(r.get("TIME", "")))
            pmi_mfg  = _safe_float(r.get("MAKE_INDEX"))
            pmi_svc  = _safe_float(r.get("NMAKE_INDEX"))
            pmi_data = {
                "period":  period_m,
                "pmi_mfg": pmi_mfg,
                "pmi_svc": pmi_svc,
            }
    except Exception as e:
        pmi_data = {"_err": f"PMI接口失败：{e}"}

    # ── 三接口全部失败 → 降级 CSV 缓存 ───────────────────────────────────
    all_failed = "_err" in cpi_data and "_err" in ppi_data and "_err" in pmi_data
    if all_failed:
        try:
            cached = _read_sd_csv()
            if cached:
                latest_period = sorted(cached.keys())[-1]
                rec = cached[latest_period].copy()
                rec["source"] = "csv_cache"
                return rec
        except Exception:
            pass
        errs = "; ".join(
            v for v in [
                cpi_data.get("_err"), ppi_data.get("_err"), pmi_data.get("_err")
            ] if v
        )
        return {"error": f"宏观供需关系全部接口失败：{errs}"}

    # ── 以 CPI 期为基准 period，PMI/PPI 有独立 period，统一取最新月 ─────
    candidate_periods = [
        d.get("period") for d in [cpi_data, ppi_data, pmi_data]
        if "_err" not in d and d.get("period")
    ]
    period = max(candidate_periods) if candidate_periods else "unknown"

    cpi_yoy   = cpi_data.get("cpi_yoy")
    cpi_mom   = cpi_data.get("cpi_mom")
    cpi_accum = cpi_data.get("cpi_accum")
    ppi_yoy   = ppi_data.get("ppi_yoy")
    ppi_accum = ppi_data.get("ppi_accum")
    pmi_mfg   = pmi_data.get("pmi_mfg")
    pmi_svc   = pmi_data.get("pmi_svc")

    ppi_cpi_spread = (
        round(ppi_yoy - cpi_yoy, 2)
        if ppi_yoy is not None and cpi_yoy is not None
        else None
    )

    result = {
        "period":         period,
        "cpi_yoy":        cpi_yoy,
        "cpi_mom":        cpi_mom,
        "cpi_accum":      cpi_accum,
        "ppi_yoy":        ppi_yoy,
        "ppi_accum":      ppi_accum,
        "ppi_cpi_spread": ppi_cpi_spread,
        "pmi_mfg":        pmi_mfg,
        "pmi_svc":        pmi_svc,
        "source":         "eastmoney",
    }

    # 回写 CSV 缓存（合并，以 period 为 key）
    try:
        cached = _read_sd_csv()
        cached[period] = result
        _write_sd_csv(cached)
    except Exception:
        pass  # 缓存写入失败不影响主流程

    return result


# ─────────────────────────────────────────────────────────────────────────────
# 四、宏观流动性（占位，待实现）
# ─────────────────────────────────────────────────────────────────────────────

def _read_liq_csv() -> dict:
    """读取宏观流动性 CSV 缓存，返回 {period: row_dict}。"""
    if not os.path.isfile(_LIQ_CSV_PATH):
        return {}
    result = {}
    with open(_LIQ_CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            p = row.get("period", "").strip()
            if not p:
                continue
            result[p] = {
                "period":         p,
                "m2_yoy":         _safe_float(row.get("m2_yoy")),
                "m2_bal":         _safe_float(row.get("m2_bal")),
                "m1_yoy":         _safe_float(row.get("m1_yoy")),
                "bond_10y":       _safe_float(row.get("bond_10y")),
                "bond_10y_code":  row.get("bond_10y_code", ""),
                "bond_10y_price": _safe_float(row.get("bond_10y_price")),
                "social_fin_yoy": _safe_float(row.get("social_fin_yoy")),
                "source":         row.get("source", ""),
            }
    return result


def _write_liq_csv(records: dict) -> None:
    """将 {period: row_dict} 写入流动性 CSV，按 period 升序。"""
    _ensure_data_dir()
    with open(_LIQ_CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_LIQ_CSV_FIELDS)
        writer.writeheader()
        for p in sorted(records.keys()):
            row = records[p]
            writer.writerow({
                k: ("" if row.get(k) is None else row[k])
                for k in _LIQ_CSV_FIELDS
            })


# ─────────────────────────────────────────────────────────────────────────────
# 居民人均可支配收入 CSV 缓存读写
# ─────────────────────────────────────────────────────────────────────────────

def _read_di_csv() -> dict:
    """读取居民人均可支配收入 CSV 缓存，返回 {period: row_dict}。"""
    if not os.path.isfile(_DI_CSV_PATH):
        return {}
    result = {}
    with open(_DI_CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            p = row.get("period", "").strip()
            if not p:
                continue
            result[p] = {
                "period":       p,
                "income_yoy":   _safe_float(row.get("income_yoy")),
                "real_yoy":     _safe_float(row.get("real_yoy")),
                "source":       row.get("source", ""),
            }
    return result


def _write_di_csv(records: dict) -> None:
    """将 {period: row_dict} 写入居民人均收入 CSV，按 period 升序。"""
    _ensure_data_dir()
    with open(_DI_CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_DI_CSV_FIELDS)
        writer.writeheader()
        for p in sorted(records.keys()):
            row = records[p]
            writer.writerow({
                k: ("" if row.get(k) is None else row[k])
                for k in _DI_CSV_FIELDS
            })


# ─────────────────────────────────────────────────────────────────────────────
# 社融 CSV 缓存读写
# ─────────────────────────────────────────────────────────────────────────────

def _read_sf_csv() -> dict:
    """读取社融 CSV 缓存，返回 {period: row_dict}。"""
    if not os.path.isfile(_SF_CSV_PATH):
        return {}
    result = {}
    with open(_SF_CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            p = row.get("period", "").strip()
            if not p:
                continue
            result[p] = {
                "period":   p,
                "sf_yoy":   _safe_float(row.get("sf_yoy")),
                "sf_bal":   _safe_float(row.get("sf_bal")),
                "source":   row.get("source", ""),
            }
    return result


def _write_sf_csv(records: dict) -> None:
    """将 {period: row_dict} 写入社融 CSV，按 period 升序。"""
    _ensure_data_dir()
    with open(_SF_CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_SF_CSV_FIELDS)
        writer.writeheader()
        for p in sorted(records.keys()):
            row = records[p]
            writer.writerow({
                k: ("" if row.get(k) is None else row[k])
                for k in _SF_CSV_FIELDS
            })


def _calc_bond_ytm(
    price: float,
    coupon_rate: float,
    maturity_date,
    face: float = 100.0,
    ref_date=None,
) -> Optional[float]:
    """
    通过二分法计算债券到期收益率（YTM，年化，简化年付息模型）。

    Args:
        price:        净价（元/百元面值，如 102.651）
        coupon_rate:  票面利率（%，如 2.1）
        maturity_date:到期日（datetime.date）
        face:         面值（默认100元）
        ref_date:     计算基准日（默认今日）

    Returns:
        YTM（%，保留4位小数），计算失败返回 None。
    """
    import datetime
    if ref_date is None:
        ref_date = datetime.date.today()
    if isinstance(maturity_date, str):
        maturity_date = datetime.date.fromisoformat(maturity_date)

    T = (maturity_date - ref_date).days / 365.0
    if T <= 0:
        return None

    coupon = face * coupon_rate / 100.0
    n = max(1, int(T))

    def _pv(ytm):
        pv = 0.0
        for i in range(1, n + 1):
            pv += coupon / (1 + ytm) ** i
        pv += face / (1 + ytm) ** n
        return pv

    try:
        lo, hi = 0.0001, 0.50
        for _ in range(200):
            mid = (lo + hi) / 2
            if _pv(mid) > price:
                lo = mid
            else:
                hi = mid
        return round(mid * 100, 4)
    except Exception:
        return None


# ── 10年国债信息表（代码：票面利率%，到期日）──
# 随时间滚动更新，program 优先取最新活跃合约
_BOND_10Y_INFO = {
    # 代码     : (票面利率%, 到期日)
    "019753": (2.10, "2034-11-18"),   # 24国债17（当前活跃）
    "019748": (2.10, "2034-09-18"),   # 24国债14
    "019740": (2.25, "2034-08-18"),   # 24国债08
    "019735": (2.33, "2034-06-18"),   # 24国债04
    "019731": (2.53, "2034-04-18"),   # 24国债01
}


def _fetch_bond_10y_price(bond_code: str, timeout: int = 10) -> Optional[float]:
    """
    通过 push2his K线接口获取指定国债代码最新收盘价。
    """
    import datetime
    today_str = datetime.date.today().strftime("%Y%m%d")
    url = (
        "https://push2his.eastmoney.com/api/qt/stock/kline/get"
        f"?secid=1.{bond_code}"
        "&fields1=f1,f2,f3,f4,f5,f6"
        "&fields2=f51,f52,f53,f54,f55,f56"
        "&klt=101&fqt=1"
        "&beg=20260101"
        f"&end={today_str}"
        "&smplmt=10&lmt=10"
    )
    req = urllib.request.Request(url, headers=_EM_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    klines = (data.get("data") or {}).get("klines") or []
    if not klines:
        return None
    # 取最后一条：格式 "日期,开盘,收盘,最高,最低,成交量"
    last = klines[-1].split(",")
    close_price = _safe_float(last[2]) if len(last) >= 3 else None
    return close_price


# ─────────────────────────────────────────────────────────────────────────────
# 中国外汇交易中心 10年国债收益率（SDDS接口）
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_bond_10y_chinamoney(timeout: int = 15) -> Optional[float]:
    """
    从中国外汇交易中心（ChinaMoney）获取10年国债收益率。

    API: https://www.chinamoney.com.cn/r/cms/www/chinamoney/data/currency/sdds-intr-rate.json

    返回:
        10年国债收益率（%），如 1.83；失败返回 None
    """
    try:
        ts = int(time.time() * 1000)
        url = f"https://www.chinamoney.com.cn/r/cms/www/chinamoney/data/currency/sdds-intr-rate.json?t={ts}"
        headers = {
            "accept": "application/json, text/javascript, */*; q=0.01",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
            "sec-ch-ua": "\"Not:A-Brand\";v=\"99\", \"Microsoft Edge\";v=\"145\", \"Chromium\";v=\"145\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"macOS\"",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "x-requested-with": "XMLHttpRequest",
        }
        req = urllib.request.Request(url, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:
            raw = resp.read().decode("utf-8")
        data = json.loads(raw)
        bond_10y = _safe_float(data.get("data", {}).get("bond10Y"))
        return bond_10y
    except Exception as e:
        print(f"[ChinaMoney国债] 获取失败: {e}")
        return None


def fetch_macro_liquidity(timeout: int = 20) -> dict:
    """
    获取宏观流动性指标：M2 同比增速、10年国债收益率（YTM）、社融增速。

    数据获取策略：
      M2：东方财富 RPT_ECONOMY_CURRENCY_SUPPLY 接口（最新2条）
          字段：BASIC_CURRENCY_SAME（M2同比%）、BASIC_CURRENCY（余额亿元）
          CURRENCY_SAME（M1同比%）
      10年国债收益率：
          - 中国外汇交易中心（ChinaMoney）API
            https://www.chinamoney.com.cn/r/cms/www/chinamoney/data/currency/sdds-intr-rate.json
          - 直接返回10年国债收益率（bond10Y字段），无须计算
      社融存量同比：
          - 使用国家统计局接口 fetch_social_finance()

      全部接口失败 → 降级读取 CSV 缓存最新一条。
      接口成功后回写 CSV 缓存。

    Args:
        timeout: 请求超时时间（秒）

    Returns:
        {
            "period":         str,    # 如 "2026-02"（以 M2 数据月份为准）
            "m2_yoy":         float,  # M2 同比增速（%）
            "m2_bal":         float,  # M2 余额（亿元）
            "m1_yoy":         float,  # M1 同比增速（%）
            "bond_10y":       float,  # 10年国债 YTM（%）
            "bond_10y_code":  str,    # 数据来源标识（chinamoney）
            "bond_10y_price": float,  # 对应债券最新收盘价（ChinaMoney不需要）
            "social_fin_yoy": float|None,  # 社融存量同比（%）
            "source":         str,
        }
        失败时：{"error": str}

    评分参考（scorer.py 使用）：
        M2 同比:
            ≥ 10%  → 货币宽松，流动性充裕           +1
            7–10%  → 正常偏松                         0
            < 7%   → 货币偏紧，流动性收缩             -1
        10年国债收益率:
            下行（当月 vs 上月 环比下行）            +0.5（附加）
            上行（当月 vs 上月 环比上行）            -0.5（附加）
            绝对水平：
            < 2%   → 利率低位，估值溢价               +1
            2–3%   → 利率正常                          0
            > 3%   → 利率偏高，高估值成长股承压       -1
        社融同比:
            ≥ 12%  → 融资旺盛，经济增长动力强         +1
            8–12%  → 正常偏松                          0
            5–8%   → 偏弱，稳增长压力                 -1
            < 5%   → 融资低迷                         -2
    """
    m2_data:   dict = {}
    bond_data: dict = {}
    sf_data:   dict = {}
    ts = int(time.time() * 1000)

    # ── M2 ──────────────────────────────────────────────────────────────
    try:
        url_m2 = (
            f"{_EM_BASE_URL}"
            "?columns=REPORT_DATE%2CTIME%2CBASIC_CURRENCY%2CBASIC_CURRENCY_SAME"
            "%2CCURRENCY%2CCURRENCY_SAME%2CFREE_CASH%2CFREE_CASH_SAME"
            "&pageNumber=1&pageSize=2"
            "&sortColumns=REPORT_DATE&sortTypes=-1"
            f"&source=WEB&client=WEB&reportName=RPT_ECONOMY_CURRENCY_SUPPLY&_={ts}"
        )
        d_m2   = _em_fetch_json(url_m2, timeout=timeout)
        rows_m = _em_extract_rows(d_m2)
        if rows_m:
            r = rows_m[0]
            period_m = _parse_month_period(str(r.get("TIME", "")))
            m2_data  = {
                "period":  period_m,
                "m2_yoy":  _safe_float(r.get("BASIC_CURRENCY_SAME")),
                "m2_bal":  _safe_float(r.get("BASIC_CURRENCY")),   # 亿元
                "m1_yoy":  _safe_float(r.get("CURRENCY_SAME")),
            }
    except Exception as e:
        m2_data = {"_err": f"M2接口失败：{e}"}

    # ── 10年国债收益率（YTM）────────────────────────────────────────────
    # 数据源：中国外汇交易中心（ChinaMoney）API
    # API: https://www.chinamoney.com.cn/r/cms/www/chinamoney/data/currency/sdds-intr-rate.json
    bond_yield = _fetch_bond_10y_chinamoney(timeout=min(timeout, 10))
    if bond_yield is not None:
        bond_data = {
            "bond_10y":       bond_yield,
            "bond_10y_code":  "chinamoney",
            "bond_10y_price": None,
        }
    else:
        bond_data = {"_err": "ChinaMoney API 获取失败"}

    # ── 社融存量同比（使用国家统计局接口）────────────────────────────────
    try:
        sf_data = fetch_social_finance(timeout=timeout)
        if "error" in sf_data:
            sf_data = {"_err": sf_data.get("error", "社融接口失败")}
    except Exception as e:
        sf_data = {"_err": f"社融接口失败：{e}"}

    # ── 全部失败 → 降级 CSV 缓存 ─────────────────────────────────────────
    all_m2_err = "_err" in m2_data
    all_bond_err = "_err" in bond_data
    all_sf_err = "_err" in sf_data

    if all_m2_err and all_bond_err and all_sf_err:
        try:
            cached = _read_liq_csv()
            if cached:
                latest_period = sorted(cached.keys())[-1]
                rec = cached[latest_period].copy()
                rec["source"] = "csv_cache"
                return rec
        except Exception:
            pass
        errs = "; ".join(
            v for v in [m2_data.get("_err"), bond_data.get("_err"), sf_data.get("_err")] if v
        )
        return {"error": f"宏观流动性全部接口失败：{errs}"}

    # ── 合并结果 ─────────────────────────────────────────────────────────
    period = m2_data.get("period") or bond_data.get("period") or sf_data.get("period") or "unknown"
    result = {
        "period":         period,
        "m2_yoy":         m2_data.get("m2_yoy"),
        "m2_bal":         m2_data.get("m2_bal"),
        "m1_yoy":         m2_data.get("m1_yoy"),
        "bond_10y":       bond_data.get("bond_10y"),
        "bond_10y_code":  bond_data.get("bond_10y_code", ""),
        "bond_10y_price": bond_data.get("bond_10y_price"),
        "social_fin_yoy": sf_data.get("sf_yoy"),   # 社融存量同比
        "source":         "eastmoney+stats.gov.cn",
    }

    # 回写 CSV 缓存
    try:
        cached = _read_liq_csv()
        cached[period] = result
        _write_liq_csv(cached)
    except Exception:
        pass

    return result
