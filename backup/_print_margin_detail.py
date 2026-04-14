"""
两融指标完整计算步骤打印。
数据来源：
  接口1  RPTA_RZRQ_LSHJ（东方财富，两融历史汇总，最新2条）
  push2  上证(1.000001) + 深证(0.399001) + 北证50(0.899050)  f48字段
"""
import ssl, time, urllib.request, json, re

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

_BASE   = "https://datacenter-web.eastmoney.com/api/data/v1/get"
_PUSH2  = "https://push2.eastmoney.com/api/qt/stock/get"
_HDR = {
    "Accept": "*/*", "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://data.eastmoney.com/",
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0.0.0 Safari/537.36"),
}

SEP  = "=" * 68
SEP2 = "-" * 68

def fetch_json(url):
    req = urllib.request.Request(url, headers=_HDR)
    with urllib.request.urlopen(req, timeout=20, context=_SSL_CTX) as r:
        raw = r.read().decode("utf-8")
    m = re.search(r"(?:jQuery\w+|datatable\w+)\((.+)\)\s*;?\s*$", raw, re.DOTALL)
    return json.loads(m.group(1)) if m else json.loads(raw)

def fetch_f48(secid):
    ts  = int(time.time() * 1000)
    url = f"{_PUSH2}?secid={secid}&fields=f48&_={ts}"
    req = urllib.request.Request(url, headers=_HDR)
    with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as r:
        d = json.loads(r.read().decode("utf-8"))
    return d.get("data", {}).get("f48")

# ══════════════════════════════════════════════════════════════════════
print(SEP)
print("  STEP 1  接口原始字段  RPTA_RZRQ_LSHJ（最新2条）")
print(SEP)

ts   = int(time.time() * 1000)
url1 = (f"{_BASE}?reportName=RPTA_RZRQ_LSHJ&columns=ALL"
        f"&source=WEB&sortColumns=DIM_DATE&sortTypes=-1"
        f"&pageNumber=1&pageSize=2&_={ts}")
d1    = fetch_json(url1)
rows  = (d1.get("result") or {}).get("data") or []
if not rows:
    print("  ❌ 接口返回空数据，退出")
    exit(1)

KEEP = ["DIM_DATE","LTSZ","RZYE","RZYEZB",
        "RZMRE","RZCHE","RZJME",
        "RQYE","RQYL","RQMCL","RQCHL","RQJMG",
        "RZRQYE","RZRQYECZ"]

for i, row in enumerate(rows):
    tag = "【最新】" if i == 0 else "【前日】"
    print(f"\n  {tag}  {str(row.get('DIM_DATE',''))[:10]}")
    for k in KEEP:
        v = row.get(k)
        print(f"    {k:15s} = {v}")

# ══════════════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("  STEP 2  push2 实时成交额（沪 / 深 / 京）")
print(SEP)

markets = [
    ("1.000001", "沪  上证综指"),
    ("0.399001", "深  深证成指"),
    ("0.899050", "京  北证50  "),
]
amt = {}
for secid, label in markets:
    f48 = fetch_f48(secid)
    yi  = round(f48 / 1e8, 2) if isinstance(f48, (int,float)) and f48 > 0 else None
    print(f"\n  [{label}]  secid={secid}")
    print(f"    f48 原始值  = {f48}")
    print(f"    换算亿元    = {f48} ÷ 1e8 = {yi} 亿元")
    amt[secid] = yi

sh_yi = amt["1.000001"] or 0
sz_yi = amt["0.399001"] or 0
bj_yi = amt["0.899050"] or 0
total_turnover = round(sh_yi + sz_yi + bj_yi, 2)

print(f"\n  {SEP2}")
print(f"  汇总  沪 {sh_yi} + 深 {sz_yi} + 京 {bj_yi}")
print(f"       = {total_turnover} 亿元  （全市场A股成交额）")

# ══════════════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("  STEP 3  两融指标逐步计算")
print(SEP)

latest = rows[0]
prev   = rows[1] if len(rows) > 1 else None

# 1. 日期
date_str = str(latest.get("DIM_DATE",""))[:10]
print(f"\n  数据日期  : {date_str}")

# 2. A股流通市值
ltsz_yuan = float(latest.get("LTSZ") or 0)
ltsz_yi   = round(ltsz_yuan / 1e8, 2)
print(f"\n  【流通市值】")
print(f"    LTSZ              = {ltsz_yuan:,.0f} 元")
print(f"    流通市值          = {ltsz_yuan:,.0f} ÷ 1e8 = {ltsz_yi:,.2f} 亿元")

