"""
找到 A05（人民生活）下的居民收入指标，特别是"累计增长(%)"字段。
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

def get_tree(dbcode, id_):
    ts = int(time.time() * 1000)
    url = f"https://data.stats.gov.cn/easyquery.htm?m=getTree&dbcode={dbcode}&wdcode=zb&id={id_}&k1={ts}"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=12, context=ssl_ctx) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw), url

# 展开 A05（人民生活）
data, url = get_tree("hgjd", "A05")
print(f"[接口URL] {url}")
print(f"[原始数据] {json.dumps(data, ensure_ascii=False)}")
print("\nA05（人民生活）子节点:")
for item in data:
    print(f"  id={item.get('id')}  name={item.get('name')}  isParent={item.get('isParent')}")

# 展开每个子节点
for item in data:
    id_ = item.get("id")
    is_parent = item.get("isParent", False)
    name = item.get("name", "")
    print(f"\n  展开 {id_}（{name}）...")
    if is_parent:
        sub_data, sub_url = get_tree("hgjd", id_)
        print(f"  [接口URL] {sub_url}")
        for sub in sub_data:
            sub_id = sub.get("id")
            sub_name = sub.get("name", "")
            sub_is_parent = sub.get("isParent", False)
            print(f"    id={sub_id}  name={sub_name}")
            if any(k in sub_name for k in ["可支配", "居民", "人均", "增长", "收入"]):
                print(f"    ★★★ 目标节点！id={sub_id}  name={sub_name}")
    time.sleep(0.2)
