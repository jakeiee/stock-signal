"""
分析子包。

各模块职责：
  signal    综合信号汇总：将四个维度的数据聚合为结构化报告字典
  scorer    评分系统：各维度数据 → -2~+2 得分

TODO：
  - scorer.py   各维度评分逻辑（参考 dividend_monitor.analysis.position）
  - signal.py   聚合所有维度数据、生成统一 report dict
"""
