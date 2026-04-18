"""
预定义数据采集步骤

封装常见的数据获取逻辑。
"""

from typing import Any, Callable, Dict, Optional
import sys
import traceback

from ..step import Step, StepConfig, StepStatus
from ..context import ExecutionContext


class FetchDataStep(Step):
    """
    通用数据采集步骤

    从指定数据源获取数据并存储到上下文。
    """

    name = "fetch_data"

    def __init__(
        self,
        data_key: str,
        fetch_func: Callable[[], Any],
        config: Optional[StepConfig] = None,
    ):
        """
        Args:
            data_key: 存储到上下文的数据键名
            fetch_func: 数据获取函数
        """
        super().__init__(config)
        self.data_key = data_key
        self.fetch_func = fetch_func

    def validate(self) -> bool:
        return self.fetch_func is not None

    def execute(self, context: ExecutionContext) -> Any:
        """执行数据获取"""
        data = self.fetch_func()
        context.set(self.data_key, data)
        return data


class FetchWindDataStep(Step):
    """
    Wind 数据采集步骤

    从 Wind 终端获取数据。
    """

    name = "fetch_wind_data"

    def __init__(
        self,
        wind_codes: list,
        fields: Optional[list] = None,
        options: Optional[Dict[str, Any]] = None,
        data_key: str = "wind_data",
        config: Optional[StepConfig] = None,
    ):
        """
        Args:
            wind_codes: Wind 代码列表
            fields: 要获取的字段列表
            options: Wind 选项参数
            data_key: 存储到上下文的数据键名
        """
        super().__init__(config)
        self.wind_codes = wind_codes
        self.fields = fields or []
        self.options = options or {}
        self.data_key = data_key

    def validate(self) -> bool:
        return len(self.wind_codes) > 0

    def execute(self, context: ExecutionContext) -> Any:
        """执行 Wind 数据获取"""
        try:
            # 尝试导入 WindPy
            from WindPy import w

            if not w.isconnected():
                context.warning("Wind is not connected, attempting to connect...")
                w.start()

            # 构建参数
            wind_codes_str = ",".join(self.wind_codes)
            fields_str = ",".join(self.fields) if self.fields else ""

            # 获取数据
            if fields_str:
                result = w.edb(wind_codes_str, fields=fields_str, **self.options)
            else:
                result = w.edb(wind_codes_str, **self.options)

            # 转换数据
            data = self._process_wind_result(result)
            context.set(self.data_key, data)

            return data

        except ImportError:
            raise RuntimeError("WindPy is not installed")
        except Exception as e:
            context.error(f"Failed to fetch Wind data: {str(e)}")
            raise

    def _process_wind_result(self, result) -> Dict[str, Any]:
        """处理 Wind 返回结果"""
        return {
            "codes": self.wind_codes,
            "fields": self.fields,
            "data": result.Data if hasattr(result, "Data") else None,
            "times": result.Times if hasattr(result, "Times") else None,
            "error_code": result.ErrorCode if hasattr(result, "ErrorCode") else 0,
        }


class FetchXalphaDataStep(Step):
    """
    xalpha 数据采集步骤

    从 xalpha 获取指数数据。
    """

    name = "fetch_xalpha_data"

    def __init__(
        self,
        index_code: str,
        data_key: str = "xalpha_data",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        config: Optional[StepConfig] = None,
    ):
        """
        Args:
            index_code: 指数代码（如 "HKHSTECH", "ZZ930601"）
            data_key: 存储到上下文的数据键名
            start_date: 开始日期（YYYY-MM-DD）
            end_date: 结束日期（YYYY-MM-DD）
        """
        super().__init__(config)
        self.index_code = index_code
        self.data_key = data_key
        self.start_date = start_date
        self.end_date = end_date

    def validate(self) -> bool:
        return bool(self.index_code)

    def execute(self, context: ExecutionContext) -> Any:
        """执行 xalpha 数据获取"""
        try:
            import xalpha

            # 创建指数信息对象
            info = xalpha.indexinfo(code=self.index_code)

            # 获取价格数据
            data = {
                "code": info.code,
                "name": info.name,
                "price": info.price,
                "start": info.start,
                "end": info.end,
            }

            context.set(self.data_key, data)
            context.set(f"{self.data_key}_info", info)

            return data

        except ImportError:
            raise RuntimeError("xalpha is not installed. Run: pip install xalpha")
        except Exception as e:
            context.error(f"Failed to fetch xalpha data: {str(e)}")
            raise


class FetchCSVDataStep(Step):
    """
    CSV 文件数据采集步骤

    从本地 CSV 文件读取数据。
    """

    name = "fetch_csv_data"

    def __init__(
        self,
        file_path: str,
        data_key: str,
        parse_dates: Optional[list] = None,
        index_col: Optional[str] = None,
        config: Optional[StepConfig] = None,
    ):
        """
        Args:
            file_path: CSV 文件路径
            data_key: 存储到上下文的数据键名
            parse_dates: 需要解析为日期的列
            index_col: 索引列名
        """
        super().__init__(config)
        self.file_path = file_path
        self.data_key = data_key
        self.parse_dates = parse_dates
        self.index_col = index_col

    def validate(self) -> bool:
        return bool(self.file_path)

    def execute(self, context: ExecutionContext) -> Any:
        """执行 CSV 数据读取"""
        import pandas as pd

        try:
            df = pd.read_csv(
                self.file_path,
                parse_dates=self.parse_dates,
                index_col=self.index_col,
            )

            context.set(self.data_key, df)
            return df

        except FileNotFoundError:
            raise RuntimeError(f"CSV file not found: {self.file_path}")
        except Exception as e:
            context.error(f"Failed to read CSV: {str(e)}")
            raise


class FetchAPIDataStep(Step):
    """
    API 数据采集步骤

    从 HTTP API 获取数据。
    """

    name = "fetch_api_data"

    def __init__(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        data_key: str = "api_data",
        config: Optional[StepConfig] = None,
    ):
        """
        Args:
            url: API URL
            method: HTTP 方法
            headers: 请求头
            params: URL 参数
            json_data: JSON 请求体
            data_key: 存储到上下文的数据键名
        """
        super().__init__(config)
        self.url = url
        self.method = method
        self.headers = headers or {}
        self.params = params or {}
        self.json_data = json_data
        self.data_key = data_key

    def validate(self) -> bool:
        return bool(self.url)

    def execute(self, context: ExecutionContext) -> Any:
        """执行 API 请求"""
        try:
            import requests

            response = requests.request(
                method=self.method,
                url=self.url,
                headers=self.headers,
                params=self.params,
                json=self.json_data,
                timeout=30,
            )

            response.raise_for_status()

            # 尝试解析 JSON
            try:
                data = response.json()
            except ValueError:
                data = {"text": response.text}

            context.set(self.data_key, data)
            return data

        except ImportError:
            raise RuntimeError("requests library is not installed")
        except Exception as e:
            context.error(f"API request failed: {str(e)}")
            raise
