"""
分析子包。

各模块职责：
  signal         综合信号汇总：将五个维度的数据聚合为结构化报告字典
  scorer         评分系统：各维度数据 → -2~+2 得分
  zhixing        知行趋势线指标计算
  position_monitor 持仓监控：通过妙想API获取持仓并分析
  stock_selector 选股器：ETF初筛 + 趋势线二次筛选
"""

from . import signal
from . import scorer
from . import zhixing
from . import position_monitor
from . import stock_selector
