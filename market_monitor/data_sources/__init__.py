"""
数据源子包。

各模块职责：
  capital   资金面：全市场成交额、北向资金净流入、融资融券余额
  valuation 基本面：全市场 PE/PB/股息率 及其历史百分位
  policy    政策面：央行政策事件（占位，待接入数据源）
  global_mkt 全球市场：美股三大指数、VIX、美元指数、原油价格

每个模块对外暴露唯一函数 fetch() -> dict，
返回 {"data": ..., "error": str|None, "updated_at": str}。
"""
