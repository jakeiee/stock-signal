#!/usr/bin/env python3
"""Test stats.gov.cn API for disposable income and social finance."""
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

print('='*60)
print('1. 居民人均可支配收入 API (dbcode=hgjd)')
print('='*60)
url1 = f'https://data.stats.gov.cn/easyquery.htm?m=QueryData&dbcode=hgjd&rowcode=zb&colcode=sj&wds=%5B%5D&dfwds=%5B%7B%22wdcode%22%3A%22sj%22%2C%22valuecode%22%3A%22LAST18%22%7D%5D&k1={ts}'
req1 = urllib.request.Request(url1, headers=headers)
with urllib.request.urlopen(req1, timeout=15, context=ssl_ctx) as resp:
    data1 = json.loads(resp.read().decode('utf-8'))

returndata = data1.get('returndata', {})
datanodes = returndata.get('datanodes', [])
print(f'total datanodes: {len(datanodes)}')
for i, node in enumerate(datanodes[:20]):
    code = node.get('code', '')
    val = node.get('data', {}).get('data')
    strdata = node.get('data', {}).get('strdata')
    print(f'[{i:2d}] code={code}')
    print(f'     data={val}, strdata={strdata}')

print()
print('='*60)
print('2. 社融存量 API (dbcode=hgnd)')
print('='*60)
url2 = f'https://data.stats.gov.cn/easyquery.htm?m=QueryData&dbcode=hgnd&rowcode=zb&colcode=sj&wds=%5B%5D&dfwds=%5B%7B%22wdcode%22%3A%22sj%22%2C%22valuecode%22%3A%22LAST20%22%7D%5D&k1={ts}'
req2 = urllib.request.Request(url2, headers=headers)
with urllib.request.urlopen(req2, timeout=15, context=ssl_ctx) as resp:
    data2 = json.loads(resp.read().decode('utf-8'))

returndata2 = data2.get('returndata', {})
datanodes2 = returndata2.get('datanodes', [])
print(f'total datanodes: {len(datanodes2)}')
for i, node in enumerate(datanodes2[:20]):
    code = node.get('code', '')
    val = node.get('data', {}).get('data')
    strdata = node.get('data', {}).get('strdata')
    print(f'[{i:2d}] code={code}')
    print(f'     data={val}, strdata={strdata}')
