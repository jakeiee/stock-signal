#!/usr/bin/env python3
"""Find growth rate codes."""
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

# 尝试获取同比数据 - 使用 sj 参数指定
# 年度数据: 2024D=2024年全年, 2024C=前三季度, 2024B=上半年, 2024A=一季度

print('='*60)
print('1. 直接计算人均收入同比增速')
print('='*60)

# 获取2024和2025的数据来计算同比
url1 = f'https://data.stats.gov.cn/easyquery.htm?m=QueryData&dbcode=hgjd&rowcode=zb&colcode=sj&wds=%5B%5D&dfwds=%5B%7B%22wdcode%22%3A%22sj%22%2C%22valuecode%22%3A%22LAST18%22%7D%5D&k1={ts}'
req1 = urllib.request.Request(url1, headers=headers)
with urllib.request.urlopen(req1, timeout=15, context=ssl_ctx) as resp:
    data1 = json.loads(resp.read().decode('utf-8'))

returndata = data1.get('returndata', {})
datanodes = returndata.get('datanodes', [])

# 找到 A010101 (全国居民人均可支配收入) 的年度数据
data_dict = {}
for node in datanodes:
    code = node.get('code', '')
    # zb.A010101_sj.2024D
    if 'A010101' in code and '_sj.2024D' in code:
        val = node.get('data', {}).get('data')
        data_dict['2024D'] = val
        print(f'2024全年: {val} 元')
    elif 'A010101' in code and '_sj.2025D' in code:
        val = node.get('data', {}).get('data')
        data_dict['2025D'] = val
        print(f'2025全年: {val} 元')
    elif 'A010101' in code and '_sj.2024Q4' in code:
        val = node.get('data', {}).get('data')
        data_dict['2024Q4'] = val
        print(f'2024Q4: {val} 元')
    elif 'A010101' in code and '_sj.2025Q4' in code:
        val = node.get('data', {}).get('data')
        data_dict['2025Q4'] = val
        print(f'2025Q4: {val} 元')
    elif 'A010101' in code and '_sj.2025C' in code:
        val = node.get('data', {}).get('data')
        data_dict['2025C'] = val
        print(f'2025前三季度: {val} 元')
    elif 'A010101' in code and '_sj.2024C' in code:
        val = node.get('data', {}).get('data')
        data_dict['2024C'] = val
        print(f'2024前三季度: {val} 元')

# 计算同比
if '2024D' in data_dict and '2025D' in data_dict:
    yoy = (data_dict['2025D'] / data_dict['2024D'] - 1) * 100
    print(f'\n2025全年 vs 2024全年 同比: {yoy:.2f}%')

if '2024C' in data_dict and '2025C' in data_dict:
    yoy = (data_dict['2025C'] / data_dict['2024C'] - 1) * 100
    print(f'2025前三季度 vs 2024前三季度 同比: {yoy:.2f}%')

print()
print('='*60)
print('2. 查找社融月度数据 (尝试 dbcode=hgnd)')
print('='*60)

# hgnd = 年度数据, hgjd = 季度数据, csjd = 月度数据 (不存在)
# 尝试用 hgnd 查询月度社融数据
url_sf = f'https://data.stats.gov.cn/easyquery.htm?m=QueryData&dbcode=hgnd&rowcode=zb&colcode=sj&wds=%5B%5D&dfwds=%5B%7B%22wdcode%22%3A%22sj%22%2C%22valuecode%22%3A%22LAST20%22%7D%5D&k1={ts}'
req_sf = urllib.request.Request(url_sf, headers=headers)
try:
    with urllib.request.urlopen(req_sf, timeout=15, context=ssl_ctx) as resp:
        data_sf = json.loads(resp.read().decode('utf-8'))
    returndata_sf = data_sf.get('returndata', {})
    datanodes_sf = returndata_sf.get('datanodes', [])
    print(f'获取到 {len(datanodes_sf)} 条数据')
    # 查看前几条
    for node in datanodes_sf[:5]:
        code = node.get('code', '')
        val = node.get('data', {}).get('data')
        print(f'  code={code}, val={val}')
except Exception as e:
    print(f'Error: {e}')

print()
print('='*60)
print('3. 尝试不同dbcode查询月度社融')
print('='*60)

# 尝试其他可能的月度数据库
for dbcode in ['monthly', 'hgyjd', 'hgjd', 'hgnd']:
    try:
        url_test = f'https://data.stats.gov.cn/easyquery.htm?m=QueryData&dbcode={dbcode}&rowcode=zb&colcode=sj&wds=%5B%5D&dfwds=%5B%7B%22wdcode%22%3A%22sj%22%2C%22valuecode%22%3A%22LAST6%22%7D%5D&k1={ts}'
        req_test = urllib.request.Request(url_test, headers=headers)
        with urllib.request.urlopen(req_test, timeout=10, context=ssl_ctx) as resp:
            data_test = json.loads(resp.read().decode('utf-8'))
        print(f'{dbcode}: OK, nodes={len(data_test.get("returndata", {}).get("datanodes", []))}')
    except Exception as e:
        print(f'{dbcode}: {e}')
