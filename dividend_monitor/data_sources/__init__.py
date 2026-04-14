"""
数据源模块
"""

from . import bond
from . import wind_app

# 中证官网数据
try:
    from . import csindex
except ImportError:
    csindex = None