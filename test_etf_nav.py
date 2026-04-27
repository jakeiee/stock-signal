#!/usr/bin/env python3
"""
ETF净值测试脚本
测试xalpha获取各ETF净值数据
"""

import json
import warnings
import xalpha as xa

warnings.filterwarnings('ignore')

# 测试的ETF代码列表
ETF_CODES = [
    ("513180", "恒生科技ETF华夏"),
    ("159202", "恒生互联网ETF"),
    ("159217", "港股通创新药ETF"),
    ("159852", "软件ETF嘉实"),
    ("159869", "游戏ETF华夏"),
    ("562500", "机器人ETF华夏"),
    ("506008", "科创板长城"),
    ("513090", "香港证券ETF"),
]

def test_etf_nav(code: str, name: str):
    """测试获取单个ETF净值"""
    print(f"\n{'='*60}")
    print(f"ETF: {code} - {name}")
    print('='*60)

    try:
        # 1. FundInfo 获取基金净值
        info = xa.FundInfo(code)
        print(f"\n1. FundInfo (基金净值):")
        print(f"   名称: {info.name}")
        print(f"   最新净值: {info.price.iloc[-1]['netvalue']}")
        print(f"   日期: {info.price.iloc[-1]['date']}")
        print(f"   最新5条:")
        for _, row in info.price.tail().iterrows():
            print(f"      {row['date'][:10]}: {row['netvalue']}")

        # 2. 对比持仓数据
        with open('data/positions.json', 'r') as f:
            positions = json.load(f)
        
        for p in positions:
            if p['code'] == code:
                print(f"\n2. 持仓数据:")
                print(f"   current_price: {p['current_price']}")
                print(f"   cost_price: {p['cost_price']}")
                print(f"   shares: {p['shares']}")
                print(f"   market_value: {p['market_value']}")
                
                # 计算盈亏
                cost = p['cost_price']
                current = p['current_price']
                if cost > 0:
                    profit = (current - cost) / cost * 100
                    print(f"   持仓盈亏: {profit:+.2f}%")
                
                # 用净值计算盈亏
                nav = info.price.iloc[-1]['netvalue']
                if cost > 0:
                    nav_profit = (nav - cost) / cost * 100
                    print(f"   净值盈亏: {nav_profit:+.2f}%")
                break
        else:
            print(f"\n2. 持仓数据: 未找到")

        return True

    except Exception as e:
        print(f"\n错误: {type(e).__name__}: {e}")
        return False


def main():
    print("=" * 60)
    print("ETF净值测试")
    print("=" * 60)
    
    results = []
    for code, name in ETF_CODES:
        success = test_etf_nav(code, name)
        results.append((code, name, success))
    
    # 汇总
    print("\n" + "=" * 60)
    print("测试汇总")
    print("=" * 60)
    for code, name, success in results:
        status = "✅" if success else "❌"
        print(f"{status} {code} - {name}")


if __name__ == "__main__":
    main()