# 3. 融资余额
rzye_yuan = float(latest.get("RZYE") or 0)
rz_bal    = round(rzye_yuan / 1e8, 2)
rzyezb    = float(latest.get("RZYEZB") or 0)
rz_ratio_calc = round(rz_bal / ltsz_yi * 100, 4) if ltsz_yi > 0 else None
print(f"\n  【融资余额 & 占比】")
print(f"    RZYE              = {rzye_yuan:,.0f} 元")
print(f"    融资余额          = {rzye_yuan:,.0f} ÷ 1e8 = {rz_bal:,.2f} 亿元")
print(f"    RZYEZB（接口直给）= {rzyezb} %  （融资余额/流通市值）")
print(f"    自算验证          = {rz_bal:,.2f} ÷ {ltsz_yi:,.2f} × 100 = {rz_ratio_calc} %")

# 4. 融券余额
rqye_yuan = float(latest.get("RQYE") or 0)
rq_bal    = round(rqye_yuan / 1e8, 2)
print(f"\n  【融券余额】")
print(f"    RQYE              = {rqye_yuan:,.0f} 元")
print(f"    融券余额          = {rqye_yuan:,.0f} ÷ 1e8 = {rq_bal:,.2f} 亿元")

# 5. 两融余额
rzrqye_yuan = float(latest.get("RZRQYE") or 0)
total_bal   = round(rzrqye_yuan / 1e8, 2)
total_ratio = round(total_bal / ltsz_yi * 100, 4) if ltsz_yi > 0 else None
print(f"\n  【两融余额 & 占流通市值】")
print(f"    RZRQYE            = {rzrqye_yuan:,.0f} 元")
print(f"    两融余额          = {rzrqye_yuan:,.0f} ÷ 1e8 = {total_bal:,.2f} 亿元")
print(f"    验证：融资 + 融券  = {rz_bal:,.2f} + {rq_bal:,.2f} = {round(rz_bal+rq_bal,2):,.2f} 亿元")
print(f"    两融余额/流通市值  = {total_bal:,.2f} ÷ {ltsz_yi:,.2f} × 100 = {total_ratio} %")

# 6. 两融余额日变动
rzrqyecz_yuan = float(latest.get("RZRQYECZ") or 0)
prev_total_bal = round(rzrqyecz_yuan / 1e8, 2) if rzrqyecz_yuan > 0 else None
if prev_total_bal is None and prev:
    prev_total_bal = round(float(prev.get("RZRQYE") or 0) / 1e8, 2) or None
bal_chg     = round(total_bal - prev_total_bal, 2) if prev_total_bal else None
bal_chg_pct = round(bal_chg / prev_total_bal * 100, 4) if (bal_chg is not None and prev_total_bal) else None
print(f"\n  【两融余额日变动】")
print(f"    RZRQYECZ（前日值）= {rzrqyecz_yuan:,.0f} 元  → {prev_total_bal:,.2f} 亿元")
print(f"    日变动            = {total_bal:,.2f} - {prev_total_bal:,.2f} = {bal_chg:+.2f} 亿元")
print(f"    日变动幅度        = {bal_chg:+.2f} ÷ {prev_total_bal:,.2f} × 100 = {bal_chg_pct:+.4f} %")

# 7. 融资交易明细
rzmre_yuan = float(latest.get("RZMRE") or 0)
rzche_yuan = float(latest.get("RZCHE") or 0)
rzjme_yuan = float(latest.get("RZJME") or 0)
rzmre_yi   = round(rzmre_yuan / 1e8, 2)
rzche_yi   = round(rzche_yuan / 1e8, 2)
rzjme_yi   = round(rzjme_yuan / 1e8, 2)
print(f"\n  【融资交易明细】")
print(f"    RZMRE 融资买入额  = {rzmre_yuan:,.0f} 元  → {rzmre_yi:,.2f} 亿元")
print(f"    RZCHE 融资偿还额  = {rzche_yuan:,.0f} 元  → {rzche_yi:,.2f} 亿元")
print(f"    RZJME 融资净买入  = RZMRE - RZCHE")
print(f"                      = {rzmre_yi:,.2f} - {rzche_yi:,.2f} = {round(rzmre_yi-rzche_yi,2):+.2f} 亿元")
print(f"    接口直给 RZJME    = {rzjme_yuan:,.0f} 元  → {rzjme_yi:+.2f} 亿元")

