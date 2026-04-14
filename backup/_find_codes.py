#!/usr/bin/env python3
"""Find all unique indicator codes in the API response."""
import urllib.request
import json
import ssl
import time
import re

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
print('1. 查找人均收入相关指标代码 (dbcode=hgjd 所有数据)')
print('='*60)

url1 = f'https://data.stats.gov.cn/easyquery.htm?m=QueryData&dbcode=hgjd&rowcode=zb&colcode=sj&wds=%5B%5D&dfwds=%5B%7B%22wdcode%22%3A%22sj%22%2C%22valuecode%22%3A%22LAST18%22%7D%5D&k1={ts}'
req1 = urllib.request.Request(url1, headers=headers)
with urllib.request.urlopen(req1, timeout=15, context=ssl_ctx) as resp:
    data1 = json.loads(resp.read().decode('utf-8'))

returndata = data1.get('returndata', {})
datanodes = returndata.get('datanodes', [])

# 提取所有唯一的zb代码
zb_codes = set()
for node in datanodes:
    code = node.get('code', '')
    # 格式: zb.A010101_sj.2025D
    match = re.match(r'zb\.([A-Za-z0-9]+)_sj\.', code)
    if match:
        zb_codes.add(match.group(1))

print(f'找到 {len(zb_codes)} 个唯一指标代码:')
for code in sorted(zb_codes):
    print(f'  {code}')

# 查找包含"收入"或"可支配"的代码
print()
print('收入相关代码:')
for code in sorted(zb_codes):
    if '0' in code or 'N' in code:
        print(f'  {code}')

print()
print('='*60)
print('2. 查找社融相关指标代码 (dbcode=csjd 月度数据)')
print('='*60)

url2 = f'https://data.stats.gov.cn/easyquery.htm?m=QueryData&dbcode=csjd&rowcode=zb&colcode=sj&wds=%5B%5D&dfwds=%5B%7B%22wdcode%22%3A%22sj%22%2C%22valuecode%22%3A%22LAST24%22%7D%5D&k1={ts}'
req2 = urllib.request.Request(url2, headers=headers)
with urllib.request.urlopen(req2, timeout=15, context=ssl_ctx) as resp:
    data2 = json.loads(resp.read().decode('utf-8'))

returndata2 = data2.get('returndata', {})
datanodes2 = returndata2.get('datanodes', [])

zb_codes2 = set()
for node in datanodes2:
    code = node.get('code', '')
    match = re.match(r'zb\.([A-Za-z0-9]+)_sj\.', code)
    if match:
        zb_codes2.add(match.group(1))

print(f'找到 {len(zb_codes2)} 个唯一指标代码:')
for code in sorted(zb_codes2):
    print(f'  {code}')
