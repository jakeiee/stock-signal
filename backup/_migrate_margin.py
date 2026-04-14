"""迁移 margin.csv 到新字段结构"""
import csv

old_path = 'market_monitor/data/margin.csv'
new_fields = ['date','total_bal','bal_chg','bal_chg_pct','bal_mktcap_ratio',
              'rz_bal','rz_buy','mkt_turnover','turnover_ratio','source']

# 读旧数据
rows = []
with open(old_path, newline='', encoding='utf-8') as f:
    for row in csv.DictReader(f):
        rows.append(row)

# 转换
new_rows = []
for row in rows:
    new_rows.append({
        'date':             row.get('date',''),
        'total_bal':        row.get('total_bal',''),
        'bal_chg':          row.get('bal_chg',''),
        'bal_chg_pct':      row.get('bal_chg_pct',''),
        'bal_mktcap_ratio': row.get('bal_mktcap_ratio',''),
        'rz_bal':           '',                        # 旧无此字段
        'rz_buy':           row.get('turnover',''),    # 原turnover含融资买入额
        'mkt_turnover':     '',                        # 旧无此字段
        'turnover_ratio':   row.get('turnover_ratio',''),
        'source':           row.get('source',''),
    })

# 写新数据
with open(old_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=new_fields)
    writer.writeheader()
    for r in new_rows:
        writer.writerow(r)

print('迁移完成')
print(open(old_path).read())