# 8. 融券交易明细
rqyl_yuan  = float(latest.get("RQYL")  or 0)
rqchl_yuan = float(latest.get("RQCHL") or 0)
rqmcl_yuan = float(latest.get("RQMCL") or 0)
rqjmg_yuan = float(latest.get("RQJMG") or 0)
print(f"\n  【融券交易明细】")
print(f"    RQYL  融券余量    = {rqyl_yuan:,.0f} 元  → {round(rqyl_yuan/1e8,2):,.2f} 亿元")
print(f"    RQCHL 融券偿还量  = {rqchl_yuan:,.0f} 元  → {round(rqchl_yuan/1e8,2):,.2f} 亿元")
print(f"    RQMCL 融券卖出量  = {rqmcl_yuan:,.0f} 元  → {round(rqmcl_yuan/1e8,2):,.2f} 亿元")
print(f"    RQJMG 融券净卖出  = {rqjmg_yuan:,.0f} 元  → {round(rqjmg_yuan/1e8,2):+.2f} 亿元")

# 9. 全市场成交额占比
rz_buy = rzmre_yi
rz_turnover_ratio = round(rz_buy / total_turnover * 100, 4) if total_turnover > 0 else None
sh_pct = round(sh_yi / total_turnover * 100, 2) if total_turnover > 0 else None
sz_pct = round(sz_yi / total_turnover * 100, 2) if total_turnover > 0 else None
bj_pct = round(bj_yi / total_turnover * 100, 2) if total_turnover > 0 else None
print(f"\n  【全市场成交额结构 & 两融交易占比】")
print(f"    沪市成交额        = {sh_yi:,.2f} 亿元  占比 {sh_pct:.2f}%")
print(f"    深市成交额        = {sz_yi:,.2f} 亿元  占比 {sz_pct:.2f}%")
print(f"    京市成交额        = {bj_yi:,.2f} 亿元  占比 {bj_pct:.2f}%")
print(f"    全市场合计        = {sh_yi} + {sz_yi} + {bj_yi} = {total_turnover:,.2f} 亿元")
print(f"    融资买入额        = {rz_buy:,.2f} 亿元")
print(f"    融资买入/全市场   = {rz_buy:,.2f} ÷ {total_turnover:,.2f} × 100 = {rz_turnover_ratio:.4f} %")

# ══════════════════════════════════════════════════════════════════════
print(f"\n{SEP}")
print("  STEP 4  最终指标汇总")
print(SEP)
print(f"  数据日期            : {date_str}  （接口1最新交易日）")
print(f"  ── 规模 ──────────────────────────────────────────────")
print(f"  A股流通市值         : {ltsz_yi:>12,.2f} 亿元")
print(f"  融资余额            : {rz_bal:>12,.2f} 亿元")
print(f"  融券余额            : {rq_bal:>12,.2f} 亿元")
print(f"  两融余额            : {total_bal:>12,.2f} 亿元")
print(f"  ── 占比 ──────────────────────────────────────────────")
print(f"  融资余额/流通市值   : {rzyezb:>12.4f} %  （RZYEZB，接口直给）")
print(f"  两融余额/流通市值   : {total_ratio:>12.4f} %  （自算）")
print(f"  ── 日变动 ────────────────────────────────────────────")
print(f"  两融余额前日值      : {prev_total_bal:>12,.2f} 亿元")
print(f"  两融余额日变动      : {bal_chg:>+12.2f} 亿元")
print(f"  两融余额日变动幅度  : {bal_chg_pct:>+12.4f} %")
print(f"  ── 交易 ──────────────────────────────────────────────")
print(f"  融资买入额          : {rzmre_yi:>12,.2f} 亿元")
print(f"  融资偿还额          : {rzche_yi:>12,.2f} 亿元")
print(f"  融资净买入          : {rzjme_yi:>+12.2f} 亿元")
print(f"  ── 全市场成交额（沪+深+京）──────────────────────────")
print(f"  沪市                : {sh_yi:>12,.2f} 亿元  ({sh_pct:.1f}%)")
print(f"  深市                : {sz_yi:>12,.2f} 亿元  ({sz_pct:.1f}%)")
print(f"  京市                : {bj_yi:>12,.2f} 亿元  ({bj_pct:.1f}%)")
print(f"  全市场合计          : {total_turnover:>12,.2f} 亿元")
print(f"  融资买入/全市场     : {rz_turnover_ratio:>12.4f} %")
print(SEP)
