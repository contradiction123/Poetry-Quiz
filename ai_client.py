"""
AI客户端模块
提供可扩展的AI接口架构
"""
from abc import ABC, abstractmethod
from typing import Dict, Any


class AIClient(ABC):
    """AI客户端抽象基类"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化AI客户端
        参数:
            config: AI提供商配置字典
        """
        self.config = config
    
    @abstractmethod
    def get_answer(self, question: str, options: Dict[str, str]) -> str:
        """
        获取答案
        参数:
            question: 题目文字
            options: 选项字典 {'A': '选项A', 'B': '选项B', ...}
        返回:
            str: 答案选项 ('A', 'B', 'C', 或 'D')
        """
        raise NotImplementedError


class AIClientFactory:
    """AI客户端工厂类"""
    
    @staticmethod
    def create_client(provider_name: str, config: Dict[str, Any]) -> AIClient:
        """
        创建AI客户端实例
        参数:
            provider_name: 提供商名称，如 'deepseek'
            config: 提供商配置字典
        返回:
            AIClient实例
        """
        if provider_name == 'deepseek':
            from ai_providers.deepseek import DeepSeekClient
            return DeepSeekClient(config)
        else:
            raise ValueError(f"不支持的AI提供商: {provider_name}")
