#!/usr/bin/env python3
"""Find correct stats codes for income yoy and social finance yoy."""
import urllib.request
import json
import ssl
import time

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

headers = {
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
    'Referer': 'https://data.stats.gov.cn/',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'X-Requested-With': 'XMLHttpRequest',
}

ts = int(time.time() * 1000)

# 尝试不同的API查询来找到正确的指标代码
# 人均收入相关的代码可能包括 A0501, A0N011 等

print('='*60)
print('1. 查找人均收入同比增速代码 (尝试不同参数)')
print('='*60)

# 尝试查询季度数据
url_q = f'https://data.stats.gov.cn/easyquery.htm?m=QueryData&dbcode=hgjd&rowcode=zb&colcode=sj&wds=%5B%7B%22wdcode%22%3A%22zb%22%2C%22valuecode%22%3A%22A0501%22%7D%5D&dfwds=%5B%7B%22wdcode%22%3A%22sj%22%2C%22valuecode%22%3A%22LAST18%22%7D%5D&k1={ts}'
req_q = urllib.request.Request(url_q, headers=headers)
try:
    with urllib.request.urlopen(req_q, timeout=15, context=ssl_ctx) as resp:
        data_q = json.loads(resp.read().decode('utf-8'))
    returndata = data_q.get('returndata', {})
    datanodes = returndata.get('datanodes', [])
    print(f'dbcode=hgjd, zb=A0501: {len(datanodes)} nodes')
    for node in datanodes[:10]:
        code = node.get('code', '')
        val = node.get('data', {}).get('data')
        strdata = node.get('data', {}).get('strdata')
        if val is not None and val != 0:
            print(f'  code={code}, data={val}, strdata={strdata}')
except Exception as e:
    print(f'Error: {e}')

print()
# 尝试 A0N011 (城镇居民人均可支配收入)
url2 = f'https://data.stats.gov.cn/easyquery.htm?m=QueryData&dbcode=hgjd&rowcode=zb&colcode=sj&wds=%5B%7B%22wdcode%22%3A%22zb%22%2C%22valuecode%22%3A%22A0N011%22%7D%5D&dfwds=%5B%7B%22wdcode%22%3A%22sj%22%2C%22valuecode%22%3A%22LAST18%22%7D%5D&k1={ts}'
req2 = urllib.request.Request(url2, headers=headers)
try:
    with urllib.request.urlopen(req2, timeout=15, context=ssl_ctx) as resp:
        data2 = json.loads(resp.read().decode('utf-8'))
    returndata = data2.get('returndata', {})
    datanodes = returndata.get('datanodes', [])
    print(f'dbcode=hgjd, zb=A0N011: {len(datanodes)} nodes')
    for node in datanodes[:10]:
        code = node.get('code', '')
        val = node.get('data', {}).get('data')
        strdata = node.get('data', {}).get('strdata')
        if val is not None and val != 0:
            print(f'  code={code}, data={val}, strdata={strdata}')
except Exception as e:
    print(f'Error: {e}')

print()
# 尝试 A0N0H (农村居民人均可支配收入)
url3 = f'https://data.stats.gov.cn/easyquery.htm?m=QueryData&dbcode=hgjd&rowcode=zb&colcode=sj&wds=%5B%7B%22wdcode%22%3A%22zb%22%2C%22valuecode%22%3A%22A0N0H%22%7D%5D&dfwds=%5B%7B%22wdcode%22%3A%22sj%22%2C%22valuecode%22%3A%22LAST18%22%7D%5D&k1={ts}'
req3 = urllib.request.Request(url3, headers=headers)
try:
    with urllib.request.urlopen(req3, timeout=15, context=ssl_ctx) as resp:
        data3 = json.loads(resp.read().decode('utf-8'))
    returndata = data3.get('returndata', {})
    datanodes = returndata.get('datanodes', [])
    print(f'dbcode=hgjd, zb=A0N0H: {len(datanodes)} nodes')
    for node in datanodes[:10]:
        code = node.get('code', '')
        val = node.get('data', {}).get('data')
        strdata = node.get('data', {}).get('strdata')
        if val is not None and val != 0:
            print(f'  code={code}, data={val}, strdata={strdata}')
