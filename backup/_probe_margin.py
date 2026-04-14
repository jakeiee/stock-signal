"""探测东方财富两融汇总接口"""
import ssl, time, urllib.request, json

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

ts = int(time.time() * 1000)

reports = [
    # 东方财富可能的两融汇总报表名
    ('RPTA_WEB_RZRQ_QUESUBTOTAL', 'STATISTICS_DATE,RZRQYE,RZYE,RQYE'),
    ('RPT_MARGIN_RZRQ_QUESUBTOTAL', 'STATISTICS_DATE,RZRQYE,RZYE,RQYE'),
    ('RPTA_WEB_RZRQ_QSTS', 'STATISTICS_DATE,RZRQYE,RZYE,RQYE'),
    ('RPT_MARGIN_QSTS', 'STATISTICS_DATE,RZRQYE'),
    ('RPTA_WEB_MARGIN_RZRQ', 'STATISTICS_DATE,RZRQYE'),
    ('RPT_RZRQ_MARKET_TOTAL', 'STATISTICS_DATE,RZRQYE'),
    ('RPTA_WEB_RZRQ_LSHJ', 'STATISTICS_DATE,RZRQYE,RZYE,RQYE,RZRQYEZB'),
    ('RPT_MARGIN_RZRQ_LSHJ', 'STATISTICS_DATE,RZRQYE,RZYE,RQYE'),
    ('RPT_RZRQ_LS', 'STATISTICS_DATE,RZRQYE'),
    ('RPTA_WEB_RZRQ_MARKET', 'STATISTICS_DATE,RZRQYE'),
]

for report, cols in reports:
    url = (f'https://datacenter-web.eastmoney.com/api/data/v1/get'
           f'?reportName={report}&columns={cols}'
           f'&pageNumber=1&pageSize=3&sortTypes=-1&sortColumns=STATISTICS_DATE'
           f'&source=WEB&client=WEB&_={ts}')
    req = urllib.request.Request(url, headers={
        'Accept': 'application/json',
        'Referer': 'https://data.eastmoney.com/rzrq/lshj.html',
        'User-Agent': 'Mozilla/5.0 Chrome/124.0.0.0',
    })
    try:
        with urllib.request.urlopen(req, timeout=8, context=_SSL_CTX) as r:
            raw = r.read().decode('utf-8')
        if '"success":true' in raw:
            print(f'*** FOUND: {report}')
            print(raw[:600])
        else:
            msg = json.loads(raw).get('message', '')
            print(f'{report}: {msg[:80]}')
    except Exception as e:
        print(f'{report}: ERROR {e}')
    print()
