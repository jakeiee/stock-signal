"""验证沪深合并两融数据"""
import akshare as ak
import pandas as pd

sh = ak.macro_china_market_margin_sh()
sz = ak.macro_china_market_margin_sz()
sh['日期'] = sh['日期'].astype(str)
sz['日期'] = sz['日期'].astype(str)

sh2 = sh.rename(columns={'融资融券余额':'sh_rzrqye','融资余额':'sh_rzye','融资买入额':'sh_rzmre','融券余额':'sh_rqye'})
sz2 = sz.rename(columns={'融资融券余额':'sz_rzrqye','融资余额':'sz_rzye','融资买入额':'sz_rzmre','融券余额':'sz_rqye'})

merged = pd.merge(
    sh2[['日期','sh_rzrqye','sh_rzye','sh_rqye','sh_rzmre']],
    sz2[['日期','sz_rzrqye','sz_rzye','sz_rqye','sz_rzmre']],
    on='日期', how='inner'
)
merged['total_bal'] = merged['sh_rzrqye'] + merged['sz_rzrqye']
merged['total_bal_亿'] = (merged['total_bal'] / 1e8).round(2)
merged['rzmre_亿'] = ((merged['sh_rzmre'] + merged['sz_rzmre']) / 1e8).round(2)

print(merged[['日期','total_bal_亿','rzmre_亿']].tail(5).to_string())
print()
row = merged[merged['日期'] == '2026-03-13']
if not row.empty:
    print(f'2026-03-13 全市场两融余额: {row["total_bal_亿"].values[0]} 亿 (参考: 26517亿)')
