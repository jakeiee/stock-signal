"""
预定义分析步骤

封装常见的技术分析和估值分析逻辑。
"""

from typing import Any, Callable, Dict, List, Optional, Tuple
import sys

import pandas as pd

from ..step import Step, StepConfig
from ..context import ExecutionContext


class AnalysisStep(Step):
    """
    通用分析步骤

    对输入数据执行自定义分析函数。
    """

    name = "analysis"

    def __init__(
        self,
        name: str,
        input_keys: List[str],
        output_key: str,
        analyze_func: Callable[[Dict[str, Any]], Any],
        config: Optional[StepConfig] = None,
    ):
        """
        Args:
            name: 步骤名称
            input_keys: 输入数据的上下文键名列表
            output_key: 输出结果的上下文键名
            analyze_func: 分析函数，接收包含输入数据的字典
        """
        super().__init__(config)
        self.name = name
        self.input_keys = input_keys
        self.output_key = output_key
        self.analyze_func = analyze_func

    def validate(self) -> bool:
        return self.analyze_func is not None

    def execute(self, context: ExecutionContext) -> Any:
        """执行分析"""
        # 收集输入数据
        input_data = {}
        for key in self.input_keys:
            input_data[key] = context.get(key)

        # 执行分析
        result = self.analyze_func(input_data)

        # 保存结果
        context.set(self.output_key, result)
        return result


class KDJAnalysisStep(Step):
    """
    KDJ 技术指标分析步骤

    计算 KDJ 指标并生成交易信号。
    """

    name = "kdj_analysis"

    def __init__(
        self,
        data_key: str = "price_data",
        output_key: str = "kdj_signal",
        n: int = 9,
        m1: int = 3,
        m2: int = 3,
        config: Optional[StepConfig] = None,
    ):
        """
        Args:
            data_key: 价格数据的上下文键名
            output_key: 输出结果的上下文键名
            n: RSV 周期
            m1: K 周期
            m2: D 周期
        """
        super().__init__(config)
        self.data_key = data_key
        self.output_key = output_key
        self.n = n
        self.m1 = m1
        self.m2 = m2

    def validate(self) -> bool:
        return True

    def execute(self, context: ExecutionContext) -> Dict[str, Any]:
        """执行 KDJ 分析"""
        import pandas as pd
        import numpy as np

        # 获取价格数据
        price_data = context.get(self.data_key)

        if price_data is None:
            raise ValueError(f"No price data found at key: {self.data_key}")

        # 转换为 DataFrame
        if isinstance(price_data, dict) and "price" in price_data:
            df = price_data["price"]
        elif isinstance(price_data, pd.DataFrame):
            df = price_data
        else:
            raise ValueError(f"Invalid price data format")

        # 确保有必要的列
        required_cols = ["high", "low", "close"]
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")

        # 计算 RSV
        low_n = df["low"].rolling(window=self.n, min_periods=1).min()
        high_n = df["high"].rolling(window=self.n, min_periods=1).max()
        rsv = (df["close"] - low_n) / (high_n - low_n) * 100
        rsv = rsv.fillna(50)

        # 计算 KDJ
        k = pd.Series(index=df.index, dtype=float)
        d = pd.Series(index=df.index, dtype=float)
        j = pd.Series(index=df.index, dtype=float)

        k.iloc[0] = 50
        d.iloc[0] = 50

        for i in range(1, len(df)):
            k.iloc[i] = (2/3) * k.iloc[i-1] + (1/3) * rsv.iloc[i]
            d.iloc[i] = (2/3) * d.iloc[i-1] + (1/3) * k.iloc[i]
            j.iloc[i] = 3 * k.iloc[i] - 2 * d.iloc[i]

        # 生成信号
        signal = self._generate_signal(k, d, j)

        result = {
            "k": k.iloc[-1] if len(k) > 0 else None,
            "d": d.iloc[-1] if len(d) > 0 else None,
            "j": j.iloc[-1] if len(j) > 0 else None,
            "signal": signal,
            "history": {
                "k": k.tail(20).tolist(),
                "d": d.tail(20).tolist(),
                "j": j.tail(20).tolist(),
            },
        }

        context.set(self.output_key, result)
        return result

    def _generate_signal(self, k: pd.Series, d: pd.Series, j: pd.Series) -> str:
        """生成交易信号"""
        if len(k) < 2:
            return "hold"

        k_now = k.iloc[-1]
        k_prev = k.iloc[-2]
        d_now = d.iloc[-1]

        # 金叉：K 从下穿过 D
        if k_prev < d_now and k_now > d_now:
            return "buy"
        # 死叉：K 从上穿过 D
        elif k_prev > d_now and k_now < d_now:
            return "sell"
        # J 值超买超卖
        elif j.iloc[-1] > 100:
            return "sell"
        elif j.iloc[-1] < 0:
            return "buy"
        else:
            return "hold"


