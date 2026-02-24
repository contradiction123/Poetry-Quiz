"""
配置管理模块
负责读取、保存和验证配置文件
"""
import json
import os
from typing import Any, Optional


class Config:
    """配置管理类（单例模式）"""
    _instance = None
    _config_data = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if Config._config_data is None:  # 使用类变量
            # 方案A：优先读取本地私有配置 config.local.json（不提交到 GitHub）
            # 也可通过环境变量 ITEM_CONFIG_PATH 指定任意路径
            env_path = os.environ.get("ITEM_CONFIG_PATH", "").strip()
            if env_path:
                self.config_path = env_path
            elif os.path.exists("config.local.json"):
                self.config_path = "config.local.json"
            else:
                self.config_path = "config.json"
            self.load_config()
    
    def load_config(self):
        """从文件加载配置"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    Config._config_data = json.load(f)  # 使用类变量
            else:
                # 如果配置文件不存在，使用默认配置
                Config._config_data = self._get_default_config()  # 使用类变量
                self.save_config()
        except json.JSONDecodeError as e:
            print(f"配置文件格式错误: {e}")
            Config._config_data = self._get_default_config()  # 使用类变量
        except Exception as e:
            print(f"加载配置文件失败: {e}")
            Config._config_data = self._get_default_config()  # 使用类变量
    
    def save_config(self):
        """保存配置到文件"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(Config._config_data, f, ensure_ascii=False, indent=2)  # 使用类变量
        except Exception as e:
            print(f"保存配置文件失败: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置项
        支持点号分隔的嵌套键，如 'ai_providers.deepseek.api_key'
        """
        if Config._config_data is None:  # 使用类变量
            return default
        
        keys = key.split('.')
        value = Config._config_data  # 使用类变量
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key: str, value: Any):
        """
        设置配置项
        支持点号分隔的嵌套键，如 'ai_providers.deepseek.api_key'
        """
        if Config._config_data is None:  # 使用类变量
            Config._config_data = {}  # 使用类变量
        
        keys = key.split('.')
        config = Config._config_data  # 使用类变量
        
        # 创建嵌套字典结构
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        # 设置值
        config[keys[-1]] = value
        self.save_config()
    
    def validate(self) -> tuple[bool, Optional[str]]:
        """
        验证配置有效性
        返回: (是否有效, 错误信息)
        """
        if Config._config_data is None:  # 使用类变量
            return False, "配置数据为空"
        
        # 检查AI提供商配置
        ai_provider = self.get('ai_provider')
        if not ai_provider:
            return False, "未指定AI提供商"
        
        ai_providers = self.get('ai_providers', {})
        if ai_provider not in ai_providers:
            return False, f"AI提供商 '{ai_provider}' 的配置不存在"
        
        provider_config = ai_providers[ai_provider]
        api_key = provider_config.get('api_key', '')
        if not api_key:
            return False, f"AI提供商 '{ai_provider}' 的API Key未配置"
        
        return True, None
    
    def _get_default_config(self) -> dict:
        """获取默认配置"""
        return {
            "version": "1.0.0",
            "ai_provider": "deepseek",
            "ai_providers": {
                "deepseek": {
                    "api_key": "",
                    "base_url": "https://api.deepseek.com/v1/chat/completions",
                    "model": "deepseek-chat",
                    "temperature": 0.7,
                    "max_tokens": 10
                }
            },
            "ocr": {
                "language": "ch",
                "use_angle_cls": True,
                "use_gpu": False,
                "device": "cpu",
                # OCR 版本：PP-OCRv3/v4/v5（一般 v3 更快，v5 更准但更慢）
                # None 表示使用库默认选择
                "ocr_version": None,
                # 方案C：固定ROI裁剪 + 仅识别(rec-only)，用于极致提速（布局稳定时推荐）
                "fast_rec": {
                    "enabled": False,
                    # 设备：优先 gpu:0（如果环境未安装GPU版paddle会自动回退cpu）
                    "device": "gpu:0",
                    # rec-only 模型：mobile 更快；如需更高准确率可换 server_rec
                    "model_name": "PP-OCRv4_mobile_rec",
                    "batch_size": 6,
                    # 任一关键ROI置信度低于阈值则回退到全流程OCR
                    "min_score": 0.5,
                    # ROI 相对坐标（0~1），可按你的 capture_region 微调
                    "rois": {
                        "title": {"x": 0.06, "y": 0.02, "w": 0.88, "h": 0.12},
                        "question": {"x": 0.06, "y": 0.14, "w": 0.88, "h": 0.22},
                        "A": {"x": 0.04, "y": 0.46, "w": 0.44, "h": 0.20},
                        "B": {"x": 0.52, "y": 0.46, "w": 0.44, "h": 0.20},
                        "C": {"x": 0.04, "y": 0.70, "w": 0.44, "h": 0.20},
                        "D": {"x": 0.52, "y": 0.70, "w": 0.44, "h": 0.20}
                    }
                },
                # 性能参数：CPU 下通常建议尝试开启 MKL-DNN(oneDNN)；不可用时引擎会自动回退
                "enable_mkldnn": None,
                "mkldnn_cache_capacity": 10,
                "cpu_threads": None,
                # PaddleX 高性能推理（HPI），默认跟随库内部策略
                "enable_hpi": None,
                # 文本检测输入限制（不设置则使用库默认）
                "text_det_limit_side_len": None,
                "text_det_limit_type": None,
                # 输入缩放：两者任选其一（优先 input_scale）。缩小输入通常可明显提速
                # 建议：input_max_side=640~800 或 input_scale=0.7~0.9
                "input_max_side": None,
                "input_scale": None,
                # 输出 OCR 内部耗时拆分日志（转数组/推理/后处理）
                "debug_timing": False
            },
            "screen": {
                "capture_interval": 2.0,
                "full_screen": True,
                "save_screenshots": False,
                "screenshot_path": "./screenshots"
            },
            "click": {
                "delay_before_click": 0.5,
                "delay_after_click": 1.0,
                "click_duration": 0.1,
                "offset_y": 20
            },
            "automation": {
                "auto_retry": True,
                "max_retry": 3,
                "retry_delay": 1.0,
                "question_detection_keywords": ["题目一", "题目二", "题目三", "题目四", "题目五", "题目六", "题目七", "题目八", "题目九", "题目十"],
                "option_keywords": ["A", "B", "C", "D"]
            },
            "ui": {
                "window_width": 800,
                "window_height": 600,
                "log_max_lines": 100
            }
        }


# 测试代码
if __name__ == "__main__":
    config = Config()
    
    # 测试读取配置
    print("AI提供商:", config.get('ai_provider'))
    print("OCR语言:", config.get('ocr.language'))
    print("截图间隔:", config.get('screen.capture_interval'))
    
    # 测试验证配置
    is_valid, error = config.validate()
    if is_valid:
        print("配置验证通过")
    else:
        print(f"配置验证失败: {error}")
