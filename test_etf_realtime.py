#!/usr/bin/env python3
"""
ETF实时行情API测试
测试各免费数据源获取ETF实时价格的能力
"""

import warnings
warnings.filterwarnings('ignore')

# 测试的ETF代码列表（场内交易代码）
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

def test_akshare():
    """测试AKShare"""
    print("\n" + "="*60)
    print("1. AKShare 测试")
    print("="*60)
    
    import akshare as ak
    
    results = {}
    for code, name in ETF_CODES:
        try:
            # 实时行情
            df = ak.stock_zh_a_spot_em()
            row = df[df['代码'] == code]
            if not row.empty:
                price = row['最新价'].values[0]
                change = row['涨跌幅'].values[0]
                results[code] = {"price": price, "change": change, "name": name}
                print(f"  ✅ {code} {name}: {price} ({change:+.2f}%)")
            else:
                print(f"  ❌ {code} {name}: 未找到")
        except Exception as e:
            print(f"  ❌ {code} {name}: {type(e).__name__}: {str(e)[:50]}")
    
    return results


def test_tushare():
    """测试Tushare"""
    print("\n" + "="*60)
    print("2. Tushare 测试")
    print("="*60)
    
    try:
        import tushare as ts
        # 尝试实时行情
        df = ts.get_realtime_quotes(ETF_CODES[0][0])
        print(f"  实时行情字段: {df.columns.tolist()}")
        
        results = {}
        for code, name in ETF_CODES[:3]:  # 先测试前3个
            try:
                df = ts.get_realtime_quotes(code)
                if not df.empty:
                    price = float(df['price'].values[0])
                    change = float(df['price'].values[0])  # 简化
                    results[code] = {"price": price, "name": name}
                    print(f"  ✅ {code} {name}: {price}")
            except Exception as e:
                print(f"  ❌ {code} {name}: {type(e).__name__}")
        
        return results
    except Exception as e:
        print(f"  ❌ Tushare初始化失败: {e}")
        return {}


def test_baostock():
    """测试Baostock"""
    print("\n" + "="*60)
    print("3. Baostock 测试")
    print("="*60)
    
    try:
        import baostock as bs
        # 登录
        lg = bs.login()
        print(f"  登录结果: {lg.error_msg}")
        
        results = {}
        for code, name in ETF_CODES:
            try:
                # 转换代码格式: 513180 -> sz.513180
                bs_code = f"sz.{code}" if code.startswith('1') else f"sh.{code}"
                rs = bs.query_history_k_data_plus(
                    bs_code,
                    "date,code,open,high,low,close,volume",
                    start_date='2026-04-27',
                    end_date='2026-04-27',
                    frequency="d"
                )
                data_list = []
                while (rs.error_code == '0') & rs.next():
                    data_list.append(rs.get_row_data())
                
                if data_list:
                    row = data_list[-1]
                    close = row[6]
                    results[code] = {"price": close, "name": name}
                    print(f"  ✅ {code} {name}: {close}")
                else:
                    print(f"  ⚠️ {code} {name}: 今日无数据")
            except Exception as e:
                print(f"  ❌ {code} {name}: {type(e).__name__}: {str(e)[:40]}")
        
        # 登出
        bs.logout()
        return results
    except Exception as e:
        print(f"  ❌ Baostock错误: {e}")
        return {}


def test_yfinance():
    """测试yfinance"""
    print("\n" + "="*60)
    print("4. YFinance 测试")
    print("="*60)
    
    import yfinance as yf
    
    results = {}
    for code, name in ETF_CODES[:3]:  # 先测试前3个
        try:
            # yfinance需要加.SZ或.SH后缀
            ticker = yf.Ticker(f"{code}.SZ")
            info = ticker.fast_info
            price = info.last_price
            results[code] = {"price": price, "name": name}
            print(f"  ✅ {code} {name}: {price}")
        except Exception as e:
            print(f"  ❌ {code} {name}: {type(e).__name__}: {str(e)[:50]}")
    
    return results


def test_eastmoney():
    """测试东方财富API"""
    print("\n" + "="*60)
    print("5. 东方财富 API (直接调用)")
    print("="*60)
    
    import requests
    
    results = {}
    for code, name in ETF_CODES:
        try:
            # 东方财富实时行情接口
            url = f"http://push2.eastmoney.com/api/qt/stock/get?secid=0.{code}&fields=f43,f57,f58,f107,f169,f170,f171"
            resp = requests.get(url, timeout=5)
            data = resp.json()
            
            if data.get('data'):
                price = data['data'].get('f43', 0) / 100  # 最新价
                change_pct = data['data'].get('f170', 0) / 100  # 涨跌幅
                results[code] = {"price": price, "change": change_pct, "name": name}
                print(f"  ✅ {code} {name}: {price} ({change_pct:+.2f}%)")
            else:
                print(f"  ❌ {code} {name}: 无数据")
        except Exception as e:
            print(f"  ❌ {code} {name}: {type(e).__name__}: {str(e)[:40]}")
    
    return results


def main():
    print("=" * 60)
    print("ETF实时行情API测试")
    print("=" * 60)
    
    all_results = {}
    
    # 1. AKShare
    results = test_akshare()
    if results:
        all_results['akshare'] = results
    
    # 2. 东方财富API
    results = test_eastmoney()
    if results:
        all_results['eastmoney'] = results
    
    # 3. Baostock
    results = test_baostock()
    if results:
        all_results['baostock'] = results
    
    # 4. Tushare
    results = test_tushare()
    if results:
        all_results['tushare'] = results
    
    # 5. YFinance
    results = test_yfinance()
    if results:
        all_results['yfinance'] = results
    
    # 汇总
    print("\n" + "=" * 60)
    print("测试汇总")
    print("=" * 60)
    for source, results in all_results.items():
        print(f"\n{source}:")
        for code, data in results.items():
            print(f"  {code}: {data.get('price')} ({data.get('change', 0):+.2f}%)" if 'change' in data else f"  {code}: {data.get('price')}")


if __name__ == "__main__":
    main()