class MACDAnalysisStep(Step):
    """
    MACD 技术指标分析步骤

    计算 MACD 指标并生成交易信号。
    """

    name = "macd_analysis"

    def __init__(
        self,
        data_key: str = "price_data",
        output_key: str = "macd_signal",
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
        config: Optional[StepConfig] = None,
    ):
        """
        Args:
            data_key: 价格数据的上下文键名
            output_key: 输出结果的上下文键名
            fast: 快线周期
            slow: 慢线周期
            signal: 信号线周期
        """
        super().__init__(config)
        self.data_key = data_key
        self.output_key = output_key
        self.fast = fast
        self.slow = slow
        self.signal_period = signal

    def validate(self) -> bool:
        return True

    def execute(self, context: ExecutionContext) -> Dict[str, Any]:
        """执行 MACD 分析"""
        import pandas as pd

        # 获取价格数据
        price_data = context.get(self.data_key)

        if price_data is None:
            raise ValueError(f"No price data found at key: {self.data_key}")

        # 转换为 DataFrame
        if isinstance(price_data, dict) and "price" in price_data:
            df = price_data["price"]
        elif isinstance(price_data, pd.DataFrame):
            df = price_data
        else:
            raise ValueError(f"Invalid price data format")

        if "close" not in df.columns:
            raise ValueError("Missing required column: close")

        # 计算 EMA
        ema_fast = df["close"].ewm(span=self.fast, adjust=False).mean()
        ema_slow = df["close"].ewm(span=self.slow, adjust=False).mean()

        # 计算 DIF 和 DEA
        dif = ema_fast - ema_slow
        dea = dif.ewm(span=self.signal_period, adjust=False).mean()
        macd = (dif - dea) * 2  # 柱状图

        # 生成信号
        signal = self._generate_signal(dif, dea, macd)

        result = {
            "dif": dif.iloc[-1] if len(dif) > 0 else None,
            "dea": dea.iloc[-1] if len(dea) > 0 else None,
            "macd": macd.iloc[-1] if len(macd) > 0 else None,
            "signal": signal,
            "history": {
                "dif": dif.tail(20).tolist(),
                "dea": dea.tail(20).tolist(),
                "macd": macd.tail(20).tolist(),
            },
        }

        context.set(self.output_key, result)
        return result

    def _generate_signal(self, dif: pd.Series, dea: pd.Series, macd: pd.Series) -> str:
        """生成交易信号"""
        if len(dif) < 2:
            return "hold"

        dif_now = dif.iloc[-1]
        dif_prev = dif.iloc[-2]
        dea_now = dea.iloc[-1]

        # 金叉：DIF 从下穿过 DEA
        if dif_prev < dea_now and dif_now > dea_now:
            return "buy"
        # 死叉：DIF 从上穿过 DEA
        elif dif_prev > dea_now and dif_now < dea_now:
            return "sell"
        # MACD 柱状图由绿变红（由负转正）
        elif macd.iloc[-1] > 0 and macd.iloc[-2] <= 0:
            return "buy"
        # MACD 柱状图由红变绿（由正转负）
        elif macd.iloc[-1] < 0 and macd.iloc[-2] >= 0:
            return "sell"
        else:
            return "hold"


class ValuationAnalysisStep(Step):
    """
    估值分析步骤

    计算和分析估值指标。
    """

    name = "valuation_analysis"

    def __init__(
        self,
        data_key: str = "valuation_data",
        output_key: str = "valuation_signal",
        pe_threshold_low: float = 10.0,
        pe_threshold_high: float = 20.0,
        config: Optional[StepConfig] = None,
    ):
        """
        Args:
            data_key: 估值数据的上下文键名
            output_key: 输出结果的上下文键名
            pe_threshold_low: PE 低估阈值
            pe_threshold_high: PE 高估阈值
        """
        super().__init__(config)
        self.data_key = data_key
        self.output_key = output_key
        self.pe_threshold_low = pe_threshold_low
        self.pe_threshold_high = pe_threshold_high

    def validate(self) -> bool:
        return True

    def execute(self, context: ExecutionContext) -> Dict[str, Any]:
        """执行估值分析"""
        # 获取估值数据
        valuation_data = context.get(self.data_key)

        if valuation_data is None:
            raise ValueError(f"No valuation data found at key: {self.data_key}")

        # 提取 PE 值
        pe = None
        if isinstance(valuation_data, dict):
            pe = valuation_data.get("pe")
        elif isinstance(valuation_data, (int, float)):
            pe = valuation_data

        # 生成信号
        signal = self._generate_signal(pe)

        result = {
            "pe": pe,
            "signal": signal,
            "thresholds": {
                "low": self.pe_threshold_low,
                "high": self.pe_threshold_high,
            },
        }

        context.set(self.output_key, result)
        return result

    def _generate_signal(self, pe: float) -> str:
        """生成估值信号"""
        if pe is None:
            return "unknown"

        if pe < self.pe_threshold_low:
            return "undervalued"
        elif pe > self.pe_threshold_high:
            return "overvalued"
        else:
            return "fair"
