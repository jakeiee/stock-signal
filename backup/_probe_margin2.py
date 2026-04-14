"""探测各机构两融汇总接口 - 第二批"""
import ssl, time, urllib.request, json, re

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

def get(url, referer='', enc='utf-8'):
    req = urllib.request.Request(url, headers={
        'Accept': '*/*',
        'Referer': referer or url,
        'User-Agent': 'Mozilla/5.0 Chrome/124.0.0.0',
        'Accept-Encoding': 'identity',
    })
    try:
        with urllib.request.urlopen(req, timeout=12, context=_SSL_CTX) as r:
            return r.read().decode(enc, 'replace')
    except Exception as e:
        return f'ERROR: {e}'

ts = int(time.time() * 1000)

# 1. 上交所两融汇总 CSV 下载
print('=== 上交所 CSV 下载 ===')
raw = get(f'https://query.sse.com.cn/commonQuery.do?jsonCallBack=jsonpCB&sqlId=COMMON_SSE_JYTZ_RZRQBY_HJZB_L&SECU_CODE=&type=inParams&isPagination=true&pageHelp.pageSize=5&pageHelp.pageNo=1&_={ts}',
          referer='https://www.sse.com.cn/market/othersdata/margin/sum/')
print(raw[:500])
print()

# 2. 深交所两融汇总
print('=== 深交所 ===')
raw2 = get(f'https://www.szse.cn/api/report/ShowReport/data?SHOWTYPE=JSON&CATALOGID=1837_rzrq&TABKEY=tab1&tab1PAGESIZE=5&tab1PAGENO=1&random={ts}',
           referer='https://www.szse.cn/market/marginStatistics/index.html')
print(raw2[:500])
print()

# 3. 证监会 SFC 融资融券汇总
print('=== CSRC ===')
raw3 = get('http://www.csrc.gov.cn/csrc/c100220/zrzy_index.shtml')
print(raw3[:300])
print()

# 4. 东方财富两融余额趋势图 embed 接口
print('=== EM trend chart ===')
raw4 = get(f'https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPTA_WEB_RZRQ_GGMX&columns=RZYE,RQYE,RZRQYE,RZMRE,DATE&pageNumber=1&pageSize=3000&filter=(DATE%3D%222026-03-13%22)&source=WEB&client=WEB&_={ts}',
           referer='https://data.eastmoney.com/rzrq/lshj.html')
print(raw4[:500])
