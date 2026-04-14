"""验证YTM计算精度"""
import datetime

face = 100.0
coupon_rate = 2.1 / 100
coupon = face * coupon_rate
price = 102.651

maturity = datetime.date(2034, 11, 18)
today = datetime.date(2026, 3, 17)
T = (maturity - today).days / 365.0

print(f"剩余年限: {T:.2f}年  票面息: {coupon}元/年")

def bond_price_calc(ytm, coupon, face, T):
    n = int(T)
    pv = 0.0
    for i in range(1, n+1):
        pv += coupon / (1 + ytm)**i
    pv += face / (1 + ytm)**n
    return pv

lo, hi = 0.0001, 0.20
for _ in range(100):
    mid = (lo + hi) / 2
    if bond_price_calc(mid, coupon, face, T) > price:
        lo = mid
    else:
        hi = mid
print(f"YTM(近似): {mid*100:.4f}%")
# 当前市场10年国债收益率约1.9%左右（2026年）