except Exception as e:
    print(f'Error: {e}')

print()
print('='*60)
print('2. 查找社融同比增速代码')
print('='*60)

# 尝试查询社融 - 使用不同的dbcode
url_sf1 = f'https://data.stats.gov.cn/easyquery.htm?m=QueryData&dbcode=hgjd&rowcode=zb&colcode=sj&wds=%5B%7B%22wdcode%22%3A%22zb%22%2C%22valuecode%22%3A%22A0L08%22%7D%5D&dfwds=%5B%7B%22wdcode%22%3A%22sj%22%2C%22valuecode%22%3A%22LAST20%22%7D%5D&k1={ts}'
req_sf1 = urllib.request.Request(url_sf1, headers=headers)
try:
    with urllib.request.urlopen(req_sf1, timeout=15, context=ssl_ctx) as resp:
        data_sf1 = json.loads(resp.read().decode('utf-8'))
    returndata = data_sf1.get('returndata', {})
    datanodes = returndata.get('datanodes', [])
    print(f'dbcode=hgjd, zb=A0L08: {len(datanodes)} nodes')
    for node in datanodes[:10]:
        code = node.get('code', '')
        val = node.get('data', {}).get('data')
        strdata = node.get('data', {}).get('strdata')
        if val is not None:
            print(f'  code={code}, data={val}, strdata={strdata}')
except Exception as e:
    print(f'Error: {e}')

print()
# 尝试 A0L01 (社会融资规模存量)
url_sf2 = f'https://data.stats.gov.cn/easyquery.htm?m=QueryData&dbcode=hgjd&rowcode=zb&colcode=sj&wds=%5B%7B%22wdcode%22%3A%22zb%22%2C%22valuecode%22%3A%22A0L01%22%7D%5D&dfwds=%5B%7B%22wdcode%22%3A%22sj%22%2C%22valuecode%22%3A%22LAST20%22%7D%5D&k1={ts}'
req_sf2 = urllib.request.Request(url_sf2, headers=headers)
try:
    with urllib.request.urlopen(req_sf2, timeout=15, context=ssl_ctx) as resp:
        data_sf2 = json.loads(resp.read().decode('utf-8'))
    returndata = data_sf2.get('returndata', {})
    datanodes = returndata.get('datanodes', [])
    print(f'dbcode=hgjd, zb=A0L01: {len(datanodes)} nodes')
    for node in datanodes[:10]:
        code = node.get('code', '')
        val = node.get('data', {}).get('data')
        strdata = node.get('data', {}).get('strdata')
        if val is not None:
            print(f'  code={code}, data={val}, strdata={strdata}')
except Exception as e:
    print(f'Error: {e}')

print()
# 尝试月度数据 (csj = monthly)
url_sf3 = f'https://data.stats.gov.cn/easyquery.htm?m=QueryData&dbcode=csjd&rowcode=zb&colcode=sj&wds=%5B%7B%22wdcode%22%3A%22zb%22%2C%22valuecode%22%3A%22A0L08%22%7D%5D&dfwds=%5B%7B%22wdcode%22%3A%22sj%22%2C%22valuecode%22%3A%22LAST24%22%7D%5D&k1={ts}'
req_sf3 = urllib.request.Request(url_sf3, headers=headers)
try:
    with urllib.request.urlopen(req_sf3, timeout=15, context=ssl_ctx) as resp:
        data_sf3 = json.loads(resp.read().decode('utf-8'))
    returndata = data_sf3.get('returndata', {})
    datanodes = returndata.get('datanodes', [])
    print(f'dbcode=csjd, zb=A0L08: {len(datanodes)} nodes')
    for node in datanodes[:10]:
        code = node.get('code', '')
        val = node.get('data', {}).get('data')
        strdata = node.get('data', {}).get('strdata')
        if val is not None:
            print(f'  code={code}, data={val}, strdata={strdata}')
except Exception as e:
    print(f'Error: {e}')
