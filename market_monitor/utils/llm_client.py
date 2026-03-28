"""
统一的 LLM 客户端封装，支持多种模型提供商。

支持的提供商：
- 阿里云百炼 (qwen)
- DeepSeek
- 硅基流动 (siliconflow)
- OpenAI 兼容接口

使用方法：
    from market_monitor.utils.llm_client import LLMClient
    
    client = LLMClient(provider="qwen")
    response = client.chat("提取以下文本的关键要点...")
"""

import os
import json
from typing import Optional, Dict, Any, List
from dataclasses import dataclass


@dataclass
class LLMResponse:
    """LLM 响应封装"""
    content: str
    usage: Optional[Dict[str, int]] = None
    model: str = ""
    raw_response: Any = None


class LLMClient:
    """
    统一的 LLM 客户端，支持多种提供商。
    
    配置方式（优先级从高到低）：
    1. 构造函数参数
    2. 环境变量
    3. 默认值
    """
    
    # 支持的提供商配置
    PROVIDERS = {
        "qwen": {
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "default_model": "qwen-turbo",
            "env_key": "DASHSCOPE_API_KEY",
        },
        "deepseek": {
            "base_url": "https://api.deepseek.com",
            "default_model": "deepseek-chat",
            "env_key": "DEEPSEEK_API_KEY",
        },
        "siliconflow": {
            "base_url": "https://api.siliconflow.cn/v1",
            "default_model": "Qwen/Qwen2.5-7B-Instruct",
            "env_key": "SILICONFLOW_API_KEY",
        },
        "openai": {
            "base_url": "https://api.openai.com/v1",
            "default_model": "gpt-3.5-turbo",
            "env_key": "OPENAI_API_KEY",
        },
    }
    
    def __init__(
        self,
        provider: str = "qwen",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ):
        """
        初始化 LLM 客户端。
        
        Args:
            provider: 提供商名称 (qwen/deepseek/siliconflow/openai)
            api_key: API 密钥，默认从环境变量读取
            base_url: 自定义 base_url
            model: 模型名称，默认使用提供商推荐模型
            temperature: 温度参数 (0-2)
            max_tokens: 最大生成 token 数
        """
        self.provider = provider.lower()
        if self.provider not in self.PROVIDERS:
            raise ValueError(f"不支持的提供商: {provider}，支持的: {list(self.PROVIDERS.keys())}")
        
        config = self.PROVIDERS[self.provider]
        
        # API Key
        self.api_key = api_key or os.getenv(config["env_key"])
        if not self.api_key:
            raise ValueError(
                f"未找到 {provider} 的 API 密钥。"
                f"请设置环境变量 {config['env_key']} 或在构造函数中传入 api_key"
            )
        
        # Base URL
        self.base_url = base_url or config["base_url"]
        
        # Model
        self.model = model or config["default_model"]
        
        # 生成参数
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        # 延迟导入 openai
        try:
            import openai
            self._client = openai.OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )
        except ImportError:
            raise ImportError("请安装 openai 包: pip install openai")
    
    def chat(
        self,
        message: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """
        单轮对话。
        
        Args:
            message: 用户消息
            system_prompt: 系统提示词
            temperature: 覆盖默认温度
            max_tokens: 覆盖默认最大 token
        
        Returns:
            LLMResponse 对象
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": message})
        
        return self.chat_messages(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    
    def chat_messages(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """
        多轮对话。
        
        Args:
            messages: 消息列表，格式 [{"role": "user", "content": "..."}, ...]
            temperature: 覆盖默认温度
            max_tokens: 覆盖默认最大 token
        
        Returns:
            LLMResponse 对象
        """
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature or self.temperature,
                max_tokens=max_tokens or self.max_tokens,
            )
            
            return LLMResponse(
                content=response.choices[0].message.content,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                } if response.usage else None,
                model=response.model,
                raw_response=response,
            )
        except Exception as e:
            raise RuntimeError(f"{self.provider} API 调用失败: {e}")
    
    def extract_json(
        self,
        message: str,
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        提取 JSON 格式的响应。
        
        Args:
            message: 用户消息
            system_prompt: 系统提示词（可选）
        
        Returns:
            解析后的 JSON 字典
        """
        default_system = """你是一个专业的数据提取助手。请从用户提供的文本中提取结构化信息，并以 JSON 格式返回。
注意：
1. 只返回 JSON，不要包含其他解释文字
2. 确保 JSON 格式正确，可以被 Python json.loads() 解析
3. 如果某些字段无法提取，使用 null 或空字符串"""
        
        response = self.chat(
            message=message,
            system_prompt=system_prompt or default_system,
        )
        
        # 清理响应内容，提取 JSON
        content = response.content.strip()
        
        # 尝试去除 markdown 代码块标记
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        
        content = content.strip()
        
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"无法解析 JSON 响应: {e}\n原始响应: {response.content[:500]}")


# 便捷函数：快速创建客户端
def get_llm_client(provider: str = "qwen", **kwargs) -> LLMClient:
    """
    快速获取 LLM 客户端实例。
    
    Args:
        provider: 提供商名称
        **kwargs: 其他参数传递给 LLMClient
    
    Returns:
        LLMClient 实例
    """
    return LLMClient(provider=provider, **kwargs)


# 便捷函数：单条消息快速调用
def quick_chat(
    message: str,
    provider: str = "qwen",
    system_prompt: Optional[str] = None,
    **kwargs
) -> str:
    """
    快速发送单条消息并获取回复。
    
    Args:
        message: 用户消息
        provider: 提供商名称
        system_prompt: 系统提示词
        **kwargs: 其他参数
    
    Returns:
        LLM 回复文本
    """
    client = get_llm_client(provider, **kwargs)
    response = client.chat(message, system_prompt=system_prompt)
    return response.content


if __name__ == "__main__":
    # 测试代码
    print("测试 LLM 客户端...")
    
    # 测试环境变量检查
    for provider, config in LLMClient.PROVIDERS.items():
        env_key = config["env_key"]
        value = os.getenv(env_key)
        status = "✓ 已设置" if value else "✗ 未设置"
        print(f"  {provider}: {env_key} {status}")
    
    print("\n使用示例:")
    print("  from market_monitor.utils.llm_client import LLMClient")
    print("  client = LLMClient(provider='qwen')")
    print("  response = client.chat('你好')")
    print("  print(response.content)")
