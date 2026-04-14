"""
通过国家统计局数据导航接口找到居民收入相关的数据库代码。
"""
import urllib.request
import json
import ssl
import time

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://data.stats.gov.cn/easyquery.htm?cn=B01",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "X-Requested-With": "XMLHttpRequest",
}

# 1. 查询hgjd数据库的导航树（找居民收入子库）
ts = int(time.time() * 1000)

# 尝试通过导航树接口找居民收入数据库
nav_url = f"https://data.stats.gov.cn/easyquery.htm?m=getTree&dbcode=hgjd&wdcode=zb&id=0&k1={ts}"
print(f"[接口URL-导航树] {nav_url}")
try:
    req = urllib.request.Request(nav_url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=12, context=ssl_ctx) as resp:
        raw = resp.read().decode("utf-8")
    data = json.loads(raw)
    print(f"[原始数据] {json.dumps(data, ensure_ascii=False)[:2000]}")
    print()
    for item in data:
        name = item.get("name", "")
        code = item.get("dbcode", item.get("id", ""))
        print(f"  code={code}  name={name}")
except Exception as e:
    print(f"  [失败] {e}")

print()
# 2. 尝试整个季度数据库B01的导航
ts = int(time.time() * 1000)
nav2_url = f"https://data.stats.gov.cn/easyquery.htm?m=getTree&dbcode=hgjd&wdcode=zb&id=zb&k1={ts}"
print(f"[接口URL-指标树] {nav2_url}")
try:
    req = urllib.request.Request(nav2_url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=12, context=ssl_ctx) as resp:
        raw = resp.read().decode("utf-8")
    data = json.loads(raw)
    print(f"[原始数据] {json.dumps(data, ensure_ascii=False)[:3000]}")
    # 找居民收入相关
    for item in data:
        name = item.get("name", "")
        pid = item.get("pid", "")
        id_ = item.get("id", "")
        if any(k in name for k in ["居民", "收入", "可支配"]):
            print(f"  ★ id={id_}  pid={pid}  name={name}")
except Exception as e:
    print(f"  [失败] {e}")

# 3. 尝试cn=B01（季度），取居民收入分类
ts = int(time.time() * 1000)
# 尝试查所有分类数据
for cn, desc in [("B01", "全国季度"), ("B02", "月度"), ("B03", "年度")]:
    ts = int(time.time() * 1000)
    url = f"https://data.stats.gov.cn/easyquery.htm?m=getOtherWds&dbcode=hgjd&wdcode=zb&id=A01&k1={ts}"
    print(f"\n[接口URL-A01子节点] {url}")
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=12, context=ssl_ctx) as resp:
            raw = resp.read().decode("utf-8")
        data = json.loads(raw)
        print(f"[原始数据] {json.dumps(data, ensure_ascii=False)[:2000]}")
        for item in (data if isinstance(data, list) else []):
            name = item.get("name", "")
            id_ = item.get("id", "")
            if any(k in name for k in ["居民", "收入", "可支配", "人均"]):
                print(f"  ★ id={id_}  name={name}")
    except Exception as e:
        print(f"  [失败] {e}")
    break
