"""
股市交易分析监控（market_monitor）

监控维度：
  - 资金面：成交量/成交额、北向资金、融资融券余额等
  - 基本面：全市场 PE/PB、股息率、风险溢价等
  - 政策面：央行降准降息、重大政策事件（占位，待补充）
  - 全球市场：美股三大指数、恐慌指数 VIX、美元指数、原油等

用法：
    python3 -m market_monitor
    python3 -m market_monitor --feishu
"""
