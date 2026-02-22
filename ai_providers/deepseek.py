"""
DeepSeek AI客户端实现
"""
import requests
import re
from typing import Dict, Any
from ai_client import AIClient


class DeepSeekClient(AIClient):
    """DeepSeek API客户端"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化DeepSeek客户端
        参数:
            config: DeepSeek配置字典，包含 api_key, base_url, model 等
        """
        super().__init__(config)
        self.api_key = config.get('api_key', '')
        self.base_url = config.get('base_url', 'https://api.deepseek.com/v1/chat/completions')
        self.model = config.get('model', 'deepseek-chat')
        self.temperature = config.get('temperature', 0.7)
        self.max_tokens = config.get('max_tokens', 10)
        
        if not self.api_key:
            raise ValueError("DeepSeek API Key未配置")
    
    def get_answer(self, question: str, options: Dict[str, str]) -> str:
        """
        调用DeepSeek API获取答案
        参数:
            question: 题目文字
            options: 选项字典 {'A': '选项A', 'B': '选项B', ...}
        返回:
            str: 答案选项 ('A', 'B', 'C', 或 'D')
        """
        try:
            # 构建提示词
            prompt = self._build_prompt(question, options)
            
            # 调用API
            response = self._call_api(prompt)
            
            # 解析响应
            answer = self._parse_response(response)
            
            return answer
        except Exception as e:
            raise Exception(f"获取AI答案失败: {e}")
    
    def _build_prompt(self, question: str, options: Dict[str, str]) -> str:
        """
        构建AI提示词
        参数:
            question: 题目文字
            options: 选项字典
        返回:
            str: 提示词
        """
        prompt = f"""你是一个诗词专家。请根据给出的诗词上句，从以下四个选项中选择正确的下句。

题目：{question}

选项：
A. {options.get('A', '')}
B. {options.get('B', '')}
C. {options.get('C', '')}
D. {options.get('D', '')}

请只返回选项字母（A、B、C或D），不要返回其他内容。"""
        return prompt
    
    def _call_api(self, prompt: str) -> Dict[str, Any]:
        """
        调用DeepSeek API
        参数:
            prompt: 提示词
        返回:
            dict: API响应
        """
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}'
        }
        
        data = {
            'model': self.model,
            'messages': [
                {'role': 'user', 'content': prompt}
            ],
            'temperature': self.temperature,
            'max_tokens': self.max_tokens
        }
        
        try:
            response = requests.post(
                self.base_url,
                headers=headers,
                json=data,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"API请求失败: {e}")
    
    def _parse_response(self, response: Dict[str, Any]) -> str:
        """
        解析API响应，提取答案
        参数:
            response: API响应字典
        返回:
            str: 答案选项 ('A', 'B', 'C', 或 'D')
        """
        try:
            # 从响应中提取内容
            content = response['choices'][0]['message']['content'].strip()
            
            # 提取答案字母（A、B、C或D）
            # 使用正则表达式查找第一个出现的选项字母
            match = re.search(r'\b([ABCD])\b', content.upper())
            if match:
                return match.group(1)
            else:
                # 如果没找到，尝试查找任何包含选项字母的内容
                if 'A' in content.upper():
                    return 'A'
                elif 'B' in content.upper():
                    return 'B'
                elif 'C' in content.upper():
                    return 'C'
                elif 'D' in content.upper():
                    return 'D'
                else:
                    raise ValueError(f"无法从响应中提取答案: {content}")
        except (KeyError, IndexError) as e:
            raise ValueError(f"API响应格式错误: {e}")


# 测试代码
if __name__ == "__main__":
    # 注意：需要配置API Key才能测试
    test_config = {
        'api_key': 'your-api-key-here',  # 替换为实际的API Key
        'base_url': 'https://api.deepseek.com/v1/chat/completions',
        'model': 'deepseek-chat',
        'temperature': 0.7,
        'max_tokens': 10
    }
    
    try:
        client = DeepSeekClient(test_config)
        
        question = "兰陵美酒郁金香"
        options = {
            'A': '玉碗盛来琥珀光',
            'B': '夜泊秦淮近酒家',
            'C': '碧天如水夜云轻',
            'D': '依旧烟笼十里堤'
        }
        
        answer = client.get_answer(question, options)
        print(f"答案: {answer}")
    except ValueError as e:
        print(f"配置错误: {e}")
    except Exception as e:
        print(f"测试失败: {e}")
